"""Isolated credential reader for Claude's remaining-window quota — the ONE place that reads the
Claude OAuth token (I/O + credential seam; omitted from the unit gate).

CLAUDE.md contract: the token is read at call time, held in memory for a single read-only GET, and
the function returns **numbers (the usage JSON), never the token** — nothing is persisted, logged,
or sent to the browser, and every error is swallowed (degrade-never-lie) so a token can never leak
through an exception. Coding agents never run this (the guard hook denies the Keychain /
.credentials.json); only the running app does.

Opt-in only: nothing here executes unless ``MC_ENABLE_CLAUDE_QUOTA=1`` is set, so credential access
is always explicit and the non-invasive default holds. Subprocess hardening (macOS Keychain):
``/usr/bin/security`` by absolute path, fixed argv, no shell; captured output is capped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_BETA = "oauth-2025-04-20"
_TIMEOUT = 5.0
_SECURITY = "/usr/bin/security"  # absolute path, never the bare name
_KEYCHAIN_SERVICE = "Claude Code-credentials"
_CACHE_TTL = 60.0  # be polite to the endpoint: at most one fetch per minute

_cache: dict[str, Any] = {}


def claude_quota_enabled() -> bool:
    """True only when remaining-window quota is explicitly opted in (it reads your OAuth token)."""
    return os.environ.get("MC_ENABLE_CLAUDE_QUOTA") == "1"


def _extract_access_token(raw: str) -> str | None:
    """Pull the access token from the credential blob: JSON {"claudeAiOauth":{"accessToken":…}}."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return raw if raw.startswith("sk-ant-") else None  # a bare token line
    if isinstance(data, dict):
        oauth = data.get("claudeAiOauth")
        if isinstance(oauth, dict) and isinstance(oauth.get("accessToken"), str):
            return str(oauth["accessToken"])
        if isinstance(data.get("accessToken"), str):
            return str(data["accessToken"])
    return None


def _token_from_keychain() -> str | None:
    try:
        proc = subprocess.run(  # noqa: S603  # reason: absolute path, fixed argv, no shell
            [_SECURITY, "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return _extract_access_token(proc.stdout[:8192])


def _token_from_file() -> str | None:
    try:
        raw = (Path.home() / ".claude" / ".credentials.json").read_text(encoding="utf-8")
    except OSError:
        return None
    return _extract_access_token(raw[:1_000_000])


def _read_token() -> str | None:
    if sys.platform == "darwin":
        tok = _token_from_keychain()
        if tok:
            return tok
    return _token_from_file()


def fetch_claude_usage() -> dict[str, Any] | None:
    """Read-only fetch of Claude's usage windows. Opt-in; returns the raw usage JSON, or None.

    The token never leaves this function; only the numeric usage JSON is returned. Any failure
    (disabled, no token, endpoint/parse error) yields None so the caller degrades cleanly.
    """
    if not claude_quota_enabled():
        return None
    cached = _cache.get("usage")
    if cached is not None and (time.monotonic() - _cache.get("at", 0.0)) < _CACHE_TTL:
        return cached if isinstance(cached, dict) else None
    token = _read_token()
    if not token:
        return None
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                _USAGE_URL,
                headers={"Authorization": f"Bearer {token}", "anthropic-beta": _BETA},
            )
            resp.raise_for_status()
            body = resp.json()
    except Exception:  # noqa: BLE001  # reason: degrade-never-lie; an error must never surface the token
        return None
    usage: dict[str, Any] | None = body if isinstance(body, dict) else None
    _cache["usage"] = usage
    _cache["at"] = time.monotonic()
    return usage
