import { useEffect, useRef, useState } from "react";
import { api, streamAgentChat } from "../api";

export default function ChatPane({ server }) {
  const [sessionId, setSessionId] = useState(null);
  const [items, setItems] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingApproval, setPendingApproval] = useState(null);
  const logRef = useRef(null);

  useEffect(() => {
    if (!server) return;
    setItems([]);
    setPendingApproval(null);
    api.createSession(server.id, `Ops: ${server.name}`).then((s) => setSessionId(s.id));
  }, [server]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [items]);

  function push(item) {
    setItems((prev) => [...prev, item]);
  }

  function appendAssistantText(text) {
    setItems((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.kind === "assistant") {
        const copy = [...prev];
        copy[copy.length - 1] = { ...last, text: last.text + text };
        return copy;
      }
      return [...prev, { kind: "assistant", text }];
    });
  }

  async function runAgent(message, autoApprove = false) {
    setBusy(true);
    setPendingApproval(null);
    await streamAgentChat(
      { session_id: sessionId, message, auto_approve: autoApprove },
      (evt) => {
        if (evt.type === "text") appendAssistantText(evt.content);
        else if (evt.type === "tool_call")
          push({ kind: "tool_call", name: evt.name, input: evt.input });
        else if (evt.type === "tool_result")
          push({ kind: "tool_result", name: evt.name, output: evt.output });
        else if (evt.type === "approval_required")
          setPendingApproval({ command: evt.command, reason: evt.reason });
        else if (evt.type === "error") push({ kind: "error", message: evt.message });
      }
    );
    setBusy(false);
  }

  async function send() {
    if (!input.trim() || !sessionId || busy) return;
    const message = input.trim();
    push({ kind: "user", text: message });
    setInput("");
    await runAgent(message, false);
  }

  async function approve() {
    push({ kind: "user", text: "✓ Approved — proceed." });
    await runAgent("Approved. Proceed with the action.", true);
  }

  return (
    <div className="pane chat-pane">
      <div className="pane-head">
        <span className="pill">AI Agent</span>
        <span style={{ color: "var(--ink-dim)", fontSize: 12 }}>
          operating {server?.username}@{server?.host}
        </span>
      </div>

      <div className="chat-log" ref={logRef}>
        {items.length === 0 && (
          <div style={{ color: "var(--ink-dim)", fontSize: 13, lineHeight: 1.6 }}>
            Ask the agent to operate this server. Try:
            <br />· "What's using the most disk space?"
            <br />· "Install nginx and start it"
            <br />· "Show me the last 20 lines of syslog"
            <br />
            Destructive commands pause for your approval.
          </div>
        )}

        {items.map((it, i) => {
          if (it.kind === "user" || it.kind === "assistant")
            return (
              <div className={`msg ${it.kind}`} key={i}>
                <div className="who">{it.kind === "user" ? "You" : "Agent"}</div>
                <div className="body">{it.text}</div>
              </div>
            );
          if (it.kind === "tool_call")
            return (
              <div className="tool-card" key={i}>
                <div className="t-name">⚙ {it.name}</div>
                <pre className="cmd">
                  {it.input.command || it.input.path || JSON.stringify(it.input)}
                </pre>
              </div>
            );
          if (it.kind === "tool_result")
            return (
              <div className="tool-card" key={i}>
                <div className="t-name">← output</div>
                <pre>{it.output}</pre>
              </div>
            );
          if (it.kind === "error")
            return (
              <div className="msg" key={i} style={{ color: "var(--red)" }}>
                <div className="who">Error</div>
                <div className="body">{it.message}</div>
              </div>
            );
          return null;
        })}

        {pendingApproval && (
          <div className="approval" style={{ border: "2px solid #e74c3c", background: "#fff5f5" }}>
            <div className="h" style={{ color: "#c0392b", fontWeight: "bold" }}>
              ⚠ Approval required — {pendingApproval.reason}
            </div>
            <pre style={{ background: "#2c3e50", color: "#ecf0f1", padding: "10px", borderRadius: "4px" }}>
              {pendingApproval.command}
            </pre>
            <div className="actions" style={{ marginTop: "10px" }}>
              <button className="primary" onClick={approve}>
                Approve & run
              </button>
              <button
                className="danger"
                onClick={() => {
                  setPendingApproval(null);
                  push({ kind: "user", text: "✗ Declined." });
                }}
              >
                Decline
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="chat-input-row">
        <textarea
          value={input}
          placeholder={busy ? "Agent is working…" : "Tell the agent what to do…"}
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="primary" onClick={send} disabled={busy || !sessionId}>
          {busy ? "···" : "Send"}
        </button>
      </div>
    </div>
  );
}
