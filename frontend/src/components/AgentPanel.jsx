import { useState } from "react";

const defaultForm = {
  name: "",
  role: "",
  system_prompt: "",
  model: "gpt-4o",
  tools: [],
  channels: ["web"],
};

const TOOL_HELP = {
  web_search: "Search the web for live information and sources.",
  calculator: "Perform numeric calculations and quick conversions.",
  summarizer: "Compress long content into a concise summary.",
};

function formatRole(role) {
  if (!role) return "Unassigned role";
  return role
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTool(tool) {
  return tool
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function AgentPanel({ agents, capabilities, onCreateAgent }) {
  const [form, setForm] = useState(defaultForm);
  const [busy, setBusy] = useState(false);

  function toggleMulti(field, value) {
    setForm((prev) => {
      const values = new Set(prev[field]);
      if (values.has(value)) {
        values.delete(value);
      } else {
        values.add(value);
      }
      return { ...prev, [field]: Array.from(values) };
    });
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await onCreateAgent({
        ...form,
        memory: {},
        guardrails: {},
      });
      setForm(defaultForm);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Agent Forge</h2>
      <form onSubmit={submit} className="stack">
        <input
          required
          placeholder="Agent name"
          value={form.name}
          onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
        />
        <input
          required
          placeholder="Role"
          value={form.role}
          onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}
        />
        <input
          required
          placeholder="Model (Azure Inference id, e.g. gpt-4o)"
          value={form.model}
          onChange={(e) => setForm((prev) => ({ ...prev, model: e.target.value }))}
        />
        <fieldset className="option-group">
          <legend>Tools</legend>
          {(capabilities?.tools || []).map((tool) => (
            <label key={tool} className="check-option" title={TOOL_HELP[tool] || tool}>
              <input type="checkbox" checked={form.tools.includes(tool)} onChange={() => toggleMulti("tools", tool)} />
              <span>{tool}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="option-group">
          <legend>Channels</legend>
          {(capabilities?.channels || []).map((channel) => (
            <label key={channel} className="check-option">
              <input
                type="checkbox"
                checked={form.channels.includes(channel)}
                onChange={() => toggleMulti("channels", channel)}
              />
              <span>{channel}</span>
            </label>
          ))}
        </fieldset>
        <textarea
          required
          rows={4}
          placeholder="System prompt"
          value={form.system_prompt}
          onChange={(e) => setForm((prev) => ({ ...prev, system_prompt: e.target.value }))}
        />
        <button type="submit" disabled={busy}>
          {busy ? "Creating..." : "Create Agent"}
        </button>
      </form>
      <h3>Your agents</h3>
      <div className="agent-list">
        {agents.map((agent) => (
          <article key={agent.id} className="agent-card">
            <div className="agent-card-name">{agent.name}</div>
            <div className="agent-card-role">{formatRole(agent.role)}</div>
            <small>{agent.model}</small>
            <div className="badge-row">
              {(agent.tools || []).length > 0 ? (
                (agent.tools || []).map((tool) => (
                  <span key={tool} className="badge">
                    {formatTool(tool)}
                  </span>
                ))
              ) : (
                <span className="badge muted">No tools</span>
              )}
            </div>
            <div className="badge-row">
              {(agent.channels || []).length > 0 ? (
                (agent.channels || []).map((channel) => (
                  <span key={channel} className="badge">
                    {channel}
                  </span>
                ))
              ) : (
                <span className="badge muted">No channels</span>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
