# Plan: Usage metrics per resolved unit

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-03

## Summary

One new core skill, `sdlc-usage`, ships a stdlib-only script, `usage.py`, with two named commands: `start` writes a mark (time and session ID) into the unit's owning record, and `stop` reads the Claude session transcripts, de-duplicated by `message.id`, and writes one usage line. Skills that resolve a unit (`sdlc-implement` for tasks and finding fixes, `sdlc-debug` for bugs) call the commands, guarded by one switch in `.sdlc/config.json`. The technique and its evidence are ADR-0002 (accepted 2026-11-03). The riskiest part is the transcript format, which Claude Code documents as internal: the script validates the shape and degrades to "not available", and a pinned real fixture plus a live `claude -p` check catch a change.

## Technical context

- Language / runtime: Python 3.9+, standard library only (`README.md`: no network, no third-party packages).
- Key dependencies: none new. Reads `~/.claude/projects/**` (or `$CLAUDE_CONFIG_DIR`), written by Claude Code, and `.sdlc/config.json`.
- Storage: marks and usage lines live in the owning markdown records. The script keeps no state file and no cache.
- Testing: `python3 -m unittest`, scripts run as subprocesses (as `tests/test_dap.py`), with generated transcript fixtures, one pinned real fixture and `HOME`/`CLAUDE_CONFIG_DIR` pointed at a temp folder.
- Target: Claude Code (CLI, desktop). Copilot degrades to "not available".
- Constraints: offline, non-interactive, no transcript content read beyond the numeric and id fields (NFR-001–003). Skill files stay at 200 lines or fewer (lint).

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| depth-follows-risk | pass | T3: new core skill and a parser of an internal format |
| agree-before-building | pass | decisions from the shop6 grill and ADR-0002; the plan's choices in the next section need approval |
| subtract-before-adding | pass | no hooks, no OTel, no server, no new config file; one script and one switch. Reuses the progress log and the existing records |
| thin-vertical-slices | pass | S1 is one task measured end to end through an installed skill |
| prove-it-works | pass | exact match against synthetic and one real recorded run (SC-002, SC-009); a live `claude -p` check before ship |
| evidence-over-claims | pass | "not available" with a reason, never 0 |
| fail-safe-keep-work | pass | `stop` never throws away the marks; a failed read writes a "not available" line and leaves everything else |

## Choices the spec left to the plan

| # | Choice | Decision | Why |
|---|---|---|---|
| P1 | Script home | New core skill `core/skills/sdlc-usage/` (`SKILL.md` + `usage.py`), installed with the core skills | Skill folders already copy sibling files verbatim (`adapters/RENDERING.md`), so no installer change. Same pattern as the dense module's `dap.py`, now in core (FR-015) |
| P2 | Command names | `usage.py start <unit> --record <file> [--section <h>]`, `usage.py stop …` (`contracts/usage.md`) | Named commands, exact arguments in the skill text (FR-006, retro L1) |
| P3 | Where a mark and line go | End of a named `##` section of the owning record: task and finding → `Progress log` of the feature's `tasks.md`; bug → `## Usage` in `spec_dir/bugs/<slug>.md`. Finding ids carry their pass (`review1-F3`) and the skill writes the finding's one-line text as the evidence bullet; **review findings only: a fix to an analyze finding is a document edit in specify, plan or tasks and is not measured** | One mechanism for all three (FR-004, FR-005). A finding's fix has no record of its own today, and review reports are written by an independent reviewer, so the feature's progress log is the single home; `sdlc-implement` is the one skill that applies fixes (analyze finding A9) |
| P4 | Bug without a record | With the switch on, `sdlc-debug` creates the minimal bug record from `bug.md` even for an obvious bug, so the line has a home | Spec FR-004 (a line per closed bug). Only with the switch on |
| P5 | Line shape | Exact integers with thousands separators, not `1.5K`/`2.1M`; a bullet `- usage <unit>: …` of its own, with the start mark as a hidden HTML comment; the example in the decision record read `usage: in 1.5K · …` inside the progress-log line. **Three departures from the decision record's example, all for exactness and parseability; they need your OK (H1)** | SC-002 is an exact match, and rounding would hide an error. A separate bullet and a comment mark keep the record readable and the parse unambiguous |
| P6 | Sub-agent field | One figure: the sum of the four token fields of sub-agents in the window | Keeps the line to one row; the four main-session fields stay separate (FR-009, FR-010) |
| P7 | Switch default in new installs | Nothing is added to `config.default.json`; absent means off | SC-004: an off install differs only by the new skill's files; the config file is project-owned |
| P8 | Session id absent | `session=unknown` in the mark, and an unknown session never matches another. With no Claude folder either, the whole line is `not available (no transcript on this target)`. With a Claude folder, tokens are `not available (session id unknown)` and wall time is still shown. Detection limit: a Copilot user who also has Claude installed gets the second form | The env var is not in the public docs (ADR-0002); degrade, never guess (`contracts/usage.md`, table of cases) |

