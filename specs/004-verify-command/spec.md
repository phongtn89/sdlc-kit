# Spec: `sdlc verify`, a program-run check with an evidence record

Feature: verify-command
Number: 004
Status: implemented <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: one-line reason). sdlc-analyze sets approved; sdlc-ship sets implemented; rejected records a feature that was built or evaluated and deliberately not adopted. -->
Approved: phong.ngo.vn, 2026-11-04 (H1, in chat, after two analyze passes; accepts that SC-004 can only be measured after the build) <!-- name, YYYY-MM-DD; filled when approved -->
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
- Defending against an agent that edits the project's config to change the commands, or writes `.sdlc/evidence/verify.json` by hand: the record carries no signature, so level 5 raises the cost of a false claim but does not close it (stated limit; E1.3 and CI, level 6, are the backstop).
- Copilot hooks. The command itself works on any host; only Claude Code gets a hook (ADR-0003).

## Glossary terms used

- **Evidence record**: the file `verify` writes (`.sdlc/evidence/verify.json`) with what ran, the exit codes and the revision.
- **Green at HEAD**: the record's revision equals the repository's current `HEAD`, the tree was clean (ignoring `.sdlc/evidence/`), at least one command ran and every command that ran exited 0.
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
3. **Given** a command's executable doesn't exist (the shell answers "not found", exit 127) or the command can't be launched at all, **When** I run `sdlc verify`, **Then** it is recorded as failed, with the exit code or the launch error, not skipped.

### S3: The record says which revision it is about (P1)

As a gate, I want to know whether the record describes the code that exists now, so that a green result from an older revision can't pass a push.

**Independent test:** after a commit the record reads as stale; a run on a dirty tree is recorded as dirty.

1. **Given** a record taken at revision A on a clean tree, **When** `HEAD` becomes B, **Then** the record's revision (A) differs from `HEAD`, so a reader applying the green-at-HEAD definition finds it not green without re-running anything.
2. **Given** uncommitted changes exist, **When** I run `sdlc verify`, **Then** the record says the tree was dirty, and a dirty record is never green at HEAD.
3. **Given** the directory is not a git repository (or has no commit yet), **When** I run `sdlc verify`, **Then** the checks run and the record says there is no revision, which is never green at HEAD.
4. **Given** a clean repository, **When** I run `sdlc verify` twice in a row, **Then** the second record is clean too: the first record's own file does not make the tree dirty.
5. **Given** a command changes files or makes a commit, **When** `verify` finishes, **Then** the record says dirty (or no revision if `HEAD` moved), because the revision was not the one that was checked.

### S4: Workspaces and skills (P2)

As an owner of a multi-repo workspace, I want to verify one repo with that repo's commands, and I want the skills to use the command, so that the claim in every report comes from it.

**Independent test:** in a workspace, `verify --repo <name>` uses `repos.<name>.commands` and writes the record in that repo.

1. **Given** a workspace config with per-repo commands, **When** I run `sdlc verify --repo api`, **Then** it runs from that repo's folder with its commands and writes its record there.
2. **Given** the kit's skills for implementing, debugging, reviewing and shipping, **When** they ask for a test result, **Then** the writing skills tell the agent to run `sdlc verify` and quote its final line, and the read-only review skill tells the reviewer to read and quote the existing record and say when it is stale or absent.

## Requirements

