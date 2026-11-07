# Spec: Reviewer can run the project's check commands, and still cannot write

Feature: reviewer-checks
Number: 010
Status: draft <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: one-line reason). sdlc-analyze sets approved; sdlc-ship sets implemented; rejected records a feature that was built or evaluated and deliberately not adopted. -->
Approved: <!-- written by `sdlc gate approve --by <name>`: name, YYYY-MM-DD, digest sha256:<64 hex> (spec, plan, tasks, contracts prefixes) -->
Owner: phong.ngo.vn
Created: 2026-11-07
Track: T3

<!-- Roadmap story E2.1 (docs/roadmap/layers-plan.md), a (D) story: it needs a decision. ADR-0003 rule "Reviewer able to write" (ladder level 2) is enforced today by rendering read-only roles with `tools: Read, Grep, Glob` for Claude and `['read', 'search']` for Copilot, tested end to end by spec 009. This story relaxes it in one narrow way, so it must keep that rule's test true in spirit. -->

## Intent

**Problem:** The reviewer role can only read, so it cannot reproduce a failure it is told about, or check that the tests really pass; it reads the `sdlc verify` record and trusts it. A reviewer who cannot run the project's own test and lint commands reviews claims, not behaviour.

**Who:** The reviewer and security-reviewer roles on Claude Code, and the person who asks for an independent review.

**Why now:** Wave 1 made the gates and hooks real; the reviewer is the one role still working on trust. ADR-0003 already names this as the follow-up (E2.1) and allows it only when the role stays unable to write.

**What the probe found (2026-11-07, `evals/results/reviewer-bash-probe.md`):** a `Bash(<pattern>)` entry in a sub-agent's `tools:` line does not limit or grant anything on Claude Code 2.1.316, so the first design (FR-001 as drafted) does not work. A project-level `PreToolUse` hook, by contrast, receives `agent_type` (the sub-agent's name) for every call a sub-agent makes, and its deny binds for that sub-agent only. This spec therefore uses the hook mechanism of spec 006: it needs `enforce`, and it is Claude Code only.

## Out of scope

- Any other command for a read-only role (`git`, a shell, an editor): only the project's configured `commands`
- GitHub Copilot: its tool list has no way to limit a command, so its read-only roles stay `read` and `search` only
- A limit through the role's `tools:` line or a `hooks:` block in its front matter (both probed, neither works on this version)
- Making the reviewer run `sdlc verify` or write the evidence record (the skill reads the record, it does not run it, spec 004)
- Choosing the reviewer's model (E2.2)
- Reading the commands from the base revision instead of the tree under review (see the README note: do not enable this for review of untrusted branches)
- Windows and other non-POSIX shells (the hook entry and `verify` are POSIX only)
- A reviewer started by another sub-agent (an implementer holds the `Agent` tool): if the host reported the parent's `agent_type` it would be judged as the main session; not verified, said in the README

## Glossary terms used

- **Read-only role**: a role whose source says `access: read-only`; rendered without any tool that writes, runs commands or delegates (spec 009, class `ReviewerAbleToWrite`).
- **Check command**: the value of `commands.<name>` in `.sdlc/config.json` for a name `sdlc verify` runs (test, lint, typecheck, build, integration; the same set and nothing else).

## User scenarios

### S1 — The reviewer reproduces a failure (P1)

As a person asking for a review, I want the reviewer to run the project's test command, so that a failure it was told about is reproduced, not assumed.

**Independent test:** a fixture project with a failing test and a one-line fix; the reviewer is told "the test `test_x` fails, confirm it".

1. **Given** `enforce` is on and `commands.test` is set, **When** the reviewer runs exactly that command string from the project root, **Then** the hook allows it and the reviewer sees the output
2. **Given** any other command (`git commit`, `rm`, `python3 -c ...`, the test command with a second command chained after it, or with a redirect), **When** the reviewer tries it, **Then** the hook refuses it with the reason, and the main session's own commands are not affected

### S2 — The reviewer still cannot write (P1)

As the owner, I want the reviewer unable to change the project, so that its verdict stays independent.

**Independent test:** the end-to-end class `ReviewerAbleToWrite` of spec 009, updated.

1. **Given** the rendered reviewer, **When** it calls a write, edit or delegate tool, **Then** the host refuses it
2. **Given** a configured check command that itself writes (a test that writes a file), **When** the reviewer runs it, **Then** it runs, and the limit is stated in the docs: the project's own commands are trusted

### S3 — Nothing changes where this cannot be limited (P2)

As a Copilot user, I want no surprise, so the Copilot reviewer stays read and search only; a project with no `commands` renders the reviewer exactly as today.

## Requirements

