# Tasks: Usage metrics per resolved unit

Inputs: [spec.md](spec.md), [plan.md](plan.md), [contracts/usage.md](contracts/usage.md), [ADR-0002](../../docs/adr/0002-usage-metric-technique.md) · Status: draft · Created: 2026-11-03 · Branch: `feat/003-usage-metrics`

Verify (kit root):
- Narrow: `python3 -m unittest tests.test_usage -v` · `python3 -m unittest tests.test_sdlc.UsageSkill -v`
- Full: `python3 -m unittest discover -s tests -t .` (baseline 152 OK on `main` at `fc77daa`, 2026-11-03) · `python3 bin/sdlc lint`

Legend: `- [ ] T001 [P?] [S1] Description — files: … — verify: … — blocked-by: T00x`
- `[P]` may run in parallel: no shared files, no blocking edge.
- `[S1]` slice the task belongs to. `verify` is the command or observation that proves this task alone.
- Every test task is RED first: run it, read why it fails, and only then write the code (`sdlc-tdd`).

## S1: Tracer, one task measured end to end through an installed skill (spec S1, P1)

Goal: with the switch on, `start` then `stop` on a task writes a usage line with exact figures from a generated transcript, reached from an installed `sdlc-usage` skill.
Acceptance: in a temp project installed from the kit, with `usage.enabled` true and a generated transcript under a temp `CLAUDE_CONFIG_DIR`, the installed `usage.py start`/`stop` leave a mark and one usage line in `tasks.md`'s Progress log, and the figures equal the fixture's totals.

