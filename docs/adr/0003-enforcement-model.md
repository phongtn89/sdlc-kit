# ADR-0003: Enforcement is opt-in and sits as high on the ladder as each host allows

Status: accepted <!-- proposed | accepted | superseded by ADR-NNNN -->
Date: 2026-11-04 · Deciders: phong.ngo.vn (scope and opt-in chosen in chat, 2026-11-04) · Related: [roadmap](../roadmap/layers-plan.md) epic E1, story E1.1

## Context

The kit's rules are mostly prose (ladder level 0) and its budgets are self-reported. The roadmap's evidence: spec 001 was built before its value gate failed, and analyze passes did not converge on spec 003. Prose decays under long context; a rule that matters needs a mechanism the agent cannot talk its way past.

**The ladder** (cheapest first, strongest last): 0 prose · 1 template field the agent fills in · 2 tool permissions (what the agent can do) · 3 hooks that intercept tool calls · 4 a controlled write path · 5 the program runs the check and the agent quotes it · 6 a CI required check or ruleset.

Constraints: Python 3.9 stdlib only, offline, no server (see ADR-0002). Hooks exist on Claude Code only. Existing installs must not change behaviour.

## Decision

1. **Opt-in.** A switch `enforce` in `.sdlc/config.json`, **off by default**, like `usage`. Only the JSON value `true` turns it on. Off means no hook is rendered and `sdlc gate` still works when called by hand or by CI.
2. **v1 scope: four "must never happen" rules**, each placed at a target level:

| Must never happen | Target | Mechanism | Story |
|---|---|---|---|
| Push while tests are red | Level 5 + 3 | `bin/sdlc verify` writes an evidence record at `HEAD`; `gate green-at-head` reads it; a `PreToolUse` hook blocks `git push` and `gh pr create` without it | E1.2, E1.3, E1.4 |
| Source edit on a T3 feature without approval | Level 5 + 3 | `gate approved` checks the `Approved` line **and** the digest of spec, plan and tasks recorded at approval; a hook blocks edits under the source tree without it | E1.3, E1.4 |
| Task ticked without evidence | Level 5 + 1 | `gate evidence-for-ticks`; a `Stop` hook warns (warns, does not block, to avoid trapping a session) | E1.3, E1.4 |
| Reviewer able to write | Level 2 | Read-only roles are already rendered as tool allow-lists (`tools: Read, Grep, Glob`); E2.1 may add allow-listed check commands | done; E2.1 |

   Out of v1: weakened tests, remediation-loop caps, secrets in the environment, untrusted ticket text, and merges to the default branch (the last belongs to branch protection, level 6, outside the kit).
3. **Gates run from the kit, not from the project.** The hook and CI call `bin/sdlc` by the path in `.sdlc/lock.json`, so an agent cannot satisfy a gate by editing a copy inside the project. `sdlc check` reports a changed kit path.
4. **CI is the common floor.** Level 6 (a workflow running `sdlc lint`, `sdlc check` and the gates) works for any host and is the required-check route for Copilot (E1.5).

## What each host gets

| Host | Levels the kit uses | Not available |
|---|---|---|
| Claude Code | 2 (role tool lists), 3 (three hooks), 5 (`verify`, `gate`), 6 (CI) | 4 |
| GitHub Copilot | 2 (role tool lists, as rendered), 5 (run by hand or by CI), 6 (CI) | 3: no equivalent hook; the kit does not pretend parity |

Level 0 and 1 stay in the skills and templates for every host.

## Consequences

- Stories E1.2 to E1.7 are specified from this table; each rule needs a test that fails when its mechanism is removed (E1.7).
- Hooks are internal-format dependent (hook JSON on stdin, exit code 2 blocks). They get pinned fixtures and a re-check row, as the usage metric does.
- A blocking hook can trap a session if its check is wrong. v1 blocks only on a gate result that is computed, never on a guess, and `Stop` only warns.
- `enforce` on by default is rejected for now: it changes every existing install; revisit after E1.7 shows the hooks hold.

## Alternatives considered

- **Prose only (status quo):** no cost, and the evidence above says it drifts.
- **On by default:** stronger, but a surprise for existing installs.
- **Rust or another compiled gate:** raised and deferred; tamper resistance is reachable in Python through decision 3.
