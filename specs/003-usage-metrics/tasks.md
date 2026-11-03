# Tasks: Usage metrics per resolved unit

Inputs: [spec.md](spec.md), [plan.md](plan.md), [contracts/usage.md](contracts/usage.md), [ADR-0002](../../docs/adr/0002-usage-metric-technique.md) · Status: draft · Created: 2026-11-03 · Branch: `feat/003-usage-metrics`

Verify (kit root):
- Narrow: `python3 -m unittest tests.test_usage -v` · `python3 -m unittest tests.test_sdlc.UsageSkill -v`
- Full: `python3 -m unittest discover -s tests -t .` (baseline 152 OK on `main` at `fc77daa`, 2026-11-03) · `python3 bin/sdlc lint`

Legend: `- [ ] T001 [L1] Description — files: … — verify: … — blocked-by: T00x`
- `[L1]` slice the task belongs to. `verify` is the command or observation that proves this task alone.
- No task is marked `[P]`: they share `tests/test_usage.py`, `usage.py` or the skill files, so the edges below run in one order.
- **A test task lists behaviours, not a batch.** Write the first test, run it, read why it fails, make it pass, then take the next (`sdlc-tdd`). A test that passes on its first run is recorded in the progress log as a guard, with the reason.

## L1: Tracer, one task measured end to end through an installed skill (spec S1, P1)

Goal: with the switch on, `start` then `stop` on a task writes a usage line with exact figures from a generated transcript, reached from an installed `sdlc-usage` skill; with the switch off nothing is written.
Acceptance: in a temp project installed from the kit, with `usage.enabled` true and a generated transcript under a temp `CLAUDE_CONFIG_DIR`, the installed `usage.py start`/`stop` leave a mark and one usage line in `tasks.md`'s Progress log, and the figures equal the fixture's totals.

