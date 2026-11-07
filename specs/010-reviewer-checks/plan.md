# Plan: Reviewer can run the project's check commands, and still cannot write

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-07

## Summary

The limit lives in the kit's existing hook runtime (spec 006): the host sends `agent_type` for every call a sub-agent makes, equal to the rendered role name (probes, `evals/results/reviewer-bash-probe.md`), so a gate in `run()` can judge a reviewer's `Bash` call differently from the main session's. For a role marked `checks: true` in its source (reviewer, security-reviewer) it allows only a command that equals, as a whole string, a configured check command (the keys `sdlc verify` runs), and refuses everything else with a JSON deny, also when `enforce` is off or `repos` is present. The roles are rendered with `Bash` added only when that hook entry will really be in place. The riskiest part is the coupling between the rendered role file and the settings entry: a role with `Bash` and no live hook would have an unlimited shell.

## Technical context

- Language / runtime: Python 3.9+, stdlib only, in `bin/sdlc` (`render_role`, `sync`, the role lint) and `bin/sdlc_hooks.py` (`on_bash`)
- Key dependencies: spec 006 (hook runtime, `settings_plan`, `merge`, `group_hash`), spec 004 (`sdlc_verify.ORDER`), spec 009 (`test_never.py`, `mutate_never.py`, whose mutations name the text `if cfg.get("enforce") is not True:` and the role's `tools:` line, so both must be updated in the task that moves them)
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

- Seams: `bin/sdlc_hooks.py:run` (the role gate before the `enforce` gate, calling a new function for the decision), `bin/sdlc:render_role` and `render` (the condition), `bin/sdlc:sync` (compute the settings plan before rendering, pass the result down), `bin/sdlc:ROLE_KEYS` and the role lint, `core/roles/reviewer.md` and `security-reviewer.md` (`checks: true`, one sentence each)
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

Contract of the new role gate. It sits in `run()` (not in `on_bash`), after the project root and the config are read and **before** the `enforce` and `repos` gates, because those gates return early and a role file may carry `Bash` after `enforce` went off or `repos` was added. It applies only when `data["agent_type"]` is a string in `CHECK_ROLES` (`sdlc-reviewer`, `sdlc-security-reviewer`) and the tool is `Bash`; any other value or a missing key is the main session, judged as today. With no project root, no `.sdlc/lock.json` or an unreadable config the hook fails open as before (note, allow).

| State, checked in this order | Output |
|---|---|
| `enforce` is not exactly true | deny: `sdlc: refused: the <role> may not run commands while enforce is off; run sdlc update` |
| `repos` is in the config | deny: `sdlc: refused: the <role> may not run commands in a workspace config; run sdlc update` |
| `tool_input.dangerouslyDisableSandbox` is true | deny: `sdlc: refused: the <role> may not run a command outside the sandbox` |
| no usable command: the string values of `commands` for the names `sdlc verify` runs (`sdlc_verify.ORDER`), blank values ignored, none left | deny: `sdlc: refused: the <role> may only run the project's configured check commands, and none is configured` |
| `command.strip()` equals the stripped value of one of them | continue into the usual push check (a configured command that pushes is still judged) |
| anything else (a chain, a redirect, an added argument, another command) | deny: `sdlc: refused: the <role> may only run the project's configured check commands (<names>)`, the names being the keys of the usable commands, at most five |

Only `tool_input.command` is compared. `strip()` removes whitespace around the whole string, a trailing newline included; an inner newline makes it another command.

Rendering: `sync` computes the settings plan first (it needs only the config, the old lock and the kit path, not the rendered files) and derives one verdict, `bash_hook_ok`: `enforce` is true, `claude` is a target, no `repos`, and the lock entry the plan returns holds `hooks["bash"] == group_hash(group(cli, "bash"))` (a skipped, hand-edited bash entry keeps the old hash, so the verdict is false while a hand-edited `edit` or `stop` entry does not matter). A role with `checks: true` gets `tools: Read, Grep, Glob, Bash` iff the verdict is true and at least one usable command exists; the check is `is True` on the parsed role key. `render` is called only from `sync`, and `check` does not render, so an untouched install stays `ok`.

## Failure modes

| Failure | Handling |
|---|---|
| `.claude/settings.json` is skipped (edited by hand, invalid, a symlink) | the verdict is false for the bash entry only if that entry is the skipped one; the roles render without `Bash` in that run; `check` reports the entry; the next successful `update` adds `Bash` |
| `enforce` turned off or `repos` added, no `update` yet | the role gate refuses the roles' `Bash` (FR-009); the main session is unaffected |
| `update` after `enforce` went off removes the hook entries but a hand-edited role file keeps `Bash` (SKIP, KEPT) | `update` prints `KEPT .claude/agents/<role>.md (lists Bash and no hook is rendered)`; `check` reports `DRIFT` for it while the bash entry is missing or edited; the role gate still refuses its calls only while the hook entry exists, so this is the one state that is a real gap, closed by `check` exit 1 and the line; fix with `update --force` or by deleting the file |
| Kit folder moved or deleted, the 90 s timeout, a Python crash, the user disables hooks or edits the entry | the rendered entry allows with a note or does nothing (spec 006); the limit is gone with it; `check` reports `KIT-PATH-MISSING` and an edited or missing entry; the README says the limit exists only while those are intact |
| Config unreadable (invalid JSON) | the hook allows with a note (NFR-001); a readable config with no usable command denies |
| A configured command itself writes (a test writes a file) | allowed on purpose; the project's own commands are trusted (S2.2, FR-007) |
| A branch under review changes `.sdlc/config.json` or the test code | its code runs when the reviewer runs the command; the README says not to enable this for untrusted branches; reading the commands from the base revision is out of scope |
| The host stops sending `agent_type`, or renames it | the reviewer is judged as the main session and has an unlimited `Bash`; the fixture `agent-bash.json` and the HR1 row pin the field |
| `commands` changes | the hook reads it at each call; `update` re-renders the role only when the `Bash` condition flips |
| Rollback | `enforce` off and `sdlc update`, or revert the commit: the roles go back to read-only |

## Security & observability

- The refusal is a computed fact (role and exact string), never a guess, so it fits ADR-0003's "block only on a computed result". Unknown `agent_type` values are not refused.
- No new data is stored or sent; refusal reasons carry command names (keys), not command strings.
- Residual risk, stated in the README: a configured command may execute anything the project's tests execute, and the commands come from the tree under review; the reviewer's independence rests on trusting them, as `verify` already does. Not for untrusted branches.
- The model cannot spoof `agent_type`: the host sets it. The roles' tools line is an allow list, so the reviewer has no `Agent` tool to start another sub-agent.
