# Plan: `sdlc verify`

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-04

## Summary

Add a `verify` subcommand to `bin/sdlc` whose logic lives in a sibling module `bin/sdlc_verify.py`, so the 923-line CLI grows by about 15 lines. It runs the configured commands through the shell with closed stdin, output sent to a temporary file, a process-group timeout, and only the file's tail read afterwards, then writes a content-free JSON record atomically. Riskiest part: stopping a hung command's process tree without hanging `verify` itself, and making the dirty flag meaningful.

## Technical context

- Language / runtime: Python 3.9+, stdlib only (`subprocess`, `os`, `signal`, `json`, `tempfile`, `time`, `datetime`, `collections`).
- Key dependencies: `git` on PATH for the revision (absent git means "no revision", never a crash).
- Storage: `.sdlc/evidence/verify.json`, one file, replaced atomically.
- Testing: `unittest` driving `bin/sdlc verify` as a subprocess in temp projects (black-box, as the existing tests do); fixture commands are `python3 -c` one-liners so tests are portable.
- Constraints: POSIX process groups (`start_new_session=True`, `os.killpg`); Windows is not a supported host (T012 adds that line to the README; today it only says Python 3.9+).
- Errors: `main()` turns any `SdlcError` into exit 1 (`bin/sdlc`), so `cmd_verify` catches `SdlcError` around config reading, `--repo` lookup, folder check and record write and returns `(2, [message])` itself; `cmd_*` already return `(code, lines)`.
- Import: `cmd_verify` imports `sdlc_verify` inside the function after setting `sys.dont_write_bytecode = True`, so other commands never depend on it and the kit stays unwritten (FR-013). Running `bin/sdlc` by path or through a symlink puts the real `bin/` first on `sys.path` (test T001b).
- Git: the module copies `git_read`'s flags (`--no-optional-locks -c core.fsmonitor=false`); it can't import them from `bin/sdlc` without a cycle. A repository with no commit counts as no revision.

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | One new file and one subcommand; no new config beyond `verify.timeout_seconds`. No retry, no parallelism, no output store. |
| thin-vertical-slices | pass | Green run first, then red, then each failure kind, then revision handling, workspace, skills. |
| prove-it-works | pass | Black-box tests with a red and a green fixture, a mutation check, and a live eval row (V1). |

## Seams & blast radius

- Seams: `bin/sdlc` near `cmd_next_spec` for the new `cmd_verify`; `build_parser` (one `add` line plus `--repo`, from the first slice); new `bin/sdlc_verify.py`; `read_config` (`bin/sdlc:179`) and `safe_path` (`bin/sdlc:113`, for `repos.<name>.path`) reused.
- Callers / consumers affected: none today. E1.3 `gate green-at-head` and E1.4 hooks will read the record; the contract (`contracts/record.md`) is their interface.
- Skills and rules touched: `sdlc-implement` (final gate, informational), `sdlc-debug`, `sdlc-ship` (after the commit, before push or PR) and `sdlc-review` (reads and quotes the record; it stays read-only, so it never runs the command), the constitution (one rule), `evals/scenarios.md` (row V1), the README command table and limits, `adapters/RENDERING.md` (command and exit-code table), `DESIGN.md` (tree), `.gitignore` handling for `.sdlc/evidence/` (below).
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

`.sdlc/evidence/` is local state. `sdlc install` already manages `.sdlc/`; the plan adds no ignore rule to the project's `.gitignore` (the kit never edits it). Because the record would otherwise make every later run dirty, the dirty check ignores `.sdlc/evidence/` (`:(exclude).sdlc/evidence`), tested with two runs in a row. A committed record names its revision, so it is stale from the next commit. Decision: do not edit the project's ignore file.

The record and the final line are read by a helper `green_at_head(record, head)` in the module, which E1.3 will reuse; it gives SC-003 a test.

## Data model / contracts

- [contracts/record.md](contracts/record.md)

## Failure modes

