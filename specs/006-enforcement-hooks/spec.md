# Spec: Enforcement hooks for Claude Code

Feature: enforcement-hooks
Number: 006
Status: draft <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: one-line reason). sdlc-analyze sets approved; sdlc-ship sets implemented; rejected records a feature that was built or evaluated and deliberately not adopted. -->
Approved: <!-- written by `sdlc gate approve --by <name>`: name, YYYY-MM-DD, digest sha256:<64 hex> (spec, plan, tasks, contracts prefixes) -->
Owner: phong.ngo.vn
Created: 2026-11-05
Track: T3

<!-- Roadmap story E1.4 (docs/roadmap/layers-plan.md); ADR-0003 (docs/adr/0003-enforcement-model.md), ladder level 3. Acts on the commands of specs 004 (`verify`) and 005 (`gate`). The CI recipe is E1.5 and the "must never happen" test set is E1.7; neither is in this spec. -->

## Intent

**Problem:** The gates of specs 004 and 005 only report. An agent that does not run them, or runs them and goes on regardless, can still push red code, edit source on a T3 feature nobody approved, or tick tasks with nothing behind them. ADR-0003 puts a host hook at level 3 of the ladder for exactly these three rules.

**Who:** Claude Code users who opt in to enforcement; maintainers who need the rules to hold when an agent's context is long and its prose rules have faded.

**Why now:** ADR-0003 is accepted, and the commands the hooks need (`verify`, `gate green-at-head`, `gate approved`, `gate evidence-for-ticks`) exist since E1.2 and E1.3.

## Out of scope

- Copilot: it has no equivalent hook. The kit renders nothing for it and says so; CI (E1.5) is its floor.
- Source edits made through the shell (redirects, `sed -i`, scripts). The hook watches the editor tools only; this is a known gap, stated in the docs, and closing it is not a v1 goal.
- Merges to the default branch (branch protection, level 6), weakened tests, secrets, untrusted ticket text, remediation-loop caps (ADR-0003 "out of v1").
- Authenticating who runs a command or the approver's name (as specs 004 and 005).
- Turning `enforce` on by default.
- Hosts and hook events other than Claude Code's tool-call and stop events.
- Workspaces (a config with `repos`): v1 renders no hook there and says so; the gates take `--repo`, and mapping a tool call to a repo is later work.
- Judging which repository a `git -C <dir> push` targets: the check always runs on the project root.

## Glossary terms used

- **Enforcement**: the `enforce` switch in `.sdlc/config.json`; only the JSON value `true` turns it on (ADR-0003).
- **Managed hook entry**: a hook entry the kit wrote into `.claude/settings.json`, recognisable as the kit's, so install, update and uninstall touch those and nothing else.
- **Active spec**: the T3 feature whose folder the hook treats as the one being worked on: the one whose number starts the current branch name.
- **Source tree**: the files an unapproved feature must not yet change: every file except those under `spec_dir`, `.sdlc/`, `.claude/`, `.github/`, `docs/`, and files ending `.md`.
- **Green at HEAD**, **approval digest**, **evidence for a tick**: as defined by specs 004 and 005.

## User scenarios

### S1: A push or PR on red is refused (P1)

As a maintainer, I want the host to refuse `git push` and `gh pr create` unless the last `verify` is green at the current HEAD, so that nobody ships code whose tests did not run.

**Independent test:** with a hook input naming a push, the hook prints the deny message (exit 0) when `gate green-at-head` fails, including when there is no record, and prints nothing when it passes.

1. **Given** `enforce` is on and no green record exists for HEAD, **When** the agent runs `git push` or `gh pr create`, **Then** the call is refused and the message says to run `sdlc verify` and quote its last line.
2. **Given** a green record at HEAD and a clean tree, **When** the same command runs, **Then** it is allowed.
3. **Given** a command that chains a push after other commands, or names `git -C <dir> push`, **When** it runs, **Then** it is checked the same way.
4. **Given** any other command (including `git status`, `git commit`, `git push --help`), **When** it runs, **Then** the hook allows it without running the gate.

### S2: Source edits wait for an approved spec (P1)

As a maintainer, I want edits to source files blocked while the feature's spec, plan and tasks are not approved, so that a T3 feature is not implemented on documents nobody agreed to.

**Independent test:** a hook input editing a source file is refused when `gate approved` fails for the active spec, allowed when it passes, and allowed when no active spec can be determined.

