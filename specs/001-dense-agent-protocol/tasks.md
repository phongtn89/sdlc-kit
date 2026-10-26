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

- [x] T011 [S2] Write failing tests:
  - `validate` rule 3 (unknown or duplicate section), rule 4 (key not allowed or repeated), rule 6 (credential in URL, private-key block, token prefix);
  - the size warning above 5% (NFR-002);
  - `commit`: an invalid tmp file leaves `dest` unchanged and exits 1; a valid one replaces it atomically (FR-018);
  - `Perf`: 10 sources and 300 KB in under 10 s (NFR-003).

  — files: `tests/test_dap.py` (classes `Validate`, `Commit`, `Perf`), `tests/fixtures/dap/` — verify: `python3 -m unittest tests.test_dap -v` fails on the new cases only — blocked-by: T007
- [x] T012 [S2] Implement rules 3, 4 and 6, the size warning and `commit` (per-process tmp name, `os.replace`) — files: `S/dap.py` — verify: `python3 -m unittest tests.test_dap -v` passes — blocked-by: T011
- [x] T013 [S2] Complete the key list: every key used in the shop6 prototype, mapped to a section type with its meaning and value form — files: `S/keys.json`, `tests/test_dap.py` (class `KeyList`) — verify: a test asserts that every key named in `contracts/index-format.md` examples exists; `python3 -m unittest tests.test_dap -v` passes — blocked-by: T012
- [x] T014 [S2] Write the skill process:
  1. List the sources per the index contract (Sources): `.sdlc/workspace.md` and `.sdlc/context/*.md` by default, extra paths given as arguments, and on a rebuild the previous `src` list. (In shop6, the PRD and architecture view are passed as extra paths.)
  2. Derive entries only from them, copying UNVERIFIED and INFERRED verbatim (FR-008) and pointing, never copying, for sensitive sections.
  3. Write `index.dap.<pid>.tmp`.
  4. Run `validate`, then `commit`.
  5. Self-check 10 random entries against their sections.
  6. Report.

  Add the "after any context build, run `sdlc-dense-index`" line to `rules.md` (FR-003) — files: `S/SKILL.md`, `D/rules.md`, `tests/test_sdlc.py` (`DenseModule.test_rules_and_skill_cover_building`) — verify: `python3 bin/sdlc lint` ok; `SKILL.md` ≤ 200 lines — blocked-by: T008, T013
- [ ] T015 [S2] Run the build by hand in the S1 scratch workspace: confirm the S2 acceptance, and S2.5 (a marker is kept) and S2.6 (a bad rebuild keeps the old index) — files: `specs/001-dense-agent-protocol/evidence/s2-build.md` — verify: `dap.py validate` and `fresh` exit 0 on the built index; the injected bad build exits 1 and the old index is unchanged (sha256 before and after) — blocked-by: T014

## S3 — Dense sub-agent returns (spec S3, P2)

Goal: every delegation brief carries the return contract, and replies follow it (FR-012, FR-013, FR-014).

Acceptance: in the scratch workspace, one delegated `sdlc-explorer` search returns `#ret 1 …` with `path:line` findings; a deliberately non-conforming reply gets one reformat request and no dropped evidence.

