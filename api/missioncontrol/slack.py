"""Pure Slack parser: read-only Web API responses -> normalized 'buried items' (mentions + DMs).

Credential-free, no I/O. Input is an already-parsed Slack Web API response dict (from
``conversations.history`` for a DM channel, or ``search.messages`` for mentions); this module
never calls Slack and never touches a token — the live reader seam supplies the JSON.

Tolerant of schema drift (CLAUDE.md C5): unknown/partial shapes are skipped, never fatal; an
auth/parse failure returns a ``degraded`` feed, never a crash and never a wrong number. Every
visible text is demangled (Slack mrkdwn) and run through ``redact_text`` so a message that happens
to contain a pasted token can never leak to the browser (tokens never leak).

"Buried items" = the things that get lost (PLAN.md pain #3): a DM, or a message that @-mentions
you. Your own messages, system/join notices, and bot posts are not buried items and are skipped.
"""

from __future__ import annotations

import re
from typing import Any

from .events import make_event
from .models import Event, SlackFeed, SlackItem
from .redact import redact_text

# One pass over Slack mrkdwn entity tokens: <@U…[|name]>, <#C…[|name]>, <!here|label>, <url|text>.
_ENTITY = re.compile(r"<(?P<body>[^<>]+)>")


def _parse_ts(ts: Any) -> float | None:
    """Slack ts is a string like '1718000000.000200'. Be tolerant: bad/absent -> None."""
    try:
        return float(ts)
    except (TypeError, ValueError):
        return None


def _name(user_id: Any, users: dict[str, str] | None) -> str | None:
    if not isinstance(user_id, str) or not user_id:
        return None
    if users and user_id in users:
        return users[user_id]
    return user_id


def _demangle(text: str, users: dict[str, str] | None) -> str:
    """Turn Slack mrkdwn entities into readable text (`<@U1|al>` -> `@al`, `<url|x>` -> `x`)."""

    def repl(m: re.Match[str]) -> str:
        body = m.group("body")
        label = body.split("|", 1)[1] if "|" in body else None
        head = body.split("|", 1)[0]
        if head.startswith("@"):  # user mention
            return f"@{label or _name(head[1:], users) or head[1:]}"
        if head.startswith("#"):  # channel link
            return f"#{label or 'channel'}"
        if head.startswith("!"):  # special mention (here/channel/everyone)
            return f"@{label or head[1:]}"
        return label or head  # plain link <url|text> -> text, <url> -> url

    return _ENTITY.sub(repl, text)


def _clean(text: Any, users: dict[str, str] | None) -> str:
    return redact_text(_demangle(text, users)) if isinstance(text, str) else ""


def _is_real_message(msg: Any) -> bool:
    """A human chat message — not a join/leave/bot/system post (those are never buried items)."""
    if not isinstance(msg, dict):
        return False
    if msg.get("type") != "message":
        return False
    if msg.get("subtype") is not None:  # channel_join, bot_message, …
        return False
    if msg.get("bot_id"):
        return False
    return True


def parse_history(
    history: Any,
    *,
    self_id: str,
    channel: dict[str, Any],
    users: dict[str, str] | None = None,
) -> SlackFeed:
    """Normalize one ``conversations.history`` response into buried items.

    For an IM channel (``channel.is_im``) every message from someone else is a DM; in a regular
    channel only messages that mention ``<@self_id>`` are surfaced. Your own messages are skipped.
    """
    if not isinstance(history, dict):
        return SlackFeed(available=False, degraded="slack history was not an object")
    if history.get("ok") is False:
        return SlackFeed(available=False, degraded=redact_text(str(history.get("error"))))
    messages = history.get("messages")
    if not isinstance(messages, list):
        return SlackFeed(available=False, degraded="slack history had no messages list")

    is_im = bool(channel.get("is_im"))
    chan_name = channel.get("name")
    chan_label = "direct message" if is_im else (chan_name if isinstance(chan_name, str) else "?")
    chan_id = channel.get("id")
    mention_tag = f"<@{self_id}"

    items: list[SlackItem] = []
    for msg in messages:
        if not _is_real_message(msg):
            continue
        author_id = msg.get("user")
        if author_id == self_id:  # your own message is not a buried item
            continue
        raw = msg.get("text")
        raw_str = raw if isinstance(raw, str) else ""
        if is_im:
            kind = "dm"
        elif mention_tag in raw_str:
            kind = "mention"
        else:
            continue
        text = _clean(raw, users)
        if not text:  # nothing readable (attachments-only, etc.) -> skip
            continue
        ts_raw = msg.get("ts")
        items.append(
            SlackItem(
                kind=kind,
                channel=chan_label,
                channel_id=chan_id if isinstance(chan_id, str) else None,
                author=_name(author_id, users) or "unknown",
                text=text,
                ts=_parse_ts(ts_raw),
                slack_ts=ts_raw if isinstance(ts_raw, str) else None,
                permalink=None,
            )
        )
    return SlackFeed(available=True, items=items)


def parse_search(
    search: Any, *, users: dict[str, str] | None = None, self_id: str | None = None
) -> SlackFeed:
    """Normalize a ``search.messages`` response (mentions of you) into buried items.

    Slack search has no exact "mentions of me" modifier, so the reader queries broadly (your
    handle) and passes ``self_id`` here: a match is kept only if its raw text actually contains
    ``<@self_id>``. That keeps mentions precise no matter how fuzzy the query was.
    """
    if not isinstance(search, dict):
        return SlackFeed(available=False, degraded="slack search was not an object")
    if search.get("ok") is False:
        return SlackFeed(available=False, degraded=redact_text(str(search.get("error"))))
    block = search.get("messages")
    matches = block.get("matches") if isinstance(block, dict) else None
    if not isinstance(matches, list):
        return SlackFeed(available=False, degraded="slack search had no matches")

    items: list[SlackItem] = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        raw = m.get("text")
        if self_id is not None and f"<@{self_id}" not in (raw if isinstance(raw, str) else ""):
            continue
        text = _clean(raw, users)
        if not text:
            continue
        chan = m.get("channel")
        chan = chan if isinstance(chan, dict) else {}
        chan_name = chan.get("name")
        chan_id = chan.get("id")
        author = m.get("username")
        if not isinstance(author, str) or not author:
            author = _name(m.get("user"), users) or "unknown"
        ts_raw = m.get("ts")
        permalink = m.get("permalink")
        items.append(
            SlackItem(
                kind="mention",
                channel=chan_name if isinstance(chan_name, str) else "?",
                channel_id=chan_id if isinstance(chan_id, str) else None,
                author=author,
                text=text,
                ts=_parse_ts(ts_raw),
                slack_ts=ts_raw if isinstance(ts_raw, str) else None,
                permalink=permalink if isinstance(permalink, str) else None,
            )
        )
    return SlackFeed(available=True, items=items)


def slack_events(feed: SlackFeed, *, source: str = "slack.collector") -> list[Event]:
    """Derive scrubbed event rows from a feed (idempotency key = ``slack_ts`` in the payload)."""
    out: list[Event] = []
    for it in feed.items:
        out.append(
            make_event(
                "slack",
                source,
                f"slack.{it.kind}",
                ts=int(it.ts) if it.ts is not None else 0,
                severity="info",
                payload={
                    "kind": it.kind,
                    "channel": it.channel,
                    "channel_id": it.channel_id,
                    "author": it.author,
                    "text": it.text,
                    "permalink": it.permalink,
                    "slack_ts": it.slack_ts,
                },
            )
        )
    return out