| Failure | Handling |
|---|---|
| Command hangs | `Popen.wait(timeout)`; on expiry the group is killed and `verify` stops waiting; recorded `timeout`; counted failed |
| Command spawns children that outlive it | The group kill covers them. A child that leaves the group (daemonises) isn't killed, but because output goes to a file and `verify` never waits on a pipe, `verify` can't hang on it (test T005) |
| `verify` is interrupted | SIGINT and SIGTERM handlers kill the running group, then exit |
| Command changes files or commits | Dirty is read again after the last command; a moved `HEAD` means no revision (FR-011) |
| Command reads stdin | Stdin is `/dev/null`, so it sees end of input |
| Huge output | It goes to a temporary file; only the last 8 KB are read and cut to 20 lines of 400 characters; the file is deleted |
| `git` missing, not a repo, or no commit | `revision: null`, `dirty: false`, final line says `(no revision, not verified at HEAD)`; commands still run |
| Launch error (`OSError`) | Recorded `not started` with the error text; counted failed. NUL or non-string commands are rejected as config errors beforehand |
| Record write fails (disk, permission) | Temporary file removed, old record untouched, results printed; exit 1 if a command failed, else 2 |
| Two `verify` runs at once | Last writer wins (atomic rename); no lock, the README's stated limit |
| Config invalid JSON, `commands.*` not a string, `verify.timeout_seconds` not a positive integer, missing `<dir>`, a repo path outside the root | Exit 2 with the reason, before anything runs |

## Security & observability

- Checklists loaded: security.
- Decisions: commands come only from config (FR-014); no argument or environment value reaches the shell (tested with hostile variables set); the record never holds output; the launch error text is `str(OSError)`, a path and a reason. A hand-written record can't be told from a real one (stated in the spec's Out of scope). No network.

## Test strategy

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| green run: exit 0, record, summary | `bin/sdlc verify` subprocess | integration | `python3 -m unittest tests.test_verify.GreenRun -v` |
| red run continues, tail printed, exit 1 | same | integration | `python3 -m unittest tests.test_verify.RedRun -v` |
| no command: exit 2, no record | same | integration | `python3 -m unittest tests.test_verify.NothingToRun -v` |
| timeout kills a group, including a child | same, `sleep` fixture | integration | `python3 -m unittest tests.test_verify.Timeout -v` |
| 127 (black-box) and launch error (patched launcher) | same, plus unit | integration | `python3 -m unittest tests.test_verify.CannotRun -v` |
| record shape, no output (SC-002) | read the record | integration | `python3 -m unittest tests.test_verify.Record -v` |
| failed write keeps the old record, removes the temp file (NFR-003) | call `write_record` with an injected failing replace | unit | `python3 -m unittest tests.test_verify.WriteFailure -v` |
| hostile environment and arguments run nothing (FR-014); nothing written outside the root (FR-013); default config works | black-box with `SDLC_VERIFY_COMMAND` etc. set, stat before and after | integration | `python3 -m unittest tests.test_verify.Isolation -v` |
| `green_at_head` truth table (SC-003) | helper | unit | `python3 -m unittest tests.test_verify.GreenAtHead -v` |
| revision, dirty, no revision, stale (SC-003) | temp git repos | integration | `python3 -m unittest tests.test_verify.Revision -v` |
| config errors | invalid config files | integration | `python3 -m unittest tests.test_verify.ConfigErrors -v` |
| `--repo` in a workspace | temp workspace | integration | `python3 -m unittest tests.test_verify.Workspace -v` |
| skills and rule text (FR-015) | rendered install | unit | `python3 -m unittest tests.test_sdlc.VerifySkills -v` |

## Rollout & rollback

- Rollout order: command and tests first, then skill text and rule, then eval row V1 and its live run, then a README capability line.
- Rollback: remove the subcommand and the sentences; the record is a local file nothing else reads yet.
- Value gate (SC-004): the live eval V1 (plain-language prompt, no skill named; added to the EvalRows pin) at n = 3 on `claude-opus-5-5` and `claude-sonnet-5-5`: the exact final line appears in the report in at least 5 of 6 runs. It can only be measured once the command exists, so there is no pre-build pilot; the command stays useful to E1.3 whatever the result, and the owner accepts the build cost on that basis (H1). Decision rule, written before any run: below 5 of 6, the skill wording is strengthened and V1 re-run once; if it still misses, the story is reported as met for the command and not met for skill adoption.

## Complexity justifications

None.
