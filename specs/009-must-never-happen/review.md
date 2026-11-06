VERDICT: REJECTED

# Review: spec 009 must-never-happen tests (E1.7)

## Pass 1 on `d01d87e`: VERDICT: REJECTED

A fresh read-only agent (2026-11-06) ran its own mutations on `git archive` copies against `tests.test_never` alone.

| Id | Finding | Outcome |
|---|---|---|
| D1 (medium) | `hook()` ran the entry by its marker and never checked the rendered event or matcher, so Write, MultiEdit and NotebookEdit unrouted, or a hook moved to `PostToolUse`, stayed green | Fixed test-first: the helper asserts the event and that the matcher fully matches the tool sent; NotebookEdit is sent with `notebook_path` |
| D2 (medium) | Only plan.md changed after approval, so the spec, tasks and contracts parts of the digest were untested end to end | Fixed test-first: each approved document is changed in turn (tasks above the progress log, which is outside the digest on purpose) |
| D3 (medium) | One task only, so a commit logged for another task was never tried | Fixed test-first: two tasks, only T002 logged |
| D4 (medium) | Only plain `git push` and a chain were tried | Fixed test-first: 14 push forms (`git -C`, `-c`, sudo, env, timeout, `bash -c`, `sh -c`, full path, `gh -R`, `;`, newline, parentheses) and 4 non-pushes |
| D5 (low) | A deny list of tool names missed `Agent` and a Copilot `shell` | Fixed test-first: allow lists, Claude ⊆ {Read, Grep, Glob}, Copilot ⊆ {read, search} |
| A1 | Any non-zero exit counted as a catch, so an error could hide a survivor (seen once, a flaky `TemporaryDirectory` cleanup) | Fixed test-first: only a failing assertion is a catch; errors and timeouts are reported and exit 1 |
| A2 | A timeout crashed the script | Fixed with A1 |
| A3, A4 | `GIT_DIR` from the caller aimed the fixture's git at another repository; developer signing or hooks config could break fixture commits | Fixed: `GIT_*` scrubbed, `commit.gpgsign=false`, `core.hooksPath=/dev/null`, no auto maintenance (test_never only; the older test files keep the pattern, a follow-up) |
| A5 | Dropping `CLAUDE_PROJECT_DIR` from the hook's root lookup survives every test (the input `cwd` is the same folder) | Left: the fallback gives the same root here; noted |

All 13 reviewer mutations were added to `tests/mutate_never.py` before the tests changed, and survived (red); after the fixes the script reports 35 of 35 caught by a failing test.

## Pass 2

Pending.
