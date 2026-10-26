# Dense module evaluation: [workspace]

<!-- Paired runs that decide whether to keep the dense module enabled in this workspace. The kit ships this method; the tasks and results are the workspace's own. Copy this file to `.sdlc/evals/dense/tasks.md` and fill it in, and record runs in `.sdlc/evals/dense/results.md` using the Results section's table. -->

Gate (spec 001 SC-001, SC-002): the module passes only if, on this task set,
- its success rate is **at least** the baseline's, **and**
- its median context before the first action is **at least 50% lower** than the baseline's.
Also reported (SC-005): the share of sub-agent returns that follow `.sdlc/templates/dense-return.md` without a reformat; target ≥ 90%.

## Procedure

1. **Write the tasks first** (at least 6: 2 routing, 2 cross-repo impact, 2 review), each from real work in this workspace, with a verbatim prompt and Expect items that are observable in the transcript or on disk. Freeze them before any run; never edit a task after seeing a result.
2. **Baseline arm, before installing the module.** For each task: a fresh session, the same model and settings for every run, the prompt pasted verbatim. Record the row.
3. **Install and build.** Install the kit with `dense` added to its modules, run `sdlc-dense-index build`, and record the `committed <rev>` revision. Don't change any source until the module arm is done.
4. **Module arm.** Repeat step 2 for every task. Every run must use the same index revision (check the `fresh <rev>` line in each transcript).
5. **Score each run** without looking at the other arm's transcript:
   - **pass**: every Expect item is observable. Anything less is a fail.
   - **context before first action**: the characters the agent had loaded before its first action, counted from the transcript. Count the auto-loaded instructions plus every file or tool result it read. The first action is the first edit, write, state-changing command or delegation. Reads, searches and `dap.py fresh` or `validate` are not actions.
   - **input tokens**: the input-token figure of that turn, where the transcript shows it (Claude). Leave blank otherwise.
   - **returns**: the number of sub-agent replies, and how many followed the return contract without a reformat (module arm).
6. **Apply the gate** and write the decision under Results. If it fails, uninstall the module (install again without `dense`) and record which Expect items or measurements failed.

## Task template

### E1: [title] ([routing | impact | review])

Prompt (verbatim):

> [prompt]

Expect:
- [observable outcome]
- [observable outcome]

## Results

Index revision used by the module arm: `[rev]` · Model: [model] · Date: [YYYY-MM-DD]

| Task | Arm | Pass | Context chars before first action | Input tokens | Returns (conforming / total) | Notes |
|---|---|---|---|---|---|---|
| E1 | baseline | | | | — | |
| E1 | dense | | | | | |

| Measure | Baseline | Dense | Rule | Met |
|---|---|---|---|---|
| Success rate | | | dense ≥ baseline | |
| Median context chars | | | dense ≤ 50% of baseline | |
| Conforming returns | — | | ≥ 90% (reported) | |

Decision: [keep enabled | uninstall] — [one-line reason]
