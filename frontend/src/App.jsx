import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import Auth from "./components/Auth";
import TerminalPane from "./components/TerminalPane";
import ChatPane from "./components/ChatPane";
import AddServerModal from "./components/AddServerModal";
import SetupModal from "./components/SetupModal";

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [needsSetup, setNeedsSetup] = useState(false);
  const [servers, setServers] = useState([]);
  const [active, setActive] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [status, setStatus] = useState({}); // serverId -> "up"|"down"

  async function loadServers() {
    const list = await api.listServers();
    setServers(list);
    if (!active && list.length) setActive(list[0]);
  }

  async function checkSetup() {
    try {
      const s = await api.settingsStatus();
      setNeedsSetup(!s.configured);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (authed) {
      loadServers();
      checkSetup();
    }
  }, [authed]);

  async function testConn(s, e) {
    e?.stopPropagation();
    setStatus((p) => ({ ...p, [s.id]: "testing" }));
    const r = await api.testServer(s.id);
    setStatus((p) => ({ ...p, [s.id]: r.ok ? "up" : "down" }));
  }

  function logout() {
    setToken("");
    setAuthed(false);
    setServers([]);
    setActive(null);
  }

  if (!authed) return <Auth onAuthed={() => setAuthed(true)} />;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <h1>
            SSHPilot<span className="blink">_</span>
          </h1>
          <div className="tag">agentic terminal</div>
        </div>
        <div className="srv-list">
          <div className="section-h">
            <span className="label" style={{ margin: 0 }}>
              Servers
            </span>
            <button style={{ padding: "3px 9px" }} onClick={() => setShowAdd(true)}>
              + add
            </button>
          </div>
          {servers.map((s) => (
            <div
              key={s.id}
              className={`srv-item ${active?.id === s.id ? "active" : ""}`}
              onClick={() => setActive(s)}
            >
              <div className="name">
                <span className={`dot ${status[s.id] || ""}`} />
                {s.name}
              </div>
              <div className="host">
                {s.username}@{s.host}:{s.port}
              </div>
              <div style={{ marginTop: 7, display: "flex", gap: 6 }}>
                <button style={{ padding: "2px 8px", fontSize: 11 }} onClick={(e) => testConn(s, e)}>
                  {status[s.id] === "testing" ? "…" : "test"}
                </button>
                <button
                  className="danger"
                  style={{ padding: "2px 8px", fontSize: 11 }}
                  onClick={async (e) => {
                    e.stopPropagation();
                    await api.deleteServer(s.id);
                    if (active?.id === s.id) setActive(null);
                    loadServers();
                  }}
                >
                  del
                </button>
              </div>
            </div>
          ))}
          {servers.length === 0 && (
            <div style={{ color: "var(--ink-dim)", fontSize: 12, padding: "8px 4px" }}>
              No servers yet. Add one to begin.
            </div>
          )}
        </div>
        <div style={{ padding: 12, borderTop: "1px solid var(--border)" }}>
          <button style={{ width: "100%" }} onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        {active ? (
          <div className="workspace">
            <div className="pane term-pane">
              <div className="pane-head">
                <span className="pill">Terminal</span>
                <span style={{ color: "var(--ink-dim)", fontSize: 12 }}>{active.name}</span>
              </div>
              <TerminalPane serverId={active.id} key={active.id} />
            </div>
            <ChatPane server={active} key={`chat-${active.id}`} />
          </div>
        ) : (
          <div className="empty">
            <div className="big">No server selected</div>
            <div>Add or select a server from the sidebar.</div>
          </div>
        )}
      </main>

      {showAdd && (
        <AddServerModal
          onClose={() => setShowAdd(false)}
          onCreated={(s) => {
            setShowAdd(false);
            setServers((p) => [...p, s]);
            setActive(s);
          }}
        />
      )}

      {needsSetup && <SetupModal onDone={() => setNeedsSetup(false)} />}
    </div>
  );
}
