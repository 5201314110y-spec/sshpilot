"""Classifies shell commands by risk so the agent can gate destructive actions.

This is intentionally conservative: when in doubt, escalate. The classifier is
pattern-based (fast, no LLM call) and is the last line of defense before a
command runs on a real server.
"""
import re
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"          # read-only / informational, auto-run
    CAUTION = "caution"    # writes state but reversible-ish, auto-run by default
    DANGEROUS = "dangerous"  # destructive / irreversible, REQUIRES approval


# Patterns that should always require explicit human approval.
_DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*(-rf|-fr|-r\s+-f|-f\s+-r)\b"), "Recursive force delete"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*/(\s|$)"), "Deleting root"),
    (re.compile(r"\bmkfs\b"), "Formatting a filesystem"),
    (re.compile(r"\bdd\b.*\bof=/dev/"), "Raw write to a block device"),
    (re.compile(r">\s*/dev/sd[a-z]"), "Overwriting a disk device"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff|init\s+0|init\s+6)\b"), "Power state change"),
    (re.compile(r":\(\)\s*\{.*\};\s*:"), "Fork bomb"),
    (re.compile(r"\bchmod\s+(-R\s+)?(0?777|a\+rwx)\b"), "World-writable permissions"),
    (re.compile(r"\bchown\s+-R\b.*\s/(\s|$)"), "Recursive ownership change on root"),
    (re.compile(r"\b(curl|wget)\b.*\|\s*(sudo\s+)?(bash|sh|zsh)\b"), "Piping remote script to shell"),
    (re.compile(r"\bgit\s+push\s+(-f|--force)\b"), "Force push"),
    (re.compile(r"\b(drop|truncate)\s+(database|table)\b", re.I), "Destructive SQL"),
    (re.compile(r"\bdocker\s+(system\s+prune|rm\s+-f|volume\s+rm)\b"), "Docker destructive op"),
    (re.compile(r"\bkubectl\s+delete\b"), "Kubernetes delete"),
    (re.compile(r"\b>\s*/etc/"), "Overwriting system config"),
    (re.compile(r"\bsudo\s+(rm|dd|mkfs|chmod|chown|userdel|passwd)\b"), "Privileged destructive op"),
    (re.compile(r"\buserdel\b|\bdeluser\b"), "Deleting a user account"),
    (re.compile(r"\biptables\s+(-F|--flush)\b"), "Flushing firewall rules"),
]

# Commands that modify state but are routine; auto-run but flag as caution.
_CAUTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(apt|apt-get|yum|dnf|brew|pip|npm|pnpm|yarn)\s+(install|remove|update|upgrade)\b"),
    re.compile(r"\bsystemctl\s+(start|stop|restart|reload|enable|disable)\b"),
    re.compile(r"\b(mkdir|touch|cp|mv|ln)\b"),
    re.compile(r"\bgit\s+(commit|merge|pull|checkout|reset|clean)\b"),
    re.compile(r"\bdocker\s+(run|build|stop|start|exec)\b"),
    re.compile(r">\s*\S+"),  # output redirection (file write)
    re.compile(r"\bsudo\b"),
    re.compile(r"\bkill\b|\bpkill\b"),
]


def classify_command(command: str) -> tuple[RiskLevel, str]:
    """Return (risk_level, reason). Splits on && ; | to catch chained tricks."""
    cmd = command.strip()
    if not cmd:
        return RiskLevel.SAFE, "empty"

    # Some dangerous patterns span pipes/operators (pipe-to-shell, fork bomb),
    # so check the whole command string first before splitting it apart.
    for pat, why in _DANGEROUS_PATTERNS:
        if pat.search(cmd):
            return RiskLevel.DANGEROUS, why

    # Then evaluate each sub-command of a chain; take the highest risk found.
    segments = re.split(r"&&|\|\||;|\|", cmd)
    highest = RiskLevel.SAFE
    reason = "read-only or informational"

    for seg in segments:
        seg = seg.strip()
        for pat, why in _DANGEROUS_PATTERNS:
            if pat.search(seg):
                return RiskLevel.DANGEROUS, why
        for pat in _CAUTION_PATTERNS:
            if pat.search(seg):
                highest = RiskLevel.CAUTION
                reason = "modifies system state"

    return highest, reason
