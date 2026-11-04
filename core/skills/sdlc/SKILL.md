---
name: sdlc
description: "Entry point for any bug, change or feature. Load this first, before any other sdlc- skill (sdlc-debug, sdlc-tdd and the rest come after it): investigates briefly, picks the delivery track (T0 trivial to T4 initiative), and opens that track's steps as a todo list. Use when the user starts a task, asks 'how should we do this', or says /sdlc. Skip it for a one-line typo, comment or rename."
argument-hint: "Describe the task, bug or feature"
user-invocable: true
---

# sdlc: route the task

## When to use

- At the start of any task that may change behaviour, or when unsure which skill applies.
- When work in progress has grown (new contract, second repo) and needs re-routing.
- Not for pure questions about the code. Answer those directly.

## Inputs

- The user's request: `$ARGUMENTS`.
- `AGENTS.md`, `.sdlc/config.json`, the glossary (`CONTEXT.md`, `GLOSSARY.md` or `docs/glossary.md`, if present), ADRs (`docs/adr/`, if present).
- In a workspace: `.sdlc/workspace.md` (the repo map) and `.sdlc/config.json` → `repos`.
- The repo's context, `.sdlc/context/<repo>.md`, if present. If `sdlc discover` marks it STALE, say so and treat it as leads only (or offer `sdlc-context --refresh`).
- Active work: the newest `specs/NNN-*/` with unchecked tasks, and any handoff (`.sdlc/handoff-*.md`, or `handoff.md` inside a spec folder).

## Process

1. **Which repo?** In a workspace, name the repo or repos the task touches, using the workspace map, and work from inside that repo. If no map exists, suggest running `sdlc-setup` first. If the repo has no context file, suggest `sdlc-context` before a T3 or T4 task. Touching more than one repo is an escalation signal; check the map's dependencies.
   **Check freshness.** Run `python3 <kit_path>/bin/sdlc discover . --json` once, with `kit_path` from `.sdlc/lock.json`, and read the repo's `context` and `head`:
   - `stale: true`: say how many commits behind it is, treat the context as leads only, and offer `sdlc-context <repo> --refresh` before a T3 or T4 task.
   - `context: null`: suggest `sdlc-context <repo>`.
   Never assume a context file is current from its date.
2. **Resume check and open work.** If a handoff file or an active spec matches the request, read it, say so, and continue from its *Next action* instead of starting over. Also look for **open work in the same area**: the context file's *Open work* section and, if `gh` is available and logged in, a read-only `gh pr list --repo <owner/repo> --state open --search "<key terms>"`. Name any matching PR or branch, and ask whether to build on it before starting parallel work.
3. **Investigate briefly.** Spend a bounded look (a few reads or searches, or one `sdlc-explorer` subagent) on the seam the task touches: callers, contracts, data, auth, other repos. Read `.sdlc/principles/depth-follows-risk.md`.
4. **Classify.** Pick the lowest track whose signals all fit:

   | Track | Signals | Skills, in order |
   |---|---|---|
   | T0 Trivial | No behaviour change (typo, docs, pin bump, config value) | do it → verify → offer `sdlc-ship` (don't commit unasked) |
   | T1 Bug | Observable wrong behaviour | `sdlc-debug` → `sdlc-review` → `sdlc-ship` |
   | T2 Change | One session, one seam, no contract, data-model, auth or tenant change | `sdlc-grill` (light) → mini-spec → `sdlc-tdd` → `sdlc-review` → `sdlc-ship` |
   | T3 Feature | New behaviour, an API, event or schema contract, a migration, security-sensitive, or more than one seam | `sdlc-specify` → `sdlc-clarify` → `sdlc-plan` → `sdlc-tasks` → `sdlc-analyze` → **human approval** → `sdlc-implement` → `sdlc-converge` → `sdlc-review` → `sdlc-ship` |
   | T4 Initiative | Several features, teams or repos; more than ~20 sessions | `sdlc-grill` → PRD (`.sdlc/templates/prd.md`) → ADRs → one T3 per feature |

   **Repo process wins.** If `.sdlc/config.json` → `repos.<repo>.process` is `spec-kit`, the repo's own rules decide the track:
   - **T0** only under the exemption the repo's `AGENTS.md` grants (quote the line).
   - **T1/T2** only within that exemption, or when the owning spec is updated in the same change, as the repo requires.
   - **T3/T4** hand off to the repo's `speckit-*` skills (specify → clarify → plan → tasks → analyze → implement → converge), with `sdlc-review` and `sdlc-ship` around them.
   - Drafts made outside the repo stay under `.sdlc/drafts/<repo>/` until owners adopt them.

5. **State the route** in 3–5 lines: the track, why (the signals you found, with `path:line`), what would escalate it, and the first skill. Documentation-only work is T0 even if it is long.
6. **Open the todo list** from the chosen track's skills. Then start the first skill. Don't wait for confirmation unless the track is T3 or T4, or the classification is genuinely unclear (then ask one question).
7. **Re-route** whenever an escalation signal appears mid-task (see Red flags). Update the todo list and say what changed.

## Rationalizations

| Excuse | Reality |
|---|---|
| "It's small, skip the look" | The look is how you find out it's small. A few reads is cheap; a missed contract is not. |
| "Spec everything to be safe" | Padding T0–T2 with specs wastes review time and buries the real decisions. |
| "It started as T2, so it stays T2" | The track follows the facts. A new contract makes it T3 now. |
| "The user said quick, so skip tests" | Quick changes the track's ceremony, not the evidence. Every track ends verified. |
| "I'll classify after coding" | Classifying is how you decide whether to agree on a spec first. |

## Red flags

Stop and re-route upward if any of these appear:
- A public API, event, schema or SDK contract changes.
- A database migration or data backfill.
- Authentication, authorization, tenant scope or secrets are touched.
- A second repository or service must change.
- The diff heads past `budget.reassess_lines` in `.sdlc/config.json`.
- Requirements conflict between the user, the spec and `AGENTS.md`. Stop and ask; don't pick one.

## Verification

- The route statement names the track, its evidence and the first skill.
- The todo list matches the track's skill sequence.
- At the end, the final report lists the track used and any re-routes, and cites the principles applied.

## Principles applied

depth-follows-risk, guard-context, agree-before-building
