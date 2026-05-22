import { useState } from "react";
import { api, setToken } from "../api";

export default function Auth({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setErr("");
    setBusy(true);
    try {
      const fn = mode === "login" ? api.login : api.register;
      const { access_token } = await fn(email, password);
      setToken(access_token);
      onAuthed();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-screen">
      <div className="card">
        <h2>
          SSH<span style={{ color: "var(--green)" }}>Pilot</span>
        </h2>
        <div className="sub">Agentic terminal for your servers</div>
        <div className="row-gap">
          <div className="field">
            <span className="label">Email</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <span className="label">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>
        </div>
        {err && <div className="err">{err}</div>}
        <button
          className="primary"
          style={{ width: "100%", marginTop: 16 }}
          onClick={submit}
          disabled={busy}
        >
          {busy ? "···" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <div style={{ marginTop: 14, textAlign: "center" }}>
          <button
            className="link"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
