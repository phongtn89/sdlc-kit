# Plan: Reviewer can run the project's check commands, and still cannot write

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-07

## Summary

The limit lives in the kit's existing `bash` hook (spec 006): the host sends `agent_type` for every call a sub-agent makes (probe, `evals/results/reviewer-bash-probe.md`), so the hook can judge a reviewer's `Bash` call differently from the main session's. For a role marked `checks: true` in its source (reviewer, security-reviewer) it allows only a command that equals, as a whole string, a value of `commands` in the config, and refuses everything else with a JSON deny. The roles are rendered with `Bash` added only when that hook entry will really be in place. The riskiest part is the coupling between the rendered role file and the settings entry: a role with `Bash` and no live hook would have an unlimited shell.

## Technical context

- Language / runtime: Python 3.9+, stdlib only, in `bin/sdlc` (`render_role`, `sync`, the role lint) and `bin/sdlc_hooks.py` (`on_bash`)
- Key dependencies: spec 006 (hook runtime, `settings_plan`, `merge`), spec 009 (`test_never.py`, `mutate_never.py`)
- Storage: none; the allowed commands are read from `.sdlc/config.json` at every call, like `enforce`
- Testing: `tests/test_hooks.py` (hook unit and fixtures), `tests/test_sdlc.py` (rendering, lint), `tests/test_never.py` (end to end), `tests/mutate_never.py` (mutations)
- Target: Claude Code sub-agents; GitHub Copilot unchanged
- Constraints: the hook never exits non-zero and refuses by JSON only (spec 006); `agent_type` equals the agent's `name` (seen with a custom agent; SC-001 checks the rendered `sdlc-reviewer`)

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | no new command, file or lock key; one branch in `on_bash`, one role key, one rendering condition |
| thin-vertical-slices | pass | S1 hook alone is shippable behind no rendering change; S2 rendering; S3 end to end and docs |
| prove-it-works | pass | the probe already settled the mechanism; SC-001 is a live eval of the rendered role |

## Seams & blast radius

- Seams: `bin/sdlc_hooks.py:on_bash` (a role branch before `pushes()`), `bin/sdlc:render_role` and `render` (the condition), `bin/sdlc:sync` (compute the settings plan before rendering, pass the result down), `bin/sdlc:ROLE_KEYS` and the role lint, `core/roles/reviewer.md` and `security-reviewer.md` (`checks: true`, one sentence each)
- Callers / consumers affected: every install of the kit that has `enforce` true and `commands` set gets a changed reviewer file at the next `update`; nothing else changes; no lock key
- Contracts touched: the rendered `tools:` line of two roles; the hook's refusal reasons (a new one)
- Migrations: none; `enforce` off or no `commands` renders exactly as before

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A: `Bash(<pattern>)` in the role's `tools:` line | one file, no hook | the host ignores it (probe 1: every command ran) | rejected, measured |
| B: a `hooks:` block in the role's front matter | scoped by construction | never ran in the probe (probe 2) | rejected, measured |
| C: the project-level `bash` hook branches on `agent_type` | works, same mechanism as spec 006, exact match is easy | Claude only, needs `enforce`, coupling with the role file | chosen |
| D: no `Bash`, the reviewer reads the `verify` record | no risk | the problem of the spec | status quo, kept as the fallback |

Contract of the new branch of `on_bash` (judged only when `data["agent_type"]` is a string in the kit's check-role list, `sdlc-reviewer` and `sdlc-security-reviewer`; any other value or a missing key is the main session, judged as today):

| State | Output |
|---|---|
| `enforce` is not true (the role file may still hold `Bash` until `update`) | deny: `sdlc: refused: the <role> may not run commands while enforce is off; run sdlc update` |
| no configured command (`commands` empty, missing, not an object) | deny: `sdlc: refused: the <role> may only run the project's configured check commands, and none is configured` |
| `command.strip()` equals the stripped value of one of `commands`' non-empty string values | continue into the usual push check (a configured command that pushes is still judged) |
| anything else, including a chain, a redirect or an added argument | deny: `sdlc: refused: the <role> may only run the project's configured check commands (<names>)`, the names being the keys of `commands`, at most five |

A workspace config (`repos`) is skipped by `run()` before this branch (spec 006: note, hooks inactive), so a role must not be rendered with `Bash` there.

## Failure modes

| Failure | Handling |
|---|---|
| `.claude/settings.json` is skipped (edited by hand, invalid, a symlink) so the hook is absent | the roles render without `Bash` in that run (FR-009); `check` already reports the missing or edited entry; the next `update` that succeeds adds `Bash` |
| `enforce` turned off in the config, no `update` yet | the hook still runs (the entry is in settings) and refuses the roles' `Bash` (FR-009), the main session is unaffected |
| The hook cannot read the config, or crashes | `run()` allows with a note (spec 006): the one place where a reviewer's `Bash` is unchecked, same as every other hook; documented |
| A configured command itself writes (a test writes a file) | allowed on purpose; the project's own commands are trusted (S2.2, FR-007) |
| The host stops sending `agent_type`, or renames it | the reviewer's calls are judged as the main session's: unlimited `Bash` for the reviewer; the live row HR1 (re-check after a major host version) gains a line, and `tests/fixtures/hooks/agent-bash.json` pins the field |
| `commands` changes | the hook reads it at each call; `update` re-renders the role only for the `Bash` condition (commands set or not) |
| Rollback | `enforce` off and `sdlc update`, or revert the commit: the roles go back to read-only |

## Security & observability

- The refusal is a computed fact (role and exact string), never a guess, so it fits ADR-0003's "block only on a computed result". Unknown `agent_type` values are not refused.
- No new data is stored or sent; refusal reasons carry command names (keys), not command strings.
- Residual risk, stated in the README: a configured command may execute anything the project's tests execute; the reviewer's independence rests on trusting those commands, as `verify` already does.
