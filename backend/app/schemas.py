from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str
    role: str
    system_prompt: str
    model: str = "openai/gpt-4.1"
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    channels: list[str] | None = None
    memory: dict[str, Any] | None = None
    guardrails: dict[str, Any] | None = None


class AgentRead(AgentBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowNode(BaseModel):
    id: str
    label: str
    agent_id: str
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})


class WorkflowCondition(BaseModel):
    type: Literal["always", "contains", "length_gt", "confidence", "on_error"] = "always"
    keyword: str | None = None
    threshold: int | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    action: Literal["retry", "skip"] | None = None


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    condition: WorkflowCondition | str = Field(default_factory=WorkflowCondition)
    label: str = "always"


class WorkflowGraph(BaseModel):
    entry_node_id: str
    max_steps: int = 8
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class WorkflowBase(BaseModel):
    name: str
    description: str = ""
    graph: WorkflowGraph


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: WorkflowGraph | None = None


class WorkflowRead(WorkflowBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateNode(BaseModel):
    id: str
    label: str
    role_hint: str
    position: dict[str, float] = Field(default_factory=dict)


class TemplateEdge(BaseModel):
    source: str
    target: str
    condition: WorkflowCondition | str
    label: str


class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str
    nodes: list[TemplateNode]
    edges: list[TemplateEdge]
    entry_node_id: str
    max_steps: int = 8


class CreateWorkflowFromTemplate(BaseModel):
    template_id: str
    workflow_name: str
    workflow_description: str = ""
    agent_mapping: dict[str, str] = Field(default_factory=dict)


class ExecutionCreate(BaseModel):
    workflow_id: str
    input_text: str
    trigger_source: str = "web"
    thread_id: str | None = None


class ExecutionRead(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger_source: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    total_tokens: int
    estimated_cost_usd: float
    started_at: datetime
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class LogEventRead(BaseModel):
    id: str
    execution_id: str
    level: str
    event_type: str
    message: str
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageRead(BaseModel):
    id: str
    execution_id: str
    source_agent_id: str | None
    target_agent_id: str | None
    content: str
    token_count: int
    cost_usd: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ThreadCreate(BaseModel):
    workflow_id: str
    title: str


class ThreadUpdate(BaseModel):
    title: str


class ThreadRead(BaseModel):
    id: str
    workflow_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
