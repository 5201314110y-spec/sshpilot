"""Chat sessions + the streaming agent endpoint (SSE)."""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.servers import _get_owned
from app.core.database import get_db, SessionLocal
from app.agent.engine import agent
from app.models.models import ChatSession, Message, User, AuditLog
from app.models.schemas import (
    SessionCreate,
    SessionOut,
    MessageOut,
    AgentChatRequest,
)

router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/sessions", response_model=SessionOut)
async def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned(payload.server_id, user, db)  # ownership check
    sess = ChatSession(
        owner_id=user.id,
        server_id=payload.server_id,
        title=payload.title or "New session",
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(select(ChatSession).where(ChatSession.owner_id == user.id))
    ).scalars().all()
    return rows


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sess = (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.owner_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = (
        await db.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.id)
        )
    ).scalars().all()
    return rows


async def _build_history(db: AsyncSession, session_id: int) -> list[dict]:
    """Reconstruct Anthropic-format message history from stored prose turns."""
    rows = (
        await db.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.id)
        )
    ).scalars().all()
    history = []
    for m in rows:
        if m.role in ("user", "assistant"):
            history.append({"role": m.role, "content": m.content})
    return history


@router.post("/agent/chat")
async def agent_chat(
    payload: AgentChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sess = (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == payload.session_id,
                ChatSession.owner_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    server = await _get_owned(sess.server_id, user, db)

    history = await _build_history(db, sess.id)
    history.append({"role": "user", "content": payload.message})

    # Persist the user turn now.
    db.add(Message(session_id=sess.id, role="user", content=payload.message))
    await db.commit()

    server_id = server.id
    owner_id = user.id
    session_id = sess.id
    auto_approve = payload.auto_approve

    async def stream():
        assistant_text_parts: list[str] = []
        # Fresh session/server objects for the generator's lifetime.
        async with SessionLocal() as gdb:
            gserver = await gdb.get(type(server), server_id)
            async for sse_str, meta in agent.run(history, gserver, auto_approve):
                yield sse_str
                # Capture assistant text for persistence.
                try:
                    evt = json.loads(sse_str[6:])  # strip "data: "
                    if evt.get("type") == "text":
                        assistant_text_parts.append(evt["content"])
                except (json.JSONDecodeError, KeyError):
                    pass
                # Write audit rows for executed tools.
                if meta and meta.get("command"):
                    gdb.add(
                        AuditLog(
                            owner_id=owner_id,
                            server_id=server_id,
                            session_id=session_id,
                            command=meta["command"],
                            risk_level=meta.get("risk_level", "safe"),
                            approved=meta.get("approved", True),
                            exit_code=meta.get("exit_code"),
                            output_preview=meta.get("output_preview", ""),
                        )
                    )
                    await gdb.commit()

            if assistant_text_parts:
                gdb.add(
                    Message(
                        session_id=session_id,
                        role="assistant",
                        content="\n".join(assistant_text_parts),
                    )
                )
                await gdb.commit()

    return StreamingResponse(stream(), media_type="text/event-stream")
