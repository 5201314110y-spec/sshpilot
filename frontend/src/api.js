// Thin API client. Token stored in module memory + restored from sessionStorage.
let token = sessionStorage.getItem("sshpilot_token") || "";

export function setToken(t) {
  token = t;
  if (t) sessionStorage.setItem("sshpilot_token", t);
  else sessionStorage.removeItem("sshpilot_token");
}
export function getToken() {
  return token;
}

async function req(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = new URLSearchParams(form);
  } else if (body) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  register: (email, password) => req("/auth/register", { method: "POST", body: { email, password } }),
  login: (email, password) => req("/auth/login", { method: "POST", form: { username: email, password } }),
  listServers: () => req("/servers"),
  createServer: (data) => req("/servers", { method: "POST", body: data }),
  updateServer: (id, data) => req(`/servers/${id}`, { method: "PATCH", body: data }),
  testServer: (id) => req(`/servers/${id}/test`, { method: "POST" }),
  verifyHostKey: (id) => req(`/servers/${id}/verify-host-key`, { method: "POST" }),
  deleteServer: (id) => req(`/servers/${id}`, { method: "DELETE" }),
  listSessions: () => req("/sessions"),
  createSession: (server_id, title) => req("/sessions", { method: "POST", body: { server_id, title } }),
  getMessages: (id) => req(`/sessions/${id}/messages`),
  settingsStatus: () => req("/settings/status"),
  updateSettings: (data) => req("/settings/status", { method: "POST", body: data }),
};

// Streaming agent chat via fetch + ReadableStream (SSE-style).
export async function streamAgentChat({ session_id, message, auto_approve }, onEvent) {
  const res = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ session_id, message, auto_approve }),
  });
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      const line = p.trim();
      if (line.startsWith("data:")) {
        try {
          onEvent(JSON.parse(line.slice(5).trim()));
        } catch {
          /* ignore malformed frame */
        }
      }
    }
  }
}