1. **Given** `enforce` is on and the active spec is draft or its digest does not match, **When** the agent edits or writes a source file, **Then** the call is refused and the message names the gate's reason.
2. **Given** the active spec passes `gate approved`, **When** the agent edits source, **Then** it is allowed.
3. **Given** the file is a spec, plan, task, contract, doc or kit file (not source), **When** it is edited, **Then** it is always allowed (the agent must be able to write the documents that get approved).
4. **Given** no active spec can be determined, **When** the agent edits anything, **Then** it is allowed: the hook blocks only on a computed result, never on a guess.

### S3: Install renders the hooks, opt-in, without harming the project's settings (P1)

As a user, I want the hooks installed only when I turn `enforce` on, merged into my existing `.claude/settings.json`, and removed cleanly, so that I can adopt and drop enforcement safely.

**Independent test:** a fixture project with its own settings and hooks gains the three entries on install, keeps every one of its own, and loses only the kit's on `enforce: false` or uninstall.

1. **Given** `enforce` is absent or not `true`, **When** I install or update, **Then** no hook is written and any hook the kit wrote earlier is removed.
2. **Given** `enforce` is true and a `.claude/settings.json` with the project's own settings and hooks, **When** I install or update, **Then** the three kit hooks are added, no other value in the file changes (formatting may be normalised on the first write), and running install again changes nothing.
3. **Given** the file is not valid JSON or its `hooks` value has an unexpected shape, **When** I install, **Then** nothing in it is written, the report says why, and the exit code is non-zero.
4. **Given** the kit's entries were edited by hand, **When** I update, **Then** they are reported as modified and left alone unless `--force`; `sdlc check` reports the drift.
5. **Given** the hooks are installed, **When** I uninstall, **Then** only the kit's entries go, and an emptied file the kit created is removed.
6. **Given** the targets do not include Claude Code, **When** I install with `enforce` on, **Then** the report says Copilot has no hook equivalent and CI is its floor.

### S4: Unevidenced ticks are flagged when the agent stops (P2)

As a reader of `tasks.md`, I want a warning when a session ends with ticked tasks that have no evidence, so that a tick without a commit does not pass silently.

**Independent test:** a Stop input with a failing `gate evidence-for-ticks` for the active spec produces a warning and exit 0; a passing or undeterminable one produces nothing.

1. **Given** the active spec has a ticked task with no evidence line, **When** the session stops, **Then** the user sees a warning that lists the tasks, and the session is not blocked.
2. **Given** the evidence is complete, no active spec can be determined, or the active spec has no `tasks.md` yet, **When** the session stops, **Then** nothing is shown. (The stop hook fires every turn, so it stays silent unless it has a computed warning.)

### S5: A broken hook never traps the session (P1)

As a user, I want the hooks to fail open on their own faults and fail closed only on a gate's computed answer, so that a bug in the kit cannot lock me out.

1. **Given** the kit path in the lock no longer exists, the hook input is malformed, or the gate itself errors, **When** a hook runs, **Then** the call is allowed, a one-line reason is written for the user, and `sdlc check` reports the missing kit path.

## Requirements

