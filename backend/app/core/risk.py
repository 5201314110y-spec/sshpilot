"""Classifies shell commands by risk so the agent can gate destructive actions.

Improved version: command parsing + path blacklisting + pattern matching.
Intentionally conservative — when in doubt, escalate.
"""
import re
import shlex
from enum import Enum
from typing import Iterable


class RiskLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


# Paths that are almost never safe to modify recursively or destructively
_CRITICAL_PATHS = {
    "/",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/lib",
    "/lib64",
    "/proc",
    "/sys",
    "/dev",
    "/root",
    "/home",
}

_DANGEROUS_COMMANDS = {
    "rm", "dd", "mkfs", "mkfs.ext4", "mkfs.xfs", "fdisk", "parted",
    "shutdown", "reboot", "halt", "poweroff",
    "userdel", "deluser", "passwd",
}

_DANGEROUS_PATTERNS = [
    (re.compile(r"\brm\s+.*(-rf|-fr|--recursive|--force)\b"), "Recursive force delete"),
    (re.compile(r"\bdd\b.*\bof=/dev/"), "Raw write to block device"),
    (re.compile(r">\s*/dev/sd[a-z]"), "Overwriting disk device"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff|init\s+[06])\b"), "Power state change"),
    (re.compile(r":\(\)\s*\{.*\};\s*:"), "Fork bomb"),
    (re.compile(r"\bchmod\s+(-R\s+)?(0?777|a\+rwx)\b"), "World-writable permissions"),
    (re.compile(r"\bchown\s+-R\b"), "Recursive ownership change"),
    (re.compile(r"\b(curl|wget)\b.*\|\s*(sudo\s+)?(bash|sh|zsh)\b"), "Piping remote script to shell"),
    (re.compile(r"\bgit\s+push\s+(-f|--force)\b"), "Force push"),
    (re.compile(r"\b(drop|truncate)\s+(database|table)\b", re.I), "Destructive SQL"),
    (re.compile(r"\bdocker\s+(system\s+prune|rm\s+-f|volume\s+rm)\b"), "Docker destructive op"),
    (re.compile(r"\bkubectl\s+delete\b"), "Kubernetes delete"),
    (re.compile(r"\biptables\s+(-F|--flush)\b"), "Flushing firewall"),
    (re.compile(r"\bsudo\s+(rm|dd|mkfs|chmod|chown|userdel)\b"), "Privileged destructive"),
]

_CAUTION_PATTERNS = [
    re.compile(r"\b(apt|apt-get|yum|dnf|brew|pip|npm|pnpm|yarn)\s+(install|remove|update|upgrade)\b"),
    re.compile(r"\bsystemctl\s+(start|stop|restart|reload|enable|disable)\b"),
    re.compile(r"\b(mkdir|touch|cp|mv|ln)\b"),
    re.compile(r"\bgit\s+(commit|merge|pull|checkout|reset|clean)\b"),
    re.compile(r"\bdocker\s+(run|build|stop|start|exec)\b"),
    re.compile(r">\s*\S+"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bkill\b|\bpkill\b"),
]


def _normalize_path(path: str) -> str:
    """Basic path normalization for risk checking."""
    path = path.strip().rstrip("/") or "/"
    path = re.sub(r"/+", "/", path)
    return path


def _is_critical_path(path: str) -> bool:
    norm = _normalize_path(path)
    if norm in _CRITICAL_PATHS:
        return True
    for crit in _CRITICAL_PATHS:
        if norm == crit or norm.startswith(crit + "/"):
            return True
    return False


def _extract_paths(args: Iterable[str]) -> list[str]:
    """Extract potential path arguments from a command's args."""
    paths = []
    for arg in args:
        if arg.startswith("-") or arg.startswith("--"):
            continue
        if "/" in arg or arg in (".", "..", "~"):
            paths.append(arg)
    return paths


def classify_command(command: str) -> tuple[RiskLevel, str]:
    """Return (risk_level, reason)."""
    cmd = command.strip()
    if not cmd:
        return RiskLevel.SAFE, "empty"

    for pat, why in _DANGEROUS_PATTERNS:
        if pat.search(cmd):
            return RiskLevel.DANGEROUS, why

    segments = re.split(r"&&|\|\||;|\|\s*", cmd)
    highest = RiskLevel.SAFE
    reason = "read-only or informational"

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        try:
            tokens = shlex.split(seg)
        except ValueError:
            tokens = seg.split()

        if not tokens:
            continue

        base_cmd = tokens[0].split("/")[-1]

        if base_cmd in _DANGEROUS_COMMANDS:
            paths = _extract_paths(tokens[1:])
            for p in paths:
                if _is_critical_path(p):
                    return RiskLevel.DANGEROUS, f"{base_cmd} on critical path: {p}"
            if highest == RiskLevel.SAFE:
                highest = RiskLevel.CAUTION
                reason = f"potentially destructive command: {base_cmd}"

        for pat, why in _DANGEROUS_PATTERNS:
            if pat.search(seg):
                return RiskLevel.DANGEROUS, why

        for pat in _CAUTION_PATTERNS:
            if pat.search(seg):
                if highest == RiskLevel.SAFE:
                    highest = RiskLevel.CAUTION
                    reason = "modifies system state"

    return highest, reason
