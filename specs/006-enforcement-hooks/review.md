VERDICT: APPROVED

# Review: spec 006 enforcement hooks

Two independent passes by fresh read-only agents (2026-11-05), against spec.md, contracts/hooks.md and plan.md, with experiments in scratch directories outside the repository.

## Pass 1 on the HEAD after T010: VERDICT: REJECTED

| Id | Finding | Outcome |
|---|---|---|
| F1 (high) | `update` and `install` failed with "path escapes target" for a symlinked `.claude/settings.json` in a project that never set `enforce` | Fixed test-first: the file is looked at only when hooks are wanted or recorded; a failure is a `SKIP` line (exit 2); `check` and `uninstall` catch the same; `read_lock` accepts only the exact settings key without resolving symlinks (found while fixing: it would have broken every command) |
| F2 (high) | A non-UTF-8 `.claude/settings.json` crashed `update` with a traceback | Fixed test-first, same guard |
| F3 (low) | `spec_dir: "./specs"` was not normalised by the source classifier | Fixed test-first (`os.path.normpath`) |
| F4 (low) | After `KEPT`, the lock kept the old hash, so `check` reported `DRIFT` on every run | Fixed test-first: a kept entry leaves the lock |

Advisories from pass 1, not fixed: the push detector misses some wrapper options (`env -C`, `sudo -D`), `dash`/`ksh`/`fish -c`, `$'push'`, and an untokenisable command (an apostrophe in a trailing comment) is allowed with a note; a push to another folder is judged against this project's record; case-insensitive filesystems classify `SPECS/x.py` as source; merging re-serialises compact arrays; an older kit's `update` would orphan the entries. The first four are now in the README gap list.

## Pass 2 on `06db6b4`: VERDICT: APPROVED

F1 to F4 reproduced and closed; install, update, check, update --force and uninstall without `enforce` give output identical to a kit built from `main`; enforce on with a symlinked or unreadable file is a `SKIP` with exit 2 and no write; odd lock shapes give `invalid lock: settings`; full suite 481 OK. Three low advisories, not fixed:

| Id | Advisory | Note |
|---|---|---|
| A1 | With `enforce` on, a settings file that is a symlink to a file inside the project is replaced by a regular file on write (the target is untouched) | Safe; treat any symlinked settings file as `SKIP` if it matters |
| A2 | `uninstall` with an unreadable or symlinked settings file reports `SKIP`, then deletes the lock, leaving the kit entries with no record | Reported to the user; the entries are removed by hand |
| A3 | After `KEPT`, turning `enforce` on again gives `SKIP` (exit 2) until the edited entry is deleted | Coherent with F4; `--force` replaces it |

Not covered: a live Claude Code session (T012), Windows, a symlinked `.claude` directory, the Copilot target, `repos` with `enforce`, the 16 mutations (run in T010).
