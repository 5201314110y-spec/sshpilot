import { useState } from "react";
import { api } from "../api";

export default function AddServerModal({ onClose, onCreated }) {
  const [f, setF] = useState({
    name: "",
    host: "",
    port: 22,
    username: "root",
    auth_method: "password",
    password: "",
    private_key: "",
    passphrase: "",
    command_whitelist: "",
  });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function save() {
    setErr("");
    setSaving(true);
    try {
      const created = await api.createServer({ ...f, port: Number(f.port) });
      onCreated(created);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="card" style={{ width: 420 }} onClick={(e) => e.stopPropagation()}>
        <h2>Add server</h2>
        <div className="sub">Credentials are encrypted at rest.</div>
        <div className="row-gap">
          <div className="field">
            <span className="label">Name</span>
            <input value={f.name} onChange={up("name")} placeholder="prod-web-01" />
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <div className="field" style={{ flex: 3 }}>
              <span className="label">Host</span>
              <input value={f.host} onChange={up("host")} placeholder="10.0.0.5" />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <span className="label">Port</span>
              <input value={f.port} onChange={up("port")} />
            </div>
          </div>
          <div className="field">
            <span className="label">Username</span>
            <input value={f.username} onChange={up("username")} />
          </div>
          <div className="field">
            <span className="label">Auth method</span>
            <select value={f.auth_method} onChange={up("auth_method")}>
              <option value="password">Password</option>
              <option value="key">Private key</option>
            </select>
          </div>
          {f.auth_method === "password" ? (
            <div className="field">
              <span className="label">Password</span>
              <input type="password" value={f.password} onChange={up("password")} />
            </div>
          ) : (
            <>
              <div className="field">
                <span className="label">Private key (PEM)</span>
                <textarea
                  style={{ height: 90 }}
                  value={f.private_key}
                  onChange={up("private_key")}
                  placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                />
              </div>
              <div className="field">
                <span className="label">Passphrase (optional)</span>
                <input type="password" value={f.passphrase} onChange={up("passphrase")} />
              </div>
            </>
          )}
          <div className="field">
            <span className="label">Command whitelist (optional, comma-separated)</span>
            <input
              value={f.command_whitelist}
              onChange={up("command_whitelist")}
              placeholder="ls,cat,df,systemctl (empty = allow all)"
            />
          </div>
        </div>
        {err && <div className="err">{err}</div>}
        <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
          <button className="primary" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save server"}
          </button>
          <button onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
