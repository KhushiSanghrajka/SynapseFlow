from app.schemas import TemplateEdge, TemplateNode, WorkflowTemplate


def get_workflow_templates() -> list[WorkflowTemplate]:
    return [
        # WorkflowTemplate(
        #     id="race-strategy-loop",
        #     name="Strategy Review Loop",
        #     description="Route a brief through strategy, drafting, and review before looping for revisions.",
        #     entry_node_id="strategist",
        #     max_steps=6,
        #     nodes=[
        #         TemplateNode(id="strategist", label="Strategy Agent", role_hint="support-router", position={"x": 70, "y": 150}),
        #         TemplateNode(
        #             id="writer",
        #             label="Draft Agent",
        #             role_hint="support-responder",
        #             position={"x": 400, "y": 80},
        #         ),
        #         TemplateNode(
        #             id="reviewer",
        #             label="Review Agent",
        #             role_hint="support-reviewer",
        #             position={"x": 400, "y": 250},
        #         ),
        #     ],
        #     edges=[
        #         TemplateEdge(source="strategist", target="writer", condition={"type": "always"}, label="draft"),
        #         TemplateEdge(source="writer", target="reviewer", condition={"type": "always"}, label="review"),
        #         TemplateEdge(
        #             source="reviewer",
        #             target="strategist",
        #             condition={"type": "contains", "keyword": "revise"},
        #             label="revise loop",
        #         ),
        #     ],
        # ),
        # WorkflowTemplate(
        #     id="research-report",
        #     name="Research & Report",
        #     description="Collect sources, analyze findings, and turn them into a concise report.",
        #     entry_node_id="researcher",
        #     max_steps=6,
        #     nodes=[
        #         TemplateNode(
        #             id="researcher",
        #             label="Research Agent",
        #             role_hint="researcher",
        #             position={"x": 60, "y": 120},
        #         ),
        #         TemplateNode(
        #             id="analyst",
        #             label="Analysis Agent",
        #             role_hint="analyst",
        #             position={"x": 360, "y": 70},
        #         ),
        #         TemplateNode(
        #             id="writer",
        #             label="Report Agent",
        #             role_hint="report-writer",
        #             position={"x": 360, "y": 250},
        #         ),
        #     ],
        #     edges=[
        #         TemplateEdge(source="researcher", target="analyst", condition={"type": "always"}, label="analyze"),
        #         TemplateEdge(source="analyst", target="writer", condition={"type": "always"}, label="draft"),
        #         TemplateEdge(
        #             source="writer",
        #             target="researcher",
        #             condition={"type": "contains", "keyword": "revise"},
        #             label="revise loop",
        #         ),
        #     ],
        # ),
        # WorkflowTemplate(
        #     id="support-escalation",
        #     name="Support Escalation Triage",
        #     description="Triage a request, draft a response, and route to review when escalation is needed.",
        #     entry_node_id="triage",
        #     max_steps=5,
        #     nodes=[
        #         TemplateNode(id="triage", label="Triage Agent", role_hint="support-router", position={"x": 60, "y": 150}),
        #         TemplateNode(
        #             id="responder",
        #             label="Response Agent",
        #             role_hint="support-responder",
        #             position={"x": 360, "y": 90},
        #         ),
        #         TemplateNode(
        #             id="reviewer",
        #             label="Escalation Reviewer",
        #             role_hint="support-reviewer",
        #             position={"x": 360, "y": 240},
        #         ),
        #     ],
        #     edges=[
        #         TemplateEdge(source="triage", target="responder", condition={"type": "always"}, label="draft"),
        #         TemplateEdge(
        #             source="responder",
        #             target="reviewer",
        #             condition={"type": "contains", "keyword": "escalate"},
        #             label="escalate",
        #         ),
        #         TemplateEdge(
        #             source="reviewer",
        #             target="responder",
        #             condition={"type": "contains", "keyword": "revise"},
        #             label="revise loop",
        #         ),
        #     ],
        # ),
        # WorkflowTemplate(
        #     id="quick-faq",
        #     name="Quick FAQ Response",
        #     description="Triage a user question and draft a concise, customer-ready answer.",
        #     entry_node_id="triage",
        #     max_steps=3,
        #     nodes=[
        #         TemplateNode(id="triage", label="Triage Agent", role_hint="support-router", position={"x": 80, "y": 140}),
        #         TemplateNode(
        #             id="responder",
        #             label="Answer Agent",
        #             role_hint="support-responder",
        #             position={"x": 360, "y": 140},
        #         ),
        #     ],
        #     edges=[
        #         TemplateEdge(source="triage", target="responder", condition={"type": "always"}, label="answer"),
        #     ],
        # ),
        WorkflowTemplate(
            id="faq-basic",
            name="FAQ",
            description="Simple FAQ handler: triage the question and return a concise answer or suggested links.",
            entry_node_id="triage",
            max_steps=3,
            nodes=[
                TemplateNode(id="triage", label="Triage Agent", role_hint="support-router", position={"x": 80, "y": 140}),
                TemplateNode(
                    id="faq_responder",
                    label="FAQ Responder",
                    role_hint="support-responder",
                    position={"x": 360, "y": 140},
                ),
            ],
            edges=[
                TemplateEdge(source="triage", target="faq_responder", condition={"type": "always"}, label="answer"),
            ],
        ),
        WorkflowTemplate(
            id="india-tax-workflow",
            name="Tax — India (Validation + Calc)",
            description="Validate inputs, compute tax under old/new regimes, and return a short recommendation summary.",
            entry_node_id="input_validator",
            max_steps=6,
            nodes=[
                TemplateNode(id="input_validator", label="Input Validator", role_hint="input-validator", position={"x": 60, "y": 120}),
                TemplateNode(id="tax_calculator", label="Tax Calculator", role_hint="tax-calculator", position={"x": 360, "y": 80}),
                TemplateNode(id="summarizer", label="Summarizer", role_hint="summarizer", position={"x": 360, "y": 220}),
            ],
            edges=[
                TemplateEdge(source="input_validator", target="tax_calculator", condition={"type": "always"}, label="validated"),
                TemplateEdge(source="tax_calculator", target="summarizer", condition={"type": "always"}, label="results"),
                TemplateEdge(source="summarizer", target="input_validator", condition={"type": "contains", "keyword": "clarify"}, label="clarify"),
            ],
        ),
    ]