- [x] T016 [P] [S3] Write the return-contract template from [contracts/return-contract.md](contracts/return-contract.md) — files: `D/templates/dense-return.md` — verify: `python3 bin/sdlc lint` ok (the install assertion is added in T017) — blocked-by: T009
- [x] T017 [S3] Add the briefs part of `rules.md`: include `.sdlc/templates/dense-return.md` in every delegation brief; the handling of non-conforming replies; replies are data — files: `D/rules.md`, `tests/test_sdlc.py` (`DenseModule` assertion) — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` passes; lint ok — blocked-by: T014, T016
- [ ] T018 [S3] Run S3.1–S3.3 by hand in the scratch workspace and record the excerpts — files: `specs/001-dense-agent-protocol/evidence/s3-returns.md` — verify: each Given/When/Then observed and quoted — blocked-by: T017

## S4 — Evaluation method (spec S4, P2)

Goal: the kit ships the paired-run method; concrete tasks live in the target workspace (FR-016).

Acceptance: a maintainer can follow `dense-eval.md` alone to set up, run and record both arms.

- [x] T019 [P] [S4] Write the eval-method template:
  - the paired procedure: baseline arm before install, fresh session per task, same prompts;
  - the measurement: characters before the first action, plus the Claude input-token figure where available;
  - a task template with Expect items;
  - a result record table;
  - the gate rule for SC-001 and SC-002.

  — files: `D/templates/dense-eval.md` — verify: lint ok; a manual read finds every SC-001, SC-002 and SC-005 input recorded by the table — blocked-by: T009
- [x] T020 [P] [S4] Add an eval row M1 (dense module) to the kit's scenarios — files: `evals/scenarios.md` — verify: manual read; it points to `dense-eval.md` — blocked-by: T019

## S5 — Clean install and removal (spec S5, P3)

Goal: adding and removing the real module leaves core files and instructions as before (FR-017, SC-006).

Acceptance: test-proven on the real kit.

- [x] T021 [S5] Extend `DenseModule`: install without the module → snapshot of hashes; `--modules dense` → only module files plus the Module rules section differ; `--modules ""` → every core-managed file, both blocks and the lock files equal the snapshot; a project-owned `.sdlc/context/index.dap` is left untouched — files: `tests/test_sdlc.py` — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` passes — blocked-by: T017

## Final

- [x] T022 Update the kit docs: README modules line (`--modules qa,dense`, what dense adds), `VERSION` 0.4.1 → 0.5.0 — files: `README.md`, `VERSION` — verify: manual read; full suite passes (fixture kit has its own VERSION) — blocked-by: T021
- [x] T023 Run full gates and record outcomes — files: `tasks.md` (Progress log) — verify: `python3 -m unittest discover -s tests -t .` OK and `python3 bin/sdlc lint` ok, recorded in the Progress log with the revision — blocked-by: T022
- [x] T024 Converge: spec, plan, tasks and code agree (`sdlc-converge`) — files: `tasks.md` (Convergence section) — verify: convergence section lists no open gaps, or each gap is a new task — blocked-by: T023
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

