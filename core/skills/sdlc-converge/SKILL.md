---
name: sdlc-converge
description: "Read-only reconciliation after implementation: compare the code at the current revision with spec.md, plan.md and tasks.md, then append a Convergence section listing gaps as new tasks and drift that needs a spec or plan update. Never edits code. Use after sdlc-implement, before review, or when the user says 'converge' or 'does the code match the spec'."
argument-hint: "Feature folder (defaults to the active feature)"
user-invocable: true
---

# sdlc-converge: keep spec and code honest

## When to use

- T3, after `sdlc-implement` finishes (or stops), and before `sdlc-review`.
- When an older feature's code has evolved and you need to know whether its spec still describes it.
- Code is **read-only** here. The only file this skill writes is `tasks.md`, where it appends the *Convergence* section.

## Inputs

- `spec.md`, `plan.md`, `tasks.md`, plus `contracts/` and `data-model.md` if present.
- The code at HEAD, and the feature's diff (`git diff <base>...HEAD`).
- The latest verification results (the progress log in `tasks.md`, or CI for this head).

## Process

1. **Record** the revision and the base.
2. **For each FR, SC and scenario**, find the implementing code and the test (`path:line`). Classify each:
   - **met**: implemented, with a test that exercises it.
   - **untested**: implemented, but no test proves it.
   - **missing**: not implemented.
   - **diverged**: implemented differently from the spec.
3. **For each plan decision** (contracts, data model, failure modes, rollout steps), check that the code follows it. Note any divergence.
4. **For each ticked task**, check that its verify evidence exists at a revision that includes the final code. If it's stale, mark it for re-verification.
5. **Look for unplanned behaviour**: code in the diff that maps to no requirement (scope creep or a missing spec update).
6. **Append to `tasks.md`**:
   ```
   ## Convergence (YYYY-MM-DD, <short sha>)
   - [ ] C001 [gap: missing FR-004] … — files: … — verify: … — blocked-by: —
   - [ ] C002 [drift: FR-002 says X, code does Y at path:line] → decide: update spec, or fix code
   ```
   If everything is met: `No gaps. N requirements met, evidence at <sha>.`
7. **Report**: the counts per class, the new convergence tasks, and the decisions needed. Drift is the user's call (spec or code); don't choose silently. Next step: implement the `C` tasks via `sdlc-implement`, or go on to `sdlc-review` when there are none.

## Rationalizations

| Excuse | Reality |
|---|---|
| "All tasks are ticked, so it matches the spec" | Tasks can be ticked against an old revision, or miss an FR. Check the code. |
| "Just fix the small gap now" | Converge is the audit. Fixing during the audit removes the record and skips TDD. Add a task. |
| "The code is right, the spec is stale. Edit the spec" | Maybe. That's a requirement change, so the user decides, through `sdlc-specify`. |
| "Unplanned extras are a bonus" | Unspecified behaviour is unreviewed and unsupported. Flag it. |

## Red flags

- A P1 scenario is missing or diverged after implementation was declared done.
- The verification evidence predates the final code.
- Convergence finds behaviour that belongs to another feature's spec.

## Verification

- Every FR and SC is classified, with `path:line` evidence or the note "not found".
- The *Convergence* section is appended with the revision. No code files are modified (check `git diff` from this skill).
- Every drift item ends in a decision request, not a silent choice.

## Principles applied

evidence-over-claims, agree-before-building, encode-lessons
