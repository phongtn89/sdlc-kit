VERDICT: APPROVED

# Review: spec 008 `sdlc budget` (E1.6)

One independent pass by a fresh read-only agent (2026-11-05), against the mini-spec, with experiments in scratch repositories outside the repository: merge-base and working-tree diff, untracked, binary, renamed and symlinked files, user git config that changes diff output (`color.ui`, `diff.external`, `diff.noprefix`, `diff.renames`), spec_dir forms, workspace `--repo` traversal, usage-line parsing against the real format, exit codes, no writes, no bytecode.

## Findings (no high or medium)

| Id | Finding | Outcome |
|---|---|---|
| R1 (low) | A dangling `origin/HEAD` was returned without checking the ref, so the fallback to `main` and `master` never ran | Fixed test-first: the ref must resolve to a commit |
| R2 (low) | A rename counts as a delete plus an add (2N for an N-line file) because of `--no-renames` | Documented in the README row; a test pins it |
| R3 (low) | A `- usage T:` line inside a fenced code block counts as a usage line | Left: matches how `usage.py` itself reads the log |

Advisories, not fixed: `GIT_TIMEOUT` (20 s, shared with `verify`) turns a slow diff in a huge repository into `git diff failed` (exit 2, right code, vague message); an untracked text file over 2 MiB counts its first 2 MiB; a spec_dir written as `/abs` is stripped to `abs` by `sdlc_gate.resolve_base`, so the exclude misses it (shared behaviour with `gate`, not new).

Held up: all boundaries, `./specs`, `specs/`, `a/../specs`, nested and empty spec_dir, no commits, detached HEAD, tag or hash base, shallow clone, user diff config, submodule pointers, newline in a file name, ids such as `review1-F3`, `T001` vs `T0010`, CRLF, every `--repo` escape (exit 2, one line), and a clean archive run of the kit leaves no bytecode or lock file.

Not covered: non-UTF-8 file names (macOS refuses to create one; `cmd_budget` catches `ValueError`), `core.autocrlf`, `.gitattributes`, `skip-worktree`, and whether step 6 reads well as an agent prompt (the V1-style live row for it is not part of this story).
