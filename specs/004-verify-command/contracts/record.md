# Contract: `sdlc verify` and the evidence record

Spec 004 (FR-001–FR-014, NFR-001–NFR-004). Decision: ADR-0003.

## Call

```text
python3 <kit_path>/bin/sdlc verify <dir> [--repo <name>]
```

`<dir>`: the project root (the folder holding `.sdlc/config.json`), as for every `sdlc` command. `--repo <name>`: workspace mode; uses `repos.<name>.commands` and runs from `repos.<name>.path` (relative to `<dir>`), and writes the record under that repo.

## Commands run

`commands.test`, `lint`, `typecheck`, `build`, `integration`, in that order; empty or absent entries are skipped. Each runs through the shell in the project root (or repo path), standard input closed (`/dev/null`), standard output and error merged into a temporary file, in its own process group. Time limit: `verify.timeout_seconds` (positive integer, not a boolean, default 600); on expiry the group is killed and `verify` stops waiting, even if a child that left the group still holds the file. After the command ends only the last 20 lines (cut to 400 characters each, at most 2,000 characters in all, decoded with replacement) are read from the file, to print on failure; the file is then deleted. `commands.*` values must be strings without NUL, else exit 2. A SIGINT or SIGTERM to `verify` kills the running group before it exits.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | at least one command ran and all that ran exited 0 |
| 1 | any command exited non-zero, timed out or could not be launched (even if the record then could not be written; the results are printed first) |
| 2 | bad arguments, missing `<dir>`, unreadable or invalid config, unknown `--repo` or a repo path outside the root, or no command configured (no record is written); also a record that could not be written when no command had failed |

## Printed output

```text
verify test: pass (12.4 s)
verify lint: FAIL exit 1 (3.1 s)
<last 20 lines of the failing command's output, at most 2,000 characters>
verify: FAILED at 3b8e173 (clean tree)
```

Final line, exactly one of (hash: first 7 characters; `PASSED` or `FAILED` as the exit code says):

```text
verify: PASSED at 3b8e173 (clean tree)
verify: PASSED at 3b8e173 (dirty tree, not verified at HEAD)
verify: PASSED (no revision, not verified at HEAD)
```

and the same three with `FAILED`. The text never contains the word "green".

## Record: `.sdlc/evidence/verify.json`

```json
{
  "version": 1,
  "started": "2026-11-04T10:00:00Z",
  "finished": "2026-11-04T10:00:15Z",
  "revision": "3b8e173f0c0c0d0e0f0a0b0c0d0e0f0a0b0c0d0e",
  "dirty": false,
  "commands": [
    {"name": "test", "command": "python3 -m unittest", "exit": 0, "seconds": 12.4, "result": "pass"},
    {"name": "lint", "command": "python3 bin/sdlc lint", "exit": 1, "seconds": 3.1, "result": "fail"}
  ]
}
```

- `started`, `finished`: UTC, `YYYY-MM-DDTHH:MM:SSZ`. `revision`: full `HEAD` hash read before the first command, or `null` outside a git repository, with no commit, or when `HEAD` changed during the run. `dirty`: `git status --porcelain -- . ':(exclude).sdlc/evidence'` was non-empty before the first command or after the last; with no revision, `dirty` is `false` and the record is never green. Git runs with `--no-optional-locks -c core.fsmonitor=false` (as `git_read` in `bin/sdlc` does), at most four calls.
- `exit`: integer (negative when a signal ended the command), or `"timeout"`, or `"not started"` (with `"error"` giving the launch error text, which holds no command output). `result`: `pass` (exit 0), `fail` (any other exit, and `not started`), `timeout`.
- **Green at HEAD** (the definition E1.3 reads): `revision` equals the current `HEAD`, `dirty` is false, `commands` is not empty and every `result` is `pass`.
- Written to a temporary file in the same folder, then renamed over the record; `.sdlc/evidence/` is created if absent. A failed write removes the temporary file, leaves the old record, prints the results and exits per the table above.
- The module sets `sys.dont_write_bytecode` before it is imported, so nothing is written in the kit.
- No field holds command output.