- 2026-10-26 after `9a6bbe3` — C001 (decided: confine): RED `python3 -m unittest tests.test_dap.Commit -v` → 3 FAIL (`committed …` to `elsewhere.dap`, via a symlink, from a stray tmp); GREEN with `commit_paths_ok` (realpath; dest must be `.sdlc/context/index.dap`, tmp `.sdlc/context/index.dap.<id>.tmp`). C002 (decided: e-mail check): RED `test_email_addresses_rejected` FAIL (`valid`); false-positive guard (`git@github.com:…`, `@jtl/…`, `pkg@1.2.3`) ok before and after; GREEN with `EMAIL_RE`. Contract rule 6 and Commit section, plan Security updated to match. `tests.test_dap` 40 OK; full suite 104 OK; lint ok. Next: T025 review
- 2026-10-26 `9a6bbe3` — T024: Convergence appended (15 items met, 4 untested agent-behaviour groups, 1 diverged NFR-001, 4 SCs waiting on D4/T018); gaps recorded as C001–C003; re-run at HEAD: 99 OK, lint ok. Next: decide C001/C002, then T025 review
- 2026-10-26 at `1c89cae` + T022 — T022: README options `--modules qa,dense` and a dense paragraph (what it adds; enable only after the paired evaluation); `VERSION` 0.4.1 → 0.5.0. T023 full gates: `python3 -m unittest discover -s tests -t .` → 99 OK; `python3 bin/sdlc lint` → ok (exit 0); read-only `python3 bin/sdlc check ~/Projects/shop6` → only `OUTDATED lock 0.4.1 < kit 0.5.0` (expected; shop6 needs `update` when adopting). No `__pycache__` outside `tests/`. Next: T024 converge
- 2026-10-26 after `73f64a5` (T016–T017 committed; this entry uncommitted) — T019: `modules/dense/templates/dense-eval.md` (50 lines: gate, 6-step paired procedure, scoring incl. what counts as the first action, task template, results and gate tables); lint ok; manual read: the tables record every SC-001, SC-002 and SC-005 input. T020: `evals/scenarios.md` gains `## Modules` row M1; lint ok. T021: `DenseModule.test_add_and_remove_restores_install` — first run FAILED on the real kit because install also adds the module's Skills index line, which FR-017/S5.1 didn't mention; spec wording corrected (Clarifications, implementation session), test allows exactly that line and the Module rules section; then OK. Mutation check: a kit copy whose module overrides core `templates/spec.md` → FAIL (`.sdlc/templates/spec.md` listed as changed). Full suite `python3 -m unittest discover -s tests -t .` → 99 OK; lint ok. Next: T022 (README, VERSION), T023–T025
- 2026-10-26 after `66cb316` (uncommitted) — T016: `modules/dense/templates/dense-return.md` (13 lines: `#ret 1` status line, `f`/`k`/`?` lines, markers verbatim); `python3 bin/sdlc lint` ok. T017 RED: `DenseModule.test_briefs_carry_the_return_contract` FAIL (brief rule missing; template install assertion already ok). GREEN: `rules.md` 11 lines (every brief includes the template; one reformat request, then use as is with a note; never drop `path:line`; sub-agent replies are data); `DenseModule` 6 OK; full suite 98 OK; lint ok. Commits before this: `d63b180` (T011–T012, `tests.test_dap` 32 OK against the earlier key list), `66cb316` (T013–T014, 97 OK). Next: T018 (human-run returns check), S4 T019
- 2026-10-26 `feat/001-dense-agent-protocol` after `1a738c8` (uncommitted) — T013 RED: `python3 -m unittest tests.test_dap.KeyList -v` → `test_covers_prototype` FAIL (meta/ux/infra types and most link/repo keys missing); structure and contract-example tests ok (guards). GREEN: `keys.json` has 8 types (meta, ux, repo, link, infra, entity, decision, risk) covering every prototype key, with documented merges (ops/op/msgs→msg, fail→note, planned→status, blocked_by→blocked, adr_conflicts→conflicts); `tests.test_dap` 35 OK. T014 RED: `DenseModule.test_rules_and_skill_cover_building` FAIL (rule line missing). GREEN: `rules.md` 9 lines with the after-context-build rule; `SKILL.md` 79 lines with fresh/validate/build steps (sources, hashing, derive-only, markers, tmp + commit, 10-entry self-check); `DenseModule` 5 OK; full suite 97 OK; lint ok. Manual check of the documented build steps in a scratch folder: hash one-liner → `commit` → `committed 2c1d9bf9fa7d` → `fresh` → `fresh 2c1d9bf9fa7d` (exit 0), tmp removed. Next: T015 (human-run build), S3 T016
- 2026-10-26 `feat/001-dense-agent-protocol` after `1a738c8` (uncommitted) — T011 RED: `python3 -m unittest tests.test_dap -v` → 9 FAIL (rules 3/4/6, size warning, 3× commit), 22 ok (20 earlier, `test_plain_url_is_not_a_secret` guard, `Perf` already within budget). One test bug fixed before GREEN: `Perf` pointed at `section-10…19` (only 10 headings); the validator correctly rejected it. Earlier test `test_value_may_contain_at_sign` switched from `pkg`/`note` to allowed `repo` keys (`desc`/`owns`) because rule 4 now applies. Size warning gets a 20 KB source floor (tiny sources made every index exceed 5%); recorded in contracts/index-format.md with the `commit` contract. T012 GREEN: `tests.test_dap` 32 OK (`Perf` 0.11 s for 10 sources / ~300 KB / 200 sections), full suite 93 OK, `python3 bin/sdlc lint` ok, no `__pycache__` under `modules/`. Next: T013 (complete key list), then T014
- 2026-10-26 `feat/001-dense-agent-protocol` on `c3abe38` (uncommitted) — T008: `keys.json` (5 types: repo, link, risk, decision, entity), `SKILL.md` shell (53 lines), `rules.md` track-start rules (8 lines); `python3 bin/sdlc lint` → ok (interim error cleared). T009: `python3 -m unittest tests.test_sdlc.DenseModule -v` → 4 OK (real-kit lint, both blocks carry `### dense`, skill + `dap.py` + `keys.json` installed, installed `dap.py` validate/fresh exit 0, Copilot-only install uses `.github/skills`). Written after T008, so not seen RED directly; instead, mutation checks via the test-only `SDLC_TEST_KIT` override: a kit copy without `rules.md`/`keys.json` → 2 FAIL; without `SKILL.md` → lint test FAIL (`SKILL.md: missing`). Full suite `python3 -m unittest discover -s tests -t .` → 81 OK; no `__pycache__` under `modules/`. Next: T010 (human-run tracer, interactive session) — S2 (T011) can start meanwhile
- 2026-10-26 `feat/001-dense-agent-protocol` on `c3abe38` (uncommitted) — T007 GREEN: `python3 -m unittest tests.test_dap -v` → 20 OK, no `__pycache__` left in `modules/`; T003 RED: `python3 -m unittest tests.test_sdlc.LintTests -v` → 2 FAIL (rules.md not linted), evals test vacuously ok; T004 GREEN: `LintTests` 13 OK; mutation check: dropping `evals` from the prefixes makes `test_evals_reference_is_project_owned` fail (`references missing .sdlc/evals/dense/results.md`), restored; T005: `adapters/RENDERING.md` sources row, bytecode note, block order and lint rules match the T001/T003 assertions (manual read); full suite 77 OK. **Known interim state:** `python3 bin/sdlc lint` → 1 error (`modules/dense/skills/sdlc-dense-index/SKILL.md: missing`) until T008 adds the skill; no test covers real-kit lint before T009. Next: T008
- 2026-10-26 branch `feat/001-dense-agent-protocol` on `c3abe38` (uncommitted) — T001 RED: `python3 -m unittest tests.test_sdlc.ModuleRules -v` → 3 FAIL (missing `## Module rules` ×2, `__pycache__` copied), 1 ok (regression guard); T006 RED: `python3 -m unittest tests.test_dap -v` → 20 FAIL (script missing); T002 GREEN: `ModuleRules` 4 OK, `python3 -m unittest tests.test_sdlc` 54 OK, `python3 bin/sdlc lint` ok; full suite 20 failures, all `tests.test_dap` (awaiting T007); next: T007, then T003/T005
- 2026-10-26 — analyze fixes A1–A12 applied to spec, plan, contracts and tasks (T001–T008, T014); A13–A15 (LOW) left as recorded findings

