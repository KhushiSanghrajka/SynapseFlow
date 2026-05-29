from app.schemas import TemplateEdge, TemplateNode, WorkflowTemplate


def get_workflow_templates() -> list[WorkflowTemplate]:
    return [
        WorkflowTemplate(
            id="race-strategy-loop",
            name="Race Strategy Loop",
            description="Route a race brief through strategy, drafting, and review before looping for revisions.",
            entry_node_id="strategist",
            max_steps=6,
            nodes=[
                TemplateNode(id="strategist", label="Strategy Agent", role_hint="support-router", position={"x": 70, "y": 150}),
                TemplateNode(
                    id="writer",
                    label="Draft Agent",
                    role_hint="support-responder",
                    position={"x": 400, "y": 80},
                ),
                TemplateNode(
                    id="reviewer",
                    label="Review Agent",
                    role_hint="support-reviewer",
                    position={"x": 400, "y": 250},
                ),
            ],
            edges=[
                TemplateEdge(source="strategist", target="writer", condition={"type": "always"}, label="draft"),
                TemplateEdge(source="writer", target="reviewer", condition={"type": "always"}, label="review"),
                TemplateEdge(
                    source="reviewer",
                    target="strategist",
                    condition={"type": "contains", "keyword": "revise"},
                    label="revise loop",
                ),
            ],
        ),
        WorkflowTemplate(
            id="research-report",
            name="Research & Report",
            description="Collect sources, analyze findings, and turn them into a concise report.",
            entry_node_id="researcher",
            max_steps=6,
            nodes=[
                TemplateNode(
                    id="researcher",
                    label="Research Agent",
                    role_hint="researcher",
                    position={"x": 60, "y": 120},
                ),
                TemplateNode(
                    id="analyst",
                    label="Analysis Agent",
                    role_hint="analyst",
                    position={"x": 360, "y": 70},
                ),
                TemplateNode(
                    id="writer",
                    label="Report Agent",
                    role_hint="report-writer",
                    position={"x": 360, "y": 250},
                ),
            ],
            edges=[
                TemplateEdge(source="researcher", target="analyst", condition={"type": "always"}, label="analyze"),
                TemplateEdge(source="analyst", target="writer", condition={"type": "always"}, label="draft"),
                TemplateEdge(
                    source="writer",
                    target="researcher",
                    condition={"type": "contains", "keyword": "revise"},
                    label="revise loop",
                ),
            ],
        ),
    ]
