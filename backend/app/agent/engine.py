"""The agent loop. Streams structured events so the UI can render live progress.

Event types emitted (as SSE `data:` JSON lines):
  - {"type": "text", "content": "..."}            assistant prose
  - {"type": "tool_call", "name", "input"}        agent decided to act
  - {"type": "tool_result", "name", "output"}     result fed back to model
  - {"type": "approval_required", "command", "reason"}  pause for human
  - {"type": "done"}                              loop finished
  - {"type": "error", "message"}
"""
import json
from collections.abc import AsyncGenerator

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.agent.tools import TOOLS, dispatch_tool, ApprovalRequired
from app.models.models import Server

settings = get_settings()

SYSTEM_PROMPT = """You are SSHPilot, an expert Linux systems engineer operating a \
server on the user's behalf via SSH tools.

Principles:
- Investigate before acting. Inspect state with read-only commands first.
- Take the smallest action that accomplishes the goal. Prefer idempotent steps.
- Explain what you find and what you're about to do in plain language.
- Never fabricate command output; rely only on tool results.
- When a task is complete, summarize what changed and any follow-ups.
- If a destructive command is blocked pending approval, explain the risk and \
wait — do not try to work around the approval gate.

You are operating on a real server. Be careful and precise."""


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _truncate_output(text: str, limit: int = 6000) -> str:
    """Keep head + tail so long command output is still useful."""
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2) :]
    return f"{head}\n\n... [truncated {len(text) - limit} chars] ...\n\n{tail}"


class Agent:
    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(
        self,
        messages: list[dict],
        server: Server,
        auto_approve: bool = False,
    ) -> AsyncGenerator[tuple[str, dict | None], None]:
        """Run the loop. Yields (sse_string, audit_meta_or_None).

        `messages` is the running Anthropic-format conversation; the caller
        persists user/assistant text separately.
        """
        for step in range(settings.agent_max_steps):
            try:
                resp = await self.client.messages.create(
                    model=settings.agent_model,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )
            except Exception as e:  # noqa: BLE001
                yield _sse({"type": "error", "message": str(e)}), None
                return

            assistant_content: list[dict] = []
            tool_uses: list[dict] = []

            for block in resp.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    yield _sse({"type": "text", "content": block.text}), None
                elif block.type == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                    yield _sse(
                        {"type": "tool_call", "name": block.name, "input": block.input}
                    ), None

            messages.append({"role": "assistant", "content": assistant_content})

            if not tool_uses:
                yield _sse({"type": "done"}), None
                return

            tool_results = []
            for tu in tool_uses:
                try:
                    output, meta = await dispatch_tool(
                        tu.name, tu.input, server, auto_approve
                    )
                    display = _truncate_output(output, 4000)
                    yield _sse(
                        {"type": "tool_result", "name": tu.name, "output": display}
                    ), meta
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": _truncate_output(output, 8000),
                        }
                    )
                except ApprovalRequired as ar:
                    yield _sse(
                        {
                            "type": "approval_required",
                            "command": ar.command,
                            "reason": ar.reason,
                            "tool_use_id": tu.id,
                        }
                    ), None
                    # Stop the loop; the client re-invokes with auto_approve to proceed.
                    return

            messages.append({"role": "user", "content": tool_results})

        yield _sse(
            {
                "type": "error",
                "message": f"Max agent steps ({settings.agent_max_steps}) reached. Task may be incomplete.",
            }
        ), None


agent = Agent()
