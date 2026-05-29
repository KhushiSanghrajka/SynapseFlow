import { useState } from "react";

const defaultForm = {
  name: "",
  role: "",
  system_prompt: "",
  model: "gpt-4o",
  tools: [],
  channels: ["web"],
};

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
          placeholder="Role id (e.g. support-responder)"
          value={form.role}
          onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}
        />
        <input
          required
          placeholder="Model (Azure Inference id, e.g. gpt-4o)"
          value={form.model}
          onChange={(e) => setForm((prev) => ({ ...prev, model: e.target.value }))}
        />
        <div className="chip-group">
          {(capabilities?.tools || []).map((tool) => (
            <button
              type="button"
              key={tool}
              className={`chip ${form.tools.includes(tool) ? "chip-on" : ""}`}
              onClick={() => toggleMulti("tools", tool)}
            >
              {tool}
            </button>
          ))}
        </div>
        <div className="chip-group">
          {(capabilities?.channels || []).map((channel) => (
            <button
              type="button"
              key={channel}
              className={`chip ${form.channels.includes(channel) ? "chip-on" : ""}`}
              onClick={() => toggleMulti("channels", channel)}
            >
              {channel}
            </button>
          ))}
        </div>
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
      <div className="agent-list">
        {agents.map((agent) => (
          <article key={agent.id} className="agent-card">
            <strong>{agent.name}</strong>
            <span>{agent.role}</span>
            <small>{agent.model}</small>
            <small>Channels: {(agent.channels || []).join(", ") || "none"}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
