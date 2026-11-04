# Tasks: `sdlc gate`

Inputs: [spec.md](spec.md), [plan.md](plan.md), [contracts/gate.md](contracts/gate.md) · Status: draft · Created: 2026-11-04 · Branch: `feat/005-gate-command`

Verify (kit root):
- Narrow: `python3 -B -m unittest tests.test_gate -v` (helper `run()` in `tests/test_gate.py`, 30 s timeout)
- Full: `python3 -B -m unittest discover -s tests -t .` (baseline 286 OK at `49717d4`) · `python3 bin/sdlc lint`

Legend: `- [ ] T001 [P?] [S1] Description — files: … — verify: … — blocked-by: T00x`. Check a box only with evidence. Usage lines are off for this feature.

## S2 and S1: Approve, then approved (P1)

- [ ] T001 [S2] Tracer: `sdlc gate approve <dir> --spec <NNN> --by <name>` on a draft spec with plan and tasks writes `Status: approved` and the `Approved` line in the contract format (combined digest and the three 12-hex prefixes), prints the PASS line, exit 0; no other byte of `spec.md` changes. New module `bin/sdlc_gate.py` (imported in `cmd_gate`, which sets `sys.dont_write_bytecode`, returns `(2, …)` on errors), parser entry — files: `bin/sdlc`, `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.Approve -v` (RED first: unknown command) — blocked-by: H1
- [ ] T002 [S1] `gate approved --spec <NNN>` passes after `approve`, and when the status was set to `implemented` — files: `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.Approve -v` — blocked-by: T001
- [ ] T003 [S1] Digest sensitivity (SC-001): after approval these make `approved` fail and name the file — a requirement edit, a plan line, a task description, a new task; these pass — ticking a box, a new progress-log line, status to `implemented`, CRLF line endings throughout; pure `digest()` is reproducible across line endings (NFR-003) — files: `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.Digest -v` — blocked-by: T002
- [ ] T004 [S1] Failures: a draft spec, no digest (empty template line, free-text line), the real legacy `Approved` lines of specs 002, 003, 004, a hand-edited digest with matching prefixes, a missing `plan.md` or `tasks.md` (exit 2), a non-UTF-8 document (exit 2) — files: `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.ApprovedFailures -v` — blocked-by: T002
- [ ] T005 [S2] Approve refusals and safety: status `implemented`, `rejected …`, `superseded by …` refused (exit 2, file untouched); missing plan or tasks; `--by` empty, with a comma, a newline, `<!--`, over 80 characters; a symlinked spec; re-approve replaces the digest; the trailing HTML comments of the old lines are kept; a failed write (injected replace) leaves the spec and removes the temp file — files: `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.ApproveRefusals -v` — blocked-by: T001

## S3 and S4: The other two gates (P1)

- [ ] T006 [S3] `gate green-at-head` truth table with real `verify` records and real git (SC-002): pass; a new commit; a record taken dirty; a tree changed after the record; a failed command; no record; unreadable JSON; no revision; the record's commands are never run (a record whose command text would create a marker file) — files: `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.GreenAtHead -v` — blocked-by: T001
- [ ] T007 [S4] `gate evidence-for-ticks` (SC-003): ticks covered by a single id, a list, ranges (`T001–T012`, `T001-T012`, `T001–012`), human-step ids; a tick whose revision is not in git, a tick with no log line, a tasks file with no ticks (pass), no `## Progress log` heading (fails); exactly one `cat-file` call (fake git logs it) — files: `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.Ticks -v` — blocked-by: T001

## Cross-cutting (P1 and P2)

- [ ] T008 [S5] CLI shape: unknown gate, missing or ambiguous or escaping `--spec`, `--by` given to another gate, missing `--by` for `approve`, unknown `--repo` and `--repo` resolution (the repo's spec folder and record), the last line grammar for every gate, hostile environment variables run nothing, no new files outside the spec on `approve` and none at all on other gates (before and after listings), the symlinked CLI works, no `__pycache__` in the kit — files: `bin/sdlc`, `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.Cli -v` — blocked-by: T005, T006, T007
- [ ] T009 [S3, S4] Git failures fail closed: a fake `git` on PATH that fails or is absent makes `green-at-head` and `evidence-for-ticks` exit 1 with a reason, never 0; git call counts stay within three — files: `bin/sdlc_gate.py`, `tests/test_gate.py` — verify: `python3 -B -m unittest tests.test_gate.GitFailures -v` — blocked-by: T006, T007
- [ ] T010 [S5] Skill, constitution, template and docs text (RED first, one test each): `sdlc-analyze` runs `gate approve --by <name>` only after the human's explicit approval; `sdlc-implement`'s readiness gate runs `gate approved`, its finish step runs `gate evidence-for-ticks` and `gate green-at-head`; `sdlc-ship` the same two; one constitution rule; the tasks template's progress-log comment states the evidence format; README command table, `adapters/RENDERING.md` table, `DESIGN.md`, `core/templates/spec.md` Approved-line comment — files: `core/skills/sdlc-analyze/SKILL.md`, `core/skills/sdlc-implement/SKILL.md`, `core/skills/sdlc-ship/SKILL.md`, `core/constitution.md`, `core/templates/tasks.md`, `core/templates/spec.md`, `README.md`, `adapters/RENDERING.md`, `DESIGN.md`, `tests/test_sdlc.py` — verify: `python3 -B -m unittest tests.test_sdlc.GateSkills -v` and `python3 bin/sdlc lint` — blocked-by: T008
- [ ] T011 Mutation check: remove in turn the digest comparison, the per-file prefix check, the commit-exists check, the record read, the still-clean tree check, and the fail-closed git handling; each makes at least one test fail; restore — files: none kept — verify: six runs of `python3 -B -m unittest tests.test_gate`, each with a failure, recorded in the progress log — blocked-by: T003, T004, T005, T009
- [ ] T012 Independent review by a fresh read-only agent (`VERDICT:` line), fix findings test-first, then run full gates — files: `specs/005-gate-command/review.md` — verify: `VERDICT: APPROVED`, full suite and lint green — blocked-by: T010, T011

## Human steps

- [ ] H1 Approve implementation after `sdlc-analyze` (the T3 gate) — owner: phong.ngo.vn — T001 waits for it
- [ ] H2 Approve merge (`sdlc-ship`; merges need explicit approval) — owner: phong.ngo.vn

## Progress log

- 2026-11-04 `791f7dd` — spec drafted and clarified (digest on the Approved line, evidence = log line plus a real commit; both chosen by phong.ngo.vn).
