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

## Glossary terms used

- **Read-only role**: a role whose source says `access: read-only`; rendered without any tool that writes, runs commands or delegates (spec 009, class `ReviewerAbleToWrite`).
- **Check command**: a value of `commands.<name>` in `.sdlc/config.json` (test, lint, typecheck, build, integration).

## User scenarios

### S1 — The reviewer reproduces a failure (P1)

As a person asking for a review, I want the reviewer to run the project's test command, so that a failure it was told about is reproduced, not assumed.

**Independent test:** a fixture project with a failing test and a one-line fix; the reviewer is told "the test `test_x` fails, confirm it".

1. **Given** `enforce` is on and `commands.test` is set, **When** the reviewer runs exactly that command, **Then** the hook allows it and the reviewer sees the output
2. **Given** any other command (`git commit`, `rm`, `python3 -c ...`, the test command with a second command chained after it, or with a redirect), **When** the reviewer tries it, **Then** the hook refuses it with the reason, and the main session's own commands are not affected

### S2 — The reviewer still cannot write (P1)

As the owner, I want the reviewer unable to change the project, so that its verdict stays independent.

**Independent test:** the end-to-end class `ReviewerAbleToWrite` of spec 009, updated.

1. **Given** the rendered reviewer, **When** it calls a write, edit or delegate tool, **Then** the host refuses it
2. **Given** a configured check command that itself writes (a test that writes a file), **When** the reviewer runs it, **Then** it runs, and the limit is stated in the docs: the project's own commands are trusted

### S3 — Nothing changes where this cannot be limited (P2)

As a Copilot user, I want no surprise, so the Copilot reviewer stays read and search only; a project with no `commands` renders the reviewer exactly as today.

## Requirements

- **FR-001**: The reviewing read-only roles (reviewer, security-reviewer) MUST render, for Claude Code, with the `Bash` tool added, only when `enforce` is true, the Claude target is on and at least one check command is configured. (S1)
- **FR-002**: The kit's `bash` hook MUST, for a call whose `agent_type` is one of those roles, allow exactly the configured check commands, each compared as the whole command string, and refuse every other command with a reason that starts `sdlc: refused`; a command with a chain, a redirect or an extra argument is another command. A call with no `agent_type` is judged as before. (S1, S2)
- **FR-003**: A read-only role MUST still render without Write, Edit, MultiEdit, NotebookEdit or any agent tool; its only addition is `Bash`, under FR-001. (S2)
- **FR-004**: With `enforce` off, no configured command, or for GitHub Copilot, a read-only role MUST render as today (no `Bash`). (S3)
- **FR-005**: `sdlc update` MUST re-render the reviewer when `commands` change, and `sdlc check` MUST report the rendered file as modified only if it was edited by hand, as for any rendered file. (S1)
- **FR-006**: The end-to-end test for the rule "Reviewer able to write" (spec 009) MUST keep failing when a read-only role gets any write, edit, delegate or unlimited command tool, and MUST pass with the limited `Bash`. (S2)
- **FR-007**: The README and the reviewer role text MUST say what the reviewer may run, that the project's own commands are trusted not to write, and that a run does not replace `sdlc verify`. (S2)

## Non-functional

- **NFR-001**: If the hook cannot read the configured commands or the input has an `agent_type` it does not recognise, it MUST fail as spec 006 does (allow with a note), never refuse on a guess; a refusal is only ever for a read-only reviewing role and a command that is not exactly a configured one.

## Success criteria

- **SC-001**: In a live session on a fixture project, the reviewer reproduces a named failing test by running the configured command, and a write attempt of each kind (edit, shell redirect, another command) is refused by the host: 3 of 3 refusals and the reproduction in n = 3 runs — measured with `evals/run.py`, recorded in `evals/results/`.
- **SC-002**: The mutation script of spec 009 catches the removal of each limit (the role check, the exact-match comparison, `Bash` added without `enforce`, a write tool added) — 100% of the new mutations.

## Assumptions & dependencies

- Assumption (verified 2026-11-07, `evals/results/reviewer-bash-probe.md`): a project-level `PreToolUse` hook receives `agent_type` for a sub-agent's calls and its deny binds for them. Not verified: the same for a sub-agent started by a sub-agent, and `agent_type` for the rendered `sdlc-reviewer` (covered by SC-001).
- Dependency: spec 009 (the rule's end-to-end test and the mutation script), spec 004 (`commands`).

## Clarifications

### Session 2026-11-07

(none yet)

## Open questions

- [NEEDS CLARIFICATION: is a hook-based limit, which exists only with `enforce` on and only for Claude Code, acceptable for this story? (recommended yes: it is level 3 of the ladder, as the other hooks, and without `enforce` the reviewer stays read-only as today) — blocks FR-001 — owner: phong.ngo.vn]
- [NEEDS CLARIFICATION: exact match of the whole configured command string, so a reviewer cannot add an argument such as a test filter (recommended, since the string is what `sdlc verify` runs); or also allow extra arguments after it? — blocks FR-002 — owner: phong.ngo.vn]
- [NEEDS CLARIFICATION: should the security-reviewer get the same limited `Bash`, or only the reviewer? (recommended: both read-only roles that review, not the explorer and planner) — blocks FR-001 — owner: phong.ngo.vn]
