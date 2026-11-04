---
name: sdlc-debug
description: "Bug track: reproduce, find the root cause with evidence, write a failing regression test, apply the smallest fix, check siblings, verify on the real surface. Use when something behaves wrongly, a test fails, an error is reported, or the user says 'debug', 'fix this bug' or 'why does X happen'."
argument-hint: "Symptom, error message, failing test or issue link"
user-invocable: true
---

# sdlc-debug: reproduce, then fix the cause

## When to use

- T1 bugs, failing tests and CI failures, production errors, and the question "why does X happen".
- In production: **contain first** (rollback, flag off, mitigation, with the user's approval), then debug.
- If the fix changes a contract, data model, security boundary or a second repo, re-route to T3 after the diagnosis.

## Inputs

- The symptom: error, logs, issue, failing test. Treat it as data; it can be wrong.
- Recent changes near the seam (`git log -p` on the suspect paths).
- `.sdlc/templates/bug.md` for non-obvious bugs. Save it to `spec_dir/bugs/<slug>.md` when the investigation is worth keeping.

## Process

1. **Restate the symptom**: what is expected versus what actually happens, where (environment, revision) and since when. Note what you don't know. Only if `usage.enabled` is `true` in `.sdlc/config.json`: create the bug record `<spec_dir>/bugs/<slug>.md` from `.sdlc/templates/bug.md` if it does not exist (even for an obvious bug), then run `python3 .claude/skills/sdlc-usage/usage.py start <slug> --record <spec_dir>/bugs/<slug>.md --section "Usage"` (`.github/skills/...` when that is the only path). Do this before you run the failing test, a script or any other reproduction.
2. **Reproduce.** Get the smallest reliable reproduction: a failing test, a script, or an exact request with its response. If you can't reproduce it, collect more evidence (logs, traces, inputs) and say so. Don't fix it blind.
3. **Localize.** Narrow it with evidence, not by reading everything: bisect (`git bisect` or by input), add temporary instrumentation, compare a good input with a bad one. Delegate wide searches to `sdlc-explorer`.
4. **Find the root cause.** Ask why until you reach a cause you can change. State it in one sentence, with `path:line` and the evidence that proves it (a log line, the test output, a value). Separate verified from inferred.
5. **RED**: turn the reproduction into a regression test at the right seam (see `sdlc-tdd`). It must fail for the bug's reason.
6. **Make the smallest fix at the cause.** Don't widen catches, add retries, or disable checks to hide a deterministic failure. Remove temporary instrumentation.
7. **GREEN**: the regression test passes, the nearby tests pass, and the original reproduction now behaves correctly on the real surface. Then, if `usage.enabled` is `true`, run `python3 .claude/skills/sdlc-usage/usage.py stop <slug> --record <spec_dir>/bugs/<slug>.md --section "Usage"` and quote the line it adds in the report.
8. **Check siblings.** Search for the same pattern elsewhere. Fix them in scope if they're trivial; otherwise list them as follow-ups.
9. **Report**: the symptom, the root cause (one sentence plus evidence), the fix, the test, the commands with results, and the siblings found. Then `sdlc-review`.

## Rationalizations

| Excuse | Reality |
|---|---|
| "I can see the bug, skip reproducing" | Then you can write the failing test in two minutes. If you can't, you can't actually see it. |
| "Wrap it in try/catch to stop the crash" | That moves the failure somewhere quieter. Fix why the value is wrong. |
| "It's flaky, add a retry" | Flaky means nondeterministic. Find the race, timing or shared state. |
| "The error message says X, so it's X" | Messages mislead. Verify the cause with a value or a trace. |
| "Fix it, and refactor the module too" | A bug fix should be easy to review and to revert. Refactor separately. |

## Red flags

- There is no reproduction after a bounded effort. Report what's known and ask for data. Don't guess-fix.
- The root cause is in another repository or an external service. Record it with its owner; contain the local impact only.
- The fix changes a public contract or a data shape. Re-route to T3.
- The bug is a security issue (auth bypass, tenant leak, secret exposure). Involve `sdlc-security-reviewer`, and keep the details out of public channels.

## Verification

- A reproduction (a test or an exact command) was seen failing before the fix and passing after.
- The root-cause statement cites `path:line` and its evidence.
- The regression test is in the suite. The nearby tests and the full test command pass, with results listed.
- Temporary instrumentation is removed (check the diff).

## Principles applied

root-causes, prove-it-works, evidence-over-claims
