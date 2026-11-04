# Plan: `sdlc gate`

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-04

## Summary

Add a `gate` subcommand to `bin/sdlc` whose logic lives in a sibling module `bin/sdlc_gate.py` (imported inside `cmd_gate`, as `verify` does). Spec 004's `sdlc_verify.py` gets two small test-first changes, in their own task: a new `git_run(workdir, *args, input=None)` returning `(status, stdout)` with status `ok`, `fail`, `timeout` or `nogit` (`git_call` becomes a thin wrapper, so spec 004's callers don't change), and `green_reason(record, head)` with `green_at_head` equal to `green_reason(...) is None`, so there is one definition and the gate can say why. The gate makes its own `rev-parse` and `status` calls through `git_run`, so a git failure keeps its reason and fails closed. Four small, independent functions: digest and approve/approved, green-at-head, evidence-for-ticks. Riskiest parts: a normalisation that is exactly as strict as the contract says (too loose misses edits, too strict breaks ordinary work), and keeping every git failure on the fail side.

## Technical context

- Language / runtime: Python 3.9+, stdlib only (`hashlib`, `re`, `os`, `subprocess`, `tempfile`, `datetime`, `json`).
- Key dependencies: `git` for HEAD, status and `cat-file`; `bin/sdlc_verify.py` (spec 004) for `git_run`, `green_reason`. `bin/sdlc` has no `.py` extension and can't be imported, so `cmd_gate` passes `read_config`'s result and `safe_path` in: the entry point is `sdlc_gate.run(target, cfg, args, safe_path)`, and the module's own `GateError` wraps `safe_path` failures (as `sdlc_verify.resolve` does) and `cmd_gate` maps it to exit 2. `spec_dirs` is **not** reused: it reads only the top-level `spec_dir` and would raise on a non-string; the gate resolves `repos.<n>.spec_dir`, then the top-level one, then `specs`, with type checks.
- Storage: none new. `approve` rewrites two lines of one spec file.
- Testing: black-box `unittest` in `tests/test_gate.py` driving `bin/sdlc gate` in temp projects, plus unit calls of the module's pure functions (digest, parsers) with `sys.dont_write_bytecode` set before import.
- Constraints: POSIX; errors for `cmd_*` are returned as `(2, ["sdlc: error: ..."])`, never raised to `main()` (which would give exit 1): `cmd_gate` catches `SdlcError`, the module's own error, `OSError`, `UnicodeDecodeError` and `ValueError`. The parser entry is `add("gate", …, dir_=False)` with positional `name` then `dir`; an unknown name is rejected by `cmd_gate`. Output is printed with replacement for unencodable characters, after the write.
- Import: `cmd_gate` sets `sys.dont_write_bytecode` and imports `sdlc_gate` inside the function; `sdlc_gate` imports `sdlc_verify` itself, so a failed import of either affects only `gate` and `verify`.

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | No new state file, no config key, no hook; reuses spec 004's record and helpers. One module, four functions. |
| thin-vertical-slices | pass | Approve and approved first (one slice, because each proves the other), then the digest's sensitivity, then the other two gates, then skills. |
| prove-it-works | pass | Black-box tests, a truth table per gate, mutation checks, independent review. |

## Seams & blast radius

