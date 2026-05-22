"""WebSocket gateway streaming an interactive PTY between browser and server.

Protocol (JSON text frames from client):
  {"type": "input", "data": "ls -la\r"}
  {"type": "resize", "cols": 120, "rows": 30}
Server → client frames:
  {"type": "output", "data": "..."}
  {"type": "status", "data": "connected"|"closed"|"error: ..."}
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import decode_token
from app.models.models import Server, User
from app.services.ssh_manager import ssh_manager

router = APIRouter()


@router.websocket("/ws/terminal/{server_id}")
async def terminal_ws(websocket: WebSocket, server_id: int, token: str = ""):
    await websocket.accept()

    # Auth via query param token (WS can't use Authorization header easily).
    email = decode_token(token)
    if not email:
        await websocket.send_text(json.dumps({"type": "status", "data": "error: unauthorized"}))
        await websocket.close()
        return

    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        server = (
            await db.execute(
                select(Server).where(
                    Server.id == server_id, Server.owner_id == user.id if user else -1
                )
            )
        ).scalar_one_or_none()

    if not server:
        await websocket.send_text(json.dumps({"type": "status", "data": "error: server not found"}))
        await websocket.close()
        return

    try:
        conn = await ssh_manager.get_connection(server)
        proc = await conn.create_process(term_type="xterm-256color", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        await websocket.send_text(json.dumps({"type": "status", "data": f"error: {e}"}))
        await websocket.close()
        return

    await websocket.send_text(json.dumps({"type": "status", "data": "connected"}))

    async def pump_output():
        try:
            async for chunk in proc.stdout:
                await websocket.send_text(json.dumps({"type": "output", "data": chunk}))
        except Exception:  # noqa: BLE001
            pass

    out_task = asyncio.create_task(pump_output())

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg["type"] == "input":
                proc.stdin.write(msg["data"])
            elif msg["type"] == "resize":
                proc.change_terminal_size(msg["cols"], msg["rows"])
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        out_task.cancel()
        proc.close()
        try:
            await websocket.send_text(json.dumps({"type": "status", "data": "closed"}))
        except Exception:  # noqa: BLE001
            pass
