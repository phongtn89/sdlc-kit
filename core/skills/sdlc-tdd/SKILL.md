---
name: sdlc-tdd
description: "Test-driven development in vertical slices: agree the test seam, then one failing test, minimal code, refactor, repeat. Use whenever changing behaviour (features, fixes, T2 changes), when writing tests, or when the user says 'TDD' or 'red-green'."
argument-hint: "The behaviour to implement, or a task ID"
user-invocable: true
---

# sdlc-tdd: one behaviour at a time

## When to use

- Any behaviour change: T1 fixes (after reproduction), T2 changes, and each T3 task.
- Not for pure refactors with existing coverage. Run the suite before and after instead.
- Not for docs or config that has no behaviour.

## Inputs

- The behaviour: a mini-spec acceptance item, a task line, or a bug reproduction.
- `.sdlc/config.json` → `commands.test` (and the narrow form your test runner supports).
- Existing tests near the seam. Match their style, fixtures and helpers.

## Process

1. **Agree the seam.** Name the public interface where the behaviour is observable: function export, HTTP route, CLI, UI interaction, message handler. For T2/T3, state it in one line before writing the test. If it isn't obvious, ask the user (one question, with a recommendation). Test the interface, not private helpers.
2. **List the behaviours** for this task, as short phrases: the happy path, then the boundary, invalid-input and failure cases that can actually occur. This is a plan, not tests yet.
3. **RED**: write **one** test for the first behaviour. Run only that test. It must fail, **for the expected reason** (an assertion about the behaviour, not an import error or typo). If it passes, the test is wrong or the behaviour already exists: investigate.
4. **GREEN**: write the minimum code that makes it pass. No speculative branches. Run the test, then the nearby tests.
5. **REFACTOR**: with everything green, remove duplication and clarify names. Keep the tests green. Don't add features.
6. **Repeat from 3** for the next behaviour. Never write the whole list of tests up front.
7. **Prove it at the boundary.** If unit tests rely on mocks of the thing being changed, add one integration or e2e check at the real boundary (DB, HTTP, queue, browser), or name why it can't run.
8. **Run each test command once, non-interactively, with a timeout** (see `.sdlc/principles/prove-it-works.md` for portable timeouts). No watch modes. Test runners must fail when zero tests are discovered (no pass-with-no-tests flags).

## Rationalizations

| Excuse | Reality |
|---|---|
| "Write all the tests first, then code" | Batch tests encode guesses about an interface that doesn't exist yet. One test, one implementation. |
| "It's obvious, skip RED" | A test you never saw fail may not test anything. RED is the proof the test works. |
| "Mock the module to make it fast" | A mock that replaces the code under test proves the mock works. Mock only at the edges you don't own. |
| "Test the private helper, it's easier" | Tests on internals break on every refactor and miss real behaviour. Test the seam. |
| "Assert it doesn't throw" | That test passes for almost any broken implementation. Assert the observable outcome. |
| "Add the edge cases later" | Later doesn't come. The boundary cases are in the behaviour list; do them now. |

## Red flags

- The test passed the first time it ran.
- The test needs to reach into private state to assert.
- The minimal code to pass is large. The behaviour is too big; split it.
- The tests are flaky (timing, ordering). Fix the nondeterminism; don't add retries.

## Verification

- Each behaviour has a test that was seen RED (name the failure message) and then GREEN.
- The narrow and nearby test commands, each with its result, at the current revision.
- A boundary test exists, or its absence is justified.
- No watch-mode, `.only` or skipped tests were left behind (grep for them).

## Principles applied

prove-it-works, thin-vertical-slices, subtract-before-adding
