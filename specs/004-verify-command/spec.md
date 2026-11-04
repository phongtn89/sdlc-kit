# Spec: `sdlc verify`, a program-run check with an evidence record

Feature: verify-command
Number: 004
Status: draft <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: one-line reason). sdlc-analyze sets approved; sdlc-ship sets implemented; rejected records a feature that was built or evaluated and deliberately not adopted. -->
Approved: <!-- name, YYYY-MM-DD; filled when approved -->
Owner: phong.ngo.vn
Created: 2026-11-04
Track: T3

<!-- Roadmap story E1.2 (docs/roadmap/layers-plan.md); decision record ADR-0003 (docs/adr/0003-enforcement-model.md): ladder level 5, "the program runs the check, the agent quotes it". -->

## Intent

**Problem:** Skills tell the agent to run the project's tests and lint before saying "done", and the agent reports what happened in its own words (ladder level 0). Nothing in the kit runs the check itself or leaves a record that a later step can read, so "tests are green" is a claim, and a gate (E1.3) or a hook (E1.4) has nothing to test it against.

**Who:** Agents that finish a task or open a PR, the humans who read their reports, and the later gates and hooks of epic E1 that need a machine-readable "green at this revision".

**Why now:** ADR-0003 fixes the enforcement model and makes this command the first building block: `gate green-at-head`, the push hook and the budget check all read its record. Nothing else in epic E1 can be specified until the record exists.

## Out of scope

- Reading the record to allow or refuse something (`gate`, hooks): E1.3 and E1.4.
- Running a project's tests in parallel, retrying a failed command, or fixing what fails.
- Choosing which commands a project has. They stay in `.sdlc/config.json` (`commands`).
- Keeping command output. The record holds no output (NFR-002).
- Defending against an agent that edits the project's config to change the commands (stated limit; the config is the project's own file).
- Copilot hooks. The command itself works on any host; only Claude Code gets a hook (ADR-0003).

## Glossary terms used

- **Evidence record**: the file `verify` writes (`.sdlc/evidence/verify.json`) with what ran, the exit codes and the revision.
- **Green at HEAD**: the record's revision equals the repository's current `HEAD`, the tree was clean, and every command that ran exited 0.
- **Stale**: a record whose revision is not the current `HEAD`.

## User scenarios

### S1: Run the project's checks and get a record (P1)

As an agent, I want one command that runs the configured checks and tells me the result, so that I quote a result instead of claiming one.

**Independent test:** a project whose configured commands all exit 0 gets exit code 0, a record, and a printed summary line per command.

1. **Given** `commands.test` and `commands.lint` are set and both succeed, **When** I run `sdlc verify`, **Then** both run once, in a fixed order, the exit code is 0, a record lists each command with its exit code and duration, and the summary says every command passed.
2. **Given** one command fails, **When** I run `sdlc verify`, **Then** the exit code is 1, the record shows that command's exit code, the commands after it still run, and the summary names the failing command and prints the last lines of its output.

### S2: A check that can't give a trustworthy answer is not green (P1)

As a reviewer, I want a missing, hanging or unrunnable check to read as not green, so that silence is never taken for success.

**Independent test:** a project with no commands, one with a command that hangs, and one with a missing executable each exit non-zero with a reason.

1. **Given** no command is configured, **When** I run `sdlc verify`, **Then** it exits 2, says nothing was verified and writes no record claiming green.
2. **Given** a command runs longer than its time limit, **When** `verify` waits, **Then** the command is stopped, recorded as timed out and counted as a failure.
3. **Given** a command can't start (missing executable), **When** I run `sdlc verify`, **Then** it is recorded as failed with the reason, not skipped.

### S3: The record says which revision it is about (P1)

As a gate, I want to know whether the record describes the code that exists now, so that a green result from an older revision can't pass a push.

**Independent test:** after a commit the record reads as stale; a run on a dirty tree is recorded as dirty.

1. **Given** a record taken at revision A on a clean tree, **When** `HEAD` becomes B, **Then** the record's revision (A) differs from `HEAD`, so any reader can see it is stale without re-running anything.
2. **Given** uncommitted changes exist, **When** I run `sdlc verify`, **Then** the record says the tree was dirty, and a dirty record is never green at HEAD.
3. **Given** the directory is not a git repository, **When** I run `sdlc verify`, **Then** the checks run and the record says there is no revision, which is never green at HEAD.

### S4: Workspaces and skills (P2)

As an owner of a multi-repo workspace, I want to verify one repo with that repo's commands, and I want the skills to use the command, so that the claim in every report comes from it.

**Independent test:** in a workspace, `verify --repo <name>` uses `repos.<name>.commands` and writes the record in that repo.

