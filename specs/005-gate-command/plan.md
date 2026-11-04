# Plan: `sdlc gate`

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-04

## Summary

Add a `gate` subcommand to `bin/sdlc` whose logic lives in a sibling module `bin/sdlc_gate.py` (imported inside `cmd_gate`, as `verify` does), reusing `sdlc_verify.git_state` and `sdlc_verify.green_at_head`. Four small, independent functions: digest and approve/approved, green-at-head, evidence-for-ticks. Riskiest parts: a normalisation that is exactly as strict as the contract says (too loose misses edits, too strict breaks ordinary work), and keeping every git failure on the fail side.

## Technical context

- Language / runtime: Python 3.9+, stdlib only (`hashlib`, `re`, `os`, `subprocess`, `tempfile`, `datetime`, `json`).
- Key dependencies: `git` for HEAD, status and `cat-file`; `bin/sdlc_verify.py` (spec 004) for `git_state`, `green_at_head`, `write_record`-style atomic writing; `bin/sdlc` for `read_config`, `safe_path`, `check_target`, `spec_dirs`.
- Storage: none new. `approve` rewrites two lines of one spec file.
- Testing: black-box `unittest` in `tests/test_gate.py` driving `bin/sdlc gate` in temp projects, plus unit calls of the module's pure functions (digest, parsers) with `sys.dont_write_bytecode` set before import.
- Constraints: POSIX; errors for `cmd_*` are returned as `(2, ["sdlc: error: …"])`, never raised to `main()` (which would give exit 1).
- Import: `cmd_gate` sets `sys.dont_write_bytecode` and imports `sdlc_gate` inside the function; `sdlc_gate` imports `sdlc_verify` itself, so a failed import of either affects only `gate` and `verify`.

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | No new state file, no config key, no hook; reuses spec 004's record and helpers. One module, four functions. |
| thin-vertical-slices | pass | Approve and approved first (one slice, because each proves the other), then the digest's sensitivity, then the other two gates, then skills. |
| prove-it-works | pass | Black-box tests, a truth table per gate, mutation checks, independent review. |

## Seams & blast radius

- Seams: `bin/sdlc` near `cmd_verify` (`cmd_gate`, parser entry with `name`, `dir`, `--spec`, `--repo`, `--by`); new `bin/sdlc_gate.py`; `bin/sdlc_verify.py` unchanged except nothing (the helpers are already importable).
- Callers / consumers affected: none yet. E1.4's hooks and E1.5's CI recipe will call the exit code. The `Approved` line format is a contract that `sdlc-analyze` now writes through the command.
- Skills and rules touched: `sdlc-analyze` (runs `approve` after the human's yes), `sdlc-implement` (readiness gate runs `gate approved`; finish runs the two other gates), `sdlc-ship` (the two other gates), the constitution (one rule), the tasks template (progress-log note), README, `adapters/RENDERING.md`, `DESIGN.md`.
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
| `git` missing, a failed or timed-out call | `green-at-head` and `evidence-for-ticks` exit 1 with the reason (never pass); `approved` and `approve` don't use git |
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
| approve then approved pass; only the two lines change | CLI in a temp spec | integration | `python3 -m unittest tests.test_gate.Approve -v` |
| digest sensitivity (SC-001): edits that fail, edits that pass, CRLF | CLI and pure `digest()` | integration + unit | `python3 -m unittest tests.test_gate.Digest -v` |
| approved failures: draft, no digest, legacy line, missing document, hand-edited digest; the real specs 002–004 | CLI on copies and on the repo's own specs | integration | `python3 -m unittest tests.test_gate.ApprovedFailures -v` |
| approve refusals, `--by` validation, atomic write, symlink, re-approve | CLI + injected replace | integration + unit | `python3 -m unittest tests.test_gate.ApproveRefusals -v` |
| green-at-head truth table (SC-002) with real `verify` records | CLI with real git | integration | `python3 -m unittest tests.test_gate.GreenAtHead -v` |
| evidence-for-ticks fixtures (SC-003), one `cat-file` call | CLI with real git and fake git | integration | `python3 -m unittest tests.test_gate.Ticks -v` |
| CLI shape: unknown gate, `--spec` errors, `--by` on another gate, `--repo`, last-line grammar, isolation, no writes, symlinked CLI, no bytecode | CLI | integration | `python3 -m unittest tests.test_gate.Cli -v` |
| git failures fail closed | fake `git` on PATH | integration | `python3 -m unittest tests.test_gate.GitFailures -v` |
| skills, constitution, template and docs text (FR-014) | rendered install | unit | `python3 -m unittest tests.test_sdlc.GateSkills -v` |

## Rollout & rollback

- Rollout order: module and tests, then skill and doc text, then mutation checks and review. No live eval: the skills' adoption of the gate is a text rule whose effect, a blocked push, belongs to E1.4; this spec measures the commands (SC-001 to SC-004), not agent behaviour.
- Rollback: remove the subcommand and the sentences; the `Approved` line format is a superset of the free text before it.
- Value gate: none (no SC is a measured threshold on agent behaviour).

## Complexity justifications

None.
