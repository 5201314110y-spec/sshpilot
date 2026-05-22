"""Runtime settings API — lets the user configure their Anthropic key in-app.

This is what makes the packaged .exe usable without editing files: on first
launch the UI detects setup is needed and prompts for the key.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.config import get_settings, save_runtime
from app.models.models import User

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsStatus(BaseModel):
    configured: bool
    agent_model: str


class SettingsUpdate(BaseModel):
    anthropic_api_key: str | None = None
    agent_model: str | None = None


@router.get("/status", response_model=SettingsStatus)
async def status():
    """Public: tells the UI whether an API key is configured yet."""
    s = get_settings()
    return SettingsStatus(
        configured=bool(s.anthropic_api_key),
        agent_model=s.agent_model,
    )


@router.post("/status", response_model=SettingsStatus)
async def update(
    payload: SettingsUpdate, user: User = Depends(get_current_user)
):
    save_runtime(
        {
            "anthropic_api_key": payload.anthropic_api_key,
            "agent_model": payload.agent_model,
        }
    )
    s = get_settings()
    return SettingsStatus(configured=bool(s.anthropic_api_key), agent_model=s.agent_model)