- 2026-10-26 `c3abe38` — tasks drafted; baseline 50 tests OK, lint ok; next: T001 and T006 (no shared files, can start in parallel)

## Convergence (2026-10-26, 9a6bbe3)

Base `c3abe38` → HEAD `9a6bbe3` (21 files, +1614/−8). Evidence re-run at HEAD: `python3 -m unittest discover -s tests -t .` → 99 OK; `python3 bin/sdlc lint` → ok.

| Item | Class | Code | Test |
|---|---|---|---|
| FR-001 opt-in | met | `bin/sdlc:205-206` (only installed modules) | `tests/test_sdlc.py:238`, `:316` |
| FR-002 key list | met | `S/keys.json`; `modules/dense/skills/sdlc-dense-index/dap.py:75`, `:158` | `tests/test_dap.py:125`, `:225-239` |
| FR-003 build after context build | untested (agent behaviour) | `D/rules.md:7`; `S/SKILL.md` build steps 4–10 | text only: `tests/test_sdlc.py:298`; behaviour: T015 (open) |
| FR-004 pointer per entry | met | `modules/dense/skills/sdlc-dense-index/dap.py:162-166` | `tests/test_dap.py:101` |
| FR-005 source hashes | met | `modules/dense/skills/sdlc-dense-index/dap.py:133` (`SRC_RE` requires SHA12) | `tests/test_dap.py:98`, `:173` |
| FR-006 freshness | met | `modules/dense/skills/sdlc-dense-index/dap.py:125`, `:134` | `tests/test_dap.py:168-189` |
| FR-007 validation errors | met | `modules/dense/skills/sdlc-dense-index/dap.py:105-179` | `tests/test_dap.py:80-128` |
| FR-008 no new facts, markers kept | untested (agent behaviour) | `S/SKILL.md` steps 6 and 9 | T015 (open); not machine-checkable (plan, accepted risk) |
| FR-009, FR-010, FR-011 orientation, citing, fallback | untested (agent behaviour) | `D/rules.md:3-6`, `:10`; exit codes `modules/dense/skills/sdlc-dense-index/dap.py:206-210` | exit codes: `tests/test_dap.py:168-201`; behaviour: T010 (open) |
| FR-012, FR-013, FR-014 return contract | untested (agent behaviour) | `D/rules.md:8-9`; `D/templates/dense-return.md` | text: `tests/test_sdlc.py:342`; behaviour: T018 (open) |
| FR-015 both targets | met (rendering) | `bin/sdlc` same block for both targets | `tests/test_sdlc.py:227`, `:286`, `:364`. Agent behaviour on Copilot: not tested |
| FR-016 eval method | met (kit part) | `D/templates/dense-eval.md`; `evals/scenarios.md` M1 | lint; workspace set is D4 (open) |
| FR-017 clean install and removal | met | module mechanism | `tests/test_sdlc.py:316` |
| FR-018 failed rebuild keeps index | met | `modules/dense/skills/sdlc-dense-index/dap.py:198-205` | `tests/test_dap.py:263-288` |
| FR-019 module rules | met | `bin/sdlc:205-206`, `:259-262`, lint `:784-791` | `tests/test_sdlc.py:224-269`, `:556-576` |
| NFR-001 no secrets / personal data | **diverged (partial)** | secrets: `modules/dense/skills/sdlc-dense-index/dap.py:25-30`, `:163`; personal data: only `S/SKILL.md:47` | `tests/test_dap.py:132-140`; personal data: none (C002) |
| NFR-002 size ≤ 5% | met | `modules/dense/skills/sdlc-dense-index/dap.py:31`, `:180` (20 KB floor, in the contract) | `tests/test_dap.py:142`, `:151` |
| NFR-003 under 10 s | met | — | `tests/test_dap.py:291` (0.11 s) |
| SC-001, SC-002, SC-005 gate | not yet measurable | — | D4 and T018 (open, human) |
| SC-003 shop6 index valid | not yet measurable | — | D4 (open) |
| SC-004 stale detection | met | `modules/dense/skills/sdlc-dense-index/dap.py:125`, `:134` | `tests/test_dap.py:173-189` |
| SC-006 hashes restored | met | — | `tests/test_sdlc.py:243`, `:316` |

