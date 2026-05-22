"""Tool definitions exposed to the LLM, and the dispatcher that executes them.

Tools are intentionally small and composable. The agent composes them to
accomplish higher-level goals. `run_command` is gated by the risk classifier.
"""
from app.core.risk import classify_command, RiskLevel
from app.models.models import Server
from app.services.ssh_manager import ssh_manager

# Anthropic tool schema. Kept minimal & explicit so the model uses them well.
TOOLS = [
    {
        "name": "run_command",
        "description": (
            "Execute a shell command on the connected Linux server and return "
            "stdout, stderr, and exit code. Use for inspection, installation, "
            "service management, etc. Destructive commands require user approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
                "explanation": {
                    "type": "string",
                    "description": "One short sentence on why you are running this.",
                },
            },
            "required": ["command", "explanation"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a text file from the server via SFTP (up to 100KB).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write/overwrite a text file on the server via SFTP. "
            "Treated as a CAUTION-level action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
]


class ApprovalRequired(Exception):
    """Raised when a dangerous command needs human sign-off."""

    def __init__(self, command: str, reason: str):
        self.command = command
        self.reason = reason
        super().__init__(reason)


async def dispatch_tool(
    name: str,
    args: dict,
    server: Server,
    auto_approve: bool = False,
) -> tuple[str, dict]:
    """Run a tool. Returns (text_result_for_llm, metadata_for_audit).

    Raises ApprovalRequired for dangerous run_command when not auto-approved.
    """
    if name == "run_command":
        command = args["command"]
        risk, reason = classify_command(command)
        if risk == RiskLevel.DANGEROUS and not auto_approve:
            raise ApprovalRequired(command, reason)

        result = await ssh_manager.run(server, command)
        combined = result.stdout
        if result.stderr:
            combined += f"\n[stderr]\n{result.stderr}"
        text = (
            f"exit_code={result.exit_code}\n{combined}".strip()
            or f"exit_code={result.exit_code} (no output)"
        )
        meta = {
            "command": command,
            "risk_level": risk.value,
            "exit_code": result.exit_code,
            "output_preview": combined[:500],
            "approved": True,
        }
        return text[:8000], meta

    if name == "read_file":
        try:
            content = await ssh_manager.read_file(server, args["path"])
            return content[:8000], {"command": f"read {args['path']}", "risk_level": "safe"}
        except Exception as e:  # noqa: BLE001
            return f"Error reading file: {e}", {"command": f"read {args['path']}", "risk_level": "safe"}

    if name == "write_file":
        try:
            await ssh_manager.write_file(server, args["path"], args["content"])
            return f"Wrote {len(args['content'])} bytes to {args['path']}", {
                "command": f"write {args['path']}",
                "risk_level": "caution",
            }
        except Exception as e:  # noqa: BLE001
            return f"Error writing file: {e}", {"command": f"write {args['path']}", "risk_level": "caution"}

    return f"Unknown tool: {name}", {"command": name, "risk_level": "safe"}
