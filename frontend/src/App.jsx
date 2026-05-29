import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

import { api, openMonitoringSocket } from "./api";
import { AgentPanel } from "./components/AgentPanel";
import { RunMonitor } from "./components/RunMonitor";
import { WorkflowCanvas } from "./components/WorkflowCanvas";

function emptyGraph() {
  return {
    entry_node_id: "start-node",
    max_steps: 6,
    nodes: [],
    edges: [],
  };
}

export default function App() {
  const [agents, setAgents] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [capabilities, setCapabilities] = useState({ tools: [], channels: ["web"] });
  const [executions, setExecutions] = useState([]);
  const [threads, setThreads] = useState([]);
  const [summary, setSummary] = useState({});
  const [liveEvents, setLiveEvents] = useState([]);
  const [activeExecutionId, setActiveExecutionId] = useState("");
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [selectedThreadId, setSelectedThreadId] = useState("");
  const [errorText, setErrorText] = useState("");

  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedWorkflowId) || null,
    [workflows, selectedWorkflowId]
  );
  const filteredExecutions = useMemo(() => {
    if (!selectedThreadId) return executions;
    return executions.filter((execution) => execution.input_payload?.thread_id === selectedThreadId);
  }, [executions, selectedThreadId]);
  const executionThreadMap = useMemo(
    () => Object.fromEntries(executions.map((execution) => [execution.id, execution.input_payload?.thread_id || ""])),
    [executions]
  );
  const filteredLiveEvents = useMemo(() => {
    if (!selectedThreadId) return liveEvents;
    return liveEvents.filter((event) => {
      if (!event.execution_id) return true;
      const eventThreadId = event.thread_id || event.metadata?.thread_id || executionThreadMap[event.execution_id] || "";
      if (!eventThreadId) return true;
      return eventThreadId === selectedThreadId;
    });
  }, [liveEvents, selectedThreadId, executionThreadMap]);

  async function refreshThreads(workflowId, createIfMissing = false) {
    const nextThreads = await api.listThreads(workflowId);
    setThreads(nextThreads);
    if (nextThreads.length === 0 && createIfMissing) {
      const created = await api.createThread({ workflow_id: workflowId, title: "" });
      setThreads([created]);
      setSelectedThreadId(created.id);
      return;
    }
    if (!nextThreads.some((thread) => thread.id === selectedThreadId)) {
      setSelectedThreadId(nextThreads[0]?.id || "");
    }
  }

  async function refreshAll() {
    const [nextAgents, nextWorkflows, nextTemplates, nextExecutions, nextSummary] = await Promise.all([
      api.listAgents(),
      api.listWorkflows(),
      api.listTemplates(),
      api.listExecutions(),
      api.getSummary(),
    ]);
    setAgents(nextAgents);
    setWorkflows(nextWorkflows);
    setTemplates(nextTemplates);
    setExecutions(nextExecutions);
    setSummary(nextSummary);
    api.getAgentCapabilities().then(setCapabilities).catch(() => {});

    const workflowId = selectedWorkflowId || nextWorkflows[0]?.id || "";
    if (workflowId) {
      setSelectedWorkflowId(workflowId);
      await refreshThreads(workflowId, true);
    }
  }

  useEffect(() => {
    refreshAll().catch((err) => setErrorText(err.message));
  }, []);

  useEffect(() => {
    let socket = null;
    let reconnectTimer = null;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      socket = openMonitoringSocket((event) => {
        setLiveEvents((prev) => [event, ...prev].slice(0, 120));
        if (event.event_type && event.event_type.includes("execution_")) {
          api.listExecutions().then(setExecutions).catch(() => {});
          api.getSummary().then(setSummary).catch(() => {});
        }
      });
      socket.onopen = () => socket.send("listen");
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (!stopped) reconnectTimer = setTimeout(connect, 1200);
      };
    };

    connect();
    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkflowId) return;
    refreshThreads(selectedWorkflowId, false).catch((err) => setErrorText(err.message));
  }, [selectedWorkflowId]);

  async function createAgent(payload) {
    try {
      await api.createAgent(payload);
      setAgents(await api.listAgents());
      setErrorText("");
    } catch (err) {
      setErrorText(err.message);
    }
  }

  async function createWorkflow() {
    try {
      const index = workflows.length + 1;
      const created = await api.createWorkflow({
        name: `Workflow ${index}`,
        description: "Custom workflow",
        graph: emptyGraph(),
      });
      const updated = await api.listWorkflows();
      setWorkflows(updated);
      setSelectedWorkflowId(created.id);
      await refreshThreads(created.id, true);
      setErrorText("");
    } catch (err) {
      setErrorText(err.message);
    }
  }

  async function deleteWorkflow(workflowId) {
    if (!workflowId) return;
    try {
      await api.deleteWorkflow(workflowId);
      const updated = await api.listWorkflows();
      setWorkflows(updated);
      const nextId = updated[0]?.id || "";
      setSelectedWorkflowId(nextId);
      if (nextId) await refreshThreads(nextId, true);
      setErrorText("");
    } catch (err) {
      setErrorText(err.message);
    }
  }

  async function createFromTemplate(templateId) {
    try {
      const template = templates.find((item) => item.id === templateId);
      const created = await api.createFromTemplate({
        template_id: templateId,
        workflow_name: `${template?.name || "Template"} Copy`,
        workflow_description: "Generated from template",
        agent_mapping: {},
      });
      const updated = await api.listWorkflows();
      setWorkflows(updated);
      setSelectedWorkflowId(created.id);
      await refreshThreads(created.id, true);
      setErrorText("");
    } catch (err) {
      setErrorText(err.message);
    }
  }

  async function saveWorkflow(workflowId, partialPayload) {
    const workflow = workflows.find((item) => item.id === workflowId);
    if (!workflow) return;
    try {
      await api.updateWorkflow(workflowId, {
        name: workflow.name,
        description: workflow.description,
        ...partialPayload,
      });
      setWorkflows(await api.listWorkflows());
      setErrorText("");
    } catch (err) {
      setErrorText(err.message);
    }
  }

  async function runWorkflow(inputText) {
    if (!selectedWorkflow || !selectedThreadId) return;
    const started = await api.startExecution({
      workflow_id: selectedWorkflow.id,
      input_text: inputText,
      trigger_source: "web",
      thread_id: selectedThreadId,
    });
    setActiveExecutionId(started.id);
    setExecutions(await api.listExecutions());
    setSummary(await api.getSummary());
    void trackExecutionUntilDone(started.id);
  }

  async function trackExecutionUntilDone(executionId) {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      const record = await api.getExecution(executionId);
      setExecutions(await api.listExecutions());
      setSummary(await api.getSummary());
      if (record.status === "completed" || record.status === "failed") return;
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
  }

  async function createThread() {
    if (!selectedWorkflowId) return;
    const created = await api.createThread({ workflow_id: selectedWorkflowId, title: "" });
    setThreads(await api.listThreads(selectedWorkflowId));
    setSelectedThreadId(created.id);
  }

  async function renameThread() {
    if (!selectedThreadId) return;
    const current = threads.find((item) => item.id === selectedThreadId);
    const nextTitle = window.prompt("Rename thread", current?.title || "Thread");
    if (!nextTitle) return;
    await api.renameThread(selectedThreadId, { title: nextTitle });
    setThreads(await api.listThreads(selectedWorkflowId));
  }

  async function deleteCurrentThread() {
    if (!selectedThreadId) return;
    await api.deleteThread(selectedThreadId, true);
    await refreshThreads(selectedWorkflowId, true);
    setExecutions(await api.listExecutions());
    setSummary(await api.getSummary());
    setActiveExecutionId("");
    setLiveEvents([]);
  }

  async function clearThreadHistory() {
    if (!selectedThreadId) return;
    await api.clearHistory({ threadId: selectedThreadId });
    setExecutions(await api.listExecutions());
    setSummary(await api.getSummary());
    setActiveExecutionId("");
    setLiveEvents([]);
  }

  async function clearAllHistory() {
    await api.clearHistory();
    setExecutions(await api.listExecutions());
    setSummary(await api.getSummary());
    setActiveExecutionId("");
    setLiveEvents([]);
  }

  return (
    <main className="app-shell">
      <header>
        <h1>OrbitFlow Studio</h1>
        <p>Design workflows visually and run agent threads like chat sessions.</p>
      </header>
      {errorText ? (
        <div className="error">
          <span>{errorText}</span>
          <button
            className="error-close"
            title="Dismiss error"
            onClick={() => setErrorText("")}
            type="button"
          >
            <X size={14} />
          </button>
        </div>
      ) : null}
      <div className="layout-grid">
        <AgentPanel agents={agents} capabilities={capabilities} onCreateAgent={createAgent} />
        <WorkflowCanvas
          workflows={workflows}
          selectedWorkflowId={selectedWorkflowId}
          onSelectWorkflow={setSelectedWorkflowId}
          agents={agents}
          onCreateWorkflow={createWorkflow}
          onDeleteWorkflow={deleteWorkflow}
          templates={templates}
          onCreateFromTemplate={createFromTemplate}
          onSaveWorkflow={saveWorkflow}
        />
        <RunMonitor
          agents={agents}
          workflows={workflows}
          selectedWorkflowId={selectedWorkflowId}
          activeExecutionId={activeExecutionId}
          threads={threads}
          selectedThreadId={selectedThreadId}
          onSelectThread={setSelectedThreadId}
          onCreateThread={createThread}
          onRenameThread={renameThread}
          onDeleteThread={deleteCurrentThread}
          onClearThreadHistory={clearThreadHistory}
          onClearAllHistory={clearAllHistory}
          onClearLiveFeed={() => setLiveEvents([])}
          onRun={runWorkflow}
          executions={filteredExecutions}
          liveEvents={filteredLiveEvents}
          summary={summary}
        />
      </div>
    </main>
  );
}
