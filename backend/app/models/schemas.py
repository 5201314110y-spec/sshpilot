"""Pydantic schemas for the REST API."""
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


# ---- Auth ----
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Servers ----
class ServerCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    auth_method: str  # "password" | "key"
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    host: str
    port: int
    username: str
    auth_method: str
    created_at: datetime


# ---- Sessions / chat ----
class SessionCreate(BaseModel):
    server_id: int
    title: str | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    server_id: int
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    created_at: datetime


class AgentChatRequest(BaseModel):
    session_id: int
    message: str
    # Auto-approve dangerous commands? Default false (human-in-the-loop).
    auto_approve: bool = False
