"""ORM models. Credentials are stored encrypted (see core.security)."""
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, Integer, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    servers: Mapped[list["Server"]] = relationship(back_populates="owner")


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(120))
    auth_method: Mapped[str] = mapped_column(String(20))  # "password" | "key"
    # Encrypted at rest:
    encrypted_password: Mapped[str] = mapped_column(Text, default="")
    encrypted_private_key: Mapped[str] = mapped_column(Text, default="")
    encrypted_passphrase: Mapped[str] = mapped_column(Text, default="")
    # Host key verification (TOFU)
    host_key_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    host_key_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    host_key_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped["User"] = relationship(back_populates="servers")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New session")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class AuditLog(Base):
    """Every command the agent runs is recorded here — non-negotiable for trust."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(nullable=True)
    command: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(20))
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    output_preview: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