- Seams: `bin/sdlc` near `cmd_verify` (`cmd_gate`, parser entry with `name`, `dir`, `--spec`, `--repo`, `--by`); new `bin/sdlc_gate.py`; `bin/sdlc_verify.py` (`git_call` gains `input`, `green_at_head` delegates to a new `green_reason`; spec 004's tests must stay green).
- Callers / consumers affected: none yet. E1.4's hooks and E1.5's CI recipe will call the exit code. The `Approved` line format is a contract that `sdlc-analyze` now writes through the command.
- Skills and rules touched: `sdlc-analyze` (runs `approve` after the human's yes), `sdlc-implement` (readiness gate runs `gate approved`, with a legacy fallback that asks the human when the spec has no digest; an intended edit to an approved document, such as updating a task line, means asking the human and running `approve` again; the finish step runs `gate evidence-for-ticks` only, because the tree is still dirty there), `sdlc-ship` (`gate evidence-for-ticks`, and `gate green-at-head` after the post-commit `verify`), `sdlc-analyze` (step 6 runs `approve` and no longer writes the line by hand), the constitution (one rule), the tasks template (progress-log evidence format; baseline counts go in the log, not the `Verify` block), README, `adapters/RENDERING.md`, `DESIGN.md`.
- Contracts touched: new `contracts/gate.md`; the `Approved` line grammar in `core/templates/spec.md`'s comment.
- Migrations: none; specs 002–004 stay digest-less and fail `approved` by design (spec, Out of scope).

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A: per-file hashes of normalised text, combined digest and 12-hex prefixes on the `Approved` line | Names the changed file with no git history; one line, in the spec | Longer line; normalisation rules to maintain | chosen |
| B: digest in a separate `.sdlc/approvals/<NNN>.json` | Cleaner spec | A second state file that can drift; the spec says the Approved line (owner's choice) | rejected |
| C: use git (`git diff` vs the approval commit) to detect edits | No digest | Needs the approval to be committed first; commit hashes in a spec change the spec | rejected |
| D: hash raw files | Simple | Ticking a task or logging breaks the approval, so the gate would be turned off | rejected |

## Data model / contracts

- [contracts/gate.md](contracts/gate.md)

## Failure modes

| Failure | Handling |
|---|---|
| Spec folder missing, ambiguous, or `--spec` escaping the root | Exit 2 with the reason; no read of other files |
| `spec.md`, `plan.md` or `tasks.md` unreadable or not UTF-8 | Exit 2 (decode with strict errors; a binary file is a malformed document) |
| `Approved` line malformed or hand-edited | `approved` fails (`no approval digest`, or `approval digest does not match the documents`) |
| `--by` containing a comma, newline or comment opener, or empty | Exit 2, nothing written |
| `approve` write fails | Temp file removed, spec untouched, exit 2 (test with an injected failing replace) |
| `approve` on a symlinked spec | Refused, exit 2 |
| Two `approve` runs at once | Last writer wins (atomic rename); stated limit, as for `verify` |
| `git` missing, a failed or timed-out call | `green-at-head` and `evidence-for-ticks` exit 1 with the reason (`git not found`, `HEAD unresolved`, `git timed out`, `git status failed`, `git failed`), never pass; `approved` and `approve` don't use git |
| Cited commits missing (squash or rebase merge, shallow CI clone) | `evidence-for-ticks` fails; when a token is missing one extra `rev-parse --is-shallow-repository` call adds `(shallow repository: ...)` to each line; a stated limit |
| Document or record is not a regular file (FIFO), over its size cap (2 MiB document, 1 MiB record) | Document: exit 2; record: exit 1 `unreadable record`; checked with `os.path.isfile` and `getsize` before reading |
| `approve` on a spec with no or several `Status:`/`Approved:` lines before the first `## ` | Exit 2, nothing written |
| Output can't be encoded (`PYTHONIOENCODING=ascii`) | Printed with replacement; `approve` prints after the write succeeded |
| Draft spec with no plan | `approved` stops at the status check: exit 1, not 2 |
| Progress log has a huge number of lines | All hex tokens go to one `git cat-file --batch-check` call on stdin; only 7–40 hex tokens are collected, at most 2,000 distinct ones (more is a failure `too many revisions to check`) |
| Task id in a range that spans prefixes or reversed (`T012–T001`) | Treated as no range; the id must then appear as a token |
| Tasks file without a `## Progress log` heading | Every tick fails (there is no evidence) |
| CRLF files | Normalised to `\n` before hashing (NFR-003); `approve` keeps the spec's own line endings |

## Security & observability

- Checklists loaded: security.
- Decisions: no command from config, tasks or the record is ever run (FR-011); the only writer is `approve`, which writes one project file; names go into a spec line, so `--by` is restricted (no comma, newline, comment opener, length 80); no network. A hand-forged `Approved` line can't be told from a real one if it has the right digest: the digest proves the documents are unchanged, not who approved (stated limit).

## Test strategy

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| approve then approved pass; only the two lines change | CLI in a temp spec | integration | `python3 -B -m unittest tests.test_gate.Approve -v` |
| digest sensitivity (SC-001): edits that fail (a contract line, including text appended under a `## Progress log` heading in spec and plan, stray `Status:`/`Approved:` lines, a stray `· Status:` in the body), edits that pass, CRLF | CLI and pure `digest()` | integration + unit | `python3 -B -m unittest tests.test_gate.Digest -v` |
| approved failures: draft, no digest, legacy line, missing document, hand-edited digest; the real specs 002–004 | CLI on copies and on the repo's own specs | integration | `python3 -B -m unittest tests.test_gate.ApprovedFailures -v` |
| approve refusals, `--by` validation, atomic write, symlink, re-approve | CLI + injected replace | integration + unit | `python3 -B -m unittest tests.test_gate.ApproveRefusals -v` |
| green-at-head truth table (SC-002) with real `verify` records | CLI with real git | integration | `python3 -B -m unittest tests.test_gate.GreenAtHead -v` |
| evidence-for-ticks fixtures (SC-003), one `cat-file` call, the real tasks files of specs 002 and 003 (pass) and 004 (fails for T015–T017 and H1), `+`-suffixed and backticked hashes, checked boxes without an id | CLI with real git and fake git | integration | `python3 -B -m unittest tests.test_gate.Ticks -v` |
| CLI shape: unknown gate, `--spec` errors, `--by` on another gate, `--repo`, last-line grammar, isolation, no writes, symlinked CLI, no bytecode | CLI | integration | `python3 -B -m unittest tests.test_gate.Cli -v` |
| `git_run` statuses and `green_reason` reasons (spec 004's module, test first) | unit | unit | `python3 -B -m unittest tests.test_verify.GitRun tests.test_verify.GreenReason -v` |
| git failures fail closed (inside the GreenAtHead and Ticks rows) | fake `git` on PATH | integration | `python3 -B -m unittest tests.test_gate.GreenAtHead tests.test_gate.Ticks -v` |
| the module imports only the standard library and `sdlc_verify` (NFR-001) | scan the source | unit | `python3 -B -m unittest tests.test_gate.Imports -v` |
| skills, constitution, template and docs text (FR-014) | rendered install | unit | `python3 -B -m unittest tests.test_sdlc.GateSkills -v` |

## Rollout & rollback

- Rollout order: module and tests, then skill and doc text, then mutation checks and review. No live eval: the skills' adoption of the gate is a text rule whose effect, a blocked push, belongs to E1.4; this spec measures the commands (SC-001 to SC-004), not agent behaviour.
- Rollback: remove the subcommand and the sentences; the `Approved` line format is a superset of the free text before it.
- Value gate: none (no SC is a measured threshold on agent behaviour).

## Complexity justifications

None.
