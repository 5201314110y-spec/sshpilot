"""Server connection CRUD. Credentials are encrypted before persistence."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import encrypt_secret
from app.models.models import Server, User
from app.models.schemas import ServerCreate, ServerOut
from app.services.ssh_manager import ssh_manager

router = APIRouter(prefix="/api/servers", tags=["servers"])


async def _get_owned(server_id: int, user: User, db: AsyncSession) -> Server:
    server = (
        await db.execute(
            select(Server).where(Server.id == server_id, Server.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.get("", response_model=list[ServerOut])
async def list_servers(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(select(Server).where(Server.owner_id == user.id))
    ).scalars().all()
    return rows


@router.post("", response_model=ServerOut)
async def create_server(
    payload: ServerCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = Server(
        owner_id=user.id,
        name=payload.name,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        auth_method=payload.auth_method,
        encrypted_password=encrypt_secret(payload.password or ""),
        encrypted_private_key=encrypt_secret(payload.private_key or ""),
        encrypted_passphrase=encrypt_secret(payload.passphrase or ""),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


@router.post("/{server_id}/test")
async def test_server(
    server_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await _get_owned(server_id, user, db)
    ok, detail = await ssh_manager.test_connection(server)
    return {"ok": ok, "detail": detail}


@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await _get_owned(server_id, user, db)
    await ssh_manager.close(server.id)
    await db.delete(server)
    await db.commit()
    return {"ok": True}