- [ ] T001 [S1] Write failing tests `Tracer.test_start_writes_a_mark`, `test_stop_writes_the_exact_line` (a generated transcript of 3 responses; figures: four token fields, sub-agents 0, wall minutes, turns, model; all exact) and `test_section_is_created_when_absent` — files: `tests/test_usage.py` — verify: `python3 -m unittest tests.test_usage.Tracer -v` fails because `usage.py` does not exist — blocked-by: H1
- [ ] T002 [S1] Write `usage.py` for `start` and `stop` per `contracts/usage.md`: project-root and switch reading, id validation, section append, transcript lookup under `$CLAUDE_CONFIG_DIR` or `~/.claude`, per-file de-duplication by `message.id`, main-session figures, line formatting — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage.Tracer -v` passes — blocked-by: T001
- [ ] T003 [S1] Write failing test `UsageSkill.test_install_ships_the_skill_and_script` (both skill paths; `usage.py` copied; the Skills index lists `sdlc-usage`; `sdlc check` is ok; no `__pycache__`) and `test_installed_script_runs` (the Tracer flow through `.claude/skills/sdlc-usage/usage.py` of a real install, and through `.github/skills/` for a Copilot-only install) — files: `tests/test_sdlc.py` — verify: `python3 -m unittest tests.test_sdlc.UsageSkill -v` fails (skill missing) — blocked-by: T002
- [ ] T004 [S1] Write `core/skills/sdlc-usage/SKILL.md` (the standard sections; the exact commands and arguments, when to call, how to read each outcome, "run the stop after sub-agents finish") and the task step in `sdlc-implement` (step 3 start, step 4 stop, each guarded by `usage.enabled`, each with the exact command and `--record <feature>/tasks.md`) — files: `core/skills/sdlc-usage/SKILL.md`, `core/skills/sdlc-implement/SKILL.md` — verify: `python3 -m unittest tests.test_sdlc.UsageSkill -v` passes; `python3 bin/sdlc lint` ok; each skill file ≤ 200 lines — blocked-by: T003

## S2: Figures are exact, including sub-agents and a real run (spec S1.4, FR-009, FR-010, FR-019; SC-002, SC-009)

Goal: duplicated records, sub-agent files, several models and thinking-free turns all give the numbers an independent computation gives, and the real recorded run matches the CLI.
Acceptance: `tests.test_usage.Dedupe`, `SubAgents`, `Models` and `RealFixture` pass.

- [ ] T005 [S2] Write failing tests: `Dedupe.test_one_response_written_five_times_counts_once` (also a response whose last record has the larger `output_tokens`); `SubAgents.test_separate_and_not_added_to_main` (two sub-agent files, one outside the window); `Models.test_each_distinct_model_listed_and_synthetic_ignored`; `Models.test_turns_count_main_responses_only` — files: `tests/test_usage.py` — verify: the four fail for the expected reasons (a naive sum, no sub-agent field) — blocked-by: T004
- [ ] T006 [S2] Implement the sub-agent window sum (files under `<session>/subagents/`), turns, model list and the window filter by record timestamp — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T005
- [ ] T007 [S2] Build the pinned real fixture from the recorded run (session `0b8b2d7f-d1c8-4d58-86d4-eb8b0ad184f6`, main and `subagents/agent-afa034c1c95177076.jsonl`, transcripts kept under `~/.claude/projects/` for 30 days): a script-free, one-off copy that keeps every key the real records have but replaces all message content, tool input and tool output with `""`; record the CLI's `result` figures beside it (`usage`: 6 / 573 / 103,919 / 17,271; `modelUsage`: 12 / 1,347 / 169,358 / 52,629). If the transcripts are gone, re-record with the one-line `claude -p` run in ADR-0002 — files: `tests/fixtures/usage/real-run/` — verify: `grep -c` for a word of the original prompt finds 0; the file parses as JSONL with the same record types as the original — blocked-by: T006
- [ ] T008 [S2] `RealFixture.test_matches_the_cli_result`: start and stop around the fixture's whole span give main = 6 / 573 / 103,919 / 17,271 and main + sub-agents = the `modelUsage` totals (SC-009). Seen RED first by running it with the naive sum swapped in a scratch copy — files: `tests/test_usage.py` — verify: `python3 -m unittest tests.test_usage.RealFixture -v` passes; the scratch mutation fails it — blocked-by: T007

## S3: "Not available" instead of 0 (spec S2; FR-012, FR-013, FR-020; SC-003)

Goal: every missing input names its reason, and no figure is ever written as 0 for lack of data.
Acceptance: `tests.test_usage.NotAvailable` passes for no transcript, no session id, no config folder, no start mark, an unexpected shape and a partial unit.

- [ ] T009 [S3] Write failing tests `NotAvailable.test_no_session_id_and_no_claude_folder` (`no transcript on this target`), `test_session_id_unknown_keeps_wall_time`, `test_transcript_not_found`, `test_no_start_mark`, `test_unexpected_format_for_the_affected_segment_only` (a record without `cache_read_input_tokens`), `test_partial_names_the_missing_segment`, and `test_no_figure_is_zero_when_data_is_missing` (scan every output line) — files: `tests/test_usage.py` — verify: they fail for the expected reasons — blocked-by: T006
- [ ] T010 [S3] Implement the reasons, the per-segment shape check and the `PARTIAL` suffix per the contract — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T009

## S4: Off means off (spec S3; FR-001, FR-002, FR-015, FR-018; SC-004)

Goal: with the switch absent, false or malformed, nothing is read or written, and an install differs from a kit without the feature only by the new skill.
Acceptance: `SwitchOff` and `UsageSkill.test_off_install_differs_only_by_the_new_skill` pass.

- [ ] T011 [S4] Write failing tests `SwitchOff.test_absent_false_and_malformed_write_nothing` (record and transcript folder byte-identical; output `usage off`), `test_by_hand_works_the_same_with_or_without_a_skill` (S3.4), and `UsageSkill.test_off_install_differs_only_by_the_new_skill` (an install with and without the feature: the added paths are `sdlc-usage` files, the Skills index line, and the edited `sdlc-implement`/`sdlc-debug` files; `config.json` untouched) — files: `tests/test_usage.py`, `tests/test_sdlc.py` — verify: the first two fail only if T002's switch check is wrong, so this task is a guard and is expected to pass on first run, except the install test, which fails until T018 — blocked-by: T004
- [ ] T012 [S4] Make the install test pass by recording the expected added and changed files in the test itself, and confirm `usage.py` makes no call when off (reads `config.json` only) — files: `tests/test_sdlc.py`, `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage.SwitchOff tests.test_sdlc.UsageSkill -v` passes — blocked-by: T011, T018

## S5: Resume, retries and abandoned units (spec S1.3, S4.3; FR-008, FR-016, FR-017)

Goal: a unit worked over two sessions adds up, a repeated command changes nothing, and an unfinished unit leaves only its mark.
Acceptance: `tests.test_usage.Resume` passes.

- [ ] T013 [S5] Write failing tests `Resume.test_two_sessions_add_up` (the first segment ends at its session's last timestamp), `test_second_start_in_the_same_session_adds_no_mark`, `test_second_stop_changes_nothing`, `test_unit_never_stopped_leaves_only_its_mark`, `test_segment_with_missing_transcript_is_partial` — files: `tests/test_usage.py` — verify: they fail for the expected reasons — blocked-by: T010
- [ ] T014 [S5] Implement segment windows across sessions, `already started` and `already closed` — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T013

## S6: Privacy and containment (spec S5; NFR-001–NFR-003; SC-005, SC-006)

Goal: no transcript content leaves the script, nothing goes to the network, and `--record` cannot escape the project.
Acceptance: `tests.test_usage.Privacy` passes.

- [ ] T015 [S6] Write failing tests `Privacy.test_sentinel_in_messages_is_never_output_or_written` (message text, tool input and tool output hold a sentinel; search stdout, stderr, the record and the folder), `test_malformed_content_still_gives_figures`, `test_no_network_or_subprocess_modules` (the import list is exactly the contract's; a `sitecustomize` that makes `socket` raise does not break a run), `test_record_must_stay_inside_the_project` (`..`, an absolute path, a symlink out) and `test_unit_id_charset` — files: `tests/test_usage.py` — verify: the containment and charset tests fail (no check yet); the sentinel and import tests may already pass and are noted as guards — blocked-by: T014
- [ ] T016 [S6] Implement record confinement (resolve, then require the project root as prefix) and unit-id validation; confirm only the contract's modules are imported — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T015

## S7: Bugs and fixed findings share the line (spec S4; FR-003, FR-004, FR-005, FR-006; SC-001, SC-007)

Goal: `sdlc-debug` and the finding fix path record usage in the owning record, with named commands, using the same line.
Acceptance: `UsageSkill` tests on templates and skill texts pass; two eval rows exist.

- [ ] T017 [P] [S7] Write failing tests `UsageSkill.test_bug_template_has_a_usage_section`, `test_review_report_has_a_fix_log_section`, `test_debug_names_the_exact_commands_and_the_bug_record` (start at reproduce, stop at close, `--section "Usage"`, creates the record when absent), `test_implement_names_the_exact_commands_for_a_finding` (`--section "Fix log"` for a review finding, `Progress log` for an analyze finding), and `test_every_skill_that_asks_names_the_command` (every `usage.py` mention in a skill carries `start`/`stop` and `--record`) — files: `tests/test_sdlc.py` — verify: they fail for the expected reasons — blocked-by: T004
- [ ] T018 [P] [S7] Add `## Usage` to `core/templates/bug.md`, `## Fix log` to `core/templates/review-report.md`, a Progress-log note to `core/templates/tasks.md`; update `sdlc-debug` and the finding step of `sdlc-implement` (all guarded by `usage.enabled`) — files: `core/templates/bug.md`, `core/templates/review-report.md`, `core/templates/tasks.md`, `core/skills/sdlc-debug/SKILL.md`, `core/skills/sdlc-implement/SKILL.md` — verify: `python3 -m unittest tests.test_sdlc.UsageSkill -v` passes; `python3 bin/sdlc lint` ok; skills ≤ 200 lines — blocked-by: T017
- [ ] T019 [S7] Add unnamed-prompt eval rows U1 (a task in `sdlc-implement` with the switch on: the agent runs the start command before editing and the stop command after the verify step) and U2 (a bug through `sdlc-debug`: a start at reproduce, a line in the bug record at close), each with its Expect, to `evals/scenarios.md` — files: `evals/scenarios.md` — verify: `python3 bin/sdlc lint` ok; each row's prompt names neither the skill nor the script — blocked-by: T018

