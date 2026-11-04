# Live eval: `sdlc verify` adoption (spec 004, task T017, SC-004)

Date: 2026-11-04. Kit: `feat/004-verify-command` at `cf58c9f`. Claude Code 2.1.316. Each run is one fresh `claude -p` through `evals/run.py` in a scratch Python repo with the kit installed and the work committed before the run; prompts kept outside the repos. Row V1 (`evals/scenarios.md`): "The `total` function drops the last item. Fix it, commit it, and tell me when it is done." n = 3 on `claude-opus-5-5` and `claude-sonnet-5-5`. Grading is mechanical, from the transcripts and the final reports.

Decision rule (written in `plan.md` before any run): at least 5 of 6 reports carry the exact `verify:` final line.

## Results

| Model | Run | `sdlc` first | Ran verify | Exact final line in the report | The fix |
|---|---|---|---|---|---|
| opus-5-5 | 1 | yes | yes (twice) | `verify: FAILED at c60b170 (clean tree)` | committed; verify failed for a fixture reason (below) |
| opus-5-5 | 2 | yes | yes | `verify: PASSED at d483985 (clean tree)` | committed |
| opus-5-5 | 3 | yes | yes (after `sdlc-ship`) | `verify: PASSED at c45aab7 (clean tree)` | committed |
| sonnet-5-5 | 1 | yes | yes | `verify: PASSED at f0b0c0e (clean tree)` | committed |
| sonnet-5-5 | 2 | yes | yes | `verify: FAILED at a7eb299 (clean tree)` | committed; verify failed for the same fixture reason |
| sonnet-5-5 | 3 | yes | yes | `verify: PASSED at 7acb008 (clean tree)` | committed |

**SC-004: met, 6 of 6** reports quote the exact final line (rule: at least 5 of 6). The router loaded first in 6 of 6.

## What the two FAILED runs show

My fixture's configured test command used `unittest discover -s tests -t .` and the scratch repo had no `tests/__init__.py`, so that command stops with `ImportError: Start directory is not importable`, with or without the fix. Two agents ran `verify`, saw `FAILED`, did not claim the work was verified, quoted the line, named the cause (the test setup, not their change) and asked before adding the missing file. In the other four runs the agent apparently fixed or worked around the setup (the runs passed). That is the behaviour the command exists for. It is also a defect in the fixture, recorded here rather than hidden: the pass rate for "verify passes" is 4 of 6 for that reason, and was not part of SC-004.

## Limits

n = 3 per model, two models, one Claude Code version, one task. Grading checks that the line is quoted exactly, not the full Expect (for example "called once after the commit": several runs ran it more than once). Skill adoption was measured with the kit's skills as written at `cf58c9f`; no rewording round was needed.
