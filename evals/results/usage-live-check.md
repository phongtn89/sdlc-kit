# Live check: usage metrics (spec 003, task T020)

Date: 2026-11-03. Kit: branch `feat/003-usage-metrics` at `5b08af9`. Claude Code 2.1.316, models `claude-opus-5-5` (and `claude-haiku-5-5` in the multi-model leg). Authenticated CLI, run with the owner's go-ahead (H3).

## Method and limits

- Three scratch Python repos (kit installed for `claude`, `"usage": {"enabled": true}`), one per unnamed-prompt row; each run is one fresh `claude -p` through `evals/run.py` with `--allowed-tools 'Read,Edit,Write,Grep,Glob,Agent,Skill,Bash(python3 .claude/skills/sdlc-usage/usage.py:*),Bash(python3 -m unittest:*),Bash(git status:*),Bash(git diff:*),Bash(git log:*),Bash(ls:*),Bash(mkdir:*)'`. Prompts and expectations were kept outside the repos.
- "Independent" figures come from a separate throwaway script (not the kit's) that reads the raw transcript: last record per `message.id`, window `[start mark, stop mark)`.
- n = 1 per leg. One model family, one Claude Code version. Copilot is not exercised (no transcript on that target). Total cost about $2 to $3.

## Results

| # | Leg | Result | Evidence |
|---|---|---|---|
| 1 | Is `CLAUDE_CODE_SESSION_ID` set in a headless run? | PASS | `printenv CLAUDE_CODE_SESSION_ID` printed `41ea6edd-356a-479c-9c11-44725f8383c6`, equal to the session id in the `system/init` event. (An `echo "$VAR"` was refused by the permission layer, so `printenv` was used.) |
| 2 | U1: "Do task T001 from the tasks file." | PASS | Loaded `sdlc-implement` unprompted; `usage.py start T001` ran before the first edit; `stop` ran after the tests passed; one mark and one line. Line `in 10 · cache-read 260,298 · cache-write 2,574 · out 2,093 · sub-agents 0 · <1 min wall · 5 turns` equals the independent figures exactly; the whole-session transcript equals the CLI's `result.usage` exactly (24 / 534,176 / 30,569 / 3,948), 6 of 11 responses lie outside the window |
| 3 | U2: bug, "`parse` returns the wrong value for empty input. Fix it." | PARTIAL | Loaded `sdlc-debug` unprompted; created `specs/bugs/parse-empty-input.md` with a `## Usage` section; `start`, then fix, then `stop`; one line; figures equal the independent computation exactly (6 / 157,944 / 2,670 / 1,914, 3 turns). **Deviation:** the agent ran the failing test once *before* `start` (in the command that read the bug template), so the first reproduction response is outside the window and the line is a lower bound by that step. The skill text says start before reproducing; see Follow-ups |
| 4 | U3: "Fix finding F3 from the review." | PASS | Unit id `review1-F3`; the finding's text recorded as a Progress-log bullet; `start` before the fix, `stop` after the verify step; one line; figures equal the independent computation exactly (10 / 272,047 / 2,605 / 1,743, 5 turns). The agent read the `sdlc-implement` text through a shell command rather than the Skill tool; the behaviour is the same |
| 5 | Sub-agent run, `start` and `stop` around an Agent call (SUB1) | PASS | `<session>/subagents/` exists (1 file). Whole-session main transcript equals the CLI's `usage` exactly (8 / 155,744 / 21,913 / 444); the line's main fields equal the independent window (4 / 84,868 / 7,282 / 287, 2 turns) and differ from the CLI's only by the two responses outside the window; the line's `sub-agents 18,833` equals `modelUsage` minus `usage` exactly (196,942 − 178,109 = 4 + 7,890 + 10,523 + 416 = 18,833) |
| 6 | Resume with the same session id (`--resume`) | PASS, with a finding | `--resume` kept the **same** session id, so the second `start` printed `already started` and the window spans both runs; the line equals the independent figures (10 / 227,971 / 12,025 / 592, 5 turns). A new mark per session arises only for a new session id |
| 7 | Two sessions (`--resume --fork-session`, RES2) | PASS | Two session ids, two marks, one line. The line (`in 8 · cache-read 182,693 · cache-write 11,307 · out 425 · 4 turns`) equals the sum of two independently computed segments (4 / 84,708 / 6,943 / 180 and 4 / 97,985 / 4,364 / 245); the forked transcript's copied history falls before its mark and is not counted |
| 8 | Multi-model unit (`--resume --model haiku`, RES3) | PASS | The line lists `model claude-opus-5-5, claude-haiku-5-5`, matching the two models in the transcript |

## Follow-ups (none blocks the spec)

1. **U2 start order.** The agent ran the reproduction before `start`. Candidate change, test-first: in `sdlc-debug`, run `start` as step 1 ("Restate the symptom"), before any command that runs the failing test. Not changed here; recorded for the retro. **Changed after 0.6.0 (E0.5):** `start` now sits in step 1 of `sdlc-debug`, with a test; the live re-check (U2 at n=3) is pending.
2. The contract's resume rule matches reality (`already started` for the same id), but the README should say that `--resume` keeps the session id.
3. Re-run this check, or UR1, on a Claude Code major-version change.
