"""Localhost hardening primitives (issue #13): pure predicates + a per-session token.

The HTTP surface is read-only in v1, but localhost is not an auth boundary, so we still defend
against the two browser-shaped threats a local service faces:

  - **DNS rebinding** — an attacker domain that resolves to 127.0.0.1 reaches us with its own
    ``Host`` header; ``host_allowed`` rejects anything but localhost/127.0.0.1.
  - **Cross-site reads** — a malicious page in the user's browser fetching our API carries its
    ``Origin``; ``origin_allowed`` rejects anything outside the dev-web allowlist.

A missing Origin/Host (curl, SSE, same-origin, HTTP/1.0) is allowed — those are not the threat.
``new_session_token`` / ``token_ok`` provide the per-session token baseline that the v1.5 action
surface will *require*; v1 read endpoints expose it but do not yet gate on it.
"""

from __future__ import annotations

import secrets

ALLOWED_ORIGINS: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
ALLOWED_HOSTS: tuple[str, ...] = ("localhost", "127.0.0.1", "::1")


def origin_allowed(origin: str | None, allowed: tuple[str, ...] = ALLOWED_ORIGINS) -> bool:
    """True if there is no Origin (not a cross-site browser request) or it is allow-listed."""
    if not origin:
        return True
    return origin in allowed


def _hostname(host: str) -> str:
    """Strip the port from a Host header, handling bracketed IPv6 (``[::1]:8787``)."""
    h = host.strip()
    if h.startswith("["):
        return h[1:].split("]", 1)[0]
    return h.split(":", 1)[0]


def host_allowed(host: str | None, allowed: tuple[str, ...] = ALLOWED_HOSTS) -> bool:
    """True if there is no Host header or its hostname is localhost/127.0.0.1/::1."""
    if not host:
        return True
    return _hostname(host) in allowed


def new_session_token() -> str:
    """A fresh, URL-safe per-session token (regenerated each process start)."""
    return secrets.token_urlsafe(32)


def token_ok(provided: str | None, expected: str) -> bool:
    """Constant-time compare; False on a missing token."""
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)
