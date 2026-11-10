"""Server connection CRUD. Credentials are encrypted before persistence."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import encrypt_secret
from app.models.models import Server, User
from app.models.schemas import ServerCreate, ServerOut, ServerUpdate
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
        command_whitelist=payload.command_whitelist or "",
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


@router.patch("/{server_id}", response_model=ServerOut)
async def update_server(
    server_id: int,
    payload: ServerUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    server = await _get_owned(server_id, user, db)
    if payload.command_whitelist is not None:
        server.command_whitelist = payload.command_whitelist
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
    ok, detail, extra = await ssh_manager.test_connection(server)

    # Persist captured host key if we got one and it wasn't verified yet
    if extra.get("host_key_fingerprint") and not server.host_key_verified:
        server.host_key_type = extra.get("host_key_type")
        server.host_key_fingerprint = extra["host_key_fingerprint"]
        await db.commit()
        await db.refresh(server)

    return {"ok": ok, "detail": detail, "host_key": extra}


@router.post("/{server_id}/verify-host-key")
async def verify_host_key(
    server_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark the currently stored host key as verified (user confirmed)."""
    server = await _get_owned(server_id, user, db)
    if not server.host_key_fingerprint:
        raise HTTPException(status_code=400, detail="No host key captured yet. Run /test first.")
    server.host_key_verified = True
    await db.commit()
    return {"ok": True, "fingerprint": server.host_key_fingerprint}


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
