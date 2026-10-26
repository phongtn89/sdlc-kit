# Tasks: Dense Agent Protocol module

Inputs: [spec.md](spec.md), [plan.md](plan.md), [contracts/](contracts/), [ADR 0001](../../docs/adr/0001-dense-index-format.md) (accepted 2026-10-26) · Status: draft · Created: 2026-10-26

Verify (the kit has no `.sdlc/config.json`; commands from `README.md:82` and `bin/sdlc lint`):
- Narrow: `python3 -m unittest tests.<module>.<Class> -v`
- Full: `python3 -m unittest discover -s tests -t .` · `python3 bin/sdlc lint`
- Baseline 2026-10-26 at `c3abe38`: 50 tests OK, lint ok

Paths: `D` = `modules/dense`, `S` = `modules/dense/skills/sdlc-dense-index`, `F` = `tests/fixtures/kit`.

Legend: `- [ ] T001 [P?] [S1] Description — files: … — verify: … — blocked-by: T00x`
- `[P]` may run in parallel: no shared files, no blocking edge.
- `[S1]` is the slice the task belongs to.
- `verify` is the command or observation that proves this task alone.

## S1 — Tracer bullet: an agent orients from a fresh index (spec S1, P1)

Goal: with the module installed, the always-loaded instructions carry the module rules, and an agent at track start checks freshness, loads the index, and cites sources (FR-009, FR-010, FR-011, FR-015, FR-019, FR-001). The index is hand-written in this slice; building it is S2.

Acceptance: `install --kit . --modules dense` into a scratch project renders the rules in both instruction blocks plus the skill and script. In a fresh session with a hand-written valid index, the transcript shows `dap.py fresh` run first, then the index loaded, then only the pointed-to sections opened, with source citations. After a source is edited, it shows the stale fallback.

- [x] T001 [S1] Write failing tests for module rules:
  - rules from a fixture module with `rules.md` appear under `## Module rules` / `### rul` in both `AGENTS.md` and `.github/copilot-instructions.md`, after the Roles index and before Project rules;
  - an install with only `qa` produces a block byte-identical to today's;
  - `install --modules rul` then `install --modules ""` leaves block and lock hashes equal to a module-free install (SC-006);
  - a `__pycache__/x.pyc` that the test creates at runtime inside a temporary copy of the fixture kit's skill folder is not installed (A10; `.gitignore` excludes `__pycache__/` and `*.pyc`, so it can't be a committed fixture).
  
  — files: `tests/test_sdlc.py` (new class `ModuleRules`), `F/modules/rul/rules.md`, `F/modules/rul/templates/rul.md` — verify: `python3 -m unittest tests.test_sdlc.ModuleRules -v` fails on the missing section — blocked-by: —
