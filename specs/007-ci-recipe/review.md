VERDICT: APPROVED

# Review: spec 007 CI recipe (E1.5)

Two independent passes by fresh read-only agents (2026-11-05), against the mini-spec, with the template's steps run under `sh -c` and `bash -e` in scratch projects outside the repository.

## Pass 1: VERDICT: REJECTED

| Id | Finding | Outcome |
|---|---|---|
| D1 (medium) | `Check install` swallowed every `sdlc check` failure that printed no drift line (no lock, corrupt lock, a crash) | Fixed test-first: the step keeps the exit code and fails unless the only reason is a `KIT-PATH-MISSING` line |
| D2 (low) | The branch-number parse took the last `NNN-` segment, the hooks take the first | Fixed test-first: first segment wins |
| Advisories | no `permissions`, credentials persisted in the checkouts; README silent on draft specs and fork or Dependabot pull requests | Fixed (read-only permissions, `persist-credentials: false`, README notes) |

## Pass 2: VERDICT: APPROVED

D1 and D2 reproduced and closed under both shells, 14 branch names checked against `BRANCH_RE`, a `KIT-PATH-MISSING` line cannot hide an error, no new false pass or false failure. Low advisories, not fixed: drift lines print twice in the CI log; `OUTDATED` and `NOTE` lines never fail the step (existing `check` behaviour); a stderr line starting with `MISSING ` would count as drift (fails safe).

Left as stated limits: a missing spec folder skips the spec gates with a message; workspaces (`repos`) are not checked per repo; actions are pinned to a tag, not a SHA.

Not covered: a real GitHub runner (`actions/checkout`, `permissions`, secrets on forks), `verify` and `green-at-head` inside the reviewer's fixtures (the tests run them).
