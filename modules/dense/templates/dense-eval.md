# Dense module evaluation: [workspace]

<!-- Paired runs that decide whether to keep the dense module enabled in this workspace. The kit ships this method; the tasks and results are the workspace's own. Copy this file to `tasks.md` in an evaluation folder **outside the workspace's working tree** (for example a sibling `<workspace>-evals/dense/`), fill it in, and record runs in `results.md` next to it using the Results section's table. Agents under test work in the workspace and search it, so a task file inside it hands them the Expect items. Never link to the evaluation folder from the workspace. Both arms are built from the same kit revision and the same pinned revisions of the workspace and its repos. -->

Gate (spec 002 SC-001, SC-002). Let A be the context loaded without the module and B the context loaded with it, for each task. The module passes only if, on this task set,
- its success rate is **at least** the baseline's (after the tie rule), **and**
- **the median of (1 − B/A) over the document tasks is at least 0.20**, **and B/A ≤ 1.10 on each code-only task**.

All base runs count toward the median, pass or fail; also report the median over the pairs where both arms passed, so an arm that gives up early can't hide behind a low number.

Also reported (SC-007, not part of the gate): the share of document-task runs with the module in which the agent used the lookup.

## Terms

- **Document task**: a task whose answer is in the workspace documents the index covers (routing, cross-repo impact, review against the PRD or architecture).
- **Code-only task**: a task answered from product code alone. The module should neither help nor hurt it.
- **Context loaded**: for one run, the characters of every tool result the agent receives before its final answer, lookup output included. Auto-loaded instructions are excluded: they are the same in both arms except the module-rules section.
- **Lookup**: one `dap.py find` call.

## Procedure

1. **Write the tasks first** (at least 6 document tasks and 2 code-only tasks), each from real work in this workspace, with a verbatim prompt in its own file and Expect items that are observable in the transcript or on disk. Check every Expect item's `path:line` against the code at the pinned revisions. Someone other than the person who builds the module reviews the Expect items. Freeze the tasks (record the sha256 of the task file) before any run; never edit a task after seeing a result.
2. **Build both arms** at the pinned revisions, installed from the same kit revision: arm A without `dense`, arm B with it, and B's index freshly built (`sdlc-dense-index build`) and validated. Record the kit revision and the index revision. A change to `dap.py` or the module rules after the first run means a full rerun.
3. **Leak check, before the first run of each arm.** From the arm's root, search for a distinctive phrase of each prompt and of each Expect item (for example `grep -rn "<phrase>" .`). It must find nothing. A run whose transcript shows the task file being read is invalid: record it as such, fix the leak, and re-run.
4. **Run one fresh, non-interactive session per task and arm** with `python3 evals/run.py <prompt-file> <arm-dir> --out <transcript> --allowed-tools '<the same read-only list in both arms, including Bash(python3 .claude/skills/sdlc-dense-index/dap.py find:*)>'`. Same model and settings for every run. Alternate which arm goes first. Keep prompt files, transcripts and results outside both arms.
5. **Grade each run** with a fresh read-only grader that sees only the answers, the Expect items and the pinned code. The owner spot-checks at least one pass and one fail per arm.
   - **pass**: every Expect item is observable. Anything less is a fail.
   - **context loaded**: counted from the transcript as defined above.
   - **lookup used**, **lookup output sizes**: from the transcript (module arm).
   - **cites index or sources**: whether the answer's claims cite source locations (`path:line`) or the index. Citing the index is a fail of the citation rule, reported per run.
6. **Tie rule.** For every task whose base result differs between the arms, run it once more in both arms (same allowlist, same parse) and grade the reruns with the same grader brief. A task counts for an arm only if both of that arm's runs passed.
7. **Apply the gate** and write the decision under Results, with the evaluated kit revision. If it fails, uninstall the module (install again without `dense`) and record which Expect items or measurements failed.

## Task template

### E1: [title] ([document | code-only])

Prompt (verbatim, also saved to its own file):

> [prompt]

Expect:
- [observable outcome, with `path:line` at the pinned revision]
- [observable outcome]

## Results

Kit revision: `[rev]` · Index revision (module arm): `[rev]` · Model: [model] · Date: [YYYY-MM-DD]

| Task | Type | Arm | Pass | Context loaded (chars) | Lookup used | Lookup output sizes | Cites index or sources | Notes |
|---|---|---|---|---|---|---|---|---|
| E1 | document | baseline | | | — | — | | |
| E1 | document | dense | | | | | | |

| Measure | Baseline | Dense | Rule | Met |
|---|---|---|---|---|
| Success rate (after the tie rule) | | | dense ≥ baseline | |
| Median of (1 − B/A), document tasks (all base runs) | | | ≥ 0.20 | |
| Same, pairs where both arms passed | | | reported | |
| B/A on each code-only task | | | ≤ 1.10 | |
| Lookups within 2,000 characters | | | 100% | |
| Document-task runs that used the lookup | | | reported | |

Decision: [keep enabled | uninstall] — [one-line reason]
