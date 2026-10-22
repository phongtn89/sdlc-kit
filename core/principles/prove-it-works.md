# prove-it-works

Behaviour changes are test-first, one slice at a time.

- Agree the test seam (public interface where the behaviour is observable) before writing the test.
- RED: write one test for one behaviour; run it; see it fail **for the expected reason**.
- GREEN: minimal code to pass. REFACTOR with tests green. Then the next test.
- Never write all tests up front, never test implementation details, never assert what the mock returns.
- Verify on the real surface the user touches (HTTP call, UI, CLI) when unit tests can't prove it.
- Run test commands once, non-interactively, with a timeout. Watch modes are forbidden.

**Smell:** a test that passed the first time it ran; a mock replacing the very code under test.
