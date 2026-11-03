# Tasks: Dense module v2, find instead of read

Inputs: [spec.md](spec.md), [plan.md](plan.md), [contracts/find.md](contracts/find.md) · Status: draft · Created: 2026-10-30 · Branch: `feat/002-dense-find`

Verify (kit root):
- Narrow: `python3 -m unittest tests.test_dap.Find -v` · `python3 -m unittest tests.test_sdlc.DenseModule -v`
- Full: `python3 -m unittest discover -s tests -t .` (baseline 74 OK on this branch, 2026-10-30) · `python3 bin/sdlc lint`
- Core untouched (FR-001, FR-020): `git diff --stat main -- core adapters bin evals` prints nothing

Legend: `- [x] T001 [P?] [S1] Description — files: … — verify: … — blocked-by: T00x`
- `[P]` may run in parallel: no shared files, no blocking edge.
- `[S1]` slice the task belongs to.
- `verify` is the command or observation that proves this task alone.

## Phase 0: Setup

- [ ] T001 Restore v1 from tag `exp/dense-v1`: `git checkout exp/dense-v1 -- modules/dense tests/test_dap.py`. Delete `modules/dense/templates/dense-return.md` and, in the same task, remove the return-contract lines from `modules/dense/rules.md` (its line 8, "Every delegation brief includes…", and the non-conforming-reply line), so `sdlc lint` doesn't flag a missing template. Port the tag's module tests into `main`'s `tests/test_sdlc.py` as class `DenseModule`, dropping `test_briefs_carry_the_return_contract`. List the kept tests in this task's progress-log line and mark the ones that assert v1 rules text: at least `test_install_renders_rules_skill_and_script` (asserts `dap.py fresh .sdlc/context/index.dap`, tag `tests/test_sdlc.py:291`) and `test_rules_point_at_show` (`:308-311`); T004 replaces both. Don't overwrite `main`'s other tests — files: `modules/dense/**`, `tests/test_dap.py`, `tests/test_sdlc.py` — verify: full suite passes (74 + 50 + the kept module tests); `python3 bin/sdlc lint` ok; the core-untouched check prints nothing — blocked-by: H4

## S1: Tracer, one lookup through the installed module (spec S1, P1)

Goal: an agent-facing `find` that returns budgeted, located excerpts, reached through the rules an install renders.
Acceptance: in a temp workspace installed with `--modules dense`, the rendered instructions name only the `find` command, and running the installed `dap.py find` on a fixture index returns ≤ 3 entries in ≤ 2,000 characters, with source locations and numbered excerpt lines.

