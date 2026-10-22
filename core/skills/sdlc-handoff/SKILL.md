---
name: sdlc-handoff
description: "Pause safely or pick up work: write a compact handoff (goal, state, evidence, blocker, next action, ruled-out paths) so a fresh session or another person can continue without re-deriving anything; or resume from one. Use when blocked, near the context or turn budget, switching phases or sessions, or when the user says 'hand off', 'pause', 'pick up' or 'continue from'."
argument-hint: "pause | pickup [path]"
user-invocable: true
---

# sdlc-handoff: stop cleanly, start fast

## When to use

- **Pause**: blocked; nearing `budget.max_turns` or the context limit; ending the session mid-task; between T3 phases when a fresh session would help.
- **Pickup**: starting a session that continues earlier work (the `sdlc` router calls this when it finds a handoff).
- Not a status report for stakeholders. That goes in the PR or issue.

## Inputs

- `.sdlc/templates/handoff.md`.
- The current state: `git status`, `git log -1`, the branch, and the `tasks.md` progress log.
- For pickup: the handoff file (default: the newest `.sdlc/handoff-*.md`, or one inside the feature folder).

## Process

**Pause**
1. **Preserve the work** (see `.sdlc/principles/fail-safe-keep-work.md`). Don't reset or discard anything. Commit only intended files, and only if committing is permitted; otherwise leave the working tree as it is and list the dirty files.
2. **Write the handoff** from the template to `specs/NNN-slug/handoff.md` for a feature, or to `.sdlc/handoff-<slug>.md` otherwise:
   - The goal, and the track.
   - The state: branch, SHA, dirty files.
   - What's done, with its evidence (commands and results).
   - What's in progress. The exact blocker: the sanitized error, the command, and who can unblock it.
   - The **next action**, phrased as the first concrete step.
   - The decisions made, and **what's been ruled out** (so nobody redoes it).
   - The files to read first, with line ranges.
3. **Keep it short**: the facts a newcomer needs, under ~60 lines. Link to artifacts; don't copy them.
4. **Leave the blocked tasks unchecked** in `tasks.md` and reference the handoff from them.
5. **Stop.** Make no more autonomous retries. Tell the user where the handoff is and what's needed from them.

**Pickup**
1. Read the handoff. Check its state against reality: is the branch and SHA still the same, and are the dirty files still present? Report any differences before acting.
2. Re-verify any claimed evidence you'll rely on (the evidence-over-claims principle). Don't repeat the ruled-out paths.
3. Start the *Next action*. Update the handoff, or delete it when the work completes (deleting it is part of finishing).

## Rationalizations

| Excuse | Reality |
|---|---|
| "I'll remember where I was" | The next session won't. Context doesn't survive; files do. |
| "Dump the whole conversation into the handoff" | Nobody reads 500 lines. Facts, evidence and the next step. |
| "Reset to a clean state before pausing" | That destroys the evidence and the work. Preserve, describe, stop. |
| "Retry once more before handing off" | If the blocker is deterministic (auth, a missing access), retrying burns budget and changes nothing. |
| "The handoff says the tests pass, so they pass" | That was true at its SHA. Re-check at the current one. |

## Red flags

- The handoff would contain secrets, tokens or personal data. Redact them.
- On pickup, the branch has moved or the dirty files are gone. Reconcile with the user before continuing.
- The same blocker appears in two successive handoffs. Escalate to a human owner.

## Verification

- The handoff file exists at the stated path, and every section is filled in or marked N/A.
- `git status` shows the work preserved, and the dirty files listed match.
- On pickup, the state check against the handoff is reported before the first edit.

## Principles applied

fail-safe-keep-work, guard-context, evidence-over-claims
