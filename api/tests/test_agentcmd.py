"""Tests for the pure jump-to-agent resume-command builder, incl. injection guards."""

from __future__ import annotations

from missioncontrol.agentcmd import resume_command


def test_builds_claude_and_codex_commands() -> None:
    assert resume_command("claude", "abc123") == ["claude", "--resume", "abc123"]
    assert resume_command("codex", "abc123") == ["codex", "resume", "abc123"]


def test_unknown_agent_is_none() -> None:
    assert resume_command("gemini", "abc123") is None


def test_accepts_realistic_session_ids() -> None:
    assert resume_command("claude", "e0e13f5e-012d-5036-adbd-f51f357fa31c") is not None
    assert resume_command("codex", "rollout-2026-06-23.session_01") is not None


def test_rejects_flag_injection_and_shell_metachars() -> None:
    assert resume_command("claude", "--help") is None  # leading hyphen => no flag injection
    assert resume_command("claude", "a; rm -rf /") is None
    assert resume_command("claude", "a/b") is None  # no path separators
    assert resume_command("claude", "$(whoami)") is None
    assert resume_command("claude", "") is None
    assert resume_command("claude", "a" * 129) is None  # too long
