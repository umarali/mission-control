# Connect Slack (optional) — buried items in the Timeline

Mission Control can surface your Slack **DMs and @-mentions** ("buried items", PLAN.md pain #3) in
the unified Timeline. It is **read-only** and **opt-in**: nothing touches Slack unless you set a
`SLACK_TOKEN`. The token is a Slack **user** token (`xoxp-…`) so it sees *your* DMs and mentions; it
is read at call time, held in memory only, and **never persisted, logged, or sent to the browser**.

You only need ~5 minutes. Use a throwaway **free** workspace to test.

## 1. Create a free Slack workspace

1. Go to <https://slack.com/get-started#/createnew> and sign in (or sign up).
2. Enter an email → type the 6-digit code Slack emails you.
3. Name the workspace (e.g. "MC Test"), add a channel name, skip inviting people.
4. You land in the new workspace on the **free** plan. Done.

> To actually *see* buried items you need messages **from someone else**: invite a second
> account (or a teammate) and have them DM you or @-mention you in a channel. Messages **you** send
> are intentionally skipped — they aren't "buried items". Bot/system messages are skipped too.

## 2. Create the read-only Slack app (from a manifest)

1. Go to <https://api.slack.com/apps> → **Create New App** → **From a manifest**.
2. Pick the workspace you just created.
3. Paste this manifest (YAML), then **Next → Create**:

```yaml
display_information:
  name: Mission Control (read-only)
  description: Local-first watcher. Reads your DMs & mentions to surface buried items. Read-only.
oauth_config:
  scopes:
    user:
      - search:read   # find your @-mentions
      - im:read       # list your DM conversations
      - im:history    # read recent DM messages
      - users:read    # resolve user IDs to names
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

These are **user** scopes (not bot scopes) — `search.messages` is user-token only, and DMs are read
as you. The app makes no write scopes, so it can never post or change anything.

## 3. Install and copy the token

1. In the app's left nav → **OAuth & Permissions** → **Install to Workspace** → **Allow**.
2. Copy the **User OAuth Token** — it starts with `xoxp-`.

## 4. Point Mission Control at it

```bash
cp api/.env.example api/.env        # if you don't have api/.env yet
echo 'SLACK_TOKEN=xoxp-…your token…' >> api/.env
```

`api/.env` is git-ignored — your token never gets committed. Restart the API:

```bash
uv --directory api run uvicorn missioncontrol.main:app --host 127.0.0.1 --port 8787
```

Open the dashboard (so the live feed ticks) and then the **Timeline** at
<http://localhost:3000/timeline>. Within a poll cycle (~30 s) your DMs and mentions appear as
`slack` rows — "DM from Alice: …" / "bob in #eng: …" — and a **slack** filter pill shows up.

## How it behaves

- **Read-only & bounded.** Per poll it calls `auth.test` + `users.list` (cached after the first),
  `conversations.list`(im) + `conversations.history` for up to 25 recent DMs, and `search.messages`
  for mentions. Well under Slack's rate limits for a personal workspace.
- **Deduped.** Each message is stored once (keyed by its Slack `ts`); the Timeline also collapses
  identical rows, so nothing repeats.
- **Degrade, never lie.** A bad/expired token or a Slack outage shows a single `slack` "degraded —
  <reason>" row (the reason is redacted of any token), never a crash and never the gauges breaking.
- **Token safety.** If you ever see a token-shaped string anywhere in the UI, logs, or the event
  store, that's a bug — report it. By design only the numbers/text (redacted) are ever surfaced.
