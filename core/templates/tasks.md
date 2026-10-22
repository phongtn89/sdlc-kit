# Tasks: [Feature name]

Inputs: [spec.md](spec.md), [plan.md](plan.md) · Status: draft · Created: [YYYY-MM-DD]

Verify (from `.sdlc/config.json` → `commands`):
- Narrow: `[test command for one file]`
- Full: `[build]` · `[test]` · `[lint]` · `[typecheck]` · `[integration]`

<!-- Dependency-ordered, independently verifiable. Slice by behaviour, not by layer. Check a box only with evidence; blocked or skipped work stays unchecked. -->

Legend: `- [ ] T001 [P?] [S1] Description — files: … — verify: … — blocked-by: T00x`
- `[P]` may run in parallel: no shared files, no blocking edge.
- `[S1]` slice the task belongs to.
- `verify` is the command or observation that proves this task alone.

## Phase 0 — Setup (only if needed)

<!-- Only work every slice depends on and that no slice can own. Delete if empty. -->

- [ ] T001 [description] — files: — verify:

## S1 — [Tracer bullet: riskiest path end to end]

Goal: [one behaviour, from spec scenario S1]
Acceptance: [independent check that proves the slice works on the real surface]

- [ ] T002 [S1] Write failing test for [behaviour] — files: — verify: `[RED command]` fails for the expected reason
- [ ] T003 [S1] Implement [behaviour] — files: — verify: `[command]` — blocked-by: T002

## S2 — [Next behaviour]

Goal:
Acceptance:

- [ ] T004 [P] [S2] … — files: — verify: — blocked-by: T003

## Final

- [ ] T0xx Run full gates and record outcomes — verify: all commands above
- [ ] T0xx Converge: spec, plan, tasks and code agree (`sdlc-converge`)
- [ ] T0xx Independent review (`sdlc-review`); verdict recorded
- [ ] T0xx Update docs, ADRs and changelog affected by the change

## Blocked / human-only

<!-- Work that cannot be done here: external dependency, credential-gated check, approval. Say who must act and what unblocks it. -->

- [ ] [item] — owner: — unblocked when:

## Progress log

<!-- One line per session: date, revision, tasks done, evidence, next task. -->

- YYYY-MM-DD `rev` — T00x done (`command` exit 0); next: T00y
