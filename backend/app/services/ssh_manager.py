"""SSH service: manages connections, runs commands, streams PTY sessions.

Connections are pooled per server id so repeated agent calls reuse one TCP/SSH
session. PTY sessions (interactive terminal) are tracked separately.
"""
import asyncio
import hashlib
from dataclasses import dataclass

import asyncssh

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models.models import Server

settings = get_settings()


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


class HostKeyMismatchError(Exception):
    """Raised when the server's host key does not match the stored fingerprint."""
    pass


class SSHManager:
    def __init__(self) -> None:
        self._conns: dict[int, asyncssh.SSHClientConnection] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, server_id: int) -> asyncio.Lock:
        return self._locks.setdefault(server_id, asyncio.Lock())

    def _fingerprint(self, key_data: bytes) -> str:
        """SHA256 fingerprint of a host key (colon-separated hex)."""
        digest = hashlib.sha256(key_data).digest()
        return ":".join(f"{b:02x}" for b in digest)

    async def _verify_host_key(self, server: Server, conn: asyncssh.SSHClientConnection) -> None:
        """If the server has a verified host key, reject on mismatch."""
        if not server.host_key_verified or not server.host_key_fingerprint:
            return

        if not hasattr(conn, "get_server_host_key"):
            return

        host_key = conn.get_server_host_key()
        if not host_key:
            raise HostKeyMismatchError("Could not retrieve host key from server")

        current_fp = self._fingerprint(host_key.public_data)
        if current_fp != server.host_key_fingerprint:
            raise HostKeyMismatchError(
                f"Host key mismatch! Expected {server.host_key_fingerprint}, "
                f"got {current_fp}. Possible MITM attack."
            )

    async def _build_conn(self, server: Server) -> asyncssh.SSHClientConnection:
        kwargs: dict = {
            "host": server.host,
            "port": server.port,
            "username": server.username,
            "connect_timeout": settings.ssh_connect_timeout,
            "known_hosts": None,
        }

        if server.auth_method == "password":
            kwargs["password"] = decrypt_secret(server.encrypted_password)
        else:
            key_data = decrypt_secret(server.encrypted_private_key)
            passphrase = decrypt_secret(server.encrypted_passphrase) or None
            kwargs["client_keys"] = [
                asyncssh.import_private_key(key_data, passphrase=passphrase)
            ]

        conn = await asyncssh.connect(**kwargs)
        # Enforce verification after connection is established
        await self._verify_host_key(server, conn)
        return conn

    async def get_connection(
        self, server: Server
    ) -> asyncssh.SSHClientConnection:
        async with self._lock(server.id):
            conn = self._conns.get(server.id)
            if conn is None or conn.is_closed():
                conn = await self._build_conn(server)
                self._conns[server.id] = conn
            return conn

    async def capture_host_key(self, server: Server) -> tuple[str, str] | None:
        """Connect once and return (key_type, fingerprint) if possible."""
        try:
            # Use a temporary connection that skips verification for capture
            kwargs: dict = {
                "host": server.host,
                "port": server.port,
                "username": server.username,
                "connect_timeout": settings.ssh_connect_timeout,
                "known_hosts": None,
            }
            if server.auth_method == "password":
                kwargs["password"] = decrypt_secret(server.encrypted_password)
            else:
                key_data = decrypt_secret(server.encrypted_private_key)
                passphrase = decrypt_secret(server.encrypted_passphrase) or None
                kwargs["client_keys"] = [
                    asyncssh.import_private_key(key_data, passphrase=passphrase)
                ]

            conn = await asyncssh.connect(**kwargs)
            if hasattr(conn, "get_server_host_key"):
                host_key = conn.get_server_host_key()
                if host_key:
                    key_type = host_key.algorithm or "unknown"
                    fp = self._fingerprint(host_key.public_data)
                    conn.close()
                    await conn.wait_closed()
                    return key_type, fp
            conn.close()
            await conn.wait_closed()
        except Exception:
            pass
        return None

    async def run(self, server: Server, command: str) -> ExecResult:
        try:
            conn = await self.get_connection(server)
            result = await asyncio.wait_for(
                conn.run(command, check=False),
                timeout=settings.command_timeout,
            )
            return ExecResult(
                exit_code=result.exit_status or 0,
                stdout=str(result.stdout or ""),
                stderr=str(result.stderr or ""),
            )
        except HostKeyMismatchError as e:
            return ExecResult(255, "", f"Host key verification failed: {e}")
        except asyncio.TimeoutError:
            return ExecResult(124, "", f"Command timed out after {settings.command_timeout}s")

    async def read_file(self, server: Server, path: str, max_bytes: int = 100_000) -> str:
        conn = await self.get_connection(server)
        async with conn.start_sftp_client() as sftp:
            async with sftp.open(path, "r") as f:
                return await f.read(max_bytes)

    async def write_file(self, server: Server, path: str, content: str) -> None:
        conn = await self.get_connection(server)
        async with conn.start_sftp_client() as sftp:
            async with sftp.open(path, "w") as f:
                await f.write(content)

    async def test_connection(self, server: Server) -> tuple[bool, str, dict]:
        """Returns (ok, detail, extra) where extra may contain host_key info."""
        extra: dict = {}
        try:
            if not server.host_key_verified:
                captured = await self.capture_host_key(server)
                if captured:
                    extra["host_key_type"] = captured[0]
                    extra["host_key_fingerprint"] = captured[1]

            result = await self.run(server, "echo ok && hostname")
            if result.exit_code == 0:
                return True, result.stdout.strip(), extra
            return False, result.stderr.strip() or "non-zero exit", extra
        except HostKeyMismatchError as e:
            return False, str(e), extra
        except Exception as e:  # noqa: BLE001
            return False, str(e), extra

    async def close(self, server_id: int) -> None:
        conn = self._conns.pop(server_id, None)
        if conn and not conn.is_closed():
            conn.close()
            await conn.wait_closed()

    async def close_all(self) -> None:
        for sid in list(self._conns):
            await self.close(sid)


# Singleton used across the app.
ssh_manager = SSHManager()
