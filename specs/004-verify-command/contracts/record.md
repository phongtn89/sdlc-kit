# Contract: `sdlc verify` and the evidence record

Spec 004 (FR-001–FR-014, NFR-001–NFR-004). Decision: ADR-0003.

## Call

```text
python3 <kit_path>/bin/sdlc verify <dir> [--repo <name>]
```

`<dir>`: the project root (the folder holding `.sdlc/config.json`), as for every `sdlc` command. `--repo <name>`: workspace mode; uses `repos.<name>.commands` and runs from `repos.<name>.path` (relative to `<dir>`), and writes the record under that repo.

## Commands run

`commands.test`, `lint`, `typecheck`, `build`, `integration`, in that order; empty or absent entries are skipped. Each runs through the shell in the project root (or repo path), standard input closed (`/dev/null`), standard output and error merged, in its own process group. Time limit: `verify.timeout_seconds` (positive integer, default 600); on expiry the whole group is killed. Only the last 20 lines (at most 2,000 characters) of each command's output are kept in memory, to print on failure.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | at least one command ran and all that ran exited 0 |
| 1 | any command exited non-zero, timed out or could not be launched |
| 2 | bad arguments, unreadable or invalid config, unknown `--repo`, or no command configured (no record is written) |

## Printed output

```text
verify test: pass (12.4 s)
verify lint: FAIL exit 1 (3.1 s)
<last 20 lines of the failing command's output, at most 2,000 characters>
verify: FAILED at 3b8e173 (clean tree)
```

Final line: `verify: PASSED at <short hash> (clean tree)`, or `FAILED`; the revision part reads `(dirty tree)` or `(no revision)` when so. `PASSED` on a dirty tree or without a revision also says `not green at HEAD` after the revision part.

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

- `revision`: full `HEAD` hash, or `null` outside a git repository. `dirty`: `git status --porcelain` is non-empty; with no revision, `dirty` is `false` and the record is never green.
- `exit`: integer, or `"timeout"`, or `"not started"` (with `"error"` giving the launch error text, which holds no command output). `result`: `pass` (exit 0), `fail`, `timeout`.
- **Green at HEAD** (the definition E1.3 reads): `revision` equals the current `HEAD`, `dirty` is false, `commands` is not empty and every `result` is `pass`.
- Written to a temporary file in the same folder, then renamed over the record; `.sdlc/evidence/` is created if absent. A failed write leaves the old record and exits 2.
- No field holds command output.
