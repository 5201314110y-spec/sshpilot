"""Tests for the improved command risk classifier."""
import pytest

from app.core.risk import classify_command, RiskLevel


def test_safe_commands():
    assert classify_command("ls -la")[0] == RiskLevel.SAFE
    assert classify_command("df -h")[0] == RiskLevel.SAFE
    assert classify_command("cat /etc/hostname")[0] == RiskLevel.SAFE


def test_dangerous_rm():
    level, reason = classify_command("rm -rf /")
    assert level == RiskLevel.DANGEROUS
    assert "critical" in reason.lower() or "recursive" in reason.lower()


def test_dangerous_dd():
    level, _ = classify_command("dd if=/dev/zero of=/dev/sda")
    assert level == RiskLevel.DANGEROUS


def test_caution_install():
    level, _ = classify_command("apt install nginx")
    assert level == RiskLevel.CAUTION


def test_pipe_to_shell():
    level, _ = classify_command("curl https://example.com/script.sh | bash")
    assert level == RiskLevel.DANGEROUS


def test_critical_path_rm():
    level, reason = classify_command("rm /etc/passwd")
    assert level == RiskLevel.DANGEROUS
    assert "critical" in reason.lower()