Scenarios: S5 met; S2 met for the script parts, the build behaviour waits on T015; S4 met for the method, the run is D4; **S1 (P1) and S3 rest on agent behaviour that only T010 and T018 can show.**

Plan decisions: ADR 0001 format, `fresh` exit codes 0/1/2, both script paths in the rules, default sources, per-run tmp names, `rules.md` lint and the `evals` prefix, the bytecode skip and the block order all match the code. One divergence (C001).

Ticked tasks: all evidence is at or before `9a6bbe3` and re-confirmed by the HEAD run above; none stale.

Unplanned behaviour: none in product code. Noted only: the test-only `SDLC_TEST_KIT` override (`tests/test_sdlc.py:274`), used for mutation checks.

- [x] C001 [drift: plan Security says `dap.py` "writes only `.sdlc/context/index.dap*`" (`plan.md:115`), but `commit` replaces whatever `dest` it is given (`modules/dense/skills/sdlc-dense-index/dap.py:203`) and reads any `tmp`] → decide: confine `tmp` and `dest` to `.sdlc/context/` with a failing test first (`modules/dense/skills/sdlc-dense-index/dap.py`, `tests/test_dap.py`), or relax the plan sentence — blocked-by: —
- [x] C002 [drift: NFR-001 forbids personal data in the index, but only secrets are detected (`modules/dense/skills/sdlc-dense-index/dap.py:25-30`); personal data relies on the skill instruction (`S/SKILL.md:47`) and the 10-entry self-check] → decide: add a narrow personal-data check (e.g. e-mail addresses) with a failing test first, or record in plan that personal data is a skill-level rule with residual risk — blocked-by: —
- [ ] C003 [untested: agent behaviour for FR-003, FR-008–FR-014 (S1 P1, S2 build, S3)] → no new task: T010, T015 and T018 cover it; they stay open and block calling S1–S3 verified — blocked-by: T010, T015, T018
