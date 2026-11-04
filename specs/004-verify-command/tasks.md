# Tasks: `sdlc verify`

Inputs: [spec.md](spec.md), [plan.md](plan.md), [contracts/record.md](contracts/record.md) · Status: draft · Created: 2026-11-04 · Branch: `feat/004-verify-command`

Verify (kit root):
- Narrow: `python3 -m unittest tests.test_verify -v`
- Full: `python3 -m unittest discover -s tests -t .` (baseline 236 OK at `bcaeb62`) · `python3 bin/sdlc lint`

Legend: `- [ ] T001 [P?] [S1] Description — files: … — verify: … — blocked-by: T00x`. Check a box only with evidence. Usage lines are off for this feature (`usage.enabled` is not set in this repository).

## S1: Green run (P1)

- [ ] T001 [S1] Tracer: `sdlc verify <dir>` runs `commands.test` (a `python3 -c "pass"` fixture), exits 0, writes `.sdlc/evidence/verify.json` with version, times, revision, dirty and one command entry, prints the per-command line and the final `PASSED` line. New module `bin/sdlc_verify.py`, `cmd_verify` and parser entry — files: `bin/sdlc`, `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.GreenRun -v` (RED first: unknown command) — blocked-by: H1
- [ ] T002 [S1] Fixed order and skipping: all five commands run in `test, lint, typecheck, build, integration` order, empty ones skipped; each runs once; stdin is closed (a fixture that reads stdin sees end of input) — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.GreenRun -v` — blocked-by: T001

## S2: Failures are not green (P1)

- [ ] T003 [S2] Red run: a failing command gives exit 1, later commands still run, the tail (last 20 lines, at most 2,000 characters, long lines cut at 400) of the failing command is printed, the final line says `FAILED` — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.RedRun -v` — blocked-by: T001
- [ ] T004 [S2] Nothing to run: no non-empty command gives exit 2, says nothing was verified, writes no record (and leaves an existing record untouched) — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.NothingToRun -v` — blocked-by: T001
- [ ] T005 [S2] Timeout: `verify.timeout_seconds` (default 600) stops the command's whole process group, including a child, records `timeout`, exit 1; a test with a 1-second limit and a sleeping child proves the child is gone — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.Timeout -v` — blocked-by: T003
- [ ] T006 [S2] Cannot run: exit 127 is recorded as failed with that code; an `OSError` at launch is recorded `not started` with the error text — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.CannotRun -v` — blocked-by: T003
- [ ] T007 [S2] Config errors: invalid JSON, `verify.timeout_seconds` not a positive integer (a boolean is not), unknown `--repo` all exit 2 before anything runs — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.ConfigErrors -v` — blocked-by: T001

## S3: Revision (P1)

- [ ] T008 [S3] Revision and dirty: in a temp git repo the record holds the full `HEAD` hash and `dirty` false on a clean tree, `dirty` true with an uncommitted change (final line says not green at HEAD); outside git `revision` is null and the final line says `(no revision)`; after a new commit the old record's revision differs from `HEAD` — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.Revision -v` — blocked-by: T001
- [ ] T009 [S3] Record is content-free and atomic: a command printing a marker string leaves no marker in the record (SC-002); a failed write (record path is a directory) exits 2 and leaves the old record — files: `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.Record -v` — blocked-by: T003

## S4: Workspace and skills (P2)

- [ ] T010 [S4] `--repo <name>`: uses `repos.<name>.commands`, runs from `repos.<name>.path`, writes the record there — files: `bin/sdlc`, `bin/sdlc_verify.py`, `tests/test_verify.py` — verify: `python3 -m unittest tests.test_verify.Workspace -v` — blocked-by: T008
- [ ] T011 [S4] Skill and rule text: `sdlc-implement`, `sdlc-review`, `sdlc-ship`, `sdlc-debug` and the constitution tell the agent to run `sdlc verify` and quote its final line and revision (`python3 <kit_path>/bin/sdlc verify .`); a test per file — files: `core/skills/sdlc-implement/SKILL.md`, `core/skills/sdlc-review/SKILL.md`, `core/skills/sdlc-ship/SKILL.md`, `core/skills/sdlc-debug/SKILL.md`, `core/constitution.md`, `tests/test_sdlc.py` — verify: `python3 -m unittest tests.test_sdlc.VerifySkills -v` and `python3 bin/sdlc lint` — blocked-by: T008
- [ ] T012 [S4] Eval row V1 (a small fix, "finish and report"; expect the run quotes `verify:` final line) in `evals/scenarios.md`; README capability line and the support/limits text (no lock, POSIX only) — files: `evals/scenarios.md`, `README.md`, `tests/test_sdlc.py` — verify: `python3 bin/sdlc lint` (the row is listed) and the EvalRows test — blocked-by: T011
- [ ] T013 Mutation check: remove the exit-code logic, the timeout kill and the record write in turn; each makes at least one test fail; restore — files: none kept — verify: three runs of `python3 -m unittest tests.test_verify`, each with a failure, recorded in the progress log — blocked-by: T009, T010
- [ ] T014 Independent review by a fresh read-only agent (`VERDICT:` line), fix findings test-first, then run full gates — files: `specs/004-verify-command/review.md` — verify: `VERDICT: APPROVED`, full suite and lint green — blocked-by: T013, T012
- [ ] T015 Live eval V1 at n = 3 on two models; decision rule in the plan; results in `evals/results/verify-live.md` — files: `evals/results/verify-live.md` — verify: ≥ 5 of 6 runs quote the final line, or the plan's fallback applies — blocked-by: T014

## Human steps

- [ ] H1 Approve implementation after `sdlc-analyze` (the T3 gate) — owner: phong.ngo.vn — T001 waits for it
- [ ] H2 Approve merge (`sdlc-ship`; merges need explicit approval) — owner: phong.ngo.vn

## Progress log

- 2026-11-04 `3b8e173` — spec drafted and clarified (dirty tree: run and record, chosen by phong.ngo.vn).