| P9 | Overlapping units | Detect and flag (`· OVERLAP: <unit>`, FR-021), and with the switch on `sdlc-implement` runs `[P]` tasks one after another | The skill's own parallelism would silently double count; silent wrong numbers are worse than slower runs |
| P10 | "Closed" and rework | A unit is closed when its line holds a figure; a whole-line `not available` can be replaced by the next stop; rework is a new unit id (`T012-r2`) (FR-022) | Retries after fixing a cause must work; a closed unit must not be rewritten |
| P11 | Project root | The folder holding the nearest `.sdlc/config.json`; the record path is relative to it; skills run the command from there | In a workspace the config is at the workspace root; the kit never writes a child repo's config (A8) |

## Seams & blast radius

- New: `core/skills/sdlc-usage/SKILL.md`, `core/skills/sdlc-usage/usage.py`, `tests/test_usage.py`, `tests/fixtures/usage/` (generated in code, plus one pinned real transcript with message content removed).
- Changed: `core/skills/sdlc-implement/SKILL.md` (steps 2–4: sequential `[P]` with the switch on; start and stop for a task; a finding-fix step), `core/skills/sdlc-debug/SKILL.md` (start at reproduce, stop at close), `core/templates/bug.md` (`## Usage`), `core/templates/tasks.md` (progress-log note), `evals/scenarios.md` (three unnamed-prompt rows and one re-check row), `README.md`. `core/templates/review-report.md` and `adapters/RENDERING.md` are **not** changed (RENDERING already says skill folders copy "any sibling files").
- Callers / consumers: every project that updates the kit gets one more skill (a Skills index line in the managed block) and edited `sdlc-implement`/`sdlc-debug` texts; `sdlc check` reports `ok` for an unchanged install (it compares installed files with the lock's hashes) and, after a `VERSION` bump, `OUTDATED lock … (run update)` with exit 0; `sdlc update` brings the new skill and the edited texts in. Projects with the switch off see no behaviour change. `bin/sdlc` is not changed: `skills/<name>/*` is already copied and `__pycache__` already skipped.
- Contracts touched: the line and mark format (`contracts/usage.md`) is new; `.sdlc/config.json` gains the optional `usage` key.
- Migrations: none.
- Lint: the new skill follows the section rules and the 200-line cap. The constitution names no new skill, so no eval is forced; SC-007 adds three eval rows regardless (a task, a bug, a finding).

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A: transcripts, marks written by named commands (ADR-0002) | Exact on the measured run; offline; one switch; no hooks | Internal format; clock-window attribution | chosen |
| B: hooks write a ledger | Documented events | No usage fields; no per-unit boundary; `bin/sdlc` renders no hooks | rejected (ADR-0002) |
| C: native OpenTelemetry | Documented and exact | Not enabled per project; collector or console; nothing printed in the test | rejected as the mechanism, documented as a cross-check (ADR-0002) |

## Data model / contracts

- [contracts/usage.md](contracts/usage.md): the commands, the switch, the mark and line formats, the reasons for "not available", segments and de-duplication.

## Failure modes

| Failure | Handling |
|---|---|
| Transcript missing, moved or deleted (30-day cleanup) | `not available (transcript not found)`; marks stay; wall time still shown |
| Transcript format changes | Shape check per record and per window → `not available (unexpected transcript format)`; the pinned fixture test shows a break only when the fixture is re-recorded, so `evals/` carries a re-check row to run when Claude Code's major version changes (owner: whoever updates the kit's supported version), and T020 records the version tested |
| Record unwritable, or a unit id with odd characters | Exit 2 with one line; nothing written |
| Second `stop` (retry, resume) | `already closed`, no change (FR-017) |
| Second `start` in the same session | `already started`, no duplicate mark |
| Unit resumed in another session | New mark; the stop sums the segments; a segment whose transcript is gone → PARTIAL, named |
| Two units open in one session (including `[P]` tasks) | Detected at `stop`: the line ends `· OVERLAP: <unit>` (FR-021); with the switch on `sdlc-implement` runs `[P]` tasks sequentially; each window is by clock, so the figures still include the other unit's work and say so |
| Crash between reading and writing | The record is written to a temporary file and renamed over the original; a failed run leaves the record as it was, marks included. Concurrent edits to the same record by another process between read and rename can be lost; the skills run the command alone and re-read the record afterwards |
| An agent rewrites the section and drops a mark | `stop` reports `not available (no start mark)`; the skill text forbids editing `<!-- usage-start` lines |
| Sub-agent still running at stop | Its records up to now are counted; the rest are missed (stated in `SKILL.md`: run the stop after the sub-agents finish) |
| Rollback of a bad release | Set the switch off, or `sdlc update` from a kit without the skill; records keep their lines as plain markdown |

