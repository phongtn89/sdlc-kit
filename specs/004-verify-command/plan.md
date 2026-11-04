# Plan: `sdlc verify`

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-04

## Summary

Add a `verify` subcommand to `bin/sdlc` whose logic lives in a sibling module `bin/sdlc_verify.py`, so the 915-line CLI grows by about 15 lines. It runs the configured commands through the shell with closed stdin, a process-group timeout and a bounded output tail, then writes a content-free JSON record atomically. Riskiest part: stopping a hung command's whole process tree and not leaking output into the record.

## Technical context

- Language / runtime: Python 3.9+, stdlib only (`subprocess`, `os`, `signal`, `json`, `tempfile`, `time`, `datetime`, `collections`).
- Key dependencies: `git` on PATH for the revision (absent git means "no revision", never a crash).
- Storage: `.sdlc/evidence/verify.json`, one file, replaced atomically.
- Testing: `unittest` driving `bin/sdlc verify` as a subprocess in temp projects (black-box, as the existing tests do); fixture commands are `python3 -c` one-liners so tests are portable.
- Constraints: POSIX process groups (`start_new_session=True`, `os.killpg`); Windows is not a supported host (README).

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | One new file and one subcommand; no new config beyond `verify.timeout_seconds`. No retry, no parallelism, no output store. |
| thin-vertical-slices | pass | Green run first, then red, then each failure kind, then revision handling, workspace, skills. |
| prove-it-works | pass | Black-box tests with a red and a green fixture, a mutation check, and a live eval row (V1). |

## Seams & blast radius

- Seams: `bin/sdlc:cmd_next_spec` area for the new `cmd_verify`; `build_parser` (one `add` line plus `--repo`); new `bin/sdlc_verify.py`; `read_config` (`bin/sdlc:179`) reused for config.
- Callers / consumers affected: none today. E1.3 `gate green-at-head` and E1.4 hooks will read the record; the contract (`contracts/record.md`) is their interface.
- Skills and rules touched: `sdlc-implement`, `sdlc-review`, `sdlc-ship`, `sdlc-debug` (one sentence each), the constitution (one rule), `evals/scenarios.md` (row V1), `.gitignore` handling for `.sdlc/evidence/` (below).
- Contracts touched: new, `contracts/record.md`. No existing contract changes.
- Migrations: none. Existing installs get the command after `sdlc update`.

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A: shell commands from config, sequential, record + tail | Matches how projects already write `commands`; simplest | Shell parsing is the project's own; POSIX only | chosen |
| B: split with `shlex`, no shell | No shell injection surface | Breaks `cd x && make`, env prefixes, pipes that projects already use | rejected |
| C: run commands in parallel | Faster | Output interleaving, shared ports and files; the spec says sequential | rejected |
| D: put the logic in `bin/sdlc` | One file | Pushes the CLI past 930 lines and mixes concerns | rejected; sibling module |
| E: record the full output | Easier debugging | Secrets and size in a file that gets read by gates; NFR-002 | rejected; tail printed only |

`.sdlc/evidence/` is local state. `sdlc install` already manages `.sdlc/`; the plan adds no ignore rule to the project's `.gitignore` (the kit never edits it). The consequence is that an agent could commit the record; the record names its revision, so a committed copy is stale by the next commit and the dirty flag covers the rest. Decision: document it, do not edit the project's ignore file.

## Data model / contracts

- [contracts/record.md](contracts/record.md)

## Failure modes

| Failure | Handling |
|---|---|
| Command hangs | Time limit; the process group is killed; recorded `timeout`; counted failed |
| Command spawns children that outlive it | The group kill covers them; a child that leaves the group (daemonises) is a stated limit |
| Command reads stdin | Stdin is `/dev/null`, so it sees end of input |
| Huge output | Only a bounded deque of the last 20 lines is kept; each line truncated to 400 characters before it enters the deque |
| `git` missing or not a repo | `revision: null`, `dirty: false`, final line says `(no revision)`; commands still run |
| Record write fails (disk, permission) | Old record untouched; message; exit 2 |
| Two `verify` runs at once | Last writer wins (atomic rename); no lock, the README's stated limit |
| Config invalid JSON or `verify.timeout_seconds` not a positive integer | Exit 2 with the reason, before anything runs |

## Security & observability

- Checklists loaded: security.
- Decisions: commands come only from config (FR-014); no argument or environment value reaches the shell; the record never holds output; the launch error text is `str(OSError)` which holds a path and a reason, never output. No network.

## Test strategy

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| green run: exit 0, record, summary | `bin/sdlc verify` subprocess | integration | `python3 -m unittest tests.test_verify.GreenRun -v` |
| red run continues, tail printed, exit 1 | same | integration | `python3 -m unittest tests.test_verify.RedRun -v` |
| no command: exit 2, no record | same | integration | `python3 -m unittest tests.test_verify.NothingToRun -v` |
| timeout kills a group, including a child | same, `sleep` fixture | integration | `python3 -m unittest tests.test_verify.Timeout -v` |
| 127 and launch error | same | integration | `python3 -m unittest tests.test_verify.CannotRun -v` |
| record shape, atomic write, no output (SC-002) | read the record | integration | `python3 -m unittest tests.test_verify.Record -v` |
| revision, dirty, no revision, stale (SC-003) | temp git repos | integration | `python3 -m unittest tests.test_verify.Revision -v` |
| config errors | invalid config files | integration | `python3 -m unittest tests.test_verify.ConfigErrors -v` |
| `--repo` in a workspace | temp workspace | integration | `python3 -m unittest tests.test_verify.Workspace -v` |
| skills and rule text (FR-015) | rendered install | unit | `python3 -m unittest tests.test_sdlc.VerifySkills -v` |

## Rollout & rollback

- Rollout order: command and tests first, then skill text and rule, then eval row V1 and its live run, then a README capability line.
- Rollback: remove the subcommand and the sentences; the record is a local file nothing else reads yet.
- Value gate (SC-004): the live eval V1 at n = 3 on two models, at least 5 of 6 runs quote the final line. Decision rule written now, before any run: below 5 of 6, the skill wording is strengthened and V1 re-run once; if it still misses, the story is reported as met for the command and not met for the skill adoption.

## Complexity justifications

None.