- [x] T002 [S1] Load `modules/<m>/rules.md` in `load_kit`, and render `## Module rules` with `### <module>` subsections in `block_inner` only when at least one module has rules; make `list_files` skip `__pycache__` and `*.pyc` — files: `bin/sdlc` — verify: `python3 -m unittest tests.test_sdlc.ModuleRules -v` passes; full suite still 50+ OK — blocked-by: T001
- [x] T003 [S1] Write failing lint tests: `rules.md` over 30 lines → error; `rules.md` referencing a missing `.sdlc/` path → error; a reference to `.sdlc/evals/…` is accepted; the fixture still passes — files: `tests/test_sdlc.py` (class `LintTests`), `F/modules/rul/rules.md` — verify: `python3 -m unittest tests.test_sdlc.LintTests -v` fails on the new cases — blocked-by: T002
- [x] T004 [S1] Lint `rules.md`: a line limit and `lint_refs`; add `evals` to the project-owned prefixes in `lint_refs` — files: `bin/sdlc` — verify: `python3 -m unittest tests.test_sdlc.LintTests -v` passes; `python3 bin/sdlc lint` ok — blocked-by: T003
- [x] T005 [P] [S1] Document module rules in the rendering contract: the source row, the optional "Module rules" section in the Instructions output, and that `__pycache__`/`*.pyc` are never copied — files: `adapters/RENDERING.md` — verify: the text matches the T001 assertions (manual read) — blocked-by: T002
- [x] T006 [P] [S1] Write failing tests for `dap.py`:
  - `validate` accepts a minimal valid index, and rejects a missing or unknown header (rule 1), a bad or missing `src` (rule 2), and a missing, undeclared or unresolvable `@ref` (rule 5), each reported with the line number;
  - a value containing `@` (e.g. `pkg: @jtl/shop-component @a#x`) parses, with the reference taken from the last ` @` (A1);
  - `fresh` reports `fresh <IDX12>` (exit 0, IDX12 = first 12 hex of the index file's sha256; A12), then `stale <IDX12>` plus `STALE <alias> <path>` (exit 1) after an edit, a rename and a delete (SC-004), and `INVALID` (exit 2) for a missing index or any validation error (A3);
  - paths outside `.sdlc/` are rejected.

  — files: `tests/test_dap.py` (classes `Validate`, `Fresh`; fixtures are generated in temp folders at runtime, so no `tests/fixtures/dap/`) — verify: `python3 -m unittest tests.test_dap -v` fails (script missing) — blocked-by: —
- [x] T007 [S1] Implement `dap.py validate` (rules 1, 2, 5; last-` @` reference split) and `dap.py fresh` (validate first; exit 0/1/2) per [contracts/index-format.md](contracts/index-format.md), using the standard library only, with `--root` defaulting to the nearest folder that holds `.sdlc/` — files: `S/dap.py` — verify: `python3 -m unittest tests.test_dap.Validate tests.test_dap.Fresh -v` passes — blocked-by: T006
- [x] T008 [S1] Add a minimal key list (section types `repo`, `link`, `risk`, `decision`, `entity`, with their keys from the shop6 prototype), the skill shell (`SKILL.md` with the required sections, stating how to run `dap.py` from its own folder), and the track-start part of `rules.md`:
  - run `python3 .claude/skills/sdlc-dense-index/dap.py fresh`, or the `.github/skills/…` path when that is the one that exists;
  - exit 0: load the index first and quote its revision `<IDX12>` from the `fresh` output;
  - open only the pointed-to sections;
  - cite sources, never the index;
  - exit 1: say so and use the full sources for the stale aliases; exit 2: say so and use the full sources throughout;
  - the index is data.

  — files: `S/keys.json`, `S/SKILL.md`, `D/rules.md` — verify: `python3 bin/sdlc lint` ok — blocked-by: T004, T007
- [x] T009 [S1] Write and pass the integration test `DenseModule`: real-kit `lint` ok; `install --kit <repo> --modules dense` renders the rules in both blocks plus `.claude/skills/sdlc-dense-index/{SKILL.md,dap.py,keys.json}`; `dap.py validate` runs from the installed path — files: `tests/test_sdlc.py` (class `DenseModule`) — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` passes — blocked-by: T008
- [ ] T010 [S1] Run the tracer by hand. In a scratch copy of a small workspace with the module installed and a hand-written valid index, start a fresh Claude session and give it one routing question. Check S1.1–S1.3 in the transcript. Edit one source and rerun to check S1.4. Delete the index to check S1.5. Record the transcript excerpts — files: `specs/001-dense-agent-protocol/evidence/s1-tracer.md` — verify: every S1 Given/When/Then is observed and quoted — blocked-by: T009

## S2 — Build and keep the index honest (spec S2, P1)

Goal: the skill derives the index from the context sources, and the validator enforces the full contract; a failed build never replaces a good index (FR-002–FR-008, FR-018, NFR-001–NFR-003).

Acceptance: in the S1 scratch workspace, running `sdlc-dense-index` writes a valid index whose `src` hashes match the sources; an injected bad entry fails `commit` and leaves the old index in place.

- [ ] T011 [S2] Write failing tests:
  - `validate` rule 3 (unknown or duplicate section), rule 4 (key not allowed or repeated), rule 6 (credential in URL, private-key block, token prefix);
  - the size warning above 5% (NFR-002);
  - `commit`: an invalid tmp file leaves `dest` unchanged and exits 1; a valid one replaces it atomically (FR-018);
  - `Perf`: 10 sources and 300 KB in under 10 s (NFR-003).

  — files: `tests/test_dap.py` (classes `Validate`, `Commit`, `Perf`), `tests/fixtures/dap/` — verify: `python3 -m unittest tests.test_dap -v` fails on the new cases only — blocked-by: T007
- [ ] T012 [S2] Implement rules 3, 4 and 6, the size warning and `commit` (per-process tmp name, `os.replace`) — files: `S/dap.py` — verify: `python3 -m unittest tests.test_dap -v` passes — blocked-by: T011
- [ ] T013 [S2] Complete the key list: every key used in the shop6 prototype, mapped to a section type with its meaning and value form — files: `S/keys.json` — verify: a test asserts that every key named in `contracts/index-format.md` examples exists; `python3 -m unittest tests.test_dap -v` passes — blocked-by: T012
- [ ] T014 [S2] Write the skill process:
  1. List the sources per the index contract (Sources): `.sdlc/workspace.md` and `.sdlc/context/*.md` by default, extra paths given as arguments, and on a rebuild the previous `src` list. (In shop6, the PRD and architecture view are passed as extra paths.)
  2. Derive entries only from them, copying UNVERIFIED and INFERRED verbatim (FR-008) and pointing, never copying, for sensitive sections.
  3. Write `index.dap.<pid>.tmp`.
  4. Run `validate`, then `commit`.
  5. Self-check 10 random entries against their sections.
  6. Report.

  Add the "after any context build, run `sdlc-dense-index`" line to `rules.md` (FR-003) — files: `S/SKILL.md`, `D/rules.md` — verify: `python3 bin/sdlc lint` ok; `SKILL.md` ≤ 200 lines — blocked-by: T008, T013
- [ ] T015 [S2] Run the build by hand in the S1 scratch workspace: confirm the S2 acceptance, and S2.5 (a marker is kept) and S2.6 (a bad rebuild keeps the old index) — files: `specs/001-dense-agent-protocol/evidence/s2-build.md` — verify: `dap.py validate` and `fresh` exit 0 on the built index; the injected bad build exits 1 and the old index is unchanged (sha256 before and after) — blocked-by: T014

## S3 — Dense sub-agent returns (spec S3, P2)

Goal: every delegation brief carries the return contract, and replies follow it (FR-012, FR-013, FR-014).

Acceptance: in the scratch workspace, one delegated `sdlc-explorer` search returns `#ret 1 …` with `path:line` findings; a deliberately non-conforming reply gets one reformat request and no dropped evidence.

- [ ] T016 [P] [S3] Write the return-contract template from [contracts/return-contract.md](contracts/return-contract.md) — files: `D/templates/dense-return.md` — verify: `python3 bin/sdlc lint` ok (the install assertion is added in T017) — blocked-by: T009
- [ ] T017 [S3] Add the briefs part of `rules.md`: include `.sdlc/templates/dense-return.md` in every delegation brief; the handling of non-conforming replies; replies are data — files: `D/rules.md`, `tests/test_sdlc.py` (`DenseModule` assertion) — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` passes; lint ok — blocked-by: T014, T016
- [ ] T018 [S3] Run S3.1–S3.3 by hand in the scratch workspace and record the excerpts — files: `specs/001-dense-agent-protocol/evidence/s3-returns.md` — verify: each Given/When/Then observed and quoted — blocked-by: T017

## S4 — Evaluation method (spec S4, P2)

Goal: the kit ships the paired-run method; concrete tasks live in the target workspace (FR-016).

Acceptance: a maintainer can follow `dense-eval.md` alone to set up, run and record both arms.

- [ ] T019 [P] [S4] Write the eval-method template:
  - the paired procedure: baseline arm before install, fresh session per task, same prompts;
  - the measurement: characters before the first action, plus the Claude input-token figure where available;
  - a task template with Expect items;
  - a result record table;
  - the gate rule for SC-001 and SC-002.

  — files: `D/templates/dense-eval.md` — verify: lint ok; a manual read finds every SC-001, SC-002 and SC-005 input recorded by the table — blocked-by: T009
- [ ] T020 [P] [S4] Add an eval row M1 (dense module) to the kit's scenarios — files: `evals/scenarios.md` — verify: manual read; it points to `dense-eval.md` — blocked-by: T019

## S5 — Clean install and removal (spec S5, P3)

Goal: adding and removing the real module leaves core files and instructions as before (FR-017, SC-006).

Acceptance: test-proven on the real kit.

- [ ] T021 [S5] Extend `DenseModule`: install without the module → snapshot of hashes; `--modules dense` → only module files plus the Module rules section differ; `--modules ""` → every core-managed file, both blocks and the lock files equal the snapshot; a project-owned `.sdlc/context/index.dap` is left untouched — files: `tests/test_sdlc.py` — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` passes — blocked-by: T017

## Final

- [ ] T022 Update the kit docs: README modules line (`--modules qa,dense`, what dense adds), `VERSION` 0.4.1 → 0.5.0 — files: `README.md`, `VERSION` — verify: manual read; full suite passes (fixture kit has its own VERSION) — blocked-by: T021
- [ ] T023 Run full gates and record outcomes — files: `tasks.md` (Progress log) — verify: `python3 -m unittest discover -s tests -t .` OK and `python3 bin/sdlc lint` ok, recorded in the Progress log with the revision — blocked-by: T022
- [ ] T024 Converge: spec, plan, tasks and code agree (`sdlc-converge`) — files: `tasks.md` (Convergence section) — verify: convergence section lists no open gaps, or each gap is a new task — blocked-by: T023
- [ ] T025 Independent review (`sdlc-review`; changes `bin/sdlc` rendering, so also check the managed-block compatibility); verdict recorded — files: `review.md` — verify: verdict is `APPROVED` or `REJECTED` with findings — blocked-by: T024

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 opt-in | T009, T021 |
| FR-002 key list | T008, T012, T013 |
| FR-003 index after context build | T014, T015 |
| FR-004, FR-005 pointers, source hashes | T006, T007 |
| FR-006 freshness | T006, T007, T010 |
| FR-007 validation errors | T006, T007, T011, T012 |
| FR-008 no new facts, markers kept | T014, T015 |
| FR-009, FR-010, FR-011 agent orientation, citing, fallback | T008, T010 |
| FR-012, FR-013, FR-014 return contract | T016, T017, T018 |
| FR-015 both targets | T001, T002, T009 |
| FR-016 eval method | T019, T020; concrete set in D4 |
| FR-017 clean install and removal | T001, T021 |
| FR-018 failed rebuild keeps index | T011, T012, T015 |
| FR-019 module rules in core | T001–T005 (incl. `__pycache__` skip and `evals` lint prefix) |
| NFR-001 no secrets | T011, T012 |
| NFR-002 size warning | T011, T012 |
| NFR-003 under 10 s | T011, T012 |
| SC-001, SC-002, SC-005 gate | D4 |
| SC-003 shop6 index valid | D4 |
| SC-004 stale detection | T006, T007 |
| SC-006 hashes restored | T001, T021 |

Parallel groups:
- {T001, T006} at the start;
- {T003, T005} after T002;
- {T016, T019} after T009, then T020.

Everything else is sequential, because tasks share `bin/sdlc`, `tests/test_sdlc.py`, `S/dap.py` or `D/rules.md`.

Size: about 200 lines of Python, 230 of tests and 240 of Markdown, in 5 slices and 25 tasks. S1 is the largest (core hook plus validator skeleton, about 230 lines of code and tests). It stays one slice because the tracer needs both; if review asks for it, T001–T005 can be reviewed as their own PR.

## Blocked / human-only

- [ ] Commits and any push of sdlc-kit work — owner: phong.ngo.vn — unblocked when: approved per action (kit repo is on `main`; branch first).
- [ ] T010, T015, T018 need an interactive Claude session in a scratch workspace — owner: phong.ngo.vn (or an agent session they start) — unblocked when: T009 / T014 / T017 are done.
- [ ] D4: shop6 evaluation set, 6 tasks covering routing, cross-repo impact and review, written in shop6 `.sdlc/evals/dense/tasks.md` from `dense-eval.md` — owner: phong.ngo.vn — unblocked when: T019 is done.
- [ ] D4: run the **baseline arm in shop6 before installing the module** — owner: phong.ngo.vn — unblocked when: the shop6 task set exists.
- [ ] D4: install `--modules dense` into shop6, build the first index (SC-003: validate 100%), run the module arm, and record the gate (SC-001, SC-002, SC-005) in shop6 `.sdlc/evals/dense/results.md` — owner: phong.ngo.vn — unblocked when: the baseline arm is recorded and T025 is APPROVED.
- [ ] D4: retire the shop6 `.sdlc/manifest.yaml` prototype only if the gate passes; otherwise uninstall the module and revisit step hooks — owner: phong.ngo.vn — unblocked when: the gate result is recorded.

## Progress log

- 2026-10-26 `feat/001-dense-agent-protocol` on `c3abe38` (uncommitted) — T008: `keys.json` (5 types: repo, link, risk, decision, entity), `SKILL.md` shell (53 lines), `rules.md` track-start rules (8 lines); `python3 bin/sdlc lint` → ok (interim error cleared). T009: `python3 -m unittest tests.test_sdlc.DenseModule -v` → 4 OK (real-kit lint, both blocks carry `### dense`, skill + `dap.py` + `keys.json` installed, installed `dap.py` validate/fresh exit 0, Copilot-only install uses `.github/skills`). Written after T008, so not seen RED directly; instead, mutation checks via the test-only `SDLC_TEST_KIT` override: a kit copy without `rules.md`/`keys.json` → 2 FAIL; without `SKILL.md` → lint test FAIL (`SKILL.md: missing`). Full suite `python3 -m unittest discover -s tests -t .` → 81 OK; no `__pycache__` under `modules/`. Next: T010 (human-run tracer, interactive session) — S2 (T011) can start meanwhile
- 2026-10-26 `feat/001-dense-agent-protocol` on `c3abe38` (uncommitted) — T007 GREEN: `python3 -m unittest tests.test_dap -v` → 20 OK, no `__pycache__` left in `modules/`; T003 RED: `python3 -m unittest tests.test_sdlc.LintTests -v` → 2 FAIL (rules.md not linted), evals test vacuously ok; T004 GREEN: `LintTests` 13 OK; mutation check: dropping `evals` from the prefixes makes `test_evals_reference_is_project_owned` fail (`references missing .sdlc/evals/dense/results.md`), restored; T005: `adapters/RENDERING.md` sources row, bytecode note, block order and lint rules match the T001/T003 assertions (manual read); full suite 77 OK. **Known interim state:** `python3 bin/sdlc lint` → 1 error (`modules/dense/skills/sdlc-dense-index/SKILL.md: missing`) until T008 adds the skill; no test covers real-kit lint before T009. Next: T008
- 2026-10-26 branch `feat/001-dense-agent-protocol` on `c3abe38` (uncommitted) — T001 RED: `python3 -m unittest tests.test_sdlc.ModuleRules -v` → 3 FAIL (missing `## Module rules` ×2, `__pycache__` copied), 1 ok (regression guard); T006 RED: `python3 -m unittest tests.test_dap -v` → 20 FAIL (script missing); T002 GREEN: `ModuleRules` 4 OK, `python3 -m unittest tests.test_sdlc` 54 OK, `python3 bin/sdlc lint` ok; full suite 20 failures, all `tests.test_dap` (awaiting T007); next: T007, then T003/T005
- 2026-10-26 — analyze fixes A1–A12 applied to spec, plan, contracts and tasks (T001–T008, T014); A13–A15 (LOW) left as recorded findings

- 2026-10-26 `c3abe38` — tasks drafted; baseline 50 tests OK, lint ok; next: T001 and T006 (no shared files, can start in parallel)
