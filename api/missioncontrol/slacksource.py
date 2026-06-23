"""I/O seam for the Slack collector: read-only Web API calls with the runtime token.

Thin + isolated on purpose (like ``paths.py``/``osnotify.py``): the *logic* — normalizing Slack
responses into buried items — lives in ``slack.py`` at 100% coverage. This module is only the
network wiring, so it is kept out of the unit-coverage gate (pyproject ``omit``) and exercised by a
real run, not unit %.

Token safety (CLAUDE.md): ``SLACK_TOKEN`` is read at call time, held in memory only for the
request, sent solely in the ``Authorization`` header, and **never** persisted, logged, or returned
to the browser; any error string is run through ``redact_text``. Read-only GETs only — no writes,
no quota-spend. Any failure returns an unavailable feed (degrade, never lie).

Live wiring is opt-in: nothing here runs unless ``SLACK_TOKEN`` is set, so the non-invasive default
holds. The token is a Slack **user** token (``xoxp-…``) so it sees your DMs and mentions; see
``api/SLACK_SETUP.md``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .models import SlackFeed, SlackItem
from .redact import redact_text
from .slack import parse_history, parse_search

_API = "https://slack.com/api"
_TIMEOUT = 6.0
_HISTORY_LIMIT = 30  # recent messages per DM channel
_IM_CAP = 25  # most-recent DM channels to scan (bounds API calls per poll)
_SEARCH_COUNT = 30  # recent mention search results

# Process-lifetime cache of the identity (self id, handle) + the user directory. These rarely
# change; caching them keeps the per-poll call count low and well under Slack's rate limits.
_identity: dict[str, Any] = {}


def slack_enabled() -> bool:
    """True only when a runtime Slack token is configured (opt-in; non-invasive by default)."""
    return bool(os.environ.get("SLACK_TOKEN"))


def _get(client: httpx.Client, method: str, params: dict[str, Any], token: str) -> dict[str, Any]:
    resp = client.get(
        f"{_API}/{method}", params=params, headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


def _users(client: httpx.Client, token: str) -> dict[str, str]:
    """One page of the user directory -> {user_id: display name}. Best-effort; tolerant."""
    out: dict[str, str] = {}
    data = _get(client, "users.list", {"limit": 200}, token)
    for m in data.get("members") or []:
        if not isinstance(m, dict):
            continue
        uid = m.get("id")
        prof_raw = m.get("profile")
        prof = prof_raw if isinstance(prof_raw, dict) else {}
        name = prof.get("display_name") or prof.get("real_name") or m.get("name")
        if isinstance(uid, str) and isinstance(name, str) and name:
            out[uid] = name
    return out


def _resolve_identity(client: httpx.Client, token: str) -> tuple[str, str, dict[str, str]]:
    """Return (self_id, handle, users), caching after the first successful resolve."""
    if "self_id" not in _identity:
        auth = _get(client, "auth.test", {}, token)
        if not auth.get("ok"):
            raise RuntimeError(str(auth.get("error") or "auth.test failed"))
        self_id = auth.get("user_id")
        handle = auth.get("user")
        if not isinstance(self_id, str):
            raise RuntimeError("auth.test returned no user_id")
        _identity["self_id"] = self_id
        _identity["handle"] = handle if isinstance(handle, str) else self_id
        _identity["users"] = _users(client, token)
    return _identity["self_id"], _identity["handle"], _identity["users"]


def _dms(client: httpx.Client, token: str, self_id: str, users: dict[str, str]) -> list[SlackItem]:
    items: list[SlackItem] = []
    listing = _get(client, "conversations.list", {"types": "im", "limit": 100}, token)
    channels = [c for c in (listing.get("channels") or []) if isinstance(c, dict)]
    for ch in channels[:_IM_CAP]:
        cid = ch.get("id")
        if not isinstance(cid, str):
            continue
        history = _get(
            client, "conversations.history", {"channel": cid, "limit": _HISTORY_LIMIT}, token
        )
        feed = parse_history(
            history, self_id=self_id, channel={"id": cid, "is_im": True}, users=users
        )
        items.extend(feed.items)
    return items


def _mentions(
    client: httpx.Client, token: str, self_id: str, handle: str, users: dict[str, str]
) -> list[SlackItem]:
    # Search has no exact "mentions of me" modifier: query broadly by handle, then let
    # parse_search keep only matches that actually contain <@self_id>.
    search = _get(
        client,
        "search.messages",
        {"query": f"@{handle}", "count": _SEARCH_COUNT, "sort": "timestamp"},
        token,
    )
    return parse_search(search, users=users, self_id=self_id).items


def fetch_slack_feed() -> SlackFeed:
    """Read your recent DMs + mentions read-only and return them as a normalized feed.

    Degrades cleanly: no token, an auth failure, or any network/parse error yields an unavailable
    feed with a redacted reason — never a crash, never a leaked token.
    """
    token = os.environ.get("SLACK_TOKEN")
    if not token:
        return SlackFeed(available=False, degraded="SLACK_TOKEN not set")
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            self_id, handle, users = _resolve_identity(client, token)
            items = _dms(client, token, self_id, users) + _mentions(
                client, token, self_id, handle, users
            )
        return SlackFeed(available=True, items=items)
    except Exception as exc:  # noqa: BLE001  # reason: degrade-never-lie; redact any token in the text
        return SlackFeed(available=False, degraded=redact_text(str(exc)))