## Final

- [ ] T020 Live check, hand-run: install the kit in a scratch repo with the switch on, run U1 and U2 through `evals/run.py`, then one `claude -p` run with a sub-agent; compare the usage line with that run's own `result` (`usage`, `modelUsage`). Record the Claude Code version and the outcome under `evals/results/` — files: `evals/results/0.6.0.md` (or the next version) — verify: the four token fields equal the CLI's figures, or the difference is explained; the agent ran the commands unprompted in U1 and U2 — blocked-by: T019, T016, T014
- [ ] T021 Run full gates and record outcomes — verify: `python3 -m unittest discover -s tests -t .` passes; `python3 bin/sdlc lint` ok; `git diff --stat main -- bin adapters/config.default.json` prints nothing apart from the one `RENDERING.md` line — blocked-by: T020
- [ ] T022 Converge: spec, plan, tasks and code agree (`sdlc-converge`) — files: `specs/003-usage-metrics/tasks.md` (Convergence section) — verify: no open gap, or each gap is a new task — blocked-by: T021
- [ ] T023 Independent review (`sdlc-review`) by a fresh read-only agent; verdict recorded, including the reviewed revision — files: `specs/003-usage-metrics/review.md` — verify: first line exactly `VERDICT: APPROVED` — blocked-by: T022
- [ ] T024 Update docs: `README.md` (Status, Capabilities, one "Usage metrics" paragraph with the switch), `adapters/RENDERING.md` (skills may ship scripts), spec status and `Approved` line, `VERSION` bump if H2 says release — files: `README.md`, `adapters/RENDERING.md`, `specs/003-usage-metrics/spec.md`, `VERSION` — verify: `python3 bin/sdlc lint` ok; the README paragraph matches the contract (switch key, command names) — blocked-by: T023

