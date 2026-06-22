---
description: Implement a GitHub issue end to end (view -> plan -> implement -> verify -> review -> PR). Manual; it commits and opens a PR.
argument-hint: <issue-number>
---

Implement issue **#$ARGUMENTS** end to end, following CLAUDE.md (read-only, tokens-never-leak,
lean+audited deps, verify-with-evidence).

1. `gh issue view $ARGUMENTS` — read it plus the PLAN.md sections it references. Restate the goal
   and the done-condition in one line.
2. If multi-file or uncertain, plan first (plan mode): a short spec naming files, interfaces,
   out-of-scope, and the verification step. One-line fix: skip planning.
3. Branch `issue-$ARGUMENTS-<slug>` off `main` (never commit to main). Keep collector core,
   subprocess, and secret handling under synchronous supervision.
4. Verify with evidence: run `/check` and paste results; for parsers add/run tests incl. degraded
   cases; for UI, screenshot.
5. Fresh-context review: `/code-review` against the plan, correctness/requirement gaps only.
6. Commit (with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer) and
   `gh pr create` linking the issue. Do NOT merge.
