"""Tests for the pure Slack parser: real-shaped fixtures, degraded cases, redaction.

Fixtures mirror the raw Slack Web API shapes the live reader will hand the parser:
``conversations.history`` (DM/channel messages) and ``search.messages`` (mentions).
"""

from __future__ import annotations

from typing import Any

from missioncontrol.redact import REDACTED
from missioncontrol.slack import parse_history, parse_search, slack_events

SELF = "U_SELF"
USERS = {"U_SELF": "Me", "U_ALICE": "Alice", "U_BOB": "Bob"}
LEAK = "sk-ant-" + "A1b2C3d4E5f6G7h8J9k0"


# --- conversations.history (DM channel) ------------------------------------------------------
IM_HISTORY: dict[str, Any] = {
    "ok": True,
    "messages": [
        "garbage",  # not a dict -> skipped
        {"type": "reaction_added", "user": "U_ALICE"},  # not a message -> skipped
        {"type": "message", "subtype": "channel_join", "user": "U_ALICE", "text": "j", "ts": "1.0"},
        {"type": "message", "bot_id": "B1", "text": "deploy ok", "ts": "2.0"},  # bot -> skipped
        {"type": "message", "user": SELF, "text": "my own note", "ts": "3.0"},  # self -> skipped
        {"type": "message", "user": "U_ALICE", "ts": "4.0"},  # no text -> skipped
        {"type": "message", "user": "U_ALICE", "text": f"psst {LEAK}", "ts": "1718000000.000100"},
        {"type": "message", "text": "anon ping", "ts": "bad"},  # no user; unparsable ts
        {"type": "message", "user": "U_ALICE", "text": "no ts msg"},  # ts missing
    ],
}
IM_CHANNEL = {"id": "D1", "is_im": True}


def test_history_dm_filters_and_redacts() -> None:
    feed = parse_history(IM_HISTORY, self_id=SELF, channel=IM_CHANNEL, users=USERS)
    assert feed.available is True
    assert [i.text for i in feed.items] == [f"psst {REDACTED}", "anon ping", "no ts msg"]
    first = feed.items[0]
    assert first.kind == "dm"
    assert first.channel == "direct message"
    assert first.author == "Alice"
    assert first.ts == 1718000000.0001
    assert first.slack_ts == "1718000000.000100"
    assert first.permalink is None
    # no "user" field -> author falls back to "unknown"; unparsable ts -> None (slack_ts kept)
    assert feed.items[1].author == "unknown"
    assert feed.items[1].ts is None and feed.items[1].slack_ts == "bad"
    # missing ts -> both None
    assert feed.items[2].ts is None and feed.items[2].slack_ts is None


# --- conversations.history (regular channel: only @-mentions of you) --------------------------
CHAN_HISTORY: dict[str, Any] = {
    "ok": True,
    "messages": [
        {"type": "message", "user": "U_BOB", "text": "random chatter", "ts": "10.0"},  # no mention
        {
            "type": "message",
            "user": "U_BOB",
            "text": "<@U_SELF> review <#C9|general> docs <https://ex.com|here> "
            "<!here> raw <https://only.url> and <@U_GHOST>",
            "ts": "1718000100.000200",
        },
        {
            "type": "message",
            "user": "U_BOB",
            "text": "<@U_SELF> ping <@U_ALICE|ali> in <#C2> by <!subteam|frontend>",
            "ts": "1718000101.000000",
        },
    ],
}
CHAN = {"id": "C1", "name": "eng"}


def test_history_channel_mentions_and_demangle() -> None:
    feed = parse_history(CHAN_HISTORY, self_id=SELF, channel=CHAN, users=USERS)
    assert [i.kind for i in feed.items] == ["mention", "mention"]
    assert feed.items[0].channel == "eng"
    assert feed.items[0].channel_id == "C1"
    assert (
        feed.items[0].text
        == "@Me review #general docs here @here raw https://only.url and @U_GHOST"
    )
    assert feed.items[1].text == "@Me ping @ali in #channel by @frontend"


