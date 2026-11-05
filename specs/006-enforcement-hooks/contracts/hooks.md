# Contract: enforcement hooks

Spec 006 (FR-001–FR-015). Decision: ADR-0003. Host: Claude Code hooks (format re-checked by fixtures and an eval row).

## Rendered entries (`.claude/settings.json`)

With `enforce` equal to JSON `true`, a Claude target and no `repos` in the config, the kit adds to `hooks`:

```json
{"PreToolUse": [
  {"matcher": "Bash", "hooks": [{"type": "command", "timeout": 60, "command": "<C bash>"}]},
  {"matcher": "Edit|Write|MultiEdit|NotebookEdit", "hooks": [{"type": "command", "timeout": 60, "command": "<C edit>"}]}],
 "Stop": [
  {"hooks": [{"type": "command", "timeout": 60, "command": "<C stop>"}]}]}
```

`<C name>` is exactly (K is the kit's `bin/sdlc` path from the lock, `shlex.quote`d):

```text
if [ -f K ]; then exec python3 K hook NAME; else echo 'sdlc: kit not found, hook skipped' >&2; exit 0; fi # sdlc-kit:NAME
```

The trailing `# sdlc-kit:NAME` marks a kit entry. Kit groups hold exactly one hook. Project groups, even with the same matcher, are never touched. Events missing from the file are created; the file is created when absent (recorded as `created`). The file is re-serialised with `json.dumps(indent=<detected: tab, 4 or 2>, ensure_ascii=False)` and a final newline; key order is kept.

## Lock

`settings: {".claude/settings.json": {"hooks": {"bash": <sha256 of canonical JSON of that group>, "edit": ..., "stop": ...}, "created": <bool>}}`; absent means none. Canonical JSON = `json.dumps(group, sort_keys=True, separators=(",", ":"))`.

## Install, update, check, uninstall

| Case | Result |
|---|---|
| enforce true | missing entries added; an entry equal to the render skipped; an entry whose hash equals the lock but differs from the render (kit moved) replaced; an entry that differs from both is `SKIP .claude/settings.json (kit hook <name> modified locally)` unless `--force` |
| enforce not true | kit entries whose hash equals the lock removed (a modified one: `KEPT`); a file the kit created that is then `{}` or only empty containers is deleted; lock key dropped |
| file invalid JSON, `hooks` not an object, or an event not a list | `SKIP .claude/settings.json (<reason>)`, nothing written, exit 2 |
| no Claude target and enforce true | `NOTE enforce: GitHub Copilot has no hook equivalent; use CI (docs)`, exit unchanged |
| config has `repos` and enforce true | `NOTE enforce: workspaces are not supported yet; no hook rendered` |
| `check` | `DRIFT .claude/settings.json: kit hook <name> edited` or `missing`; `KIT-PATH-MISSING <path>` when the lock's `kit_path` is not a directory (exit 1 only for drift, as today; the missing path is reported and also exit 1) |
| `uninstall` | as enforce off |

## Runtime: `sdlc hook <bash|edit|stop>`

Reads standard input as JSON (cap 1 MiB). Project root: the nearest folder at or above `$CLAUDE_PROJECT_DIR` (else the input's `cwd`) that holds `.sdlc/lock.json`; none means allow silently. A config with `repos` means allow with a note.

| Event | Input fields used | Refuse (exit 2, text on stderr) | Warn (exit 0, JSON on stdout) |
|---|---|---|---|
| `bash` (PreToolUse, Bash) | `tool_input.command` | a `git push` or `gh pr create` segment and `gate green-at-head` exit 1: `sdlc: refused: <gate lines>. Run sdlc verify, quote its last line, then retry.` | none |
| `edit` (PreToolUse, editor tools) | `tool_input.file_path` or `notebook_path`, `cwd` | source file, active spec `draft` or `approved`, `gate approved` exit 1: `sdlc: refused: <path> is source and spec <NNN> is not approved: <gate lines>. Get the human's approval and run sdlc gate approve.` | none |
| `stop` (Stop) | none needed | never | `gate evidence-for-ticks` exit 1: `{"systemMessage": "sdlc: spec NNN has ticked tasks without evidence: <ids>"}` |

Allow = exit 0 with empty output, or exit 0 with `{"systemMessage": "sdlc: <one-line reason>"}` when a fault made the hook unable to decide.

**Command parsing** (`pushes(command)`): `shlex.shlex(command, posix=True, punctuation_chars=True)` with `whitespace_split`; split on the tokens `;`, `&&`, `||`, `|`, `&` and newlines; per segment skip leading `NAME=value` words and the wrappers `sudo env command time nohup exec`; the program must have basename `git` or `gh`; for `git` skip global options (`-C <x>`, `-c <x>`, `--git-dir=…`, `--work-tree=…`, `--no-pager`, `-P`, `--namespace <x>`), then the first word is the subcommand: `push` matches unless the segment has `-h` or `--help`; for `gh` skip `-R <x>`/`--repo <x>`, the words are `pr create`; a segment whose program is `sh`, `bash` or `zsh` with `-c <string>` is parsed again once. A tokenising error means allow with a note.

**Active spec**: `git rev-parse --abbrev-ref HEAD` through `sdlc_verify.git_run`; regex `^(?:[^/]+/)*?(\d{3})-` on the branch; exactly one folder `<spec_dir>/<NNN>-*` containing `spec.md`; else none. `spec_dir` as spec 005 resolves it (top-level).

**Source tree**: relative path (realpath, inside the project root, else allow) that is not under `<spec_dir>/`, `.sdlc/`, `.claude/`, `.github/`, `docs/`, and does not end in `.md`.
