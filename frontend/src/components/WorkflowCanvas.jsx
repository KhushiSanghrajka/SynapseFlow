import { useEffect, useMemo, useState } from "react";
import { Plus, Save, Trash2, WandSparkles } from "lucide-react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  addEdge,
  useEdgesState,
  useNodesState,
} from "reactflow";

const CONDITION_OPTIONS = [
  { value: "always", label: "Always continue" },
  { value: "contains", label: "If output contains keyword" },
  { value: "length_gt", label: "If output length > n" },
  { value: "confidence", label: "If agent confidence matches" },
  { value: "on_error", label: "On error" },
];

const CONFIDENCE_OPTIONS = ["high", "medium", "low"];
const ERROR_OPTIONS = ["retry", "skip"];

function getAgentAccent(agentId) {
  const seed = String(agentId || "agent").split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return `hsl(${seed % 360} 78% 56%)`;
}

function normalizeCondition(condition) {
  if (!condition) return { type: "always" };
  if (typeof condition === "object") {
    if (typeof condition.model_dump === "function") {
      return normalizeCondition(condition.model_dump());
    }
    return {
      type: condition.type || "always",
      keyword: condition.keyword || "",
      threshold: condition.threshold ?? 0,
      confidence: condition.confidence || "medium",
      action: condition.action || "retry",
    };
  }
  const normalized = String(condition).trim().toLowerCase();
  const tail = normalized.includes(":") ? normalized.slice(normalized.indexOf(":") + 1).trim() : "";
  if (normalized.startsWith("contains:")) {
    return { type: "contains", keyword: tail };
  }
  if (normalized.startsWith("length_gt:")) {
    return { type: "length_gt", threshold: Number(tail) || 0 };
  }
  if (normalized.startsWith("confidence:")) {
    return { type: "confidence", confidence: tail };
  }
  if (normalized.startsWith("on_error:")) {
    return { type: "on_error", action: tail || "retry" };
  }
  return { type: normalized || "always" };
}

function conditionLabel(condition) {
  const resolved = normalizeCondition(condition);
  if (resolved.type === "contains") {
    return resolved.keyword ? `Contains "${resolved.keyword}"` : "Contains keyword";
  }
  if (resolved.type === "length_gt") {
    return resolved.threshold ? `Length > ${resolved.threshold}` : "Length check";
  }
  if (resolved.type === "confidence") {
    return resolved.confidence ? `Confidence = ${resolved.confidence}` : "Confidence check";
  }
  if (resolved.type === "on_error") {
    return resolved.action ? `On error -> ${resolved.action}` : "On error";
  }
  return "Always continue";
}

function serializeCondition(condition) {
  const resolved = normalizeCondition(condition);
  if (resolved.type === "contains") {
    return { type: "contains", keyword: resolved.keyword?.trim() || "" };
  }
  if (resolved.type === "length_gt") {
    return { type: "length_gt", threshold: Math.max(1, Number(resolved.threshold) || 1) };
  }
  if (resolved.type === "confidence") {
    return { type: "confidence", confidence: resolved.confidence || "medium" };
  }
  if (resolved.type === "on_error") {
    return { type: "on_error", action: resolved.action || "retry" };
  }
  return { type: "always" };
}

