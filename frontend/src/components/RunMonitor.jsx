import { useEffect, useMemo, useState } from "react";
import { Eraser, Pencil, Plus, Trash2 } from "lucide-react";

import { api } from "../api";

export function RunMonitor({
  agents,
  workflows,
  selectedWorkflowId,
  activeExecutionId,
  threads,
  selectedThreadId,
  onSelectThread,
  onCreateThread,
  onRenameThread,
  onDeleteThread,
  onClearThreadHistory,
  onClearAllHistory,
  onClearLiveFeed,
  onRun,
  executions,
  liveEvents,
  summary,
}) {
  const [inputText, setInputText] = useState("User issue: Login failed after password reset. Please help.");
  const [handoffMessages, setHandoffMessages] = useState([]);
  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedWorkflowId) || null,
    [workflows, selectedWorkflowId]
  );
  const selectedExecution = useMemo(() => {
    if (!executions.length) return null;
    if (activeExecutionId) {
      const active = executions.find((execution) => execution.id === activeExecutionId);
      if (active) return active;
    }
    return executions[0];
  }, [executions, activeExecutionId]);
  const agentNameById = useMemo(() => {
    const index = {};
    for (const agent of agents || []) {
      index[agent.id] = agent.name;
    }
    return index;
  }, [agents]);
  const userHistory = useMemo(
    () =>
      executions
        .map((execution) => ({
          id: execution.id,
          text: execution.input_payload?.input_text || "",
          status: execution.status,
          at: execution.started_at,
        }))
        .filter((item) => item.text),
    [executions]
  );
  const derivedHandoffs = useMemo(() => {
    const trace = selectedExecution?.output_payload?.trace || [];
    if (!Array.isArray(trace) || trace.length < 2) return [];
    const computed = [];
    for (let i = 0; i < trace.length - 1; i += 1) {
      computed.push({
        id: `trace-${i}`,
        source_agent_id: trace[i].agent_id || trace[i].node_id || "start",
        target_agent_id: trace[i + 1].agent_id || trace[i + 1].node_id || "end",
        content: trace[i].output || "",
      });
    }
    return computed;
  }, [selectedExecution?.id, selectedExecution?.output_payload]);
  const visibleHandoffs = handoffMessages.length > 0 ? handoffMessages : derivedHandoffs;
  const finalOutputText = selectedExecution?.output_payload?.final_output || "";

  useEffect(() => {
    if (!selectedExecution?.id) {
      setHandoffMessages([]);
      return;
    }
    api
      .listMessages(selectedExecution.id)
      .then((messages) => setHandoffMessages(messages))
      .catch(() => setHandoffMessages([]));
  }, [selectedExecution?.id]);

  return (
    <section className="panel">
      <h2>Session</h2>
      <div className="metrics-grid">
        <div>
          <span>Total Runs</span>
          <strong>{summary.executions || 0}</strong>
        </div>
        <div>
          <span>Tokens</span>
          <strong>{summary.tokens || 0}</strong>
        </div>
        <div>
          <span>Est. Cost</span>
          <strong>${Number(summary.cost_usd || 0).toFixed(4)}</strong>
        </div>
      </div>

      <textarea rows={4} value={inputText} onChange={(e) => setInputText(e.target.value)} />

      <div className="thread-bar">
        <select value={selectedThreadId || ""} onChange={(e) => onSelectThread(e.target.value)}>
          {threads.length === 0 ? <option value="">No thread</option> : null}
          {threads.map((thread) => (
            <option key={thread.id} value={thread.id}>
              {thread.title}
            </option>
          ))}
        </select>
        <button title="New Thread" className="icon-btn" onClick={onCreateThread}>
          <Plus size={16} />
        </button>
        <button title="Rename Thread" className="icon-btn" disabled={!selectedThreadId} onClick={onRenameThread}>
          <Pencil size={16} />
        </button>
        <button title="Clear Thread History" className="icon-btn" disabled={!selectedThreadId} onClick={onClearThreadHistory}>
          <Eraser size={16} />
        </button>
        <button title="Delete Thread" className="icon-btn danger" disabled={!selectedThreadId} onClick={onDeleteThread}>
          <Trash2 size={16} />
        </button>
      </div>

      <div className="run-row">
        <button disabled={!selectedWorkflowId || !selectedThreadId} onClick={() => onRun(inputText)}>
          Run
        </button>
        <button className="subtle-btn" onClick={onClearAllHistory}>
          Clear All
        </button>
      </div>

      <div className="guardrail-banner">
        Guardrail: max workflow steps = {selectedWorkflow?.graph?.max_steps || 6}
      </div>

      <h3>Message History</h3>
      <div className="execution-list">
        {userHistory.slice(0, 20).map((item) => (
          <article key={item.id} className="execution-card">
            <strong>{item.status.toUpperCase()}</strong>
            <small>{item.text}</small>
          </article>
        ))}
      </div>

      <div className="section-head">
        <h3>Live Feed</h3>
        <button className="subtle-btn" onClick={onClearLiveFeed}>
          Clear
        </button>
      </div>
      <div className="log-list">
        {liveEvents.slice(0, 40).map((event, idx) => (
          <div key={`${event.timestamp || idx}-${idx}`} className="log-line">
            <span>{event.event_type}</span>
            <small>{event.message}</small>
          </div>
        ))}
      </div>

      <h3>Inter-Agent Handoffs</h3>
      <div className="log-list">
        {visibleHandoffs.length === 0 ? <div className="log-line"><small>No handoff messages yet.</small></div> : null}
        {visibleHandoffs.slice(0, 25).map((message) => (
          <div key={message.id} className="log-line">
            <span>
              {agentNameById[message.source_agent_id] ||
                (message.source_agent_id ? message.source_agent_id.slice(0, 6) : "start")}{" "}
              -&gt;{" "}
              {agentNameById[message.target_agent_id] ||
                (message.target_agent_id ? message.target_agent_id.slice(0, 6) : "end")}
            </span>
            <small>{message.content}</small>
          </div>
        ))}
      </div>

      {selectedExecution ? (
        <>
          <h3>Final Answer</h3>
          <div className="final-output-box">
            {selectedExecution.status === "running" && !finalOutputText
              ? "Execution is running..."
              : finalOutputText || "No final answer yet."}
          </div>
          <h3>Latest Output</h3>
          <pre>
            {selectedExecution.status === "running" && !Object.keys(selectedExecution.output_payload || {}).length
              ? "Execution is still running. Output will appear automatically when complete."
              : JSON.stringify(selectedExecution.output_payload, null, 2)}
          </pre>
        </>
      ) : null}
    </section>
  );
}
