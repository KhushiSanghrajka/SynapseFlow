import { useEffect, useMemo, useState } from "react";
import { Activity, Clock3, Eraser, MessageSquare, Pencil, Plus, Trash2 } from "lucide-react";

import { api } from "../api";

function summarizeText(text, limit = 120) {
  const value = String(text || "").trim();
  if (!value) return "No content yet.";
  if (value.length <= limit) return value;
  return `${value.slice(0, limit).trimEnd()}...`;
}

function formatFinalAnswer(text) {
  const value = String(text || "").trim();
  if (!value) return "No final answer yet.";
  return value
    .replace(/```[\s\S]*?```/g, (match) => match.replace(/```/g, ""))
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1 ($2)")
    .trim();
}

function formatTimestamp(value) {
  if (!value) return "Now";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

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
}) {
  const [inputText, setInputText] = useState("User issue: Login failed after password reset. Please help.");
  const [handoffMessages, setHandoffMessages] = useState([]);
  const [activeTab, setActiveTab] = useState("chat");
  const [showRawOutput, setShowRawOutput] = useState(false);

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
        created_at: selectedExecution?.started_at || "",
      });
    }
    return computed;
  }, [selectedExecution?.id, selectedExecution?.output_payload, selectedExecution?.started_at]);

  const visibleHandoffs = handoffMessages.length > 0 ? handoffMessages : derivedHandoffs;
  const finalOutputText = selectedExecution?.output_payload?.final_output || "";
  const latestOutput = selectedExecution?.output_payload || {};

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

  useEffect(() => {
    setShowRawOutput(false);
  }, [selectedExecution?.id, activeTab]);

  return (
    <section className="panel run-monitor">
      <div className="tab-bar" role="tablist" aria-label="Run panel tabs">
        <button
          type="button"
          className={`tab-btn ${activeTab === "chat" ? "tab-btn-active" : ""}`}
          title="Chat"
          onClick={() => setActiveTab("chat")}
        >
          <MessageSquare size={16} />
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "logs" ? "tab-btn-active" : ""}`}
          title="Activity"
          onClick={() => setActiveTab("logs")}
        >
          <Activity size={16} />
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "history" ? "tab-btn-active" : ""}`}
          title="History"
          onClick={() => setActiveTab("history")}
        >
          <Clock3 size={16} />
        </button>
      </div>

      {activeTab === "chat" ? (
        <div className="panel-section">
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
            <button
              title="Clear Thread History"
              className="icon-btn"
              disabled={!selectedThreadId}
              onClick={onClearThreadHistory}
            >
              <Eraser size={16} />
            </button>
            <button title="Delete Thread" className="icon-btn danger" disabled={!selectedThreadId} onClick={onDeleteThread}>
              <Trash2 size={16} />
            </button>
          </div>

          <textarea rows={4} value={inputText} onChange={(e) => setInputText(e.target.value)} />

          <div className="run-row">
            <button className="primary-action" disabled={!selectedWorkflowId || !selectedThreadId} onClick={() => onRun(inputText)}>
              Run
            </button>
            <button className="subtle-btn" onClick={onClearAllHistory}>
              Clear All
            </button>
          </div>
        </div>
      ) : null}

      {activeTab === "logs" ? (
        <div className="panel-section">
          <div className="section-head section-head-tight">
            <h3>Live Feed</h3>
            <button className="subtle-btn inline-button" onClick={onClearLiveFeed}>
              Clear Live Feed
            </button>
          </div>
          <div className="log-list log-list-expanded">
            {liveEvents.slice(0, 40).map((event, idx) => (
              <div key={`${event.timestamp || idx}-${idx}`} className="log-card">
                <div className="log-card-head">
                  <span>{event.event_type}</span>
                  <small>{formatTimestamp(event.timestamp || event.created_at)}</small>
                </div>
                <small>{event.message}</small>
              </div>
            ))}
            {liveEvents.length === 0 ? <div className="empty-copy">No live activity yet.</div> : null}
          </div>

          <h3>Inter-Agent Handoffs</h3>
          <div className="handoff-list">
            {visibleHandoffs.length === 0 ? <div className="empty-copy">No handoff messages yet.</div> : null}
            {visibleHandoffs.slice(0, 25).map((message) => (
              <article key={message.id} className="handoff-card">
                <div className="handoff-card-head">
                  <strong>
                    {agentNameById[message.source_agent_id] ||
                      (message.source_agent_id ? message.source_agent_id.slice(0, 6) : "start")}
                  </strong>
                  <span>-&gt;</span>
                  <strong>
                    {agentNameById[message.target_agent_id] ||
                      (message.target_agent_id ? message.target_agent_id.slice(0, 6) : "end")}
                  </strong>
                  <small>{formatTimestamp(message.created_at || message.timestamp)}</small>
                </div>
                <p>{summarizeText(message.content, 160)}</p>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {activeTab === "history" ? (
        <div className="panel-section">
          <h3>Message History</h3>
          <div className="execution-list execution-list-expanded">
            {userHistory.slice(0, 20).map((item) => (
              <article key={item.id} className="execution-card">
                <strong>{item.status.toUpperCase()}</strong>
                <small>{summarizeText(item.text, 140)}</small>
                <span>{formatTimestamp(item.at)}</span>
              </article>
            ))}
            {userHistory.length === 0 ? <div className="empty-copy">No runs yet.</div> : null}
          </div>

          {selectedExecution ? (
            <div className="history-output">
              <h3>Final Answer</h3>
              <div className="final-output-box">
                {selectedExecution.status === "running" && !finalOutputText
                  ? "Execution is running..."
                  : formatFinalAnswer(finalOutputText)}
              </div>
              <button className="subtle-btn inline-button" onClick={() => setShowRawOutput((value) => !value)}>
                {showRawOutput ? "Hide raw output" : "Show raw output"}
              </button>
              {showRawOutput ? (
                <pre>
                  {selectedExecution.status === "running" && !Object.keys(latestOutput || {}).length
                    ? "Execution is still running. Output will appear automatically when complete."
                    : JSON.stringify(latestOutput, null, 2)}
                </pre>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