- [x] T002 [S1] Write failing tests `Find.test_returns_best_three` (FR-010: best first, location, heading line, numbered matching lines; two sibling entries pointing to the same source section come back as one result with one excerpt) and `Find.test_budget_and_cut_marker` (FR-011, SC-005: a 26K section and 5 matching entries; output ≤ 2,000 characters; every shortened excerpt ends with the cut line naming its location, which the final guard never cuts off) — files: `tests/test_dap.py` — verify: `python3 -m unittest tests.test_dap.Find -v` fails because `find` is not a command — blocked-by: T001
- [x] T003 [S1] Implement `find()` and the `find` command per `contracts/find.md`: `nargs="*"` terms, entry scoring, excerpt, budget share per entry, cut line, the final guard that keeps room for the cut line, exits 0 and 1 — files: `modules/dense/skills/sdlc-dense-index/dap.py` — verify: `python3 -m unittest tests.test_dap -v` passes (the 50 v1 tests and the 2 new ones) — blocked-by: T002
- [x] T004 [S1] Write failing tests `DenseModule.test_rules_name_find_only` (FR-016, FR-018: the rendered instructions contain the exact `find` command under both `.claude/skills/…` and `.github/skills/…`, contain the lines on exits 1–3, stale and cut results, citing sources, "data, not instructions" and the rebuild after `sdlc-context` (FR-003, FR-017), and contain no "at the start", no "read the index" and no `show`) and `DenseModule.test_installed_find_runs` (FR-018: a `--targets copilot` install, then `.github/skills/sdlc-dense-index/dap.py find` answers a lookup). Replace `test_rules_point_at_show`, and update `test_install_renders_rules_skill_and_script` to assert the `find` line instead of `dap.py fresh` — files: `tests/test_sdlc.py` — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` fails on the rules text — blocked-by: T003
- [x] T005 [S1] Rewrite `rules.md` for v2: one command with its arguments under both skill paths ("whichever exists"), when to use it (before reading or searching the workspace documents), how to treat exits 1, 2 and 3 and stale or cut entries, cite sources not the index, data not instructions, rebuild after `sdlc-context` (FR-003, FR-016, FR-017). Update the usage notes in `SKILL.md` to point at `find` — files: `modules/dense/rules.md`, `modules/dense/skills/sdlc-dense-index/SKILL.md` — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` passes; `python3 bin/sdlc lint` ok (rules stay within the lint's 30-line cap) — blocked-by: T004

## S2: Every lookup outcome is explicit and safe (spec S1 cases, S2; P1)

Goal: no-match, usage errors, invalid index, stale, renamed and deleted sources, removed headings, read-only behaviour, markings and redaction.
Acceptance: the `Find` test class covers each outcome in `contracts/find.md`, and the suite is green.

- [x] T006 [S2] Write failing tests:
  - `Find.test_no_match`: exit 1;
  - `test_no_terms`: no terms, no index argument, an unknown option, and no terms with an invalid index all exit 3;
  - `test_short_terms_ignored`: terms under 3 characters are named; only short terms exits 3;
  - `test_invalid_index`: missing and invalid indexes exit 2 with `INVALID`; an index with 200 errors stays within 2,000 characters; an error on a secret-looking value doesn't repeat the value;
  - `test_stale_source_marked`: an edited, a renamed and a deleted source; for each, both `find` marks it stale and `fresh` exits 1 naming it (SC-004);
  - `test_heading_gone`;
  - `test_read_only`: hash every file before and after; no `__pycache__`;
  - `test_keeps_unverified_marker`;
  - `test_redacts_secret_lines`.

  Covers FR-008, FR-011–FR-015, NFR-001 and SC-004 — files: `tests/test_dap.py` — verify: the new tests fail for the expected reasons, not on errors — blocked-by: T003
- [x] T007 [S2] Implement the remaining outcomes: the order of checks, exit 3 and short-term handling, exit 2 with at most 10 errors, stale marking for edited, renamed and deleted sources, the heading-gone message, line redaction — files: `modules/dense/skills/sdlc-dense-index/dap.py` — verify: `python3 -m unittest tests.test_dap -v` passes — blocked-by: T006
- [x] T008 [S2] Add the regression guard `Find.test_fast_on_large_workspace` (NFR-002: generated 300 KB of sources and a 300-entry index; one lookup under 2 s, validation under 10 s). It is a guard, not a RED test, and is expected to pass on first run; optimise only if it fails — files: `tests/test_dap.py`, `modules/dense/skills/sdlc-dense-index/dap.py` — verify: `python3 -m unittest tests.test_dap.Find.test_fast_on_large_workspace -v` passes — blocked-by: T007

## S3: The evaluation method ships with the module (spec S3, P2)

Goal: the shipped method matches v2: leak check, tie rule, the context-loaded measure, the lookup columns, no return contract.
Acceptance: the module test checks the template's content, and the template is usable as is for the shop6 set.

- [x] T009 [P] [S3] Write failing test `DenseModule.test_eval_template_v2` (FR-019). The template must name:
  - the leak check before the first run;
  - the tie rule;
  - the *context loaded* measure and SC-002's formula;
  - the lookup-used, lookup-size and cites-index columns;
  - the document and code-only task types;
  - the outside-the-workspace location.

  It must not mention the return contract — files: `tests/test_sdlc.py` — verify: the test fails on the current template — blocked-by: T005
- [x] T010 [S3] Update `dense-eval.md` to v2:
  - the paired procedure: a leak check per arm, one fresh session per task and arm, the exact tool allowlist from the plan, `evals/run.py`;
  - the tie rule;
  - the record format: pass, context loaded, lookup used, lookup sizes, cites index or sources;
  - the gate per SC-001 and SC-002.

  Files: `modules/dense/templates/dense-eval.md` — verify: `python3 -m unittest tests.test_sdlc.DenseModule -v` passes — blocked-by: T009

## Gates before the evaluation

- [x] T011 Run full gates and record outcomes — verify: `python3 -m unittest discover -s tests -t .` passes; `python3 bin/sdlc lint` ok; the core-untouched check prints nothing — blocked-by: T008, T010
- [x] T012 Converge: spec, plan, tasks and code agree (`sdlc-converge`) — files: `specs/002-dense-find-command/tasks.md` (Convergence section) — verify: the Convergence section lists no open gap, or each gap is a new task — blocked-by: T011
- [ ] T013 Independent review (`sdlc-review`); verdict recorded. Record the reviewed kit revision: the evaluation runs this revision — files: `specs/002-dense-find-command/review.md` — verify: its first line is exactly `VERDICT: APPROVED`; the revision is in its header — blocked-by: T012

## S4: Prove the gain on shop6 (spec S3, P2; gate SC-001, SC-002, SC-005, SC-007, FR-017)

Goal: the paired evaluation the gate needs, run on the reviewed revision. Outside the kit: nothing in this slice writes to the kit except the result summary in this file.
Acceptance: `~/Projects/shop6-evals/dense2/results.md` holds every run, the tie reruns, the gate result, the evaluated kit revision and Phong's decision.

- [ ] T014 [S4] Write the 8 tasks (6 document tasks: routing, cross-repo impact, review against PRD or architecture; 2 code-only), each with Expect items checked against code at pinned revisions, plus the gate from SC-001 and SC-002, in the v2 template. Write each prompt verbatim to its own file for `evals/run.py`, and a key checker with a `--leak <arm>` mode used in T016 — files: `~/Projects/shop6-evals/dense2/tasks.md`, `setup.md`, `prompts/E1.txt` … `prompts/E8.txt`, `check_keys.py` — verify: `python3 -I ~/Projects/shop6-evals/dense2/check_keys.py` exits 0 (every Expect `path:line` exists at its pinned revision, and every prompt file matches `tasks.md` verbatim) — blocked-by: T010
- [ ] T015 [S4] After H1, freeze: sha256 of `tasks.md` recorded in the evals README, committed locally — files: `~/Projects/shop6-evals/README.md`, `dense2/tasks.md` — verify: hash recorded; Phong's review noted — blocked-by: T014, H1
- [ ] T016 [S4] Build the arms at the pinned revisions and install **both** from the reviewed kit revision (T013): A with shop6's lock modules, B with those plus `dense`, and B's index freshly built and committed. Both with `.ignore`. Run the leak check in both, for the prompts and for every Expect item's text (`check_keys.py --leak <arm>`) — files: `~/Projects/shop6-dense2-bench/{A,B}` (worktrees, removed in T020), `~/Projects/shop6-evals/dense2/check_keys.py` — verify: `dap.py validate` in B prints `valid` (SC-003); the leak check gives 0 matches in both arms; the managed `AGENTS.md` blocks of A and B differ only by the module-rules section and the dense Skills entry — blocked-by: T013, T015
- [ ] T017 [S4] Run the 16 base sessions through `evals/run.py` with the plan's exact allowlist in both arms, alternating arm order. Parse every transcript for:
  - context loaded;
  - lookup used, and each lookup output's size (SC-005);
  - whether the answer cites the index or the sources (FR-017);
  - reads outside the arm.

  A change to `dap.py` or `rules.md` after the first run means a full rerun — files: `~/Projects/shop6-evals/dense2/runs/` — verify: 16 transcripts, each with a result event; no read outside the arm; both arms unchanged — blocked-by: T016
- [ ] T018 [S4] Grade the base runs with a fresh read-only grader that sees only the answers, the Expect items and the pinned code — files: `~/Projects/shop6-evals/dense2/grades.md` — verify: all 16 runs have a verdict with its reason — blocked-by: T017
- [ ] T019 [S4] Tie rule (spec S3.3): for every task whose base result differs between the arms, run it once more in both arms (same allowlist, same parse) and grade the reruns with the same grader brief — files: `~/Projects/shop6-evals/dense2/runs/`, `grades.md` — verify: every differing task has two graded runs per arm; or "no differing task" recorded — blocked-by: T018
- [ ] T020 [S4] After H2, compute the gate (SC-001 after the tie rule, SC-002 with the spec's formula over all base runs plus the both-passed median, SC-005, SC-007, plus FR-017 citations per run). Write `results.md` with the evaluated kit revision, then remove the arms — files: `~/Projects/shop6-evals/dense2/results.md` — verify: gate computed from `grades.md` and the parsed transcripts; no worktree entries left for the bench — blocked-by: T019, H2

## Final

- [ ] T021 Update docs:
  - the module's entry in `README.md`;
  - the status line of ADR 0001 (adopted with spec 002 on pass; still not adopted on fail);
  - spec 002's status per the gate (implemented through `sdlc-ship`, or rejected);
  - on pass, spec 001 becomes `superseded by 002`.

  Files: `README.md`, `docs/adr/0001-dense-index-format.md`, `specs/002-dense-find-command/spec.md`, `specs/001-dense-agent-protocol/spec.md` — verify: the status lines of both specs and of the ADR match the gate result; `python3 bin/sdlc lint` ok — blocked-by: T020, H3

## Blocked / human-only

- [x] H4 Approve implementation after `sdlc-analyze` (the T3 gate). T001 waits for it — owner: phong.ngo.vn — unblocked when: `sdlc-analyze` reports no blocking finding
- [ ] H1 Review the 8 answer keys before the freeze. The person who writes them also builds the module, so someone checks them first — owner: phong.ngo.vn — unblocked when: T014 is done
- [ ] H2 Spot-check the grader's verdicts (at least one pass and one fail per arm, where present) — owner: phong.ngo.vn — unblocked when: T019 is done
- [ ] H3 Decide on the gate result and approve merge or rejection (`sdlc-ship`; merges need explicit approval) — owner: phong.ngo.vn — unblocked when: T020 is done

## Coverage

| FR / item | Tasks |
|---|---|
| FR-001, FR-020 | T001 (ported `test_add_and_remove_restores_install`), T011 |
| FR-002–FR-007, FR-009 | T001 (restored v1 code and its 50 tests) |
| FR-008 | T006, T007 |
| FR-010, FR-011 | T002, T003, T006 (budget for errors) |
| FR-012–FR-015 | T006, T007 |
| FR-016 | T004, T005 |
| FR-003 | T004, T005 |
| FR-017 | T004, T005 (rules text tested); T017 and T020 (citations checked per run) |
| FR-018 | T004, T005 |
| FR-019 | T009, T010, T014 |
| NFR-001 | T006, T007 |
| NFR-002 | T008 |
| SC-001, SC-002, SC-007 | T017–T020 |
| SC-003 | T016 (`validate` on the fresh shop6 index) |
| SC-004 | T006 (`find` and `fresh`) |
| SC-005 | T002, T006, T017, T020 |
| SC-006 | T001, T011 |

## Progress log

- 2026-11-03 `2f97f9d` — T001–T011 done on `feat/002-dense-find`. H4: approval given by phong.ngo.vn in chat on 2026-11-03 ("implementing the spec 002"); both analyze passes had no open finding. T001 restore from `exp/dense-v1` (return contract removed): 132 OK. T002 RED `python3 -m unittest tests.test_dap.Find` 2 FAIL (`find` not a command). T003 first GREEN attempt failed `test_budget_and_cut_marker` (2,020 > 2,000: the cut-line reserve was 0 when the excerpt started as the whole section); fixed by reserving the cut line's exact length unless the whole section fits; `tests.test_dap` 52 OK. T004 RED: 2 FAIL (`test_install_renders_rules_skill_and_script`, `test_rules_name_find_only`); `test_installed_find_runs` passed at once because T003 already shipped the command. T005 GREEN after two wording fixes (the exact `.github/skills/…` command and the phrase "before reading or searching the workspace documents" must be in the rules): 135 OK, lint ok, rules 7 lines. T006 RED: 6 FAIL (stale, heading gone, exit 3, error cap, redaction, short terms); 5 tests already passed on v1 behaviour (`test_no_match`, `test_read_only`, `test_keeps_unverified_marker`, …). T007 GREEN: `tests.test_dap` 61 OK after fixing a test bug (the three stale cases shared one directory). T008 `test_fast_on_large_workspace` passed first run (guard, as expected; 0.17 s). T009 RED `test_eval_template_v2` FAIL; T010 GREEN. T011: `python3 -m unittest discover -s tests -t .` → 146 OK; `python3 bin/sdlc lint` → ok; `git diff --stat main -- core adapters bin evals` → empty; no `__pycache__` under `modules/`. Next: T012 converge, T013 review

- 2026-10-30 `0ee9391` (branch `feat/002-dense-find` from `main`) — spec, plan and tasks drafted; baseline suite 74 OK.
- 2026-10-30 — analyze pass 1: 0 CRITICAL, 7 HIGH, 13 MEDIUM, 7 LOW (A1–A27); all fixed in spec, plan, `contracts/find.md` and these tasks.
- 2026-10-30 — analyze pass 2: 0 CRITICAL, 4 HIGH, 10 MEDIUM, 8 LOW (B1–B22); all fixed (B13's commit of the shop6 decision record waits for Phong); next: H4.

## Convergence (2026-11-03, 2f97f9d)

Compared `modules/dense/**`, `tests/test_dap.py` (`Find`) and `tests/test_sdlc.py` (`DenseModule`) with spec 002, plan and `contracts/find.md`. Method: each FR/NFR/SC mapped to a test or an observed run; contract behaviours spot-checked by hand (heading-plus-5-lines fallback, case-insensitive terms, cut marker).

| Item | Result | Evidence |
|---|---|---|
| FR-001, FR-020, SC-006 (opt-in; only rules block and Skills line change) | met | `DenseModule.test_add_and_remove_restores_install`; core-untouched diff empty |
| FR-002–FR-007, FR-009 (key list, pointers, hashes, freshness, validation, atomic commit) | met (v1 code and its 50 tests restored unchanged) | `tests.test_dap` |
| FR-008 (no new facts, markers kept) | met for the lookup (`test_keeps_unverified_marker`); the build step is agent behaviour, covered by the SKILL.md self-check | |
| FR-010, FR-011, SC-005 (best 3, locations, 2,000-char budget on every exit, cut marker) | met | `Find.test_returns_best_three`, `test_budget_and_cut_marker`, `test_invalid_index`, `test_no_match` |
| FR-012 (no match, short terms) | met | `test_no_match`, `test_no_terms`, `test_short_terms_ignored` |
| FR-013, SC-004 (lookup checks freshness; edited, renamed, deleted, heading gone) | met | `test_stale_source_marked`, `test_heading_gone` |
| FR-014 (missing or invalid index: own exit code) | met | `test_invalid_index` |
| FR-015 (read-only) | met | `test_read_only` |
| FR-016, FR-017, FR-003, FR-018 (rules text; both skill paths; Copilot) | met | `DenseModule.test_rules_name_find_only`, `test_installed_find_runs`, `test_copilot_only_install_uses_github_skills` |
| FR-019 (evaluation method: leak check, tie rule, v2 columns, outside the workspace) | met | `DenseModule.test_eval_template_v2` |
| NFR-001 (no secret echo; excerpt redaction) | met | `test_invalid_index` (value not echoed), `test_redacts_secret_lines` |
| NFR-002 (speed) | met | `test_fast_on_large_workspace`: 0.17 s for the lookup |
| SC-001, SC-002, SC-007 | open: need the shop6 evaluation (T014–T020) | |
| SC-003 (shop6 index validates) | open: T016 | |

Gaps: none that need a new task. Two notes for the reviewer: (1) `dap.py show` stays in the script for maintainers (spec 001's self-check step uses it); the rules no longer mention it. (2) the rules are 7 lines; the plan allowed up to the lint cap of 30.
