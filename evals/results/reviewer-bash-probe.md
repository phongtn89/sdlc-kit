# Probe: how can a read-only role run only the project's check commands? (spec 010, E2.1)

Date: 2026-11-07. Claude Code 2.1.316, model `claude-sonnet-5-5`. Each run is one fresh `claude -p` through `evals/run.py` in a scratch project holding a custom sub-agent `probe` that is told to run five shell commands as separate Bash calls. Grading reads the sub-agent's own tool calls and results in the transcript (`parent_tool_use_id` set), not its summary. n = 1 per variant: this is a mechanism probe, not a rate.

Commands tried, in order: (1) `echo hello` (2) `echo hello; echo second` (3) `echo other` (4) `touch made-by-agent.txt` (5) `echo hello > redirected.txt`.

## Probe 1: a `Bash(<pattern>)` entry in the sub-agent's `tools:` line

| Variant | `tools:` line | Main session allowed | Result |
|---|---|---|---|
| exact, agent only | `Read, Bash(echo hello)` | `Agent` | 1, 2, 3 ran; 4 and 5 stopped with "needs approval" (the ordinary permission system, not the pattern) |
| exact, Bash allowed | `Read, Bash(echo hello)` | `Agent Bash` | all five ran; `made-by-agent.txt` and `redirected.txt` exist |
| prefix, agent only | `Read, Bash(echo hello:*)` | `Agent` | same as the exact variant |
| prefix, Bash allowed | `Read, Bash(echo hello:*)` | `Agent Bash` | all five ran |

**The pattern does not limit anything and does not grant anything**: `echo other` and the chained command ran under both forms, and with a broad allow in the main session every command ran. What stopped `touch` and the redirect in the "agent only" runs was the default permission rule for writes. The spec's design (FR-001 as first written) does not work on this version.

## Probe 2: hooks

| Variant | Result |
|---|---|
| A `hooks:` block in the sub-agent's own front matter (PreToolUse, matcher `Bash`, a command that logs and denies) | never ran: no log written, all five commands ran |
| A project-level `PreToolUse` hook in `.claude/settings.json`, logging its input | ran for every Bash call of the sub-agent; its input carries `agent_id` and `agent_type` (the sub-agent's `name`, here `probe`); for a call made by the main session `agent_type` is absent (`null`) |
| The same project-level hook denying everything except `echo hello` when `agent_type == "probe"` (JSON deny, exit 0) | (1) ran; (2) the chained command, (3) `echo other`, (4) `touch`, (5) the redirect were each refused with `PreToolUse:Bash hook error: <our reason>`; the main session's own `echo main-session > main.txt` ran, untouched |

**A project-level hook can scope a rule to one sub-agent by `agent_type`, and its deny binds for that sub-agent.** This is the mechanism the kit already ships for the main session (spec 006), so it needs `enforce` and exists for Claude Code only.

## Limits

n = 1 per variant, one model, one Claude Code version. The front-matter `hooks:` block may need other syntax or a newer host; not pursued. Whether the host also sends `agent_type` for a sub-agent started by another sub-agent was not tried. `agent_type` equal to the agent's `name` was seen with a custom agent; the rendered `sdlc-reviewer` is assumed to behave the same and is part of the spec's live eval (SC-001).

## Probe 3: the rendered roles (added 2026-11-07, closes the analyze finding A6)

The kit installed with `sdlc install --targets claude` into a scratch project, a project-level `PreToolUse` logging hook (matcher `Read|Grep|Glob|Bash`), and a fresh `claude -p` asked to have `sdlc-reviewer` and then `sdlc-security-reviewer` read `README.md`. The hook log shows one call each: `agent_type` is `sdlc-reviewer` (tool `Read`, an `agent_id` set) and `sdlc-security-reviewer`. So `agent_type` equals the rendered `name:`; the spec's roles list is `sdlc-reviewer` and `sdlc-security-reviewer`. n = 1 each. Not tried: a sub-agent started by a sub-agent.

## Probe 4: does a silent hook let a command through? (added 2026-11-07, analyze pass 2, finding N2)

A sub-agent `probe` (tools `Read, Bash`), a project-level `PreToolUse` hook for `agent_type == probe`, and a main session allowed only `Agent`. Commands: `python3 -c "print(40+2)"`, `touch made-by-agent.txt`, `python3 -m unittest --help`.

| Hook output for the sub-agent's calls | Result |
|---|---|
| nothing (the spec 006 "allow") | all three stopped: "This command requires approval" (and the `touch` write rule); nothing ran |
| `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", ...}}` | all three ran, `made-by-agent.txt` exists |

**A silent hook leaves the host's permission pipeline in charge**: a configured test command is not read-only, so it would be refused in a headless run and prompted for in an interactive one. For the reviewer to run a configured command the hook must answer an explicit `allow`. n = 1 per variant; the default permission rules are the host's and may differ with a project's own allow rules.
