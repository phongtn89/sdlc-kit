# Mini-spec: `sdlc budget` computes the budgets (E1.6)

Track: T2 · Status: approved · Owner: phong.ngo.vn · Created: 2026-11-05

<!-- Roadmap story E1.6 (docs/roadmap/layers-plan.md), ladder level 5 (ADR-0003: the program runs the check). Today `budget.target_lines`, `reassess_lines`, `target_turns` and `max_turns` in `.sdlc/config.json` are text the agent is asked to watch (sdlc-implement step 6, the implementer role, the definition of done). This makes the program compute them. Reuses `sdlc_verify.git_run` (spec 004) and the usage lines of spec 003. Promote to a full spec (T3) if open question 1 is answered "yes". -->

## Intent

An agent that says "the diff is small" or "I am at turn 12" is self-reporting. `sdlc budget` reads the diff and the recorded usage and compares them with `budget.*`, so the skills quote a computed result. The seam is one new read-only command plus one sentence in `sdlc-implement`; it writes nothing and changes no other command.

## Acceptance

- [ ] `sdlc budget <dir> [--repo <name>] [--base <ref>]` counts the lines added plus deleted between the merge-base of `<ref>` and the working tree (committed and uncommitted changes, untracked files included, a binary file counts 0), excluding the spec folder, `.sdlc/` and `.claude/` (artifacts, not code size), and prints one line per budget and a final line `budget: OK`, `budget: ABOVE TARGET` or `budget: REASSESS` (exit 0, 0 and 1)
- [ ] Without `--base` the base is the default branch (`origin/HEAD`, else `main`, else `master`); with none of them, exit 2 and say so
- [ ] With `--unit <id> --spec <NNN>` (they go together) and a `- usage <id>:` line in that spec's `tasks.md`, the turns of that line are compared with `target_turns` (above: ABOVE TARGET) and `max_turns` (at or above: REASSESS); no usage line means the turns line says `unknown (no usage line for <id>)` and does not change the result
- [ ] Negative cases, by test: a diff of 301 lines is `REASSESS` (exit 1); 201 is `ABOVE TARGET` (exit 0); 200 is `OK`; deleting counts as much as adding; a non-numeric or missing budget value is exit 2 with a one-line error; not a git repo is exit 2
- [ ] `sdlc-implement` step 6 runs the command and quotes its last line instead of estimating; README documents it; `sdlc lint` still passes
- [ ] No behaviour change in other commands; the command writes no file

Verify: `python3 -B -m unittest tests.test_budget -v` and `python3 bin/sdlc lint`

Red first, then green: the 28 tests in `tests/test_budget.py` failed before `bin/sdlc_budget.py` existed (22 failures, 14 errors, subtests counted); sixteen mutations (limits at `>=`, deletions not counted, untracked skipped, spec folder or `.claude` counted, base used instead of the merge-base, first usage line winning, turns at max not reassess, turns ignored, `origin/HEAD` ignored, option-like base allowed, thousands comma, binary counted, unit and spec not paired, target above reassess allowed) each fail at least one test; two survived at first (`origin/HEAD`, option-like base) and drove a better test each.

## Decisions (2026-11-05, phong.ngo.vn accepted all four recommendations in chat; the track stays T2)

1. **Is a new command with a stable output grammar a T2 or a T3?** The roadmap says T2 · S, but `verify` and `gate` (same kind of command) were full specs. Recommended: stay T2, because the command is read-only, writes nothing and adds no lock key or rendered file; the last-line grammar is tested here. Say "T3" and I will write spec, plan and tasks instead.
2. **What counts as the diff?** Recommended: added plus deleted lines from `git diff --numstat` against the merge-base, working tree included, minus the spec folder, `.sdlc/` and `.claude/`; binary files count 0. Tests and docs count (the definition of done speaks of "diff size"), no per-project exclude list in v1.
3. **What do the turns compare against?** Turns are known only for a finished unit (the `stop` of `usage.py` writes the line), so the command cannot see a running session's turns. Recommended: report them for a named finished unit and say plainly that a running turn count is not available; the implementer role keeps the live `max_turns` rule as text.
4. **Which result is a failure?** Recommended: only `REASSESS` (over `reassess_lines`, or turns at or over `max_turns`) exits 1; `ABOVE TARGET` is advice with exit 0, because the skills say "above target: simplify, above reassess: stop and checkpoint".
