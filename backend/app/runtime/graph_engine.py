import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.llm.github_models import GitHubMarketplaceClient
from app.models import Agent
from app.schemas import WorkflowEdge, WorkflowGraph, WorkflowNode


class RuntimeState(TypedDict, total=False):
    execution_id: str
    workflow_input: str
    current_output: str
    outputs: dict[str, str]
    steps: int
    max_steps: int
    flow_trace: list[dict[str, Any]]
    token_total: int
    cost_total: float


EventHook = Callable[[dict[str, Any]], Awaitable[None]]


class GraphExecutionEngine:
    def __init__(self, llm_client: GitHubMarketplaceClient) -> None:
        self._llm_client = llm_client

    async def run(
        self,
        *,
        execution_id: str,
        workflow: WorkflowGraph,
        agents_by_id: dict[str, Agent],
        user_input: str,
        on_event: EventHook,
    ) -> RuntimeState:
        builder = StateGraph(RuntimeState)
        nodes_by_id = {node.id: node for node in workflow.nodes}
        edges_by_source: dict[str, list[WorkflowEdge]] = {}
        for edge in workflow.edges:
            edges_by_source.setdefault(edge.source, []).append(edge)

        for node in workflow.nodes:
            agent = agents_by_id.get(node.agent_id)
            if agent is None:
                raise ValueError(f"Workflow node '{node.id}' references unknown agent '{node.agent_id}'.")
            builder.add_node(node.id, self._build_node_runner(node, agent, on_event))

        builder.set_entry_point(workflow.entry_node_id)

        for node_id, outgoing in edges_by_source.items():
            path_map = {edge.target: edge.target for edge in outgoing}
            path_map["END"] = END
            builder.add_conditional_edges(
                node_id,
                self._build_router(node_id, outgoing, on_event),
                path_map,
            )

        for node in workflow.nodes:
            if node.id not in edges_by_source:
                builder.add_edge(node.id, END)

        graph = builder.compile()
        initial_state: RuntimeState = {
            "execution_id": execution_id,
            "workflow_input": user_input,
            "current_output": "",
            "outputs": {},
            "steps": 0,
            "max_steps": workflow.max_steps,
            "flow_trace": [],
            "token_total": 0,
            "cost_total": 0.0,
        }
        result = await graph.ainvoke(initial_state, config={"recursion_limit": max(20, workflow.max_steps * 4)})
        return result

    def _build_node_runner(self, node: WorkflowNode, agent: Agent, on_event: EventHook):
        async def run_node(state: RuntimeState) -> RuntimeState:
            step = state.get("steps", 0) + 1
            prior_outputs = json.dumps(state.get("outputs", {}), ensure_ascii=True)
            memory_blob = json.dumps(agent.memory or {}, ensure_ascii=True)
            prompt = (
                f"Primary user request:\n{state.get('workflow_input', '')}\n\n"
                f"Current orchestration outputs:\n{prior_outputs}\n\n"
                f"Agent memory profile:\n{memory_blob}\n\n"
                f"You are step {step} in the workflow. Keep output concise and actionable."
            )
            llm_response = await self._llm_client.complete(
                system_prompt=agent.system_prompt,
                user_prompt=prompt,
                model=agent.model,
            )
            output_text = llm_response.content or ""
            guardrails = agent.guardrails or {}
            max_chars = guardrails.get("max_output_chars")
            if isinstance(max_chars, int) and max_chars > 0 and len(output_text) > max_chars:
                output_text = output_text[:max_chars].rstrip() + "..."
                await on_event(
                    {
                        "execution_id": state.get("execution_id"),
                        "event_type": "agent_guardrail",
                        "message": f"{node.label} output truncated by max_output_chars guardrail.",
                        "metadata": {
                            "node_id": node.id,
                            "agent_id": agent.id,
                            "max_output_chars": max_chars,
                        },
                    }
                )

            blocked_terms = guardrails.get("blocked_terms", [])
            if isinstance(blocked_terms, list):
                for term in blocked_terms:
                    if isinstance(term, str) and term and term.lower() in output_text.lower():
                        output_text = output_text.replace(term, "[redacted]")
                        await on_event(
                            {
                                "execution_id": state.get("execution_id"),
                                "event_type": "agent_guardrail",
                                "message": f"{node.label} output redacted blocked term.",
                                "metadata": {
                                    "node_id": node.id,
                                    "agent_id": agent.id,
                                    "blocked_term": term,
                                },
                            }
                        )

            outputs = dict(state.get("outputs", {}))
            outputs[node.id] = output_text
            trace = list(state.get("flow_trace", []))
            trace.append({"node_id": node.id, "agent_id": agent.id, "output": output_text})

            await on_event(
                {
                    "execution_id": state.get("execution_id"),
                    "event_type": "node_completed",
                    "message": f"{node.label} completed step {step}.",
                    "metadata": {
                        "node_id": node.id,
                        "node_label": node.label,
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "tokens": llm_response.total_tokens,
                        "cost_usd": llm_response.estimated_cost_usd,
                    },
                }
            )

            return {
                **state,
                "steps": step,
                "current_output": output_text,
                "outputs": outputs,
                "flow_trace": trace,
                "token_total": int(state.get("token_total", 0)) + llm_response.total_tokens,
                "cost_total": round(float(state.get("cost_total", 0.0)) + llm_response.estimated_cost_usd, 6),
            }

        return run_node

    def _build_router(self, node_id: str, outgoing: list[WorkflowEdge], on_event: EventHook):
        async def route(state: RuntimeState) -> str:
            if state.get("steps", 0) >= state.get("max_steps", 8):
                await on_event(
                    {
                        "execution_id": state.get("execution_id"),
                        "event_type": "guardrail_stop",
                        "message": "Workflow hit max step guardrail.",
                        "metadata": {"node_id": node_id, "max_steps": state.get("max_steps", 8)},
                    }
                )
                return "END"

            text = state.get("current_output", "")
            for edge in outgoing:
                if self._condition_matches(edge.condition, text, state):
                    await on_event(
                        {
                            "execution_id": state.get("execution_id"),
                            "event_type": "edge_selected",
                            "message": f"Routing {edge.source} -> {edge.target} ({edge.condition}).",
                            "metadata": {
                                "source": edge.source,
                                "target": edge.target,
                                "condition": edge.condition,
                                "edge_id": edge.id,
                            },
                        }
                    )
                    return edge.target
            return "END"

        return route

    @staticmethod
    def _condition_matches(condition: str, text: str, state: RuntimeState) -> bool:
        normalized = (condition or "always").strip()
        if normalized in {"always", "*"}:
            return True
        if normalized.startswith("contains:"):
            probe = normalized.split(":", 1)[1].strip().lower()
            return probe in text.lower()
        if normalized.startswith("equals:"):
            probe = normalized.split(":", 1)[1].strip().lower()
            return text.strip().lower() == probe
        if normalized.startswith("regex:"):
            pattern = normalized.split(":", 1)[1]
            return re.search(pattern, text, flags=re.IGNORECASE) is not None
        if normalized.startswith("step_lt:"):
            threshold = int(normalized.split(":", 1)[1])
            return int(state.get("steps", 0)) < threshold
        return False