1. **Given** a workspace config with per-repo commands, **When** I run `sdlc verify --repo api`, **Then** it runs from that repo's folder with its commands and writes its record there.
2. **Given** the kit's skills for implementing, reviewing and shipping, **When** they ask for a result, **Then** they tell the agent to run `sdlc verify` and quote its summary and record revision.

## Requirements

- **FR-001**: `sdlc verify` MUST run the non-empty entries of `commands` (`test`, `lint`, `typecheck`, `build`, `integration`), each once, sequentially, in that fixed order, from the project root. (S1)
- **FR-002**: Each command MUST run non-interactively: no input is available to it, and no prompt can wait for an answer. (S1, S2)
- **FR-003**: `verify` MUST continue after a failing command and run the rest. (S1)
- **FR-004**: Each command MUST have a time limit, default 600 seconds, overridable by `verify.timeout_seconds` in `.sdlc/config.json`; a command over the limit MUST be stopped, recorded as timed out and counted as failed. (S2)
- **FR-005**: A command that can't start MUST be recorded as failed with the reason. (S2)
- **FR-006**: The exit code MUST be 0 only when at least one command ran and every command that ran exited 0; 1 when any command failed or timed out; 2 for bad arguments, an unreadable config, or no command configured. (S1, S2)
- **FR-007**: With no command configured, `verify` MUST say so and MUST NOT write a record. (S2)
- **FR-008**: `verify` MUST write the evidence record atomically to `.sdlc/evidence/verify.json`, replacing the previous one. It holds: format version, UTC start and end time, the revision (`HEAD` as a full hash, or none), whether the tree was dirty, and per command its name, text, exit code (or `timeout` or `not started`), duration and result. (S1, S3)
- **FR-009**: The record MUST NOT contain command output (NFR-002). (S1)
- **FR-010**: `verify` MUST print one summary line per command (name, result, duration), then one final line saying passed or failed and giving the revision and dirty state; for a failed command it MUST print the last 20 lines of that command's combined output, at most 2,000 characters. (S1)
- **FR-011**: The record MUST state whether the tree was dirty and MUST state "no revision" outside a git repository; a dirty or revision-less record MUST NOT be described as green at HEAD in the final line. (S3)
- **FR-012**: In a workspace, `verify --repo <name>` MUST use `repos.<name>.commands`, run from that repo's path, and write that repo's record; an unknown repo name is exit 2. (S4)
- **FR-013**: `verify` MUST work when `enforce` and `usage` are off, and MUST NOT read or write any file outside the project root except the commands' own side effects. (S1)
- **FR-014**: The commands MUST come only from `.sdlc/config.json`; `verify` MUST NOT accept a command from its arguments or the environment. (S1)
- **FR-015**: The kit's skills that report test results (`sdlc-implement` convergence step, `sdlc-review`, `sdlc-ship`, `sdlc-debug` verification) MUST tell the agent to run `sdlc verify` and quote its final line and revision, and the rendered `AGENTS.md` rule MUST say the same. (S4)

## Non-functional

- **NFR-001**: Python 3.9+ standard library only, no network, no prompts (the kit's constraints).
- **NFR-002**: The record is content-free: names, commands as configured, numbers and a revision, never output.
- **NFR-003**: A failed write leaves the previous record unchanged.
- **NFR-004**: `verify` adds no more than 1 second of its own time to the commands' time on a repository of 1,000 files.

## Success criteria

- **SC-001**: A red and a green fixture command give exit codes 1 and 0 and the matching record, and removing the record-writing or the exit-code logic makes at least one test fail — measured by unit tests plus a mutation check.
- **SC-002**: The record of any run contains no byte of command output — measured by a test that runs a command printing a marker string and searches the record.
- **SC-003**: After a new commit, a reader comparing the record's revision with `HEAD` finds it stale in 100% of test cases (clean, dirty, no repository) — measured by unit tests.
- **SC-004**: In a live eval (new row V1, n = 3 on two models) an agent told to finish a small fix and report runs `sdlc verify` and quotes its final line in at least 5 of 6 runs — measured from the transcripts.

## Assumptions & dependencies

- Assumption: a project's `commands` are the checks it wants run before "done"; an empty `integration` means none, not failure.
- Assumption: 600 seconds is enough for a project's whole test command; slower suites set `verify.timeout_seconds`.
- Assumption: `.sdlc/evidence/` is local state, not committed; the plan decides how installs ignore it.
- Dependency: ADR-0003 (accepted). Later: E1.3 reads this record; E1.4's hooks call E1.3.

## Clarifications

### Session 2026-11-04

- Q: Which stories does the epic's E1.2 cover → A: only the command and its record; reading it is E1.3 (roadmap).
- Q: How is a dirty tree treated → A: `verify` runs and records `dirty: true`; such a record is never green at HEAD (FR-011). Chosen by phong.ngo.vn in chat, 2026-11-04.

## Open questions

None.
