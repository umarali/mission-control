---
description: Clean handoff before a context switch — update the HTML knowledge base for the work just done, then emit a paste-ready handoff prompt for a fresh agent.
---

Produce two things, in order. Keep both comprehensive but brief (quality over volume).

## 1. Update the knowledge base (`docs/`)
- Create or update an entry `docs/NNNN-<slug>.html` (next zero-padded number) for the work since the
  last handoff, copying `docs/_template.html`. Structure: **Problem &rarr; Solution &rarr; Context**.
  Capture the why and the decisions/edge-cases, not a transcript.
- Add a link to the new entry in `docs/index.html`.
- If an existing entry covers this work, update it instead of duplicating.

## 2. Emit a handoff prompt
Output a single fenced code block the user can paste into a new chat. Include:
- **Goal** — what we are building right now, in one or two lines.
- **Repo + key paths** — `github.com/umarali/mission-control`; read `docs/index.html` and `PLAN.md` first; then `CLAUDE.md`.
- **Done** — the meaningful state (link the KB entry).
- **Next** — the immediate next actions, with issue numbers.
- **Open decisions** — anything awaiting the owner.
- **Locked principles** — read-only/non-invasive, tokens-never-leak, lean+audited deps, vendor-neutral, degrade-never-lie.
- A first instruction: "Read `docs/index.html` + `PLAN.md` before doing anything."

## When to run
Before handing to a new agent, before starting a new task, or when you reach ~60&ndash;65% of the
context window (see CLAUDE.md "Documentation &amp; handoff"). Do not commit secrets into either output.
