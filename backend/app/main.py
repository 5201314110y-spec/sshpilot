"""SSHPilot backend entrypoint."""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings, ensure_encryption_key
from app.core.database import init_db
from app.services.ssh_manager import ssh_manager
from app.api import auth, servers, agent, terminal, settings as settings_api

settings = get_settings()


def resource_dir() -> Path:
    """Locate bundled resources whether running from source or a PyInstaller exe."""
    if getattr(sys, "frozen", False):  # running inside a PyInstaller bundle
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent  # backend/


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_encryption_key()
    await init_db()
    yield
    await ssh_manager.close_all()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(servers.router)
app.include_router(agent.router)
app.include_router(terminal.router)
app.include_router(settings_api.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


# ---- Static frontend (bundled build) ----
# The built Vite app is copied to backend/static during the build step.
_static = resource_dir() / "static"
if _static.is_dir():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(_static / "index.html")

    # SPA fallback: any non-API, non-WS path returns index.html so the
    # client-side app can route it.
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = _static / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
