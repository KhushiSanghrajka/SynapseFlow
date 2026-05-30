import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import SessionLocal
from app.llm.github_models import GitHubMarketplaceClient
from app.models import Agent, Execution, InterAgentMessage, LogEvent, Workflow, WorkflowThread
from app.runtime.graph_engine import GraphExecutionEngine
from app.runtime.log_bus import LogBus
from app.schemas import (
    AgentCreate,
    AgentUpdate,
    CreateWorkflowFromTemplate,
    ExecutionCreate,
    WorkflowCreate,
    WorkflowGraph,
    WorkflowUpdate,
)
from app.templates import get_workflow_templates


class OrchestratorService:
    SUPPORTED_TOOLS = ["web_search", "calculator", "summarizer"]
    SUPPORTED_CHANNELS = ["web", "telegram"]

    def __init__(self, settings: Settings, log_bus: LogBus):
        self._settings = settings
        self._log_bus = log_bus
        self._llm = GitHubMarketplaceClient(settings)
        self._engine = GraphExecutionEngine(self._llm)
        self._execution_tasks: dict[str, asyncio.Task] = {}
        self._logger = logging.getLogger("orbitflow.runtime")

    @property
    def log_bus(self) -> LogBus:
        return self._log_bus

    def list_agents(self, db: Session) -> list[Agent]:
        return list(db.scalars(select(Agent).order_by(Agent.created_at.desc())).all())

    def get_agent(self, db: Session, agent_id: str) -> Agent | None:
        return db.get(Agent, agent_id)

    def create_agent(self, db: Session, payload: AgentCreate) -> Agent:
        self._validate_agent_config(payload.tools, payload.channels)
        record = Agent(**payload.model_dump())
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update_agent(self, db: Session, agent: Agent, payload: AgentUpdate) -> Agent:
        tools = payload.tools if payload.tools is not None else agent.tools
        channels = payload.channels if payload.channels is not None else agent.channels
        self._validate_agent_config(tools, channels)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(agent, key, value)
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent

    def capabilities(self) -> dict[str, list[str]]:
        return {"tools": self.SUPPORTED_TOOLS, "channels": self.SUPPORTED_CHANNELS}

    def delete_agent(self, db: Session, agent: Agent) -> None:
        db.delete(agent)
        db.commit()

    def list_workflows(self, db: Session) -> list[Workflow]:
        return list(db.scalars(select(Workflow).order_by(Workflow.created_at.desc())).all())

    def get_workflow(self, db: Session, workflow_id: str) -> Workflow | None:
        return db.get(Workflow, workflow_id)

    def create_workflow(self, db: Session, payload: WorkflowCreate) -> Workflow:
        workflow_name = self._ensure_unique_workflow_name(db, payload.name)
        record = Workflow(
            name=workflow_name,
            description=payload.description,
            graph_json=payload.graph.model_dump(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def update_workflow(self, db: Session, workflow: Workflow, payload: WorkflowUpdate) -> Workflow:
        values = payload.model_dump(exclude_unset=True)
        if "graph" in values:
            graph = values.pop("graph")
            values["graph_json"] = graph if isinstance(graph, dict) else graph.model_dump()
        if "name" in values:
            values["name"] = self._ensure_unique_workflow_name(db, str(values["name"]))
        for key, value in values.items():
            setattr(workflow, key, value)
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        return workflow

    def delete_workflow(self, db: Session, workflow: Workflow) -> None:
        self.clear_history(db, workflow_id=workflow.id)
        db.execute(delete(WorkflowThread).where(WorkflowThread.workflow_id == workflow.id))
        db.delete(workflow)
        db.commit()

    def list_templates(self):
        return get_workflow_templates()

    def list_threads(self, db: Session, workflow_id: str | None = None) -> list[WorkflowThread]:
        stmt = select(WorkflowThread).order_by(WorkflowThread.updated_at.desc())
        if workflow_id:
            stmt = stmt.where(WorkflowThread.workflow_id == workflow_id)
        return list(db.scalars(stmt).all())

    def create_thread(self, db: Session, workflow_id: str, title: str) -> WorkflowThread:
        workflow = db.get(Workflow, workflow_id)
        if workflow is None:
            raise ValueError("Workflow not found.")
        existing_titles = set(
            db.scalars(select(WorkflowThread.title).where(WorkflowThread.workflow_id == workflow_id)).all()
        )
        requested = (title or "").strip()
        if not requested:
            requested = self._next_default_thread_title(existing_titles)
        unique_title = self._ensure_unique_thread_title(requested, existing_titles)
        thread = WorkflowThread(workflow_id=workflow_id, title=unique_title)
        db.add(thread)
        db.commit()
        db.refresh(thread)
        return thread

    def update_thread(self, db: Session, thread_id: str, title: str) -> WorkflowThread:
        thread = db.get(WorkflowThread, thread_id)
        if thread is None:
            raise ValueError("Thread not found.")
        thread.title = title.strip() or thread.title
        db.add(thread)
        db.commit()
        db.refresh(thread)
        return thread

    def delete_thread(self, db: Session, thread_id: str, *, clear_history: bool = True) -> None:
        thread = db.get(WorkflowThread, thread_id)
        if thread is None:
            raise ValueError("Thread not found.")
        if clear_history:
            self.clear_history(db, thread_id=thread_id)
        db.delete(thread)
        db.commit()

    def create_workflow_from_template(self, db: Session, payload: CreateWorkflowFromTemplate) -> Workflow:
        templates = {template.id: template for template in get_workflow_templates()}
        template = templates.get(payload.template_id)
        if template is None:
            raise ValueError(f"Unknown template id '{payload.template_id}'.")

        available_agents = self.list_agents(db)
        role_index: dict[str, str] = {agent.role: agent.id for agent in available_agents}

        nodes = []
        fallback_agent_ids = [agent.id for agent in available_agents]
        fallback_idx = 0
        for node in template.nodes:
            mapped = payload.agent_mapping.get(node.id) or role_index.get(node.role_hint)
            if mapped is None:
                if not fallback_agent_ids:
                    raise ValueError(
                        f"Template node '{node.id}' requires role '{node.role_hint}'. "
                        "Create at least one agent or provide an explicit mapping."
                    )
                mapped = fallback_agent_ids[fallback_idx % len(fallback_agent_ids)]
                fallback_idx += 1
            nodes.append(
                {
                    "id": node.id,
                    "label": node.label,
                    "agent_id": mapped,
                    "position": node.position,
                }
            )
        edges = [
            {
                "id": f"{edge.source}-{edge.target}",
                "source": edge.source,
                "target": edge.target,
                "condition": edge.condition.model_dump() if hasattr(edge.condition, "model_dump") else edge.condition,
                "label": edge.label,
            }
            for edge in template.edges
        ]
        graph = WorkflowGraph(entry_node_id=template.entry_node_id, nodes=nodes, edges=edges, max_steps=template.max_steps)
        workflow_name = self._ensure_unique_workflow_name(db, payload.workflow_name)
        record = Workflow(
            name=workflow_name,
            description=payload.workflow_description or template.description,
            graph_json=graph.model_dump(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    async def start_execution(self, db: Session, payload: ExecutionCreate) -> Execution:
        workflow = db.get(Workflow, payload.workflow_id)
        if workflow is None:
            raise ValueError("Workflow not found.")
        execution = Execution(
            workflow_id=payload.workflow_id,
            status="queued",
            trigger_source=payload.trigger_source,
            input_payload={"input_text": payload.input_text, "thread_id": payload.thread_id},
            output_payload={},
            total_tokens=0,
            estimated_cost_usd=0.0,
            started_at=datetime.now(timezone.utc),
        )
        if payload.thread_id:
            thread = db.get(WorkflowThread, payload.thread_id)
            if thread is None:
                raise ValueError("Thread not found.")
            if thread.workflow_id != payload.workflow_id:
                raise ValueError("Thread does not belong to the selected workflow.")
            thread.updated_at = datetime.now(timezone.utc)
            db.add(thread)
        db.add(execution)
        db.commit()
        db.refresh(execution)

        task = asyncio.create_task(self._run_execution(execution.id))
        self._execution_tasks[execution.id] = task
        return execution

    def list_executions(self, db: Session, limit: int = 40) -> list[Execution]:
        stmt = select(Execution).order_by(Execution.started_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    def get_execution(self, db: Session, execution_id: str) -> Execution | None:
        return db.get(Execution, execution_id)

    def get_logs(self, db: Session, execution_id: str) -> list[LogEvent]:
        stmt = select(LogEvent).where(LogEvent.execution_id == execution_id).order_by(LogEvent.created_at.asc())
        return list(db.scalars(stmt).all())

    def get_messages(self, db: Session, execution_id: str) -> list[InterAgentMessage]:
        stmt = select(InterAgentMessage).where(InterAgentMessage.execution_id == execution_id).order_by(
            InterAgentMessage.created_at.asc()
        )
        return list(db.scalars(stmt).all())

    def monitoring_summary(self, db: Session) -> dict[str, Any]:
        total_runs = db.scalar(select(func.count()).select_from(Execution)) or 0
        total_tokens = db.scalar(select(func.coalesce(func.sum(Execution.total_tokens), 0))) or 0
        total_cost = db.scalar(select(func.coalesce(func.sum(Execution.estimated_cost_usd), 0.0))) or 0.0
        return {"executions": int(total_runs), "tokens": int(total_tokens), "cost_usd": float(total_cost)}

    def clear_history(
        self,
        db: Session,
        *,
        thread_id: str | None = None,
        workflow_id: str | None = None,
    ) -> int:
        executions = self.list_executions(db, limit=5000)
        matched_ids: list[str] = []
        for execution in executions:
            payload = execution.input_payload or {}
            if thread_id and payload.get("thread_id") != thread_id:
                continue
            if workflow_id and execution.workflow_id != workflow_id:
                continue
            matched_ids.append(execution.id)

        if not matched_ids:
            return 0

        db.execute(delete(LogEvent).where(LogEvent.execution_id.in_(matched_ids)))
        db.execute(delete(InterAgentMessage).where(InterAgentMessage.execution_id.in_(matched_ids)))
        db.execute(delete(Execution).where(Execution.id.in_(matched_ids)))
        db.commit()
        return len(matched_ids)

    @staticmethod
    def _next_default_thread_title(existing_titles: set[str]) -> str:
        index = 1
        while True:
            candidate = f"Thread {index}"
            if candidate not in existing_titles:
                return candidate
            index += 1

    @staticmethod
    def _ensure_unique_thread_title(requested: str, existing_titles: set[str]) -> str:
        if requested not in existing_titles:
            return requested
        index = 2
        while True:
            candidate = f"{requested} ({index})"
            if candidate not in existing_titles:
                return candidate
            index += 1

    def _ensure_unique_workflow_name(self, db: Session, requested: str) -> str:
        base = (requested or "").strip() or "Workflow"
        existing = set(db.scalars(select(Workflow.name)).all())
        if base not in existing:
            return base
        index = 2
        while True:
            candidate = f"{base} ({index})"
            if candidate not in existing:
                return candidate
            index += 1

    def _build_thread_context(self, db: Session, *, thread_id: str, exclude_execution_id: str) -> str:
        stmt = select(Execution).order_by(desc(Execution.started_at)).limit(18)
        recent = list(db.scalars(stmt).all())
        lines: list[str] = []
        count = 0
        for execution in recent:
            if execution.id == exclude_execution_id:
                continue
            payload = execution.input_payload or {}
            if payload.get("thread_id") != thread_id:
                continue
            user_text = str(payload.get("input_text", "")).strip()
            final_answer = str((execution.output_payload or {}).get("final_output", "")).strip()
            if not user_text and not final_answer:
                continue
            lines.append(f"- User: {user_text[:180]}")
            if final_answer:
                lines.append(f"  Assistant: {final_answer[:220]}")
            count += 1
            if count >= 3:
                break
        return "\n".join(lines)

    def _validate_agent_config(self, tools: list[str], channels: list[str]) -> None:
        invalid_tools = [tool for tool in (tools or []) if tool not in self.SUPPORTED_TOOLS]
        if invalid_tools:
            raise ValueError(f"Unsupported tools: {', '.join(invalid_tools)}.")
        invalid_channels = [channel for channel in (channels or []) if channel not in self.SUPPORTED_CHANNELS]
        if invalid_channels:
            raise ValueError(f"Unsupported channels: {', '.join(invalid_channels)}.")

    async def run_telegram_agent(self, user_text: str) -> str:
        with SessionLocal() as db:
            target: Agent | None = None
            if self._settings.telegram_agent_id:
                target = db.get(Agent, self._settings.telegram_agent_id)
            if target is None:
                for candidate in db.scalars(select(Agent)).all():
                    if "telegram" in (candidate.channels or []):
                        target = candidate
                        break
            if target is None:
                target = db.scalars(select(Agent).limit(1)).first()
            if target is None:
                return "No agents available. Create an agent first in Synapse Flow."

        response = await self._llm.complete(
            system_prompt=target.system_prompt,
            user_prompt=user_text,
            model=target.model,
        )
        await self._log_bus.publish(
            {
                "event_type": "telegram_message",
                "message": "Telegram request handled.",
                "metadata": {"agent_id": target.id, "agent_name": target.name, "tokens": response.total_tokens},
            }
        )
        self._emit_terminal_event(
            {
                "event_type": "telegram_message",
                "message": "Telegram request handled.",
                "metadata": {"agent_id": target.id, "agent_name": target.name, "tokens": response.total_tokens},
            }
        )
        return response.content

    async def _run_execution(self, execution_id: str) -> None:
        try:
            with SessionLocal() as db:
                execution = db.get(Execution, execution_id)
                if execution is None:
                    return
                execution.status = "running"
                db.add(execution)
                db.commit()

            await self._publish_execution_event(execution_id, "execution_started", "Workflow execution started.")

            with SessionLocal() as db:
                execution = db.get(Execution, execution_id)
                workflow = db.get(Workflow, execution.workflow_id) if execution else None
                if execution is None or workflow is None:
                    return
                workflow_graph = WorkflowGraph.model_validate(workflow.graph_json)
                agent_ids = [node.agent_id for node in workflow_graph.nodes]
                stmt = select(Agent).where(Agent.id.in_(agent_ids))
                agents = list(db.scalars(stmt).all())
                agents_by_id = {agent.id: agent for agent in agents}
                user_input = str(execution.input_payload.get("input_text", ""))
                thread_id = (execution.input_payload or {}).get("thread_id")
                if thread_id:
                    context_text = self._build_thread_context(db, thread_id=thread_id, exclude_execution_id=execution_id)
                    if context_text:
                        user_input = (
                            f"{user_input}\n\n"
                            "Recent thread context:\n"
                            f"{context_text}\n"
                        )

            result = await self._engine.run(
                execution_id=execution_id,
                workflow=workflow_graph,
                agents_by_id=agents_by_id,
                user_input=user_input,
                on_event=self._persist_and_publish_event,
            )

            trace = list(result.get("flow_trace", []))
            with SessionLocal() as db:
                execution = db.get(Execution, execution_id)
                if execution is None:
                    return
                execution.status = "completed"
                execution.output_payload = {
                    "final_output": result.get("current_output", ""),
                    "node_outputs": result.get("outputs", {}),
                    "trace": trace,
                }
                execution.total_tokens = int(result.get("token_total", 0))
                execution.estimated_cost_usd = float(result.get("cost_total", 0.0))
                execution.ended_at = datetime.now(timezone.utc)
                db.add(execution)

                for index in range(0, max(0, len(trace) - 1)):
                    src = trace[index]
                    dst = trace[index + 1]
                    db.add(
                        InterAgentMessage(
                            execution_id=execution_id,
                            source_agent_id=src.get("agent_id"),
                            target_agent_id=dst.get("agent_id"),
                            content=src.get("output", ""),
                            token_count=0,
                            cost_usd=0.0,
                        )
                    )

                db.commit()

            await self._publish_execution_event(execution_id, "execution_completed", "Workflow execution completed.")
        except Exception as exc:  # noqa: BLE001
            with SessionLocal() as db:
                execution = db.get(Execution, execution_id)
                if execution:
                    execution.status = "failed"
                    execution.output_payload = {"error": str(exc)}
                    execution.ended_at = datetime.now(timezone.utc)
                    db.add(execution)
                    db.commit()
            await self._publish_execution_event(execution_id, "execution_failed", f"Execution failed: {exc}")
        finally:
            self._execution_tasks.pop(execution_id, None)

    async def _publish_execution_event(self, execution_id: str, event_type: str, message: str) -> None:
        await self._persist_and_publish_event(
            {"execution_id": execution_id, "event_type": event_type, "message": message, "metadata": {}}
        )

    async def _persist_and_publish_event(self, event: dict[str, Any]) -> None:
        execution_id = event.get("execution_id")
        thread_id: str | None = event.get("thread_id")
        if execution_id and not thread_id:
            with SessionLocal() as db:
                execution = db.get(Execution, execution_id)
                if execution and isinstance(execution.input_payload, dict):
                    thread_id = execution.input_payload.get("thread_id")
            if thread_id:
                event["thread_id"] = thread_id

        if execution_id:
            with SessionLocal() as db:
                safe_metadata = self._json_safe(event.get("metadata", {}))
                db.add(
                    LogEvent(
                        execution_id=execution_id,
                        level=event.get("level", "info"),
                        event_type=event.get("event_type", "runtime"),
                        message=event.get("message", ""),
                        metadata_json=safe_metadata,
                    )
                )
                db.commit()
        self._emit_terminal_event(event)
        await self._log_bus.publish(event)

    def _emit_terminal_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("event_type", "runtime"))
        message = str(event.get("message", ""))
        execution_id = str(event.get("execution_id", ""))[:8]
        metadata = event.get("metadata", {}) or {}

        color = self._event_color(event_type)
        level = self._event_level(event_type)

        meta_chunks = []
        for key in ("node_label", "source", "target", "tokens", "cost_usd", "agent_name"):
            if key in metadata:
                meta_chunks.append(f"{key}={metadata[key]}")
        meta_text = f" ({', '.join(meta_chunks)})" if meta_chunks else ""

        execution_part = f"[{execution_id}] " if execution_id else ""
        line = f"[bold {color}]{event_type}[/bold {color}] {execution_part}{message}{meta_text}"
        self._logger.log(level, line)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, dict):
            return {key: OrchestratorService._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [OrchestratorService._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [OrchestratorService._json_safe(item) for item in value]
        if isinstance(value, set):
            return [OrchestratorService._json_safe(item) for item in sorted(value, key=str)]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    @staticmethod
    def _event_level(event_type: str) -> int:
        if event_type in {"execution_failed"}:
            return logging.ERROR
        if event_type in {"guardrail_stop"}:
            return logging.WARNING
        return logging.INFO

    @staticmethod
    def _event_color(event_type: str) -> str:
        if event_type in {"execution_started", "execution_completed"}:
            return "cyan"
        if event_type in {"execution_failed"}:
            return "red"
        if event_type in {"node_completed"}:
            return "green"
        if event_type in {"edge_selected"}:
            return "yellow"
        if event_type in {"guardrail_stop"}:
            return "magenta"
        if event_type in {"telegram_message"}:
            return "blue"
        return "white"

    def seed_demo_data(self) -> None:
        if not self._settings.demo_auto_seed:
            return
        with SessionLocal() as db:
            if db.scalar(select(func.count()).select_from(Agent)) != 0:
                return

            agents = [
                Agent(
                    name="Strategy Agent",
                    role="support-router",
                    system_prompt=(
                        "You triage requests and send a concise direction for the response agent."
                    ),
                    model=self._settings.default_model,
                    tools=["summarizer"],
                    channels=["web"],
                    guardrails={"max_output_chars": 400},
                ),
                Agent(
                    name="Draft Agent",
                    role="support-responder",
                    system_prompt=(
                        "You draft helpful user-facing responses based on router instructions."
                    ),
                    model=self._settings.default_model,
                    tools=["web_search", "summarizer"],
                    channels=["web", "telegram"],
                ),
                Agent(
                    name="Review Agent",
                    role="support-reviewer",
                    system_prompt=(
                        "You review response quality and return 'revise' only when critical issues remain."
                    ),
                    model=self._settings.default_model,
                    tools=["summarizer"],
                    channels=["web"],
                ),
            ]
            db.add_all(agents)
            db.commit()
            for agent in agents:
                db.refresh(agent)

            graph = WorkflowGraph(
                entry_node_id="router",
                max_steps=6,
                nodes=[
                    {"id": "router", "label": "Router Agent", "agent_id": agents[0].id, "position": {"x": 80, "y": 150}},
                    {"id": "responder", "label": "Response Agent", "agent_id": agents[1].id, "position": {"x": 380, "y": 80}},
                    {"id": "reviewer", "label": "Review Agent", "agent_id": agents[2].id, "position": {"x": 380, "y": 250}},
                ],
                edges=[
                    {"id": "e-1", "source": "router", "target": "responder", "condition": "always", "label": "draft"},
                    {"id": "e-2", "source": "responder", "target": "reviewer", "condition": "always", "label": "review"},
                    {"id": "e-3", "source": "reviewer", "target": "router", "condition": "contains:revise", "label": "revise"},
                ],
            )
            db.add(
                Workflow(
                    name="Support Loop",
                    description="Seeded support workflow with router-response-review loop.",
                    graph_json=graph.model_dump(),
                )
            )
            db.commit()
