# Live evals: wave 0 (E0.1 router reachability, E0.5 debug usage order)

Date: 2026-11-04. Kit: `main` at `570c9c5`. Claude Code 2.1.316. Each run is one fresh `claude -p` through `evals/run.py` in a scratch repo with the kit installed (U2 with `"usage": {"enabled": true}`); prompts kept outside the repos. n = 3 per cell, 15 runs. Grading is mechanical, from the transcripts (order of Skill, Edit and Bash tool calls).

## Results

| Row | Model | Expect | Result |
|---|---|---|---|
| R6 (bug, plain language) | claude-opus-5-5 | first skill call is `sdlc` | **0/3**: `sdlc-debug` first in 2 runs; `sdlc` appeared only in run 3 (after `sdlc-debug`) |
| R6 | claude-sonnet-5-5 | same | **0/3**: `sdlc-debug` first every time |
| R7 (typo, plain language) | both models | no `sdlc` load | **6/6** pass: no skill call, edit made |
| U2 (bug, usage on) | claude-opus-5-5 | `start` before the first test run | **3/3** pass; one line per run, `stop` after the fix |

U2 note: in all three runs the agent created the bug record before `start` (an Edit), then `start`, then ran the tests. Order meets the story's acceptance.

## Decision

- **E0.5: met.** Keep.
- **E0.1: not met.** The typo case is right (6/6), but a plain-language bug goes straight to `sdlc-debug` (5/6 runs never loaded `sdlc`), because `sdlc-debug`'s own description matches the prompt. Removing the flag made the router reachable (it loaded in 1 of 6 runs unprompted) but not the first call. The track is still chosen implicitly by the debug skill. Options: accept that the specific skill is the entry for a clearly-typed task and change the R6 expectation to "loads `sdlc` or the matching track skill", or strengthen the router description and the constitution line and re-run. Owner's call; not changed here.
