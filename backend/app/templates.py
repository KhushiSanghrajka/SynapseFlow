from app.schemas import TemplateEdge, TemplateNode, WorkflowTemplate


def get_workflow_templates() -> list[WorkflowTemplate]:
    return [
        WorkflowTemplate(
            id="support-routing-loop",
            name="Support Routing Loop",
            description=(
                "Route incoming requests, draft a response, and loop for revision when needed."
            ),
            entry_node_id="router",
            max_steps=6,
            nodes=[
                TemplateNode(id="router", label="Router Agent", role_hint="support-router", position={"x": 70, "y": 150}),
                TemplateNode(
                    id="responder",
                    label="Response Agent",
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
                TemplateEdge(source="router", target="responder", condition="always", label="draft"),
                TemplateEdge(source="responder", target="reviewer", condition="always", label="review"),
                TemplateEdge(source="reviewer", target="router", condition="contains:revise", label="revise loop"),
            ],
        ),
        WorkflowTemplate(
            id="meeting-notes-loop",
            name="Meeting Notes Loop",
            description="Turn rough meeting bullets into polished notes with review feedback loop.",
            entry_node_id="collector",
            max_steps=6,
            nodes=[
                TemplateNode(
                    id="collector",
                    label="Collector Agent",
                    role_hint="notes-collector",
                    position={"x": 60, "y": 120},
                ),
                TemplateNode(
                    id="writer",
                    label="Writer Agent",
                    role_hint="notes-writer",
                    position={"x": 360, "y": 70},
                ),
                TemplateNode(
                    id="editor",
                    label="Editor Agent",
                    role_hint="notes-editor",
                    position={"x": 360, "y": 250},
                ),
            ],
            edges=[
                TemplateEdge(source="collector", target="writer", condition="always", label="compose"),
                TemplateEdge(source="writer", target="editor", condition="always", label="polish"),
                TemplateEdge(source="editor", target="collector", condition="contains:revise", label="revise loop"),
            ],
        ),
    ]