def test_history_channel_without_name_or_id() -> None:
    history = {
        "ok": True,
        "messages": [{"type": "message", "user": "U_BOB", "text": "<@U_SELF> hi"}],
    }
    feed = parse_history(history, self_id=SELF, channel={"is_im": False}, users=USERS)
    assert feed.items[0].channel == "?"
    assert feed.items[0].channel_id is None


def test_history_degraded_states() -> None:
    assert (
        parse_history("nope", self_id=SELF, channel={}).degraded
        == "slack history was not an object"
    )
    bad_auth = parse_history({"ok": False, "error": "invalid_auth"}, self_id=SELF, channel={})
    assert bad_auth.available is False and bad_auth.degraded == "invalid_auth"
    no_list = parse_history({"ok": True}, self_id=SELF, channel={})
    assert no_list.degraded == "slack history had no messages list"


# --- search.messages (mentions of you) -------------------------------------------------------
SEARCH: dict[str, Any] = {
    "ok": True,
    "messages": {
        "matches": [
            "nope",  # not a dict -> skipped
            {"type": "message", "text": "", "channel": {"id": "C1", "name": "general"}},  # empty
            {
                "type": "message",
                "text": "<@U_SELF> deploy please",
                "channel": {"id": "C1", "name": "general"},
                "username": "alice",
                "ts": "1718000200.000300",
                "permalink": "https://x.slack.com/archives/C1/p1718000200000300",
            },
            {  # channel not a dict -> "?"; no username -> resolve user (miss) -> id; ts int
                "type": "message",
                "text": "ping",
                "channel": "weird",
                "user": "U_GHOST",
                "ts": 42,
            },
        ]
    },
}


def test_search_matches() -> None:
    feed = parse_search(SEARCH, users=USERS)
    assert feed.available is True
    assert len(feed.items) == 2
    a, b = feed.items
    assert a.kind == "mention"
    assert a.channel == "general" and a.channel_id == "C1"
    assert a.author == "alice"
    assert a.text == "@Me deploy please"
    assert a.ts == 1718000200.0003 and a.slack_ts == "1718000200.000300"
    assert a.permalink == "https://x.slack.com/archives/C1/p1718000200000300"
    assert b.channel == "?" and b.channel_id is None
    assert b.author == "U_GHOST"  # username absent -> resolved (map miss) to the id
    assert b.ts == 42.0 and b.slack_ts is None and b.permalink is None


def test_search_self_id_keeps_only_real_mentions() -> None:
    # The broad search returns 2 usable matches, but only the "deploy" one mentions <@U_SELF>.
    feed = parse_search(SEARCH, users=USERS, self_id="U_SELF")
    assert [i.text for i in feed.items] == ["@Me deploy please"]


def test_search_degraded_states() -> None:
    assert parse_search(None).degraded == "slack search was not an object"
    bad = parse_search({"ok": False, "error": "not_authed"})
    assert bad.available is False and bad.degraded == "not_authed"
    assert parse_search({"ok": True, "messages": []}).degraded == "slack search had no matches"


# --- event derivation ------------------------------------------------------------------------
def test_slack_events_shape_and_idempotency_key() -> None:
    feed = parse_history(IM_HISTORY, self_id=SELF, channel=IM_CHANNEL, users=USERS)
    events = slack_events(feed, source="slack.dms")
    assert [e.surface for e in events] == ["slack", "slack", "slack"]
    assert [e.type for e in events] == ["slack.dm", "slack.dm", "slack.dm"]
    assert all(e.severity == "info" and e.source == "slack.dms" for e in events)
    # ts: parsed -> int seconds; unparsable/missing -> 0
    assert events[0].ts == 1718000000
    assert events[1].ts == 0 and events[2].ts == 0
    payload = events[0].payload
    assert payload["channel"] == "direct message"
    assert payload["author"] == "Alice"
    assert payload["text"] == f"psst {REDACTED}"  # token never reaches the store
    assert payload["slack_ts"] == "1718000000.000100"


def test_slack_events_default_source_and_mention_type() -> None:
    feed = parse_search(SEARCH, users=USERS)
    events = slack_events(feed)
    assert events[0].source == "slack.collector"
    assert events[0].type == "slack.mention"
    assert events[0].payload["permalink"].endswith("p1718000200000300")
