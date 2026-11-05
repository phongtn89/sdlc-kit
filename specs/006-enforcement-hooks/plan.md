# Plan: Enforcement hooks for Claude Code

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-05

## Summary

A new module `bin/sdlc_hooks.py` holds both halves: the runtime of the three hooks (`sdlc hook bash|edit|stop`, reading the host's JSON on stdin and calling the gates in process) and the merge, hash and removal of the kit's entries in `.claude/settings.json`. `bin/sdlc` gains `cmd_hook`, a `settings` key in the lock, and small additions to `sync`, `check` and `uninstall`. Each rendered entry is a one-line shell command that runs the kit by its recorded absolute path, or exits 0 when the kit is gone. Riskiest parts: parsing a shell command line well enough to find `git push` without blocking innocent commands, and keeping every non-gate failure on the allow side, because the host blocks on exit code 2 and python exits 2 for a missing script.

## Technical context

- Language / runtime: Python 3.9+, stdlib only (`json`, `shlex`, `re`, `os`, `hashlib`, `types`).
- Key dependencies: `sdlc_gate.run(target, cfg, args, safe_path)` and `sdlc_verify.git_run` (specs 004, 005), called in process with a `types.SimpleNamespace` of the gate's arguments; `bin/sdlc`'s `sync`, `read_lock`, `check`, `uninstall`, `read_config`, `safe_path`, `write_file`.
- Storage: lock gains `settings: {".claude/settings.json": {"hooks": {"bash": sha, "edit": sha, "stop": sha}, "created": bool}}`; `read_lock` defaults it to `{}`, so older locks stay valid.
- Testing: black-box `unittest` in `tests/test_hooks.py`: the rendered command from a real install is run with `sh -c` and pinned hook JSON on stdin in temp git projects built with real `install`, `verify` and `gate approve`; pure unit tests for the command parser, source classifier and settings merge.
- Target: Claude Code hooks. Host contract in [contracts/hooks.md](contracts/hooks.md), pinned as fixtures in `tests/fixtures/hooks/`.
- Constraints: POSIX shell for the rendered command; a hook entry carries `"timeout": 60`; `main()` prints `cmd_*` lines to stdout only, so `cmd_hook` prints its own stderr and stdout and returns `(code, [])`.

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | No new config key beyond the already-decided `enforce`; the active spec comes from the branch, the source tree is a fixed rule, gates are reused in process. One new module. |
| thin-vertical-slices | pass | Push-on-red first, end to end through the rendered command (the riskiest path), then edit, stop, fail-open, then rendering and lock handling. |
| prove-it-works | pass | Every rule is tested through the real rendered command; mutation checks; a live session eval (SC-003); independent review. |

## Seams & blast radius

- Seams: `bin/sdlc` (`sync` after the blocks step, `cmd_check`, `cmd_uninstall`, `read_lock`, parser entry `hook` with `dir_=False`, positional `name`); new `bin/sdlc_hooks.py`; `docs`: README, `adapters/RENDERING.md`, `DESIGN.md`, ADR-0003 consequences line; `core/skills/sdlc-implement` and `sdlc-ship` (one sentence each saying a refusal is the cue to run `verify` or get approval, not to work around it).
- Callers / consumers affected: every project that installs the kit (only when `enforce` is `true`); `sdlc check` gains a kit-path-missing line (all installs); the lock format gains a defaulted key.
- Contracts touched: new `contracts/hooks.md` (host input, outputs, entry shape, lock key, messages).
- Migrations: none. Existing installs with `enforce` absent render and remove nothing.

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A: three entries in `.claude/settings.json`, each running `sdlc hook <name>` by the kit's absolute path, gates called in process | Matches the roadmap and ADR-0003; one source of truth for logic; path outside the project (decision 3) | The settings file is shared with the project, so merge, hash and removal logic is needed | chosen |
| B: separate generated file (`.claude/settings.local.json`) | No merge | Not what the roadmap says; local files are often git-ignored so a teammate loses the guard; still a merge with the user's local file | rejected |
| C: hook command is `python3 <path>` directly | Shorter | A missing kit makes python exit 2, which the host reads as a refusal: a trap (FR-011) | rejected; the shell wrapper exits 0 |
| D: gates run as subprocesses of `bin/sdlc` | Isolation | Slower, two interpreter starts, no benefit: the gates already bound their git calls | rejected |
| E: detect pushes by regex on the raw command | Simple | Matches `echo "git push"` and misses `git -C x push`; blocks on a guess | rejected; `shlex` with operator splitting, fail open when it cannot tokenise |

## Data model / contracts

- [contracts/hooks.md](contracts/hooks.md)

## Failure modes

| Failure | Handling |
|---|---|
| Kit folder moved or deleted | The wrapper finds no script, prints one line, exits 0; `sdlc check` reports `KIT-PATH-MISSING`; `update` from the new kit re-renders the path |
| Python crashes in a hook | Any exception is caught at the top of `cmd_hook`: allow, one-line note; an uncaught crash exits 1 (non-blocking) |
| Hook input is not JSON, lacks `tool_name`, or has an unexpected shape | Allow with a note |
| Gate exits 2 (error) or the in-process call raises | Allow with the gate's error line |
| Gate exits 1 | Bash and edit hooks refuse (exit 2, reason on stderr); stop hook warns (exit 0) |
| Host cancels a slow hook at `timeout` | The host's behaviour (non-blocking); the gates bound their own git calls at 20 s each |
| `.claude/settings.json` invalid JSON, `hooks` not an object, an event value not a list | Nothing written, `SKIP` line naming why, install exits 2 (`skipped`) |
| Settings file is a symlink | Refused like any other unmanaged write: `safe_path` rejects escaping paths; a symlink to a file inside the project is followed by `write_file`, as for other kit files (same limit) |
| User edited a kit entry by hand | `SKIP` unless `--force`; `check` reports drift; uninstall keeps it (`KEPT`) |
| User deleted a kit entry | `update` adds it back (like a deleted kit file) |
| Two projects on one kit path | Entries embed the one kit path; each project's lock records it |
| Branch name has two numbers (`fix/006-x-for-003-y`) | The first `NNN-` after a slash or at the start wins; a folder that does not match exactly one spec means no active spec, so the hook allows |
| Detached HEAD, no git, bare repo | `git_run` status is not `ok` or the branch is `HEAD`: no active spec, allow |
| Compound commands, `bash -c '...'`, `sudo`, `env X=1 git push` | Operator-split segments; leading assignments and the wrappers `sudo`, `env`, `command`, `time`, `nohup`, `exec` skipped; a `sh`/`bash`/`zsh -c <string>` argument is parsed once more (depth 2); anything deeper or built from `$(...)`, `eval`, aliases or scripts is the stated gap |
| `shlex` cannot tokenise (unbalanced quote) | Allow with a note (never a guess) |

## Security & observability

- Checklists loaded: security.
- Decisions: the hooks write nothing in the project (FR-012); the command line in settings contains only the quoted kit path and a fixed name (the kit path is `shlex.quote`d, so a path with spaces or quotes is safe); hook input is data, never evaluated or passed to a shell; refusal messages quote the gate's own text, never the command or file content from the input beyond the file's relative path. A refusal is a protection against drift, not against a hostile agent: the agent can edit `.claude/settings.json` (it is not source in the classifier). `sdlc check` and CI (E1.5) detect that; stated limit.

## Test strategy

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| Push on red refused, on green allowed, through the rendered command (S1, SC-001) | install + `sh -c` of the settings command + fixture JSON | integration | `python3 -B -m unittest tests.test_hooks.BashHook -v` |
| Command parsing table: chains, `-C`, wrappers, `-c`, `--help`, quotes, unbalanced | `sdlc_hooks.pushes(command)` | unit | `python3 -B -m unittest tests.test_hooks.Parse -v` |
| Edit refused without approval, allowed with; source classifier; active spec from branch (S2) | real temp repo on `feat/NNN-x` | integration + unit | `python3 -B -m unittest tests.test_hooks.EditHook tests.test_hooks.Classify -v` |
| Stop warns, never blocks (S4) | same | integration | `python3 -B -m unittest tests.test_hooks.StopHook -v` |
| Fail-open cases: kit moved, bad JSON, gate error, crash (S5) | `sh -c` with the kit folder renamed; stdin garbage | integration | `python3 -B -m unittest tests.test_hooks.FailOpen -v` |
| Settings merge: preserves project values and indent, idempotent, invalid shapes, hand edits, deleted entry, created flag, enforce off removes (S3, SC-002) | pure functions and CLI | unit + integration | `python3 -B -m unittest tests.test_hooks.Settings tests.test_hooks.Install -v` |
| `check` drift and `KIT-PATH-MISSING`; uninstall exactness; Copilot-only and workspace notes | CLI | integration | `python3 -B -m unittest tests.test_hooks.Lifecycle -v` |
| Host format pinned: fixtures for each event | files in `tests/fixtures/hooks/`, a re-check row in `evals/scenarios.md` | unit | `python3 -B -m unittest tests.test_hooks.Fixtures -v` |
| Module imports stdlib and sibling modules only (NFR-001); no bytecode in the kit | scan | unit | `python3 -B -m unittest tests.test_hooks.Imports -v` |
| Text of skills and docs (FR-014) | rendered install | unit | `python3 -B -m unittest tests.test_sdlc.HookDocs -v` |
| Live: push on red refused and on green allowed in a real Claude Code session (SC-003) | scratch project, `evals/run.py` pattern of spec 004 | e2e | the eval row H1 |

## Rollout & rollback

- Rollout order: module and tests (runtime first, then settings), lifecycle, docs, mutation checks, review, live eval. `enforce` stays off by default, so merging changes nothing for existing installs.
- Rollback: set `enforce` to false and run `update` (removes the entries), or revert the commit; the extra lock key is ignored by older kits.
- Value gate: SC-003 is the check that the host actually refuses; it runs before merge.

## Complexity justifications

None.
