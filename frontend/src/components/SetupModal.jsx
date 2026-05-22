import { useState } from "react";
import { api } from "../api";

export default function SetupModal({ onDone }) {
  const [key, setKey] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!key.trim()) {
      setErr("Enter your Anthropic API key.");
      return;
    }
    setErr("");
    setBusy(true);
    try {
      await api.updateSettings({ anthropic_api_key: key.trim() });
      onDone();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-bg">
      <div className="card" style={{ width: 440 }}>
        <h2>Welcome to SSHPilot</h2>
        <div className="sub">
          One-time setup. Paste your Anthropic API key to power the AI agent.
        </div>
        <div className="field">
          <span className="label">Anthropic API key</span>
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="sk-ant-..."
            onKeyDown={(e) => e.key === "Enter" && save()}
          />
        </div>
        <div style={{ color: "var(--ink-dim)", fontSize: 11, lineHeight: 1.5 }}>
          Get a key at console.anthropic.com. It is stored locally in
          sshpilot_data/ next to the app and never leaves your machine except to
          call the Anthropic API.
        </div>
        {err && <div className="err">{err}</div>}
        <button
          className="primary"
          style={{ width: "100%", marginTop: 16 }}
          onClick={save}
          disabled={busy}
        >
          {busy ? "Saving…" : "Save & continue"}
        </button>
      </div>
    </div>
  );
}
