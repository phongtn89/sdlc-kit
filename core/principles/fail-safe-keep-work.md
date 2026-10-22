# fail-safe-keep-work

When blocked, preserve progress and stop burning effort.

- Never `git reset --hard`, delete branches, or discard uncommitted work on failure.
- Checkpoint: keep the working tree, record what passed, the exact blocker, and the next action (`sdlc-handoff`).
- Commit only intended files and only when permitted; push or mark PRs Draft only with existing authorization.
- Deterministic auth/permission failures (HTTP 401/403, `E401`/`E403`, missing credentials) are terminal: zero retries, report `BLOCKED_<AREA>_AUTH` with sanitized command, host and error, and the human action needed.
- Retry at most once, only for clearly transient errors (timeout, reset, 429, 5xx).
- Leave blocked tasks visibly unchecked in `tasks.md`.

**Smell:** switching package registry after a 401; marking a task done "except for the tests".
