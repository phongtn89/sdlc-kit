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

<!-- One line per session: date, short commit hash, tasks done, evidence, next task. A ticked task needs a line here that names its ID (or a range such as `T001–T004`) and the short commit hash that holds the work: `sdlc gate evidence-for-ticks` checks it. Put baseline test counts here, not in the Verify block. `## Convergence` goes after this log. Write ids plainly at the start of a tick (`- [x] T001 ...`, not bold), and name a range as `T001–T004` (the prefix twice); "T001 – 57 tests" is not a range. Any edit to the spec, plan, contracts or task text after approval needs the human and a new `gate approve` (re-approval). With usage metrics on (`usage.enabled` in `.sdlc/config.json`), `sdlc-usage` also adds hidden `usage-start` and `usage-stop` comments and a `- usage <task id>: …` bullet per task here. Do not edit them. -->

- YYYY-MM-DD `rev` — T00x done (`command` exit 0); next: T00y
