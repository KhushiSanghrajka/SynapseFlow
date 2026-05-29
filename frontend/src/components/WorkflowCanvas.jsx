import { useEffect, useMemo, useState } from "react";
import { Trash2 } from "lucide-react";
import ReactFlow, { Background, Controls, addEdge, useEdgesState, useNodesState } from "reactflow";

const CONDITION_OPTIONS = [
  { value: "always", label: "Always continue" },
  { value: "contains:revise", label: "If output mentions 'revise'" },
  { value: "contains:approve", label: "If output mentions 'approve'" },
  { value: "contains:urgent", label: "If output mentions 'urgent'" },
];

export function WorkflowCanvas({
  workflows,
  selectedWorkflowId,
  onSelectWorkflow,
  agents,
  onCreateWorkflow,
  onDeleteWorkflow,
  onCreateFromTemplate,
  templates,
  onSaveWorkflow,
}) {
  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedWorkflowId) || null,
    [workflows, selectedWorkflowId]
  );
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [templateId, setTemplateId] = useState("");
  const [agentForNode, setAgentForNode] = useState("");
  const [maxSteps, setMaxSteps] = useState(6);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);

  useEffect(() => {
    if (!selectedWorkflow) {
      setNodes([]);
      setEdges([]);
      return;
    }
    setNodes(
      selectedWorkflow.graph.nodes.map((node) => ({
        id: node.id,
        position: node.position,
        data: { label: node.label, agent_id: node.agent_id },
      }))
    );
    setEdges(
      selectedWorkflow.graph.edges.map((edge) => ({
        ...edge,
        data: { condition: edge.condition || "always" },
      }))
    );
    setMaxSteps(selectedWorkflow.graph.max_steps || 6);
  }, [selectedWorkflowId, workflows]);

  function deleteSelection() {
    const selectedNodeIds = new Set(nodes.filter((node) => node.selected).map((node) => node.id));
    const selectedEdgeIds = new Set(edges.filter((edge) => edge.selected).map((edge) => edge.id));
    if (selectedNodeIds.size === 0 && selectedEdgeIds.size === 0) {
      return;
    }
    setNodes((prev) => prev.filter((node) => !selectedNodeIds.has(node.id)));
    setEdges((prev) =>
      prev.filter(
        (edge) =>
          !selectedEdgeIds.has(edge.id) && !selectedNodeIds.has(edge.source) && !selectedNodeIds.has(edge.target)
      )
    );
  }

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      const active = document.activeElement;
      const tag = active?.tagName || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || active?.isContentEditable) return;
      if (!nodes.some((node) => node.selected) && !edges.some((edge) => edge.selected)) return;
      event.preventDefault();
      deleteSelection();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [nodes, edges]);

  function addAgentNode() {
    if (!agentForNode) return;
    const agent = agents.find((item) => item.id === agentForNode);
    if (!agent) return;
    const nodeId = `node-${Date.now()}`;
    setNodes((prev) =>
      prev.concat({
        id: nodeId,
        position: { x: 120 + prev.length * 35, y: 120 + prev.length * 18 },
        data: { label: agent.name, agent_id: agent.id },
      })
    );
    // Keep newly added nodes visible without requiring manual pan.
    setTimeout(() => reactFlowInstance?.fitView({ padding: 0.2, duration: 250 }), 0);
  }

  async function save() {
    if (!selectedWorkflowId || nodes.length === 0) return;
    await onSaveWorkflow(selectedWorkflowId, {
      graph: {
        entry_node_id: nodes[0].id,
        max_steps: Math.max(1, Math.min(20, Number(maxSteps) || 6)),
        nodes: nodes.map((node) => ({
          id: node.id,
          label: node.data.label,
          agent_id: node.data.agent_id,
          position: node.position,
        })),
        edges: edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label || edge.data?.condition || "always",
          condition: edge.data?.condition || "always",
        })),
      },
    });
  }

  return (
    <section className="canvas-panel">
      <div className="canvas-toolbar">
        <select value={selectedWorkflowId || ""} onChange={(e) => onSelectWorkflow(e.target.value)}>
          <option value="">Workflow</option>
          {workflows.map((workflow) => (
            <option key={workflow.id} value={workflow.id}>
              {workflow.name}
            </option>
          ))}
        </select>
        <button onClick={() => onCreateWorkflow()}>+ New</button>
        <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
          <option value="">Template</option>
          {templates.map((template) => (
            <option key={template.id} value={template.id}>
              {template.name}
            </option>
          ))}
        </select>
        <button disabled={!templateId} onClick={() => onCreateFromTemplate(templateId)}>
          Use Template
        </button>
        <button
          disabled={!selectedWorkflowId}
          onClick={() => onDeleteWorkflow(selectedWorkflowId)}
          title="Delete Workflow"
          className="icon-btn danger"
        >
          <Trash2 size={16} />
        </button>
      </div>

      <div className="canvas-toolbar">
        <select value={agentForNode} onChange={(e) => setAgentForNode(e.target.value)}>
          <option value="">Agent for node</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        <button onClick={addAgentNode}>Add Node</button>
        <button
          title="Delete Selected Node/Line"
          className="icon-btn danger"
          onClick={deleteSelection}
          disabled={!nodes.some((node) => node.selected) && !edges.some((edge) => edge.selected)}
        >
          <Trash2 size={16} />
        </button>
        <label className="guardrail-label">
          Max steps
          <input
            className="guardrail-input"
            type="number"
            min={1}
            max={20}
            value={maxSteps}
            onChange={(e) => setMaxSteps(Number(e.target.value) || 1)}
          />
        </label>
        <button onClick={save}>Save</button>
      </div>
      <p className="canvas-hint">
        Connect nodes by dragging from a node handle (small dot) to another node. Edge conditions evaluate the source node output text.
        Click a node/line and press Delete to remove it.
      </p>

      <div className="canvas-shell">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          onInit={setReactFlowInstance}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={(params) =>
            setEdges((prev) =>
              addEdge(
                {
                  ...params,
                  id: `edge-${Date.now()}`,
                  label: "always",
                  data: { condition: "always" },
                },
                prev
              )
            )
          }
        >
          <Controls />
          <Background gap={20} />
        </ReactFlow>
      </div>

      <h3>Edge Conditions</h3>
      <div className="edge-editor-list">
        {edges.length === 0 ? <div className="edge-empty">No connections yet. Create a line between two nodes first.</div> : null}
        {edges.map((edge) => {
          const active = edge.data?.condition || "always";
          const activeOption = CONDITION_OPTIONS.find((item) => item.value === active);
          return (
            <div key={edge.id} className="edge-editor-row">
              <span>
                {edge.source} -&gt; {edge.target}
              </span>
              <select
                value={active}
                onChange={(e) =>
                  setEdges((prev) =>
                    prev.map((item) =>
                      item.id === edge.id
                        ? { ...item, data: { condition: e.target.value }, label: e.target.value }
                        : item
                    )
                  )
                }
              >
                {activeOption ? null : <option value={active}>{active}</option>}
                {CONDITION_OPTIONS.map((condition) => (
                  <option key={condition.value} value={condition.value}>
                    {condition.label}
                  </option>
                ))}
              </select>
              <button
                title="Delete this connection"
                className="icon-btn danger edge-delete-btn"
                onClick={() => setEdges((prev) => prev.filter((item) => item.id !== edge.id))}
              >
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