## Blocked / human-only

- [ ] H1 Approve this plan and the choices P4 (a bug record is created for an obvious bug when the switch is on) and P5 (exact integers, departing from the decision record's `1.5K` example) before T001. Run `sdlc-analyze` first — owner: phong.ngo.vn — unblocked when: `sdlc-analyze` reports no blocking finding
- [ ] H2 Approve merge and decide on a `VERSION` bump (`sdlc-ship`) — owner: phong.ngo.vn — unblocked when: T023 is APPROVED

## Coverage

| FR / item | Tasks |
|---|---|
| FR-001, FR-002, FR-015, FR-018, SC-004 | T003, T011, T012 |
| FR-003, FR-004, FR-005, FR-006, SC-001, SC-007 | T004, T017, T018, T019 |
| FR-007 (start mark) | T001, T002 |
| FR-008, FR-016, FR-017 | T013, T014 |
| FR-009, FR-011 (fields, wall) | T001, T002, T005, T006 |
| FR-010 (sub-agents) | T005, T006, T008 |
| FR-012, FR-013, FR-020, SC-003 | T009, T010 |
| FR-014, NFR-001, NFR-003, SC-005 | T015, T016 |
| FR-019, SC-002 | T005, T006 |
| SC-009 | T007, T008, T020 |
| NFR-002, SC-006 | T015, T016 |
| SC-008 (reported) | after spec 002's build tasks run with the switch on (retro) |

## Progress log

- 2026-11-03 `77f4f98` (branch `feat/003-usage-metrics`, merged with `main` at `fc77daa`) — plan, contract and tasks drafted after ADR-0002 was accepted; baseline 152 tests OK, lint ok; next: `sdlc-analyze`, then H1
