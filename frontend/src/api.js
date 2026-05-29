const API_BASE = import.meta.env.VITE_API_BASE || "/api";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (error) {
    throw new Error(`Network error on ${path}: ${error.message}`);
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `API request failed on ${path}: ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export const api = {
  listAgents: () => request("/agents"),
  getAgentCapabilities: () => request("/agents/capabilities"),
  createAgent: (payload) => request("/agents", { method: "POST", body: JSON.stringify(payload) }),
  listWorkflows: () => request("/workflows"),
  createWorkflow: (payload) => request("/workflows", { method: "POST", body: JSON.stringify(payload) }),
  updateWorkflow: (id, payload) => request(`/workflows/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteWorkflow: (id) => request(`/workflows/${id}`, { method: "DELETE" }),
  listTemplates: () => request("/workflows/templates/library"),
  createFromTemplate: (payload) => request("/workflows/templates/create", { method: "POST", body: JSON.stringify(payload) }),
  startExecution: (payload) => request("/executions", { method: "POST", body: JSON.stringify(payload) }),
  getExecution: (id) => request(`/executions/${id}`),
  listExecutions: () => request("/executions"),
  listThreads: (workflowId) =>
    request(`/threads${workflowId ? `?workflow_id=${encodeURIComponent(workflowId)}` : ""}`),
  createThread: (payload) => request("/threads", { method: "POST", body: JSON.stringify(payload) }),
  renameThread: (id, payload) => request(`/threads/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteThread: (id, purgeHistory = true) =>
    request(`/threads/${id}?purge_history=${purgeHistory ? "true" : "false"}`, { method: "DELETE" }),
  clearHistory: ({ threadId, workflowId } = {}) => {
    const query = new URLSearchParams();
    if (threadId) query.set("thread_id", threadId);
    if (workflowId) query.set("workflow_id", workflowId);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request(`/monitoring/history${suffix}`, { method: "DELETE" });
  },
  listLogs: (executionId) => request(`/monitoring/executions/${executionId}/logs`),
  listMessages: (executionId) => request(`/monitoring/executions/${executionId}/messages`),
  getSummary: () => request("/monitoring/summary"),
};

export function openMonitoringSocket(onEvent) {
  const wsBase = import.meta.env.VITE_WS_BASE;
  let wsUrl = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api/monitoring/ws/live`;
  if (wsBase) {
    wsUrl = `${wsBase}/api/monitoring/ws/live`;
  }
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (evt) => {
    try {
      onEvent(JSON.parse(evt.data));
    } catch (_error) {
      // Ignore parse errors from non-JSON websocket messages.
    }
  };
  return ws;
}
