# Plan: Reviewer can run the project's check commands, and still cannot write

Spec: [spec.md](spec.md) · Status: approved · Created: 2026-11-07

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

Contract of the new role gate. It is a function called from `run()` (not from `on_bash`), after the input is parsed and the project root is found and **before** the `enforce` and `repos` gates, because those gates return early and a role file may carry `Bash` after `enforce` went off or `repos` was added. Its text must not repeat `if cfg.get("enforce") is not True:`, which the mutation script of spec 009 expects exactly once. It applies only when `data["agent_type"]` is a string in `CHECK_ROLES` (`sdlc-reviewer`, `sdlc-security-reviewer`) and the tool is `Bash`; any other value or a missing key is the main session, judged as today. With no project root or no `.sdlc/lock.json` the hook allows silently for the main session as before and **denies for a reviewing role** (a role file exists only where the kit is installed, so a missing lock is a tampered or broken project, not a foreign one). The same fail-closed rule covers an input the hook cannot parse or that is over the size cap, when the raw text names `sdlc-reviewer` or `sdlc-security-reviewer` as `agent_type`: in `run()`, for the `bash` hook, a deny instead of the note.

| State, checked in this order | Output |
|---|---|
| no project root or no lock, the config cannot be read, or the gate raises | deny: `sdlc: refused: the <role> may not run commands: the project's config or lock could not be read` |
| `enforce` is not exactly true | deny: `sdlc: refused: the <role> may not run commands while enforce is off; run sdlc update` |
| `repos` is in the config | deny: `sdlc: refused: the <role> may not run commands in a workspace config; run sdlc update` |
| `tool_input.dangerouslyDisableSandbox` is true | deny: `sdlc: refused: the <role> may not run a command outside the sandbox` |
| no usable command: the string values of `commands` for the names `sdlc verify` runs (`sdlc_verify.ORDER`), blank values ignored, none left | deny: `sdlc: refused: the <role> may only run the project's configured check commands, and none is configured` |
| `command.strip(" \t\r\n")` equals the same-stripped value of one of them, and the usual push check finds no push (a green push, and the unbalanced-quote case where it cannot tell, are in the next two rows) | **allow, explicitly**: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "sdlc: a configured check command"}}` (probe 4: a silent hook leaves the host's permission rules in charge and a test command is not read-only) |
| a configured command that the push check finds to push | the usual push decision: a deny when not green, an explicit allow when green |
| a configured command the push check cannot tell about (an unbalanced quote) | deny: `sdlc: refused: the <role> could not tell whether the command pushes` (the main session keeps spec 006's note and allow) |
| anything else (a chain, a redirect, an added argument, another command) | deny: `sdlc: refused: the <role> may only run the project's configured check commands (<names>)`, the names being the keys of the usable commands, at most five |

Only `tool_input.command` is compared. The strip removes spaces, tabs, carriage returns and newlines around the whole string; an inner newline makes it another command. The allow, the deny and the note are built by one helper `decision(kind, reason)` so that the text anchors the mutation script of spec 009 expects exactly once (`"hookEventName": "PreToolUse", "permissionDecision"`, `"permissionDecisionReason": reason`) stay unique; T001 updates those texts.

Rendering: `sync` computes the settings plan first (it needs only the config, the old lock and the kit path, not the rendered files), then derives one verdict, `bash_hook_ok`, **from the settings text the run will leave behind** (the new text if the plan writes, else the file as it is, a missing file being false): `enforce` true, `claude` a target, no `repos`, the text parses, and the group carrying the marker `# sdlc-kit:bash` has `group_hash(g) == group_hash(group(cli, "bash"))`. The lock is not consulted: a skipped, hand-edited entry keeps its old lock hash, which still equals the expected one while the kit has not moved (analyze pass 2, N1). A new function `bash_entry_ok(text, cli)` in `sdlc_hooks.py` holds the rule, and it is the only rule: true iff the text parses, `disableAllHooks` is not truthy, exactly one group in the whole file carries the marker `# sdlc-kit:bash`, that group sits under `PreToolUse`, and its `group_hash` equals the expected group's (pass 3, B1). `check` uses the same function for its role `DRIFT`, so the two cannot disagree (B13). The settings file is written before the role files in `sync`, so a failed settings write leaves the roles as they were (B2). A role with `checks: true` gets `tools: Read, Grep, Glob, Bash` iff `bash_hook_ok` and at least one usable command exists; the key is read with `is True`. `render` is called only from `sync`, and `check` does not render, so an untouched install stays `ok`.