- **FR-001**: Installing or updating with `enforce` equal to JSON `true` and a Claude Code target MUST add three hook entries to `.claude/settings.json`: a tool-call hook for `Bash`, a tool-call hook for the editor tools (`Edit`, `Write`, `MultiEdit`, `NotebookEdit`), and a stop hook. (S3)
- **FR-002**: Any other `enforce` value, or a missing key, MUST add no entry and MUST remove entries the kit wrote earlier; and a hook that finds `enforce` not equal to `true` at run time MUST allow silently, so turning it off takes effect before the next update. (S3)
- **FR-003**: The kit MUST NOT change any value in `.claude/settings.json` other than its own entries, MUST keep the project's own hooks on the same events, MUST keep the file's indentation, and MUST produce identical bytes when run twice. (S3)
- **FR-004**: The kit MUST NOT write the file when it is not valid JSON or has a shape it cannot merge into; it MUST report why and exit non-zero. (S3)
- **FR-005**: The lock MUST record a hash of what the kit wrote into the settings file, `sdlc check` MUST report a change to the kit's entries as drift, and update MUST NOT overwrite a changed entry without `--force`. (S3)
- **FR-006**: Uninstall MUST remove exactly the kit's entries and a settings file the kit created that is then empty. (S3)
- **FR-007**: Each hook MUST call the kit by the path recorded in `.sdlc/lock.json`, never a copy inside the project (ADR-0003 decision 3). (S1, S2)
- **FR-008**: The Bash hook MUST refuse a command that runs `git push` or `gh pr create`, alone or inside a chain, whenever `sdlc gate green-at-head` does not pass, and MUST show the gate's reason. It MUST allow every other command without running a gate. (S1)
- **FR-009**: The editor hook MUST refuse an edit to a source file whenever the active spec's status word is `draft` or `approved` and `sdlc gate approved` does not pass, showing the gate's reason, and MUST always allow edits to non-source files and edits while the active spec has any other status (`implemented`, `rejected`, `superseded`, missing or unknown: no feature is known to be in flight; an unknown status allows with a note). (S2)
- **FR-010**: The stop hook MUST warn, never block, when `sdlc gate evidence-for-ticks` fails for the active spec, listing the failing tasks. (S4)
- **FR-011**: A hook MUST allow the call when it cannot compute a gate result: unreadable input, a missing kit (the entry prints one line saying so), no active spec, a gate error (exit 2), or a timeout. It MUST say why in one line. A gate that completes and fails (exit 1) is the only thing that refuses. The entry MUST end with exit code 0 whatever the kit does, so a kit that is missing, older, newer or broken cannot block the host; a refusal is a structured deny message the host reads on a zero exit. (S5)
- **FR-012**: A hook MUST finish within a fixed time limit set on its entry, and MUST NOT write to the project's files. (S5)
- **FR-013**: With a Copilot-only target, install MUST render no hook and MUST state that no equivalent exists. (S3)
- **FR-014**: The documentation MUST list what the hooks do not cover (shell edits, other hosts, and that the config, lock, evidence record and settings file are editable by an agent's editor tools) and how to turn enforcement off, that hooks are read when a session starts (restart after install or update), that `sdlc verify` and the push must be separate tool calls, and that the kit's evidence record and lock are not protected from an agent's editor tools. (S3)
- **FR-015**: With a workspace config (`repos` present) install MUST render no hook and MUST say that workspaces are not supported yet. (S3)
- **FR-016**: When `enforce` is on and `commands` in the config is empty, install MUST say that a push can never pass until commands are configured, and the push refusal MUST say so too. (S1, S3)

## Non-functional

- **NFR-001**: Python 3.9+ standard library only, no network, no new dependency (ADR-0002).
- **NFR-002**: A hook that allows without running a gate adds under 200 ms on a typical machine; a hook that runs a gate adds no more than the gate itself.
- **NFR-003**: Hook inputs and outputs follow the host's documented format; the formats are pinned as fixtures and re-checked by a row in the evals, as the usage metric's are.

## Success criteria

- **SC-001**: For each of the three rules, a test that feeds the hook a realistic input fails when the hook (or its rendering) is removed or disabled — measured by mutation checks, 3 of 3 (the full set is E1.7).
- **SC-002**: A fixture project with its own settings keeps 100% of its own values across install, update, `enforce` off and uninstall — measured by comparing the parsed file outside the kit's entries.
- **SC-003**: In a live Claude Code session in a scratch project with `enforce` on, a push on red is refused and a push on green is allowed — measured by a recorded eval, 1 of 1 each way, in the manner of spec 004's V1.

## Assumptions & dependencies

- Assumption: the host reads hook entries when a session starts, so install and update need a restart to take effect (unverified; stated in the docs).
- Assumption: the host passes the tool name and input to a tool-call hook as JSON on standard input and treats a zero exit with a structured deny message (`permissionDecision` `deny` and a reason) as a refusal shown to the agent; a stop hook that exits 0 with a JSON `systemMessage` shows a warning without blocking. These are the host's, not the kit's: they are pinned by fixtures (NFR-003) and proven by the live eval (SC-003).
- Assumption: a hook entry may carry a time limit that the host enforces (FR-012), and the host treats any exit code other than 2 as non-blocking, so a crash or a missing interpreter allows the call.
- Assumption: the editor tools are the ones that carry a file path for source edits; shell-based edits are the stated gap.
- Assumption: a refusal is surfaced to the agent as a tool error, which it can act on by running `verify` or getting an approval.
- Dependency: specs 004 and 005 (`verify`, `gate`), ADR-0003, and the install/lock machinery in `bin/sdlc`.

## Clarifications

<!-- Written by `sdlc-clarify`. -->

### Session 2026-11-05

- Q: Which files count as the source tree? → A: every file except those under `spec_dir`, `.sdlc/`, `.claude/`, `.github/`, `docs/`, and files ending `.md`. No configuration in v1.
- Q: How is the active spec found? → A: the current branch name starts with a spec number (as in `feat/006-...`) that matches a folder in `spec_dir`; otherwise there is none and the hook allows. No config key in v1.

## Open questions

None.