function AgentNode({ data }) {
  return (
    <div className="workflow-node" style={{ "--node-accent": data.accent || "#58a6ff" }}>
      <div className="workflow-node-strip" />
      <Handle type="target" position={Position.Top} className="workflow-handle" />
      <div className="workflow-node-title">{data.label}</div>
      <div className="workflow-node-role">{data.role}</div>
      <div className="workflow-node-meta">{data.agentName}</div>
      <Handle type="source" position={Position.Bottom} className="workflow-handle" />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };

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
  onDirtyChange,
  onWorkflowSaved,
}) {
  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedWorkflowId) || null,
    [workflows, selectedWorkflowId]
  );
  const agentIndex = useMemo(() => Object.fromEntries((agents || []).map((agent) => [agent.id, agent])), [agents]);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [templateId, setTemplateId] = useState("");
  const [agentForNode, setAgentForNode] = useState("");
  const [maxSteps, setMaxSteps] = useState(6);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!selectedWorkflow) {
      setNodes([]);
      setEdges([]);
      setDirty(false);
      return;
    }
    setNodes(
      selectedWorkflow.graph.nodes.map((node) => ({
        id: node.id,
        type: "agentNode",
        position: node.position,
        data: {
          label: node.label,
          agentId: node.agent_id,
          agentName: agentIndex[node.agent_id]?.name || node.label,
          role: agentIndex[node.agent_id]?.role || "",
          accent: getAgentAccent(node.agent_id),
        },
      }))
    );
    setEdges(
      selectedWorkflow.graph.edges.map((edge) => ({
        ...edge,
        data: { condition: normalizeCondition(edge.condition || "always") },
        label: conditionLabel(edge.condition || "always"),
        markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(88, 166, 255, 0.95)" },
        style: { strokeWidth: 2.5, stroke: "rgba(88, 166, 255, 0.95)" },
      }))
    );
    setMaxSteps(selectedWorkflow.graph.max_steps || 6);
    setDirty(false);
  }, [selectedWorkflowId, workflows, agentIndex]);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  function markDirty() {
    if (selectedWorkflowId) {
      setDirty(true);
    }
  }

  function updateEdgeCondition(edgeId, updater) {
    setEdges((prev) =>
      prev.map((edge) => {
        if (edge.id !== edgeId) return edge;
        const current = normalizeCondition(edge.data?.condition || edge.condition || "always");
        const nextCondition = typeof updater === "function" ? updater(current) : updater;
        return {
          ...edge,
          data: { condition: nextCondition },
          label: conditionLabel(nextCondition),
        };
      })
    );
    markDirty();
  }

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
    markDirty();
  }

  function handleNodesChange(changes) {
    onNodesChange(changes);
  }

  function handleEdgesChange(changes) {
    onEdgesChange(changes);
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
        type: "agentNode",
        position: { x: 120 + prev.length * 35, y: 120 + prev.length * 18 },
        data: {
          label: agent.name,
          agentId: agent.id,
          agentName: agent.name,
          role: agent.role,
          accent: getAgentAccent(agent.id),
        },
      })
    );
    markDirty();
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
          agent_id: node.data.agentId,
          position: node.position,
        })),
        edges: edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label || conditionLabel(edge.data?.condition || "always"),
          condition: serializeCondition(edge.data?.condition || "always"),
        })),
      },
    });
    setDirty(false);
    onWorkflowSaved?.();
  }

  return (
    <section className="canvas-panel">
      <div className="canvas-toolbar">
        <select value={selectedWorkflowId || ""} onChange={(e) => onSelectWorkflow(e.target.value)}>
          <option value="">Select workflow</option>
          {workflows.map((workflow) => (
            <option key={workflow.id} value={workflow.id}>
              {workflow.name}
            </option>
          ))}
        </select>
        <button title="Create workflow" className="icon-btn" onClick={() => onCreateWorkflow()}>
          <Plus size={16} />
        </button>
        <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
          <option value="">Template</option>
          {templates.map((template) => (
            <option key={template.id} value={template.id}>
              {template.name}
            </option>
          ))}
        </select>
        <button title="Create from template" disabled={!templateId} className="icon-btn" onClick={() => onCreateFromTemplate(templateId)}>
          <WandSparkles size={16} />
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
          <option value="">Select agent</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        <button title="Add node" className="icon-btn" onClick={addAgentNode}>
          <Plus size={16} />
        </button>
        <button
          title="Delete Selected Node/Line"
          className="icon-btn danger"
          onClick={deleteSelection}
          disabled={!nodes.some((node) => node.selected) && !edges.some((edge) => edge.selected)}
        >
          <Trash2 size={16} />
        </button>
        <label className="guardrail-label" title="Stop execution when this many workflow steps are reached.">
          Step limit
          <input
            className="guardrail-input"
            type="number"
            min={1}
            max={20}
            value={maxSteps}
            onChange={(e) => {
              setMaxSteps(Number(e.target.value) || 1);
              markDirty();
            }}
          />
        </label>
        <span className="guardrail-pill">Max workflow steps: {maxSteps}</span>
        <button title="Save workflow" className="icon-btn save-btn" onClick={save}>
          <Save size={16} />
        </button>
      </div>

      <div className="canvas-shell">
        {nodes.length === 0 ? (
          <div className="canvas-empty-state">
            <strong>Drag an agent from the left panel to get started.</strong>
            <span>Add a node, connect it, then pick a condition for each edge.</span>
          </div>
        ) : null}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          onInit={setReactFlowInstance}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onNodeDragStop={markDirty}
          onConnect={(params) =>
            (markDirty(),
            setEdges((prev) =>
              addEdge(
                {
                  ...params,
                  id: `edge-${Date.now()}`,
                  label: conditionLabel({ type: "always" }),
                  data: { condition: { type: "always" } },
                  markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(88, 166, 255, 0.95)" },
                  style: { strokeWidth: 2.5, stroke: "rgba(88, 166, 255, 0.95)" },
                },
                prev
              )
            ))
          }
          nodeTypes={nodeTypes}
          defaultEdgeOptions={{
            markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(88, 166, 255, 0.95)" },
            style: { strokeWidth: 2.5, stroke: "rgba(88, 166, 255, 0.95)" },
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Controls className="flow-controls" />
          <Background gap={20} />
        </ReactFlow>
      </div>

      <h3>Edge Conditions</h3>
      <div className="edge-editor-list">
        {edges.length === 0 ? <div className="edge-empty">No connections yet. Create a line between two nodes first.</div> : null}
        {edges.map((edge) => {
          const active = normalizeCondition(edge.data?.condition || edge.condition || "always");
          return (
            <div key={edge.id} className="edge-editor-row">
              <span>
                {edge.source} -&gt; {edge.target}
              </span>
              <div className="edge-condition-editor">
                <select
                  value={active.type}
                  onChange={(e) =>
                    updateEdgeCondition(edge.id, {
                      ...active,
                      type: e.target.value,
                    })
                  }
                >
                  {CONDITION_OPTIONS.map((condition) => (
                    <option key={condition.value} value={condition.value}>
                      {condition.label}
                    </option>
                  ))}
                </select>
                {active.type === "contains" ? (
                  <input
                    placeholder="keyword"
                    value={active.keyword || ""}
                    onChange={(e) => updateEdgeCondition(edge.id, { ...active, keyword: e.target.value })}
                  />
                ) : null}
                {active.type === "length_gt" ? (
                  <input
                    type="number"
                    min={1}
                    placeholder="n"
                    value={active.threshold || 1}
                    onChange={(e) =>
                      updateEdgeCondition(edge.id, { ...active, threshold: Number(e.target.value) || 1 })
                    }
                  />
                ) : null}
                {active.type === "confidence" ? (
                  <select
                    value={active.confidence || "medium"}
                    onChange={(e) => updateEdgeCondition(edge.id, { ...active, confidence: e.target.value })}
                  >
                    {CONFIDENCE_OPTIONS.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                ) : null}
                {active.type === "on_error" ? (
                  <select
                    value={active.action || "retry"}
                    onChange={(e) => updateEdgeCondition(edge.id, { ...active, action: e.target.value })}
                  >
                    {ERROR_OPTIONS.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                ) : null}
              </div>
              <button
                title="Delete this connection"
                className="icon-btn danger edge-delete-btn"
                onClick={() => {
                  setEdges((prev) => prev.filter((item) => item.id !== edge.id));
                  markDirty();
                }}
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