## Failure modes

| Failure | Handling |
|---|---|
| `.claude/settings.json` is skipped (edited by hand, invalid, a symlink) | the verdict is false for the bash entry only if that entry is the skipped one; the roles render without `Bash` in that run; `check` reports the entry; the next successful `update` adds `Bash` |
| `enforce` turned off or `repos` added, no `update` yet | the role gate refuses the roles' `Bash` (FR-009); the main session is unaffected |
| `update` after `enforce` went off removes the hook entries but a hand-edited role file keeps `Bash` (the existing `SKIP (modified locally)`, exit 2) | `update` also prints `NOTE .claude/agents/<role>.md lists Bash and the bash hook entry is not rendered; run sdlc update --force or delete the file`; `check` reports `DRIFT` for it while the bash entry is missing or edited; the role gate still refuses its calls only while the hook entry exists, so this is the one state that is a real gap, closed by `check` exit 1 and the line; fix with `update --force` or by deleting the file |
| Kit folder moved or deleted, the 90 s timeout, a Python crash, the user disables hooks or edits the entry | the rendered entry allows with a note or does nothing (spec 006); the limit is gone with it; `check` reports `KIT-PATH-MISSING` and an edited or missing entry; the README says the limit exists only while those are intact |
| Config unreadable (invalid JSON, a list, an exception) | for a reviewing role the hook denies (fail closed, N3); for the main session it allows with a note as in spec 006 |
| A configured command itself writes (a test writes a file) | allowed on purpose; the project's own commands are trusted (S2.2, FR-007) |
| A branch under review changes `.sdlc/config.json` or the test code | its code runs when the reviewer runs the command; the README says not to enable this for untrusted branches; reading the commands from the base revision is out of scope |
| The host stops sending `agent_type`, or renames it | the reviewer is judged as the main session and has an unlimited `Bash`; the fixture `agent-bash.json` and the HR1 row pin the field |
| `commands` changes | the hook reads it at each call; `update` re-renders the role only when the `Bash` condition flips |
| Rollback | `enforce` off and `sdlc update`, or revert the commit: the roles go back to read-only |

## Security & observability

- The refusal is a computed fact (role and exact string), never a guess, so it fits ADR-0003's "block only on a computed result". Unknown `agent_type` values are not refused.
- No new data is stored or sent; refusal reasons carry command names (keys), not command strings.
- Fail closed for the two roles is a deliberate departure from the ADR's "block only on a computed result": the computed facts are the role's identity and that its tools list carries a shell only this hook limits; the ADR addendum says so (B12).
- Residual risk, stated in the README: a configured command may execute anything the project's tests execute, and the commands come from the tree under review; the reviewer's independence rests on trusting them, as `verify` already does. Not for untrusted branches.
- The model cannot spoof `agent_type`: the host sets it. The roles' tools line is an allow list, so the reviewer has no `Agent` tool to start another sub-agent.
- The same branch can edit `.claude/settings.json` (the hook entry), `.claude/agents/*.md` (the role file) and delete `.sdlc/lock.json` (the main session's hook goes silent; the roles' gate still denies), and `uninstall` keeps a hand-edited role file that still lists `Bash` after removing the hook entries; all documented, `check` reports the first (and the role files on disk, not only locked ones), the `NOTE` of `update` the second. A reviewer started by another sub-agent is not verified (the host might report the parent's `agent_type`).