## Security & observability

- Checklists loaded: `.sdlc/checklists/security.md`, `.sdlc/checklists/performance.md`.
- Decisions: the script reads records only through `json.loads` and keeps only ids, timestamps, model names and four integers; it opens no socket and starts no process (`test_imports_are_exactly_the_contracts_list`: the imports are listed and checked); transcripts are never copied or printed; the sentinel test (SC-005) proves no content leaves; `--record` must stay inside the project root (no `..`, symlinks resolved), as `dap.py commit` does; the unit id, the session id and the model name are checked against fixed character sets before use (NFR-004). Performance: one pass over one or a few JSONL files of tens of MB in well under a second; no timing target beyond the test's 5 s guard.
- Observability: the line is the observation. No log, no metric.

## Test strategy

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| A task: start then stop gives the line with exact figures (S1) | `usage.py` subprocess on a generated transcript and a temp project | integration | `python3 -m unittest tests.test_usage.Tracer -v` fails: no `usage.py` |
| One response written as several records counts once (FR-019) | generated fixture with 5 duplicates | unit via subprocess | `python3 -m unittest tests.test_usage.Dedupe -v` |
| Sub-agent usage is separate and exact (FR-010) | fixture with `subagents/agent-*.jsonl` | integration | `tests.test_usage.SubAgents` |
| Equals the CLI's own figures on a real run (SC-009) | pinned real transcript with content removed, expected = the recorded `result` | integration | `tests.test_usage.RealFixture` |
| No data: no transcript, no session id, no mark, unexpected shape, partial (S2) | temp `HOME`, odd fixtures | integration | `tests.test_usage.NotAvailable` |
| Resume across two sessions; idempotent start and stop (S1.3, FR-016, FR-017) | two fixtures, two sessions | integration | `tests.test_usage.Resume` |
| Switch off: nothing written, nothing read; install differs only by the new skill (S3, SC-004) | switch absent/false/malformed; `sdlc install` + `check` | integration | `tests.test_usage.SwitchOff`, `tests.test_sdlc.UsageSkill` |
| Privacy: sentinel in message text is never output or written (SC-005); no network/subprocess (NFR-001, SC-006) | fixture with a sentinel; import check; run with a `sitecustomize` that makes sockets raise | integration | `tests.test_usage.Privacy` |
| Skill texts name the exact commands (FR-006, SC-007) | rendered `sdlc-implement`, `sdlc-debug` text; lint | unit | `tests.test_sdlc.UsageSkill` |
| Bug and finding units use the same line (S4) | `usage.py start/stop` against a bug record with `--section Usage` and a `tasks.md` progress log with a `review1-F3` unit; the skill texts name the commands | integration | `tests.test_usage.Units`, `tests.test_sdlc.UsageSkill` |
| Overlap, closed, replace (FR-021, FR-022) | two units in one session; a whole-line `not available` replaced by the next stop | integration | `tests.test_usage.Resume` |
| Timestamps with `Z` and `.123Z`; half-open windows; single rounding (FR-011) | boundary fixtures | unit via subprocess | `tests.test_usage.Windows` |
| A real session obeys the unnamed prompt (SC-007) | `evals/run.py` on a scratch repo, switch on | hand-run eval | eval rows U1 (task), U2 (bug), U3 (finding) |

Level note: no mocks of the transcript reader. Every test reads real files in a temp folder. Within one task, tests are written and seen RED one at a time (`sdlc-tdd`), not as a batch. The live check, a `claude -p` run compared with its own `result`, needs an authenticated CLI, network and a tool allowlist, so it is a hand-run before ship (task T020), not part of the suite.

## Rollout & rollback

- Rollout order / flags: merge to `main` with the switch absent everywhere; a project turns it on by adding `"usage": {"enabled": true}` to `.sdlc/config.json`. First use: spec 002's evaluation tasks or the next feature built, so SC-008 can be reported (the order in decision 7 was not kept; see the spec's Why now).
- Rollback steps: remove the key, or `sdlc update` from the previous kit.
- Value gate: not applicable. No success criterion is a measured threshold (spec SC list). SC-009 is an exact-match check on a pinned fixture; T020 repeats it live.

## Size

About 250 lines for `usage.py`, 80 for `SKILL.md`, 350 for tests, 40 across skills and templates, plus fixtures. Over `budget.reassess_lines` in total, but each task stays near 100–200 changed lines, and the work is split by slice, not by layer. Reassessment point: after lane L2 (T008), check `git diff --stat` for `usage.py`; above about 300 lines, simplify before lane L3.

## Complexity justifications

None.
