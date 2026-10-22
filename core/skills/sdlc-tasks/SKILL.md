---
name: sdlc-tasks
description: "Break a plan into dependency-ordered tracer-bullet tasks.md: vertical slices, each with write set, verify command and blocking edges; optionally publish them as issues. Use after sdlc-plan, or when the user says 'break this down', 'create tasks' or 'make issues'."
argument-hint: "Path of plan.md (defaults to the active feature); add --issues to publish"
user-invocable: true
---

# sdlc-tasks: slices you can verify alone

## When to use

- T3, after `plan.md` has no open research items.
- With `--issues`: also publish the tasks to the tracker in `.sdlc/config.json` → `tracker`.

## Inputs

- `spec.md`, `plan.md`, and `data-model.md` / `contracts/` if present.
- `.sdlc/templates/tasks.md`, `.sdlc/principles/thin-vertical-slices.md`, `.sdlc/config.json` → `commands`, `budget`.

## Process

1. **Cut slices by scenario.** S1 is the tracer bullet: the P1 scenario's narrowest end-to-end path through the riskiest integration. Later slices widen it (more cases, P2/P3 scenarios, hardening). Never cut by layer.
2. **Write tasks inside each slice** using the template's line format: `- [ ] T001 [P] [S1] Description — files: … — verify: … — blocked-by: …`.
   - **files**: the exact write set. Tasks with overlapping files can't be `[P]` (parallel).
   - **verify**: a concrete command or observable check from `config.commands`, or a precise manual step. Never "it works".
   - **blocked-by**: explicit edges. No hidden ordering.
   - Tests are part of the slice's tasks: a test task comes before its implementation task. They are never a final "write tests" phase.
3. **Add the closing tasks**: contract and docs updates required by the plan, `sdlc-converge`, `sdlc-review`, and the full-suite verification with the commands from config.
4. **Keep human-only and blocked work visible** in the *Blocked / human-only* section, with an owner. Don't drop it and don't pretend it's done.
5. **Check coverage.** Every FR maps to at least one task, and every task maps to an FR, a scenario or a plan item. Fix orphans.
6. **Size check.** Count the slices and estimate lines against `budget`. If over, simplify in the plan; don't silently trim scope.
7. **Publish (`--issues`, only on request).** One issue per slice (not per task). Body: slice goal, acceptance check, task checklist, blocked-by links, and a spec link. Create blockers first so the links resolve. Use the platform's CLI or MCP. Creating issues is outward-facing, so confirm the count and target repo with the user before creating anything.
8. **Report**: the tasks path, slice and task counts, the parallel groups, any blocked items, and the next step `sdlc-analyze`.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Models first, then routes, then UI" | Layer phases can't be verified until the end. A vertical slice proves itself on day one. |
| "Tests go in the final phase" | Then they get cut, or written to match the bugs. A test task precedes each implementation task. |
| "Ordering is obvious, skip blocked-by" | Parallel agents and reviewers can't see what's obvious to you. Write the edges. |
| "Bigger tasks mean fewer handoffs" | A task you can't verify alone is a task you can't call done. |
| "Leave the human-only step out, it's not code" | Invisible work is forgotten work. List it with an owner. |

## Red flags

- A slice has no independent acceptance check.
- Two `[P]` tasks share a file.
- A task's verify step needs credentials or an environment that isn't available. Mark it blocked now, not at implement time.
- The FR-to-task coverage has gaps you can't close without changing the spec. Go back to `sdlc-specify`.

## Verification

- `tasks.md` follows the template's line format, and every task has files, verify and blocked-by (or `—`).
- The coverage check passed: no FR without a task, no orphan task.
- S1 is an end-to-end tracer bullet for a P1 scenario.
- If `--issues` was used: the issue URLs are listed, and blocked-by links resolve.

## Principles applied

thin-vertical-slices, prove-it-works, depth-follows-risk