- **FR-001**: `sdlc verify` MUST run the non-empty entries of `commands` (`test`, `lint`, `typecheck`, `build`, `integration`), each once, sequentially, in that fixed order, from the project root. (S1)
- **FR-002**: Each command MUST run non-interactively: no input is available to it, and no prompt can wait for an answer. (S1, S2)
- **FR-003**: `verify` MUST continue after a failing command and run the rest. (S1)
- **FR-004**: When the time limit ends or the command exits, the command's process group MUST be killed so no child of it outlives the run; if `verify` itself is interrupted (SIGINT, SIGTERM) it MUST kill the running group, write no record, print `verify: interrupted, no record written` and exit 1. Each command MUST have a time limit, default 600 seconds, overridable by `verify.timeout_seconds` in `.sdlc/config.json`; a command over the limit MUST be stopped, recorded as timed out and counted as failed. (S2)
- **FR-005**: A command that exits 127 (not found) MUST be recorded as failed with that code; a command that can't be launched (an operating-system error at launch) MUST be recorded as `not started` with the error text, result `fail`. A non-string command, or one containing a NUL character, is a config error (exit 2). (S2)
- **FR-006**: The exit code MUST be 0 only when at least one command ran and every command that ran exited 0; 1 when any command failed or timed out; 2 for bad arguments, a missing project folder, an unreadable or invalid config (including a config of the wrong shape), a repo path outside the project root, or no command configured. If the record can't be written after the commands ran, `verify` MUST still print every result, then exit 1 when a command had failed and 2 otherwise. (S1, S2)
- **FR-007**: With no command configured (entries empty, whitespace-only, `null` or absent), `verify` MUST say so on its last line (FR-010) and MUST NOT write a record. A whitespace-only command is treated as empty, never as a pass. (S2)
- **FR-008**: `verify` MUST write the evidence record atomically to `.sdlc/evidence/verify.json`, replacing the previous one. It holds: format version, UTC start and end time, the revision (`HEAD` as a full hash, or none), whether the tree was dirty, and per command its name, text, exit code (an integer, negative when a signal ended it, or `timeout`, or `not started`), duration, result (`pass`, `fail` or `timeout`) and, for `not started`, the launch error text. Times are UTC, `YYYY-MM-DDTHH:MM:SSZ`. (S1, S3)
- **FR-009**: The record MUST NOT contain command output (NFR-002). (S1)
- **FR-010**: `verify` MUST print one summary line per command (name, result, duration), then one final line, exactly one of `verify: PASSED at <7-char hash> (clean tree)`, `verify: PASSED at <7-char hash> (dirty tree, not verified at HEAD)`, `verify: PASSED (no revision, not verified at HEAD)`, or the same three with `FAILED`. Two more last lines sit outside those six: `verify: NOTHING VERIFIED (no command configured)` (exit 2, FR-007) and `verify: record NOT written (<reason>); not verified` (printed after the results when the record can't be written, FR-006). A command's own summary line reads `pass`, `FAIL exit <n>`, `TIMEOUT after <n> s` or `NOT STARTED (<error>)`; for a failed command it MUST print the last 20 lines of that command's combined output, at most 2,000 characters. (S1)
- **FR-011**: The revision and the dirty state MUST be read before the first command and the dirty state again after the last; the record is dirty if either read was dirty (a `git status` that fails or times out counts as dirty), and has no revision if `HEAD` changed in between or there is no git repository or commit; `dirty` keeps its real value when `HEAD` moved. The dirty state ignores `.sdlc/evidence/`, so a first record does not make the next run dirty. A dirty or revision-less run MUST NOT be reported as verified at HEAD (final-line grammar in FR-010). (S3)
- **FR-012**: In a workspace, `verify --repo <name>` MUST use `repos.<name>.commands`, run from that repo's path, and write that repo's record; an unknown repo name is exit 2. (S4)
- **FR-013**: `verify` MUST work when `enforce` and `usage` are off, and MUST NOT write any file outside the project root (not even bytecode in the kit) except the commands' own side effects and one temporary output file in the operating system's temporary folder, which is removed before `verify` exits; a repo path from the config that leaves the project root is exit 2. (S1, S4)
- **FR-014**: The commands MUST come only from `.sdlc/config.json`; `verify` MUST NOT run a command taken from its arguments or the environment. (S1)
- **FR-015**: `sdlc-implement` (its final gate, informational because the tree is still dirty), `sdlc-debug` (its verification) and `sdlc-ship` (after the commit, before any push or PR) MUST tell the agent to run `sdlc verify` (with `--repo <repo>` in a workspace; with the tool's timeout raised or in the background, since a suite may take minutes) and quote its exact final line in the report, and to treat only a final line ending `(clean tree)` as verified at HEAD; `sdlc-review`, which is read-only, MUST tell the reviewer to read `.sdlc/evidence/verify.json`, quote its revision and result, and say when it is stale or absent. The constitution MUST carry one rule saying the same. (S4)

## Non-functional

- **NFR-001**: Python 3.9+ standard library only, no network, no prompts (the kit's constraints).
- **NFR-002**: The record is content-free: names, commands as configured, numbers, a revision and a launch error text, never command output.
- **NFR-003**: A failed write leaves the previous record unchanged.
- **NFR-004**: `verify` runs `git` a fixed number of times (at most four calls), independent of the repository's size.

## Success criteria

- **SC-001**: A red and a green fixture command give exit codes 1 and 0 and the matching record, and removing the record-writing or the exit-code logic makes at least one test fail — measured by unit tests plus a mutation check.
- **SC-002**: The record of any run contains no byte of command output — measured by a test that runs a command printing a marker string and searches the record.
- **SC-003**: A helper implementing the green-at-HEAD definition returns false for a record after a new commit, for a dirty record, for a revision-less record and for a record with a failed command, and true only for a clean, current, all-pass record, in 100% of test cases — measured by unit tests.
- **SC-004**: In a live eval (new row V1, n = 3 on two models) an agent told to finish a small fix and report runs `sdlc verify` and the exact final line appears in its report in at least 5 of 6 runs — measured from the transcripts.

## Assumptions & dependencies

- Assumption: a project's `commands` are the checks it wants run before "done"; an empty `integration` means none, not failure.
- Assumption: 600 seconds is enough for a project's whole test command; slower suites set `verify.timeout_seconds`.
- Assumption: `.sdlc/evidence/` is local state, not committed; the dirty check ignores it (plan).
- Assumption: a project ignores its own build and cache output (for example `.pytest_cache`, `__pycache__`, `dist/`); untracked, non-ignored files left by a command make the run dirty, and that is intended: the tree checked is not the tree committed.
- Dependency: ADR-0003 (accepted). Later: E1.3 reads this record; E1.4's hooks call E1.3.

## Clarifications

### Session 2026-11-04

- Q: Which stories does the epic's E1.2 cover → A: only the command and its record; reading it is E1.3 (roadmap).
- Q: How is a dirty tree treated → A: `verify` runs and records `dirty: true`; such a record is never green at HEAD (FR-011). Chosen by phong.ngo.vn in chat, 2026-11-04.

## Open questions

None.
