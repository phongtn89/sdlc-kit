# Contract: enforcement hooks

Spec 006 (FR-001–FR-016). Decision: ADR-0003. Host: Claude Code hooks (format re-checked by fixtures and an eval row).

## Rendered entries (`.claude/settings.json`)

With `enforce` equal to JSON `true`, a Claude target and no `repos` in the config, the kit adds to `hooks`:

```json
{"PreToolUse": [
  {"matcher": "Bash", "hooks": [{"type": "command", "timeout": 90, "command": "<C bash>"}]},
  {"matcher": "Edit|Write|MultiEdit|NotebookEdit", "hooks": [{"type": "command", "timeout": 90, "command": "<C edit>"}]}],
 "Stop": [
  {"hooks": [{"type": "command", "timeout": 90, "command": "<C stop>"}]}]}
```

`<C name>` is exactly (K is the kit's `bin/sdlc` path from the lock, `shlex.quote`d):

```text
if [ -f K ]; then python3 K hook NAME || :; else echo '{"systemMessage": "sdlc: kit not found, hook skipped"}'; fi; exit 0 # sdlc-kit:NAME
```

The entry always ends with exit code 0, whatever python does (a missing or older kit, an unknown subcommand, a crash), because the host reads exit code 2 as a refusal. A refusal is therefore never an exit code: the hook prints a structured deny message on standard output (below) and exits 0.

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
| `check` | `DRIFT .claude/settings.json: kit hook <name> edited` or `missing` (drift, exit 1); `KIT-PATH-MISSING <path>` when `lock.get("kit_path")` is set and not a directory: drift (exit 1) only if the lock records settings hooks or `enforce` is true in the config, otherwise a note with no exit change (existing installs and CI `check` jobs must not start failing); a kit path that differs from the running kit is `OUTDATED`-style information only; `NOTE enforce is true but the lock records no hooks (run update)` (no exit change) |
| enforce true and `commands` empty | `NOTE enforce: commands is empty, so sdlc verify cannot pass and every push will be refused; set commands in .sdlc/config.json` |
| `uninstall` | as enforce off |

## Runtime: `sdlc hook <bash|edit|stop>`

`cmd_hook` sets `sys.dont_write_bytecode`, imports `sdlc_hooks` and prints its own output (encoded with replacement); `bin/sdlc` passes in `safe_path`, `read_config`, `sha` and `write_file` as `sdlc_gate.run` already receives `safe_path`. The process exit code is always 0; every exception, including the gate's `GateError`, `SdlcError`, `OSError`, `UnicodeDecodeError`, `ValueError` and anything else, becomes an allow with a note.

Reads standard input as JSON (cap 1 MiB). Project root: the nearest folder at or above `$CLAUDE_PROJECT_DIR` (else the input's `cwd`) that holds `.sdlc/lock.json`; none means allow silently. Config `enforce` not `true` means allow silently. A config with `repos` means allow with a note.

| Event | Input fields used | Refuse (stdout JSON, exit 0) | Warn (stdout JSON, exit 0) |
|---|---|---|---|
| `bash` (PreToolUse, Bash) | `tool_input.command` | a `git push` or `gh pr create` segment and `gate green-at-head` exit 1 | none |
| `edit` (PreToolUse, editor tools) | `tool_input.file_path` or `notebook_path`, `cwd` | source file, active spec status word `draft` or `approved`, `gate approved` exit 1 | none |
| `stop` (Stop) | none needed | never | `gate evidence-for-ticks` exit 1 |

Refuse output: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "<text>"}}`. Texts: bash: `sdlc: refused: <gate lines>. Run sdlc verify in its own tool call, quote its last line, then retry the push. (If commands in .sdlc/config.json is empty, set it first.)`; edit: `sdlc: refused: <path> is source and spec <NNN> is not approved: <gate lines>. Get the human's approval and run sdlc gate approve.` Warn output: `{"systemMessage": "sdlc: spec <NNN> has ticked tasks without evidence: <ids>"}`. Allow = empty output, or `{"systemMessage": "sdlc: <one-line reason>"}` when a fault stopped the hook from deciding (the stop hook prints nothing for a missing `tasks.md` or no active spec; only an unexpected crash makes it print a note).

**Order for `edit`**: classify the path first and call git only for a source file. A relative path resolves against the input's `cwd`; `realpath` of the longest existing prefix handles a file that does not exist yet; a path outside the project root is allowed.

**Status**: for the active spec the hook reads the first `Status:` word before the first `## ` heading with `sdlc_gate.header_lines` and `status_word`; `gate approved` runs only when it is `draft` or `approved`; a missing or unknown word allows with a note.

**Command parsing** (`pushes(command)`): first replace backslash-newline with a space; then `shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")` with `whitespace_split=True`, `whitespace=" \t\r"` and `commenters=""` (shlex's default `#` comment would swallow the newline after `git add . # note` and hide the next line; the cost is that a comment with an unbalanced quote means "cannot tell": allow with a note). `punctuation_chars` makes runs of adjacent separators one token (`;\n`, `&&\n`, `);`, `\n\n`, `;;`, `>&`): **a token made only of punctuation characters ends the segment**, whatever it is. So `;`, `&&`, `||`, `|`, `&`, parentheses, redirects and newlines separate segments, also when glued (`git push;`, `a&&git push`, `git push>out`, `(git push);`); per segment skip, repeatedly: leading `NAME=value` words, `{`, `!`, the keywords `if then else elif do while until`, and wrappers `sudo env command time nohup exec timeout nice ionice setsid stdbuf` together with their option words (a word starting with `-`, and the word after `-u`, `-g` for `sudo`; `env` options and assignments); the program must have basename `git` or `gh`; for `git` skip global options (`-C <x>`, `-c <x>`, `--git-dir <x>`, `--git-dir=<x>`, `--work-tree <x>`, `--work-tree=<x>`, `--namespace <x>`, `--no-pager`, `-P`), then the first word is the subcommand: `push` matches unless the segment has `-h` or `--help`; for `gh` skip `-R <x>`/`--repo <x>`, the words are `pr create`, unless `--help`/`-h` is present; a segment whose program is `sh`, `bash` or `zsh` with an option cluster containing `c` (`-c`, `-lc`, `-ec`) followed by a string is parsed again once (depth 2). A tokenising error means allow with a note. `$(git push)` unquoted is matched (the parenthesis is a separator); inside double quotes (`"$(git push)"`) and in backticks it is not. Known gaps, stated in the docs: quoted `$(...)`, backticks, aliases and functions, other launchers (`xargs`), scripts that push, `eval`, and a heredoc body that contains a push line (a false positive: refused until verified).

**Active spec**: `git symbolic-ref --short -q HEAD` through `sdlc_verify.git_run` (works before the first commit); a failure or empty output means none; regex `^(?:[^/]+/)*?(\d{3})-` on the branch; exactly one folder `<spec_dir>/<NNN>-*` containing `spec.md`; else none. `spec_dir` as spec 005 resolves it (top-level).

**Source tree**: relative path (inside the project root, else allow) that is not under `<spec_dir>/`, `.sdlc/`, `.claude/`, `.github/`, `docs/`, and does not end in `.md`. The kit's evidence record (`.sdlc/evidence/verify.json`), `.sdlc/lock.json`, `.sdlc/config.json` (an agent could set `enforce` false or `commands` to `["true"]`) and `.claude/settings.json` are therefore writable by an agent's editor tools: a stated limit (the hooks guard against drift, not against a hostile agent); `sdlc check` and CI (E1.5) are the detection.
