---
name: sdlc-implement
description: "Execute approved tasks.md slice by slice: readiness gate, test-first per task, tick tasks with evidence, full verification at the end, checkpoint on blockers. Use after human approval of a T3 feature, or when the user says 'implement' or 'build the tasks'."
argument-hint: "Feature folder, or the task IDs to run (defaults to the next unchecked slice)"
user-invocable: true
---

# sdlc-implement: build what was approved

## When to use

- T3 after the human has approved `spec.md`, `plan.md` and `tasks.md` (the `sdlc-analyze` gate).
- To resume a partly done `tasks.md`.
- T2 goes straight to `sdlc-tdd` with the mini-spec; it doesn't need this skill.

## Inputs

- `tasks.md` (required), `spec.md`, `plan.md`, `data-model.md` / `contracts/` if present. These are binding.
- `.sdlc/config.json` → `commands`, `budget`.
- `.sdlc/checklists/definition-of-done.md`.
- Any handoff file for this feature.

## Process

1. **Readiness gate.** Stop and ask if any of these fails:
   - [ ] Approval holds: run `python3 <kit_path>/bin/sdlc gate approved . --spec <NNN>` (`--repo <repo>` in a workspace) and quote its last line. If it reports no approval digest (a spec approved before digests existed), ask the human to confirm; don't go on your own say-so. If it reports that a part changed since approval, stop: ask the human and run `gate approve` again.
   - [ ] There are no open CRITICAL findings from `sdlc-analyze`, and no `[NEEDS CLARIFICATION]` marker on anything a P1 scenario or an in-scope task depends on.
   - [ ] The verification commands exist and run. Run the test command once now to record a **baseline** (pre-existing failures are noted, not fixed silently).
   - [ ] `git status` was checked, and unrelated changes are preserved and won't be staged.
   - [ ] Private registry and credential prerequisites are present (check presence only; never print values).
2. **Pick the next slice**: the lowest unchecked slice whose `blocked-by` tasks are all done. After all slices, take the unchecked `C` tasks under `## Convergence`. Within it, run `[P]` tasks in parallel only through subagents with disjoint write sets. With usage metrics on (`.sdlc/config.json` → `usage.enabled` is `true`), run `[P]` tasks one after another instead, because overlapping units double count.
3. **For each task**, first (only if `usage.enabled` is `true`) run `python3 .claude/skills/sdlc-usage/usage.py start <task id> --record <feature folder>/tasks.md` (`.github/skills/...` when that is the only path). Then follow `sdlc-tdd`: RED (watch it fail for the expected reason), then GREEN (minimal code), then REFACTOR. Stay inside the task's `files`. If you must touch another file, say why and update the task line (that is an edit to an approved document: ask the human and run `gate approve` again).
4. **Tick a task** (`[x]`) only when its `verify` step passed at the current revision. Append to the *Progress log*: the task ID, the short hash of the commit that holds the work, the command and its result (`gate evidence-for-ticks` needs the ID and an existing commit on one line). Never tick work that is blocked, skipped or unverified. Then, if `usage.enabled` is `true`, run `python3 .claude/skills/sdlc-usage/usage.py stop <task id> --record <feature folder>/tasks.md` and quote the line it adds. A **review finding** you are fixing (not a planned task) is a unit too: its id is `<pass>-<finding id>` (for example `review1-F3`), its record is the feature's `tasks.md`, section `Progress log`. Write the finding's one-line text as a Progress-log bullet, then run the same start and stop commands with that id and `--record <feature folder>/tasks.md` (the folder's path relative to the project root: `<repo>/specs/NNN-slug/tasks.md` in a workspace). Findings from `sdlc-analyze` are fixed in specify, plan or tasks and are not measured.
5. **Check after each slice**: run the slice's acceptance check, then the narrow test set. Look at the diff (`git diff --stat`, then the slice's hunks) for scope creep, debug output, dead code or stale comments.
6. **Watch the budget.** If the diff passes `budget.reassess_lines` or the turns pass `budget.target_turns`, pause: simplify, or checkpoint with `sdlc-handoff`. At `budget.max_turns`, checkpoint and stop.
7. **On a blocker**, follow `.sdlc/principles/fail-safe-keep-work.md`:
   - Auth errors are terminal: report `BLOCKED_<AREA>_AUTH` and retry zero times.
   - A transient error gets at most one retry.
   - Leave the task unchecked, write a handoff, and stop dependent work.
8. **Finish** with the full gate: run `python3 <kit_path>/bin/sdlc verify .` (`kit_path` from `.sdlc/lock.json`; in a workspace add `--repo <repo>`; raise the tool timeout or run it in the background, since a suite can take minutes) and quote its exact final line. Only a final line ending `(clean tree)` counts as verified at HEAD. Its final line is informational here, because the tree is still dirty before the commit; it runs every configured command once, non-interactively, with a timeout. Then run `python3 <kit_path>/bin/sdlc gate evidence-for-ticks . --spec <NNN>` and quote its last line; fix every tick it lists. Then the definition-of-done checklist, then `sdlc-converge`. If `enforce` is on and a hook refusal appears (an edit or a push turned down), it is the cue to get the approval or run `sdlc verify`; never edit `.claude/settings.json` or work around the hook.
9. **Report**: the slices done, the commands with their outcomes, any skipped or blocked items and why, and the next step (`sdlc-converge`, then `sdlc-review`).

## Rationalizations

| Excuse | Reality |
|---|---|
| "Approval is implied, they asked for the feature" | T3 needs explicit approval of the artifacts. Ask once; it takes one message. |
| "Tick it, the test will pass once X lands" | A tick is a claim of evidence. Unverified stays unchecked. |
| "Fix the unrelated failing test while I'm here" | Note it as baseline. Fixing it silently hides it from review and widens the diff. |
| "Quick refactor of the neighbour module" | Out of the write set means out of scope. Propose it separately. |
| "Retry the install with another registry" | A 401 or 403 is terminal. Switching registries bypasses an access control. |
| "Reset and start clean" | Never discard work. Checkpoint, then decide with the user. |

## Red flags

- The implementation needs behaviour the spec doesn't state. Stop: update the spec through `sdlc-specify` or `sdlc-clarify`.
- The plan's approach proves wrong. Stop: update `plan.md` (and the ADR) before you continue.
- Tests pass on the first run (RED was never seen). The test may not be testing anything.
- A task needs a second repository or a contract change that isn't in the plan. Re-route.

## Verification

- Every ticked task has a progress-log entry with its command and result at the current revision.
- The full gate ran, with each command and outcome listed. Failures and skips are named, not hidden.
- The definition-of-done checklist was completed.
- `git diff` contains only the files in the tasks' write sets plus the documented additions.

## Principles applied

prove-it-works, evidence-over-claims, fail-safe-keep-work, thin-vertical-slices, guard-context
