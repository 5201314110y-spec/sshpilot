# SSHPilot

An agentic SSH client. Connect to your servers, get a live terminal, and let an
AI agent (Claude) operate the box for you — with a human-in-the-loop approval
gate on anything destructive.

```
┌──────────── Browser ────────────┐
│  Terminal (xterm)  │  AI Agent   │
└─────────┬──────────┴──────┬──────┘
       WS │ PTY       SSE/HTTP │ agent loop
┌─────────▼──────────────────▼──────┐
│            FastAPI backend         │
│  WS gateway · agent engine · REST  │
│  ┌──────────────────────────────┐  │
│  │  SSH manager (asyncssh)       │  │
│  │  risk classifier + approval   │  │
│  └──────────────────────────────┘  │
└──────┬───────────────────┬─────────┘
   SQLite              Anthropic API
 (encrypted creds)       (Claude)
        │
   Target servers (SSH/SFTP)
```

## Why it's built this way

- **Agent = ReAct loop with tools.** The LLM is given three tools
  (`run_command`, `read_file`, `write_file`) and reasons step-by-step, observing
  real output between actions. See `app/agent/`.
- **Safety is a separate layer, not a prompt.** Every command is run through a
  pattern-based risk classifier (`app/core/risk.py`). `DANGEROUS` commands halt
  the loop and require explicit user approval in the UI. The model cannot talk
  its way past the gate.
- **Credentials encrypted at rest** with Fernet (`app/core/security.py`).
- **Everything the agent does is audited** to the `audit_logs` table.

## Project layout

```
sshpilot/
├── backend/
│   ├── launcher.py             # exe entry point: boots server + opens browser
│   ├── sshpilot.spec           # PyInstaller build spec
│   ├── build.bat               # one-command Windows build → dist/SSHPilot.exe
│   ├── app/
│   │   ├── main.py             # FastAPI app + serves bundled frontend
│   │   ├── core/
│   │   │   ├── config.py        # settings + runtime overlay (API key from UI)
│   │   │   ├── security.py      # encryption, hashing, JWT
│   │   │   ├── risk.py          # command risk classifier  ← safety core
│   │   │   └── database.py      # async SQLAlchemy engine
│   │   ├── models/
│   │   │   ├── models.py        # ORM tables
│   │   │   └── schemas.py       # Pydantic request/response
│   │   ├── services/
│   │   │   └── ssh_manager.py   # asyncssh connection pool, exec, sftp
│   │   ├── agent/
│   │   │   ├── tools.py         # tool schema + dispatcher
│   │   │   └── engine.py        # the ReAct loop (SSE streaming)
│   │   └── api/
│   │       ├── deps.py          # auth dependency
│   │       ├── auth.py          # register / login
│   │       ├── servers.py       # server CRUD + test
│   │       ├── agent.py         # sessions + streaming chat
│   │       ├── terminal.py      # WebSocket PTY gateway
│   │       └── settings.py      # in-app API-key configuration
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx              # layout orchestration
    │   ├── api.js               # API client + SSE stream reader
    │   └── components/
    │       ├── Auth.jsx
    │       ├── SetupModal.jsx   # first-run API-key setup
    │       ├── TerminalPane.jsx # xterm ↔ WebSocket
    │       ├── ChatPane.jsx     # agent chat + approval UI
    │       └── AddServerModal.jsx
    ├── package.json
    └── vite.config.js
```

## Get the .exe without a Windows machine (GitHub Actions)

This repo includes a workflow (`.github/workflows/build-windows.yml`) that builds
`SSHPilot.exe` on a cloud Windows runner. You never touch a Windows machine.

**One-time setup:**

1. Create a new repository on GitHub (empty, no README).
2. Push this project to it:
   ```bash
   cd sshpilot
   git init
   git add .
   git commit -m "SSHPilot initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```

**The build runs automatically on push.** To get your exe:

3. Open your repo on GitHub → **Actions** tab → click the latest
   **"Build Windows EXE"** run.
4. When it finishes (green check, ~3–5 min), scroll to **Artifacts** at the
   bottom and download **`SSHPilot-windows`**. Unzip it to get `SSHPilot.exe`.

**Optional — a permanent download link via Releases:** push a version tag and
the workflow attaches the exe to a GitHub Release:
```bash
git tag v0.1.0
git push origin v0.1.0
```
The exe then appears under your repo's **Releases** page as a direct download.

You can also trigger a build manually anytime: **Actions** tab → **Build Windows
EXE** → **Run workflow**.

---

## Build the Windows .exe yourself (one command)

On a **Windows** machine with **Python 3.10+** and **Node.js 18+** installed:

```bat
cd backend
build.bat
```

This builds the frontend, bundles it into the backend, installs dependencies,
and runs PyInstaller. The result is a single file:

```
backend\dist\SSHPilot.exe
```

Double-click `SSHPilot.exe`. It starts a local server, opens your browser, and
shows a console window (close it to quit). On first launch the app asks for your
Anthropic API key, then you register an account and add servers.

All data — the encrypted database, your API key, and the auto-generated
encryption key — is stored in a `sshpilot_data\` folder created **next to the
exe**. Back up or delete that folder to reset the app. Nothing is written to
system locations.

> **Why you build it yourself:** a Windows `.exe` can only be produced on
> Windows (PyInstaller does not cross-compile from Linux/Mac). The repo is
> structured so the single `build.bat` does everything; you don't write any code.

### Run from source (development)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (separate terminal, with hot reload):
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api and /ws to :8000
```

In dev you can also drop a `.env` in `backend/sshpilot_data/` with
`ANTHROPIC_API_KEY=...` instead of using the in-app setup screen.

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create account → JWT |
| POST | `/api/auth/login` | OAuth2 password → JWT |
| GET | `/api/servers` | List your servers |
| POST | `/api/servers` | Add a server (creds encrypted) |
| POST | `/api/servers/{id}/test` | Test SSH connection |
| DELETE | `/api/servers/{id}` | Remove a server |
| POST | `/api/sessions` | Start an agent chat session |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}/messages` | Session history |
| POST | `/api/agent/chat` | Stream agent loop (SSE) |
| WS | `/ws/terminal/{id}?token=` | Interactive PTY |
| GET | `/api/health` | Liveness |

## Production hardening (next steps)

This is an MVP. Before real production use:

1. **Pin SSH host keys** — `known_hosts` is currently `None` (TOFU off). Store
   and verify host keys per server to prevent MITM.
2. **Per-user encryption keys / KMS** — move credential encryption keys into a
   managed KMS or per-user derived keys, not one global key.
3. **Postgres + connection limits** — swap SQLite, add rate limiting and quotas.
4. **Sandbox the agent further** — restrict to allow-listed commands per server,
   add max-blast-radius limits, run agent commands as a deprivileged user.
5. **Audit UI + alerting** — surface `audit_logs`, alert on dangerous approvals.
6. **Refresh tokens + RBAC** — short-lived access tokens, team/role scoping.
7. **Streaming command output** for long-running commands (currently buffered).
```
