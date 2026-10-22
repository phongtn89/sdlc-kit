# Rendering contract

How `bin/sdlc` turns kit sources into files inside a project. This file is the spec. `tests/` enforce it.

## Sources

| Source | Format |
|---|---|
| `core/skills/<name>/SKILL.md` (+ any sibling files) | Frontmatter: `name` (= folder name), `description` (≤1024 chars), optional `argument-hint`, `user-invocable` (bool, default true), `disable-model-invocation` (bool, default false) |
| `core/roles/<role>.md` | Frontmatter: `name` (= file stem), `description`, `access` (`read-only` or `full`); body = instructions |
| `core/constitution.md`, `core/principles/*.md`, `core/checklists/*.md`, `core/templates/*.md` | Plain markdown, copied |
| `modules/<module>/{skills,roles,checklists,templates}/` | Same formats as core; installed only with `--modules <module>` |
| `adapters/models.json` | Default model per role per target |

Frontmatter is a strict YAML subset: `key: value` lines; values are bare words, `true`/`false`, or double-quoted strings. Lists aren't allowed in sources.

## Outputs

Paths are relative to the project root. `<P>` = role file stem.

| What | `claude` target | `copilot` target |
|---|---|---|
| Skills | `.claude/skills/<name>/` (copied verbatim) | `.github/skills/<name>/` **only if `claude` is not also a target**. Copilot also reads `.claude/skills`, so a second copy would duplicate them. |
| Roles | `.claude/agents/sdlc-<P>.md` | `.github/agents/sdlc-<P>.agent.md` |
| Instructions | Managed block in `AGENTS.md`; `CLAUDE.md` must import `@AGENTS.md` (see below) | Managed block in `.github/copilot-instructions.md` |
| Shared docs | `.sdlc/constitution.md`, `.sdlc/principles/`, `.sdlc/checklists/`, `.sdlc/templates/` | same (written once) |
| Project config | `.sdlc/config.json`: created from `adapters/config.default.json` if absent, **never overwritten, never hashed**. In a workspace, `sdlc-setup` adds `repos: {<name>: {path, spec_dir, commands}}`. | same |
| Repo context | `.sdlc/context/<repo>.md`: written by `sdlc-context` from `.sdlc/templates/context.md`, starting with a `Built from: \`<sha>\`` line. Project-owned, not hashed. `discover` reports `context: {path, built_from, stale, commits_behind}` per repo. | same |
| Workspace map | `.sdlc/workspace.md`: written by `sdlc-setup` in workspace mode from `.sdlc/templates/workspace.md`. Project-owned, not hashed. | same |
| Lock | `.sdlc/lock.json` | same |

Skill bodies refer to shared docs by the project-relative paths `.sdlc/...`, so the bodies are identical for every target.

### Role frontmatter

Claude (`.claude/agents/sdlc-<P>.md`):
```yaml
---
name: sdlc-<P>
description: <description>
tools: Read, Grep, Glob            # access: read-only
# (no tools key)                   # access: full → inherits all tools
model: <models.json claude[<P>], overridable by config.json models.claude[<P>]>
---
```

Copilot (`.github/agents/sdlc-<P>.agent.md`):
```yaml
---
name: sdlc-<P>
description: <description>
tools: ['read', 'search']          # read-only
tools: ['read', 'search', 'edit', 'execute', 'todo']   # full
model: <only if config.json models.copilot[<P>] is set>
target: github-copilot             # only when claude is also a target (VS Code reads .claude/agents)
---
```

### Managed blocks

```
<!-- BEGIN sdlc-kit (managed; edit .sdlc/config.json or the kit instead) -->
...
<!-- END sdlc-kit -->
```

- The block content is generated from `core/constitution.md` (everything below its first heading), followed by a generated index of tracks, skills and roles, and then `config.json` → `extra_instructions` (a list of strings, rendered as bullets).
- If the file has no block, append one, preceded by a blank line. Create the file if it doesn't exist. Text outside the block is never modified.
- `CLAUDE.md`: if the file is missing, create it with the single line `@AGENTS.md`. If it exists but contains no `@AGENTS.md` line, add a managed block that contains `@AGENTS.md`.

## Lock (`.sdlc/lock.json`)

```json
{ "kit_version": "0.1.0", "kit_path": "/abs/path/to/sdlc-kit", "targets": ["claude","copilot"], "modules": [],
  "files":  { "<relpath>": "<sha256>" },
  "blocks": { "<relpath>": "<sha256 of block inner text>" } }
```

## Commands

| Command | Behaviour | Exit |
|---|---|---|
| `install <dir> [--targets claude,copilot] [--modules qa] [--force]` | Render everything. If a lock exists, behave like `update`. Before the first install, an existing unmanaged file at an output path is a conflict: report it and write nothing unless `--force`. | 0 ok, 2 conflict |
| `update <dir> [--force]` | Re-render with the targets and modules in the lock. A file whose current hash ≠ its lock hash was edited locally: skip it and report it (`--force` overwrites). Files in the old lock that are no longer rendered are removed if unmodified. | 0, 2 if any skipped |
| `check <dir>` | Compare the disk with the lock: `MODIFIED`, `MISSING`, block drift. Also report `DUPLICATE-SPEC <NNN>: <dirs>` for `config.spec_dir` (default `specs`), and `OUTDATED` when the lock version < the kit `VERSION`. Prints one finding per line. | 0 clean, 1 drift (duplicates and outdated alone are warnings → 0) |
| `uninstall <dir>` | Remove locked files that are unmodified, managed blocks, empty dirs it created, and the lock. Keep `config.json`. Report modified files that were kept. | 0 |
| `discover <dir> [--json]` | Read-only. For each git repo directly under `<dir>` (no symlinks, no recursion, `node_modules` skipped), report branch, HEAD, dirty count, origin URL with credentials stripped, `packageManager`, lockfiles, root `package.json` scripts matching test/lint/typecheck/build/integration/validate/check, other manifests, CI workflow count, `specs/` count with duplicate prefixes, Spec Kit version (`.specify/*.json` → `speckit_version`), agent surfaces, `AGENTS.md`/`CLAUDE.md` line counts, and installed kit version. Git runs with `--no-optional-locks -c core.fsmonitor=false`. Nothing is executed from the repos and nothing is written. Default output is a markdown table; `--json` gives `{workspace, repos[]}`. | 0 |
| `next-spec <dir>` | Print the next free 3-digit prefix: max existing + 1, zero-padded. | 0 |
| `lint` | Validate the kit itself: frontmatter keys and values; `name` = folder; required skill sections (`## When to use`, `## Process`, `## Rationalizations`, `## Red flags`, `## Verification`); SKILL.md ≤ 200 lines; every `.sdlc/<path>` mentioned in a skill or role exists in the kit under `core/` or `modules/` (the `.sdlc/config.json` path is allowed). | 0, 1 on errors |

Python 3.9 standard library only. No network.
