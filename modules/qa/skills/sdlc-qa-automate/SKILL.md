---
name: sdlc-qa-automate
description: "Turn approved automatable test cases from testcases/<NNN-slug>/test-cases.md into real automated tests in the project's existing suite, test-first, and record which cases are covered. Use when test cases are approved and the user says \"automate the test cases\", \"qa automate\", or asks for end-to-end coverage of a spec."
user-invocable: true
---
# sdlc-qa-automate

Convert approved, automatable cases into tests in the suite the project already has, and close the loop so manual QA knows what is covered.

## When to use

- `testcases/NNN-slug/test-cases.md` exists, its cases are agreed, and some are marked `automatable`.
- New cases were added and need automation.
- Not for: feature implementation (`sdlc-implement`); deriving cases (`sdlc-qa-plan`); unit tests for internal code (`sdlc-tdd`).

## Inputs

- `testcases/NNN-slug/test-cases.md` (required).
- The existing test suite: its config, helpers, auth setup, fixtures, and one existing test as the style reference.
- `.sdlc/config.json` → `commands.test`, `commands.integration` for how tests run.
- The application's real routes, screens, endpoints or commands the cases exercise.

## Process

1. If the test-cases file is missing, stop and point to `sdlc-qa-plan`.
2. Scope gate: confirm the suite can reach the case's actor and surface (the right app, role, environment). If it cannot, stop for that case and report which suite or repository owns it.
3. Read one existing test in the target suite in full. Reuse its imports, setup, auth, selectors and assertion style; do not invent new patterns.
4. Locate each case's real surface (route, screen, endpoint, command). Name and place test files by that surface, never by the test-case file's slug. If no clear match exists, stop and ask.
5. Triage: automate only cases the suite can verify end to end with real assertions on observable state. Mark the rest `skipped` with the reason (missing data setup, external system, visual judgment).
6. For each case, test-first:
   - write the test with the case ID in its name or annotation;
   - run it against the build without the behaviour, or with the assertion inverted, and confirm it can fail for the expected reason;
   - run it against the current build; record the result.
   A test that cannot fail does not count as coverage.
7. If a target test file already exists, extend it; ask before overwriting anything.
8. Run the suite once, non-interactively, with a timeout.
9. Update the `Automated coverage` table in `test-cases.md`: case, test file, command, status. Do not change case text or recorded manual results.
10. Report automated, skipped (with reason) and failing cases, the files written, and the exact commands with outcomes.

## Rationalizations

| Excuse | Reality |
|---|---|
| "I'll add a small new helper; it's cleaner." | The suite's existing setup is the contract other tests rely on. Reuse it; propose changes separately. |
| "Name the file after the test-case slug so it's easy to find." | Tests live by product surface; the case ID in the test name gives traceability. |
| "This case is hard to automate, so I'll assert something nearby." | A test that does not verify the case is false coverage. Mark it skipped with the reason. |
| "It passed on the first run, so it's fine." | Unproven tests may never fail. Show it failing for the expected reason once. |
| "A failing case means the test is wrong." | It may be a real defect. Report it as a bug with the case ID; do not weaken the assertion. |
| "Test code isn't production, so no review needed." | Tests change CI and gate merges. Treat them as source changes. |

## Red flags

- The suite cannot reach the case's actor or surface → stop; report the owning suite.
- You are editing case text, spec files or recorded manual results → stop.
- You are adding retries, sleeps or wider timeouts to make a test pass → treat as a defect or flake to investigate (`sdlc-debug`).
- The suite needs credentials or a hosted environment you do not have → stop; report the check as unverified.
- A test asserts what a mock returns → rewrite against observable behaviour.

## Verification

- Each automated case has a test file path, and the test name or annotation carries the case ID.
- Evidence that each new test failed for the expected reason once, and its current result.
- The suite command ran once non-interactively at the current revision; exit status recorded.
- `Automated coverage` table updated; skipped cases have reasons.
- `git diff --stat` shows only test files and `test-cases.md`.

## Principles applied

- prove-it-works: test-first, seen failing, run on the real surface.
- subtract-before-adding: reuse the existing suite, setup and helpers.
- evidence-over-claims: coverage counts only verified, passing tests.
- root-causes: a failing case is a defect to investigate, not an assertion to loosen.
- fail-safe-keep-work: missing credentials or environments stop the case, not the work done so far.