- [ ] T001 [L1] Tests, one at a time, in `Tracer`: `test_start_writes_a_mark`; `test_stop_writes_the_exact_line` (3 responses; four token fields, sub-agents 0, wall minutes, turns, model; exact); `test_section_is_created_when_absent`; `test_off_writes_nothing_and_reads_no_transcript` (switch absent and `false`); `test_unit_id_charset`; `test_timestamps_with_z_and_fraction` (`...00Z` and `...00.123Z`, which Python 3.9's `fromisoformat` rejects) — files: `tests/test_usage.py` — verify: `python3 -m unittest tests.test_usage.Tracer -v` fails because `usage.py` does not exist — blocked-by: H1
- [ ] T002 [L1] Write the minimum `usage.py` that T001's tests force, no more: `start` and `stop` per `contracts/usage.md` for one session and one record: project-root and switch reading (only JSON `true` is on), id validation, a plain append at the end of the section (created when absent), transcript lookup under `$CLAUDE_CONFIG_DIR` or `~/.claude`, the main-session figures from one record per message id, line formatting, the timestamp regex. **Not yet:** de-duplication (T006), sub-agents and windows (T006), the atomic temporary-file write (T013), reasons for missing data (T010). The real kit lints red from now until T004 (a skill folder without `SKILL.md`); run only the narrow tests until then — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage.Tracer -v` passes — blocked-by: T001
- [ ] T003 [L1] Write failing test `UsageSkill.test_install_ships_the_skill_and_script` (both skill paths; `usage.py` copied; the Skills index lists `sdlc-usage`; `sdlc check` is `ok`; no `__pycache__`) `test_installed_script_runs` (the Tracer flow through `.claude/skills/sdlc-usage/usage.py` of a real install, and through `.github/skills/` for a Copilot-only install) and `test_implement_runs_start_and_stop_for_a_task` (the rendered `sdlc-implement` names `usage.py start` and `usage.py stop` with `--record`, guards both with `usage.enabled`, and says to run `[P]` tasks one after another when the switch is on) — files: `tests/test_sdlc.py` — verify: `python3 -m unittest tests.test_sdlc.UsageSkill -v` fails (skill missing, text missing) — blocked-by: T002
- [ ] T004 [L1] Write `core/skills/sdlc-usage/SKILL.md` (the standard sections; the exact commands and arguments; run from the project root; how to read each outcome; "run the stop after sub-agents finish"; never edit `<!-- usage-start` lines) and the task step in `sdlc-implement` (step 2: with the switch on, run `[P]` tasks one after another; step 3 start; step 4 stop; each guarded by `usage.enabled`, with the exact command and `--record <feature>/tasks.md`) — files: `core/skills/sdlc-usage/SKILL.md`, `core/skills/sdlc-implement/SKILL.md` — verify: `python3 -m unittest tests.test_sdlc.UsageSkill -v` passes; `python3 bin/sdlc lint` ok; each skill file ≤ 200 lines — blocked-by: T003

## L2: Figures are exact, including sub-agents and a real run (spec S1.4, FR-009–FR-011, FR-019; SC-002, SC-009)

Goal: duplicated records, sub-agent files, several models, window edges and rounding all give the numbers an independent computation gives, and the real recorded run matches the CLI.
Acceptance: `Dedupe`, `SubAgents`, `Models`, `Windows` and `RealFixture` pass.

- [ ] T005 [L2] Tests, one at a time: `Dedupe.test_one_response_written_five_times_counts_once` (and a response whose last record has the larger `output_tokens`); `SubAgents.test_separate_and_not_added_to_main` (two files, one outside the window) and `test_no_subagents_folder_means_zero`; `Models.test_each_distinct_model_listed_synthetic_and_invalid_ignored`; `Models.test_turns_count_main_responses_only`; `Windows.test_half_open_and_straddling_response_counted_once`; `Windows.test_wall_rounded_once_half_up` — files: `tests/test_usage.py` — verify: each fails for its expected reason (a naive sum, no sub-agent field, rounding per segment) — blocked-by: T004
- [ ] T006 [L2] Implement per-file de-duplication by `message.id` (last record wins), the sub-agent window sum (files under `<session>/subagents/`), turns, model list, the half-open window filter on the last record's timestamp, and single rounding — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T005
- [ ] T007 [L2] Build the pinned real fixture from the recorded run (session `0b8b2d7f-d1c8-4d58-86d4-eb8b0ad184f6`: main transcript and `subagents/agent-afa034c1c95177076.jsonl`, kept under `~/.claude/projects/` for 30 days) with a throwaway allowlist script that is **not** committed: for each record keep only `type`, `timestamp`, and for assistant records `message.{id,model,role,usage}`, with a fixture session id; drop `cwd`, `sessionId`, paths, content, tool input and output. Record the CLI's `result` beside it (`usage`: 6 / 573 / 103,919 / 17,271; `modelUsage`: 12 / 1,347 / 169,358 / 52,629; `thinkingTokens` 66). If the transcripts are gone, re-record with the `claude -p` run in ADR-0002 — files: `tests/fixtures/usage/real-run/` — verify: a scan of the fixture for the home path, the user name and `@` finds 0 matches; every line parses as JSON; record counts per type equal the original's usage-bearing records — blocked-by: T006
- [ ] T008 [L2] `RealFixture.test_matches_the_cli_result`: with a window that spans the run, the four main fields equal `usage` exactly, and main plus the sub-agent figure equals the `modelUsage` sum over the four fields (SC-009). Seen RED first with the naive sum swapped in, in a scratch copy — files: `tests/test_usage.py` — verify: `python3 -m unittest tests.test_usage.RealFixture -v` passes; the scratch mutation fails it — blocked-by: T007

Reassessment point (plan, Size): after T008 run `git diff --stat main -- core/skills/sdlc-usage/usage.py`; above about 300 lines, simplify before S3.

## L3: "Not available" instead of 0 (spec S2; FR-012, FR-013, FR-020; SC-003)

Goal: every missing input names its reason, no figure is 0 for lack of data, and a real zero stays a zero.
Acceptance: `NotAvailable` passes for each row of the contract's table of cases.

- [ ] T009 [L3] Tests, one at a time, one per row of the contract's table: `test_no_session_id_and_no_claude_folder` (whole line, `no transcript on this target`); `test_session_id_unknown_keeps_wall_time`; `test_transcript_not_found_keeps_wall_time`; `test_no_start_mark`; `test_unexpected_format_per_segment` (a record without `cache_read_input_tokens`; a record without `message.id`; a timestamp not matching the regex; no response in the window; a bad middle line vs a bad last line); `test_partial_names_the_missing_segment`; `test_a_real_zero_is_written_as_zero` (`sub-agents 0`, uncached input 0); `test_no_data_fixture_has_no_zero_figure` (the zero scan runs only on the no-data fixtures) — files: `tests/test_usage.py` — verify: each fails for its expected reason — blocked-by: T008
- [ ] T010 [L3] Implement the reasons, the per-segment shape check, the bad-line rule and the `PARTIAL` suffix per the contract — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T009

## L4: Off means off (spec S3; FR-001, FR-002, FR-015; SC-004 first half)

Goal: with the switch in any non-`true` form, nothing is read or written, and the script works the same by hand as from a skill.
Acceptance: `SwitchOff` passes.

- [ ] T011 [L4] Guard tests (expected to pass on first run, because T002 already reads the switch; they pin the contract's cases): `SwitchOff.test_every_non_true_form_writes_nothing` (`"true"` string, `"usage": true`, `{"enabled": 1}`, invalid JSON, no `.sdlc/config.json`; the record and transcript folder byte-identical; output `usage off`), `test_by_hand_works_the_same_with_or_without_a_skill` (S3.4), `test_workspace_root_uses_the_nearest_config` (a child folder with its own config is ignored when run from the workspace root) — files: `tests/test_usage.py` — verify: `python3 -m unittest tests.test_usage.SwitchOff -v` passes; if a test fails, that is a defect in T002 and is fixed first — blocked-by: T010

## L5: Resume, retries, overlap and abandoned units (spec S1.3, S4.3; FR-008, FR-016, FR-017, FR-021, FR-022)

Goal: a unit worked over two sessions adds up, a repeated command changes nothing, overlap is flagged, and an unfinished unit leaves only its mark.
Acceptance: `Resume` passes.

- [ ] T012 [L5] Tests, one at a time: `test_two_sessions_add_up` (the first segment ends at the earlier of its session's last timestamp and the next mark); `test_second_start_in_the_same_session_adds_no_mark`; `test_unknown_session_marks_never_match`; `test_second_stop_changes_nothing`; `test_not_available_line_is_replaced_by_the_next_stop`; `test_id_match_is_exact` (`T01` vs `T012`); `test_unit_never_stopped_leaves_only_its_mark`; `test_segment_with_missing_transcript_is_partial`; `test_overlap_is_flagged`; `test_insertion_in_a_middle_section_keeps_the_rest_byte_for_byte` — files: `tests/test_usage.py` — verify: each fails for its expected reason — blocked-by: T011
- [ ] T013 [L5] Implement segment windows across sessions, `already started`, `already closed`, replacement, exact id match, overlap flag and the atomic insert (temporary file in the same folder, `os.replace`) — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T012

## L6: Privacy and containment (spec S5; NFR-001–NFR-004; SC-005, SC-006)

Goal: no transcript content leaves the script, nothing goes to the network, and the record and ids cannot escape.
Acceptance: `Privacy` passes.

- [ ] T014 [L6] Tests, one at a time: `test_sentinel_in_messages_tool_input_and_tool_output_is_never_output_or_written` (search stdout, stderr, the record and the folder); `test_malformed_content_still_gives_figures`; `test_imports_are_exactly_the_contracts_list`; `test_runs_with_sockets_and_stdin_unavailable` (a `sitecustomize` that makes `socket` raise, `stdin=DEVNULL`); `test_record_must_stay_inside_the_project` (`..`, an absolute path, a symlink out); `test_session_id_and_model_charsets` — files: `tests/test_usage.py` — verify: containment and charset tests fail (no check yet); the sentinel, import and socket tests may already pass and are recorded as guards — blocked-by: T013
- [ ] T015 [L6] Implement record confinement (resolve, then require the project root as prefix), the session-id and model checks, and the exit-2 cases — files: `core/skills/sdlc-usage/usage.py` — verify: `python3 -m unittest tests.test_usage -v` passes — blocked-by: T014

## L7: Bugs and fixed findings share the line (spec S4; FR-003–FR-006; SC-001, SC-007)

Goal: `sdlc-debug` and the finding-fix path record usage in the owning record, with named commands, using the same line.
Acceptance: `Units` and the `UsageSkill` text tests pass; three eval rows exist.

- [ ] T016 [L7] Tests, one at a time: `Units.test_bug_record_usage_section` (start and stop with `--section Usage` on a bug record, created from the template when absent); `Units.test_finding_unit_in_the_progress_log` (`review1-F3` and `analyze2-A5` in a `tasks.md`); `UsageSkill.test_bug_template_has_a_usage_section`; `UsageSkill.test_debug_names_the_exact_commands_and_the_bug_record` (start at reproduce, stop at close, `--section "Usage"`, creates the record when absent); `UsageSkill.test_implement_names_the_exact_commands_for_a_finding`; `UsageSkill.test_every_skill_that_asks_names_the_command` (every `usage.py` mention in a skill carries `start` or `stop` and `--record`; a guard for `sdlc-implement`, which T004 already covers); `UsageSkill.test_eval_rows_u1_u2_u3_name_neither_skill_nor_script` (reads `evals/scenarios.md`; fails until T018) — files: `tests/test_usage.py`, `tests/test_sdlc.py` — verify: the template and text tests fail for their expected reasons; `Units` may pass already (a guard: the script is section-generic) — blocked-by: T015
- [ ] T017 [L7] Add `## Usage` to `core/templates/bug.md` and a Progress-log note to `core/templates/tasks.md`; update `sdlc-debug` (start at reproduce, stop at close, create the bug record when the switch is on) and the finding step of `sdlc-implement` (unit id `<pass>-<finding id>`, `Progress log`), all guarded by `usage.enabled` — files: `core/templates/bug.md`, `core/templates/tasks.md`, `core/skills/sdlc-debug/SKILL.md`, `core/skills/sdlc-implement/SKILL.md` — verify: `python3 -m unittest tests.test_sdlc.UsageSkill -v` passes; `python3 bin/sdlc lint` ok; skills ≤ 200 lines — blocked-by: T016
- [ ] T018 [L7] Add unnamed-prompt eval rows U1 (a task in `sdlc-implement` with the switch on: the agent runs the start command before editing and the stop command after the verify step), U2 (a bug: a start at reproduce, a line in the bug record at close) and U3 (a review finding fix: a line in the progress log with the pass-prefixed id), each with its Expect — files: `evals/scenarios.md` — verify: `python3 bin/sdlc lint` ok; `python3 -m unittest tests.test_sdlc.UsageSkill.test_eval_rows_u1_u2_u3_name_neither_skill_nor_script -v` passes — blocked-by: T017

## Final

- [ ] T019 Install-set test, a guard that holds once all pieces exist: `UsageSkill.test_install_adds_only_the_expected_paths` (an install of this kit differs from the same list of paths without the feature only by the `sdlc-usage` files, the Skills index line, and the edited `sdlc-implement`, `sdlc-debug`, `bug.md` and `tasks.md`; `.sdlc/config.json` equals the default and has no `usage` key; `sdlc check` is `ok`) and `test_reinstall_is_idempotent_and_check_is_ok` (a second `install` writes nothing new). The suite cannot build the pre-feature kit without git history, so an update from an older install is covered by the pinned path list, the existing update tests, and the live check's fresh install (T020). The pinned path list lives in the test — files: `tests/test_sdlc.py` — verify: `python3 -m unittest tests.test_sdlc.UsageSkill -v` passes — blocked-by: T018
- [ ] T020 Live check, hand-run (needs an authenticated `claude` CLI and network; run by the owner or with their go-ahead). Steps: (1) in a headless run with `--allowed-tools 'Bash(echo:*)'`, print `$CLAUDE_CODE_SESSION_ID` and note whether it is set; (2) install the kit in a scratch repo with the switch on and run U1, U2, U3 through `evals/run.py --allowed-tools 'Read,Edit,Write,Grep,Glob,Agent,Bash(python3 .claude/skills/sdlc-usage/usage.py:*),Bash(python3 -m unittest:*),Bash(git status:*),Bash(git diff:*)'`; (3) one `claude -p` run with a sub-agent and, in it, start and stop around the whole task, asserting that `<session>/subagents/` exists on disk for that run (a moved folder would read as zero); (4) a resume leg (`--resume`) for one unit. Compare each usage line with that run's own `result` (`usage`, `modelUsage`); the line may differ only by responses before the start mark and after the stop, which are listed from the transcript. Record the Claude Code version and the outcome — files: `evals/results/usage-live-check.md` — verify: main fields ≤ the CLI's, and the difference is exactly the listed outside-window responses; the agent ran the commands unprompted in U1, U2 and U3; step 1 recorded — blocked-by: T008, T018, T019, H3
- [ ] T021 Update docs: `README.md` (Status, Capabilities, a "Usage metrics" paragraph with the switch key and the command names), `adapters/RENDERING.md` (skills may ship scripts), a README note on re-running the SC-009 check when Claude Code's major version changes — the spec's `Approved` line is set when H1 is given and `Status: implemented` by `sdlc-ship`, not here — files: `README.md`, `adapters/RENDERING.md` — verify: `python3 bin/sdlc lint` ok; the README paragraph matches the contract (switch key, command names, section names) — blocked-by: T020
- [ ] T022 Run full gates and record outcomes — verify: `python3 -m unittest discover -s tests -t .` passes; `python3 bin/sdlc lint` ok; `git diff --stat main -- bin adapters/config.default.json` prints nothing — blocked-by: T021
- [ ] T023 Converge: spec, plan, tasks and code agree (`sdlc-converge`) — files: `specs/003-usage-metrics/tasks.md` (Convergence section) — verify: no open gap, or each gap is a new task — blocked-by: T022
- [ ] T024 Independent review (`sdlc-review`) by a fresh read-only agent; verdict recorded, including the reviewed revision. The review report is written by the reviewer and is not edited — files: `specs/003-usage-metrics/review.md` — verify: first line exactly `VERDICT: APPROVED` — blocked-by: T023

## Blocked / human-only

- [ ] H1 Approve this plan before T001, including the departures in P5 (exact integers; a separate `- usage` bullet; a hidden mark comment), P4 (a bug record is created for an obvious bug when the switch is on), the single home for findings (the feature's progress log, P3) and the departure from decision 7's order (spec "Why now") — owner: phong.ngo.vn — unblocked when: a second `sdlc-analyze` pass reports no HIGH or CRITICAL finding
- [ ] H3 Go-ahead to run the live check (T020): it needs your authenticated `claude` CLI and network and costs a few model runs — owner: phong.ngo.vn — unblocked when: T019 is done
- [ ] H2 Approve merge and decide on a `VERSION` bump (`sdlc-ship`) — owner: phong.ngo.vn — unblocked when: T024 is APPROVED

## Coverage

| FR / item | Tasks |
|---|---|
| FR-001, FR-002, FR-015, SC-004 | T001, T003, T011, T019 |
| FR-018 (lint and drift stay green, switch on and off) | T004, T017, T019, T022 |
| FR-003, FR-004, FR-005, FR-006, SC-001, SC-007 | T004, T016, T017, T018, T020 |
| FR-007 (start mark) | T001, T002 |
| FR-008, FR-016, FR-017, FR-021, FR-022 | T012, T013 |
| FR-009, FR-011 (fields, wall, windows, rounding) | T001, T002, T005, T006 |
| FR-010 (sub-agents) | T005, T006, T008 |
| FR-012, FR-013, FR-020, SC-003 | T009, T010 |
| FR-014, NFR-001, NFR-003, SC-005 | T014, T015 |
| NFR-002, SC-006 | T014, T015 |
| NFR-004 (containment, charsets) | T001, T014, T015 |
| FR-019, SC-002 | T005, T006 |
| SC-009 | T007, T008, T020 |
| SC-008 (reported) | after the first feature built with the switch on (retro) |

## Progress log

- 2026-11-03 `77f4f98` (branch `feat/003-usage-metrics`, merged with `main` at `fc77daa`) — plan, contract and tasks drafted after ADR-0002 was accepted; baseline 152 tests OK, lint ok; next: `sdlc-analyze`, then H1
- 2026-11-03 `e2f0e19` — `sdlc-analyze` pass 1 (a fresh read-only agent): 0 CRITICAL, 9 HIGH, 19 MEDIUM, 6 LOW (A1–A34). All fixed in spec, plan, contract and these tasks. Verified before fixing: A11 (`sdlc check` compares installed files with the lock's hashes and reports `ok`, or `OUTDATED` after a `VERSION` bump) and A13 (Python 3.9.6 `fromisoformat` rejects `...00Z` and `...00.123Z`). Notable changes: findings have one home (the feature's progress log, ids carry the pass), so `review-report.md` is no longer changed (A9, A17); `[P]` marks removed and edges made one chain (A5, A26); the install-set test moved to the end so no edge is circular (A10); zero versus unknown is defined (A2, A3); the table of cases, project root, closed, overlap, atomic write and charset rules are in the contract (A4, A7, A8, A16, A18, A19); the live check is a hand-run with an allowlist (A23); docs come before the gates and the review (A24); next: a second analyze pass, then H1
- 2026-11-03 `953278a` — `sdlc-analyze` pass 2 (a second fresh agent): 0 CRITICAL, 1 HIGH, 10 MEDIUM, 7 LOW (B1–B18); 8 of the 9 pass-1 HIGH items resolved, A6 not (B1: T002 implemented de-duplication, windows and the atomic write that no test forced, so T005, T009 and T012 could not fail first). All fixed: T002 cut to what T001 forces, de-duplication moved to T006, the atomic write to T013; a text test for the task step added to T003; the eval-row test added to T016 (the `grep` in T018 had no file operand); T021 no longer edits the spec status; the pre-feature update test replaced by an idempotent reinstall test; contract: marks carry milliseconds, the earlier segment end is the session's last timestamp + 1 ms, closed needs a token, sub-agent or turn figure, precedence of the table rows, overlap limited to the same record, `<synthetic>` and duplicate rules, `(seconds + 30) // 60`, bytes I/O with mode and symlink handling; slices renamed L1–L7; T020 behind H3. Next: a third pass or H1
