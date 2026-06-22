# Mission Control — Design System

The single source of truth for the look of **both** the HTML knowledge base (`docs/`) and the app
dashboard (`web/`). Keep them visually one product. Light by design (no external fonts/CDNs).

## Identity

- **Name:** Mission Control. **Codename:** Radar.
- **Mark:** a radar scope — concentric rings, a sweep line, a blip. See `docs/logo.svg` (baked
  brand-indigo; the app may use a `currentColor` variant). Reads on light and dark.
- **Voice:** calm, precise, control-room. Short labels, real numbers, no hype. "57% left · resets in
  3h 12m", not "You still have plenty of quota!".

## Color tokens

Define these as CSS custom properties in both surfaces so they stay identical.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--brand` | `#4f6bed` | `#7c93ff` | wordmark, mark, primary accent |
| `--brand-soft` | `#eaf1ff` | `#16263f` | accent fills, callouts |
| `--bg` | `#fcfcfd` | `#0d1117` | page background |
| `--surface` | `#ffffff` | `#11161d` | cards, panels |
| `--fg` | `#1c2024` | `#d8dee6` | primary text |
| `--muted` | `#687076` | `#8b949e` | secondary text |
| `--line` | `#e7e9ee` | `#232b35` | borders |

**Gauge / status semantics** (reserved — never used for branding, so a state always reads true):

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `--ok` | `#16a34a` | `#22c55e` | healthy headroom |
| `--warn` | `#d97706` | `#f59e0b` | caution (window filling / nearing reset) |
| `--crit` | `#dc2626` | `#ef4444` | throttled / < ~5% left |

## Typography

- **UI / body:** system sans (`-apple-system, "Segoe UI", Roboto, ...`). Body 17px / 1.7 in docs;
  the dashboard may run denser.
- **Numbers (gauges, %, countdowns):** monospace with `font-variant-numeric: tabular-nums` so digits
  don't jitter as they tick.
- **Wordmark:** semibold, letter-spacing `-0.01em`, paired with the mark.

## Shape & spacing

- Radius: 10–12px (cards/panels), 999px (chips/pills).
- Comfortable reading measure in docs (~44rem); generous vertical rhythm.
- Subtle shadows in light mode, none in dark.

## Gauge anatomy (dashboard, for reference)

Each gauge: a label (e.g. "Codex · 5h"), a bar/ring filled by **remaining %** colored
`--ok`/`--warn`/`--crit`, the remaining % in tabular mono, and a reset countdown. Claude's card (v1)
shows **consumed tokens** instead of a remaining bar until the remaining-window source is added.

## Reuse

The app imports the same token names. Changing a hex here means changing it in both
`docs/style.css` and the app's token file. Treat this file as the contract.
