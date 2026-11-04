---
name: sdlc-ship
description: "Prepare verified work for delivery: final gate on the exact revision, focused commits, PR description from the template, rollout and rollback notes; pushes, PRs and merges only with explicit user approval. Use when work is reviewed and the user says 'ship', 'open a PR', 'commit this' or 'release'."
argument-hint: "What to ship (branch, feature folder); optional: commit-only | pr | release"
user-invocable: true
---

# sdlc-ship: deliver exactly what was verified

## When to use

- After `sdlc-review` returns `APPROVED`. For T0, after you've verified it.
- Committing, opening or updating a PR, writing release notes, preparing a rollout.
- Not a substitute for review. If there's no APPROVED review and the track requires one, run it first.

## Inputs

- The branch and its diff against the base; the `tasks.md` progress log; the review report.
- `.sdlc/templates/pr.md`, `.sdlc/checklists/definition-of-done.md`, `.sdlc/checklists/compatibility-migration.md` (when it applies).
- `.sdlc/config.json` → `commands`. The repository's PR template and contribution rules, if present.

## Process

1. **Check the branch.** Never commit straight to the default branch. If you're on it, create a feature branch (name it after the spec or issue), or ask. Don't rename an assigned branch.
2. **Run the final gate on this exact revision**: the full gate is `sdlc verify` in step 4, after the commit, so the suite runs once; until then run only the narrow checks. Record each outcome. Anything failing or skipped is named, and blocks a "ready" claim. If a gate fails or is skipped, or you find a defect in the change yourself, **stop before any outward action and report it**, even if the push or PR was authorized up front. That authorization covered verified work, and this work isn't verified. A failure proven to exist before the change (the same failure on the base revision) can be shipped only if you say so explicitly and the user agrees.
3. **Check the diff.** `git status` and `git diff --stat`: only the intended files. No secrets, debug output, `.only`, large generated noise or unrelated user changes. Stage explicit paths, never `git add -A` over unknown files.
4. **Commit** only when the user asked to ship or commit, with focused, conventional messages (`type(scope): summary`, then a body with the why) and any attribution lines the repository requires; right after the commit and before any push or PR, run `python3 <kit_path>/bin/sdlc verify .` (`kit_path` from `.sdlc/lock.json`; in a workspace add `--repo <repo>`; raise the tool timeout or run it in the background, since a suite can take minutes) and quote its exact final line. Only a final line ending `(clean tree)` counts as verified at HEAD. Quote it in the PR. Then run `python3 <kit_path>/bin/sdlc gate evidence-for-ticks . --spec <NNN>` and, only after that `verify`, `python3 <kit_path>/bin/sdlc gate green-at-head .`, quoting each last line; a failing gate blocks the push.
   If the user did not ask to commit, show the proposed branch, files and message, and ask; say that the verify gate has not run on a committed revision.
5. **Write the PR** from `.sdlc/templates/pr.md`, or from the repository's own template:
   - Link the spec or issue.
   - Paste the verification commands with their real outcomes.
   - State the risk and rollback, migrations and rollout order, and what remains unverified (remote-only checks, credentials, environments).
6. **Outward actions need approval.** Pushing, opening or merging a PR, publishing a package, deploying, posting to trackers: confirm each with the user, once per action, unless they authorized it explicitly in this task. Never enable auto-merge or force-push unless asked.
7. **Release** (when asked): release notes from the merged PRs, a version bump following the project's scheme, migration and rollback notes. Then the deploy steps from the plan, in rollout order.
8. **Close the spec**: once the PR is merged, set the spec's `Status: implemented`. If the spec was replaced, set `superseded by NNN`.
9. **Report**: the branch, commit SHAs, PR URL (if created), the gate results, the unverified remote checks, and what the human does next.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Tests passed before the last commit" | The gate is for the exact revision you ship. Run it again. |
| "Push now, CI will tell us" | Pushing is outward-facing and needs approval. And CI isn't a substitute for the local gate. |
| "`git add -A` is faster" | It ships unrelated changes and secrets. Stage explicit paths. |
| "Skip the rollback section, it's a small change" | One line ("revert the commit, no data change") is enough. Writing it proves you checked. |
| "Mark the remote checks as passed, they're equivalent" | Local isn't remote. Name what only the pipeline can verify. |

## Red flags

- The review verdict is missing or `REJECTED`, and the track requires one.
- The diff contains credentials, tokens or personal data. Stop, remove them, and tell the user. If anything was already pushed, rotate.
- A migration has no rollback or forward-fix plan.
- The PR mixes unrelated changes. Split it.

## Verification

- The final gate commands and their outcomes are listed for the shipped SHA.
- The diff was checked, with only intended files committed (list them).
- The PR body includes the verification, risk and rollback, and unverified items.
- Every outward action has a matching user approval in this session, or is listed as pending.

## Principles applied

evidence-over-claims, fail-safe-keep-work