- **FR-001**: The reviewing read-only roles (reviewer, security-reviewer) MUST render, for Claude Code, with the `Bash` tool added, only when `enforce` is true, the Claude target is on, no `repos` is configured and at least one check command is configured, and only when the `bash` hook entry is present and unedited in the settings text that results from the same install or update, judged on that text, not by the lock: exactly one group with the marker `# sdlc-kit:bash` in the whole file, under `PreToolUse`, whose hash equals the expected group's, and `disableAllHooks` not truthy (a hand-edited or moved entry, an unreadable file and a symlink that escapes the project all count as not present). (S1)
- **FR-002**: The kit's `bash` hook MUST, for a call whose `agent_type` is one of those roles, allow exactly the configured check commands, each compared as the whole command string after removing spaces, tabs, carriage returns and newlines around it (inner characters, including a newline, are never removed), answer an explicit `allow` decision for it (a silent hook leaves the host's permission rules in charge, and a test command is not read-only, probe 4), and refuse every other command with a reason that starts `sdlc: refused`; a command with a chain, a redirect or an extra argument is another command. Only `tool_input.command` is compared, and a call that sets `dangerouslyDisableSandbox` to true is refused. A call with no `agent_type`, or one that is not a reviewing role, is judged as before. (S1, S2)
- **FR-003**: A read-only role MUST still render without Write, Edit, MultiEdit, NotebookEdit or any agent tool; its only addition is `Bash`, under FR-001. (S2)
- **FR-008**: A role source marks the roles that may get the limited `Bash` with `checks: true`, valid only with `access: read-only`; `sdlc lint` refuses `checks` on a full-access role or with a value other than `true` or `false`; the hook's list of roles equals the roles of the kit's core and modules marked so (the check is `is True`). (S2)
- **FR-009**: The hook MUST refuse every `Bash` call of a reviewing role when `enforce` is not true or `repos` is configured (the role file may carry `Bash` until the next `update`), judged before the hook's other gates, and MUST refuse them too when the config cannot be read, there is no project root or no lock, the input is too large or unreadable but names a reviewing role in its `agent_type`, or the gate itself raises (for these roles only, fail closed; the main session keeps spec 006's silence or note). `sdlc check` MUST report, for every file on disk named like a reviewing role (`.claude/agents/sdlc-reviewer.md`, `sdlc-security-reviewer.md`), also one no longer in the lock, whose `tools:` line has `Bash` while the `bash` hook entry is not intact in the sense of FR-001, `DRIFT` and exit 1; `update` MUST add a `NOTE` line for such a file it leaves alone, by the existing `SKIP` or the `KEPT` path. The settings file MUST be written before the role files, so a failed settings write leaves the roles as they were. (S1, S2)
- **FR-004**: With `enforce` off, no configured command, or for GitHub Copilot, a read-only role MUST render as today (no `Bash`). (S3)
- **FR-005**: `sdlc update` MUST re-render the reviewer when `commands` change, and `sdlc check` MUST report the rendered file as modified only if it was edited by hand, as for any rendered file. (S1)
- **FR-006**: The end-to-end test for the rule "Reviewer able to write" (spec 009) MUST keep failing when a read-only role gets any write, edit, delegate or unlimited command tool, and MUST pass with the limited `Bash`. (S2)
- **FR-007**: The README and the reviewer role text MUST say what the reviewer may run, that the project's own commands are trusted not to write, and that a run does not replace `sdlc verify`. (S2)

## Non-functional

- **NFR-001**: An `agent_type` the hook does not recognise is the main session, judged as in spec 006 (an unreadable config allows with a note). For a reviewing role the hook fails closed: a refusal is the answer to `enforce` not true, `repos` present, an unreadable config, an exception, no usable command, or a command that is not exactly a configured one. The role gate is the one place where fail closed replaces fail open, because the role file carries a shell that only this hook limits.

## Success criteria

- **SC-001**: In a live session on a fixture project, the reviewer reproduces a named failing test by running the configured command, and a write attempt of each kind (an edit tool, a shell redirect, another command, the configured command with an added argument) is refused by the host: 4 of 4 refusals and the reproduction in n = 3 runs — measured with `evals/run.py`, recorded in `evals/results/`.
- **SC-002**: The mutation script of spec 009 catches the removal of each limit (the role check, the exact-match comparison, `Bash` added without `enforce` or with a skipped settings entry, a write tool added) — 100% of the new mutations.

## Assumptions & dependencies

- Assumption (verified 2026-11-07, `evals/results/reviewer-bash-probe.md`, probes 2 and 3): a project-level `PreToolUse` hook receives `agent_type` for a sub-agent's calls, equal to the rendered name (`sdlc-reviewer`, `sdlc-security-reviewer`), and its deny binds for them. Not verified: the same for a sub-agent started by a sub-agent. If the host stopped sending `agent_type`, the reviewer's calls would be judged as the main session's, so the HR1 re-check row pins the field.
- Residual risk, stated in the README: the allowed commands run code from the tree under review (test scripts, a Makefile) and are read from that tree's `.sdlc/config.json`, so a branch that changes either gets its code run by the reviewer. Do not enable this for review of untrusted branches. The limit also exists only while the kit folder, the hook entry and `enforce` are intact (`sdlc check` reports a moved kit and an edited or missing entry). The same branch can change `.claude/settings.json`, `.claude/agents/*.md` and `.sdlc/lock.json` (a missing lock makes the gate refuse the roles, but the main session's hook goes silent), and `uninstall` leaves a hand-edited role file that still lists `Bash` after it removes the hook entries; the README says so.
- Dependency: spec 009 (the rule's end-to-end test and the mutation script), spec 004 (`commands`).

## Clarifications

### Session 2026-11-07

- Q: Is a hook-based limit (needs `enforce` and Claude Code) acceptable? → A: yes; without `enforce` the reviewer stays read-only as today (phong.ngo.vn, in chat)
- Q: Exact match of the whole configured command, or extra arguments allowed? → A: exact match of the whole string; a test filter or any added argument is another command (phong.ngo.vn, in chat)
- Q: Which roles get the limited `Bash`? → A: the reviewer and the security-reviewer, not the explorer and planner (phong.ngo.vn, in chat)
- Decided while writing the plan, from the probe's limits: the hook refuses every `Bash` call of those roles when `enforce` is no longer true (the role file may still carry `Bash` until `update`), and the role is only rendered with `Bash` when the bash hook entry is really going to be in `.claude/settings.json` (not when the file is skipped, or for a workspace config).

## Open questions

None.
