# Spec: Usage metrics per resolved unit

Feature: usage-metrics
Number: 003
Status: implemented <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: one-line reason). sdlc-analyze sets approved; sdlc-ship sets implemented; rejected records a feature that was built or evaluated and deliberately not adopted. -->
Approved: phong.ngo.vn, 2026-11-03 (H1, in chat: plan, P4/P5, review-findings-only scope, decision-7 order departure) <!-- name, YYYY-MM-DD; filled when approved -->
Owner: phong.ngo.vn
Created: 2026-11-03
Track: T3

<!-- Source of the decisions: pilot workspace, .sdlc/decisions/2026-10-30-usage-metrics.md (sdlc-grill, play-back confirmed by phong.ngo.vn 2026-10-30; not yet committed in pilot: cite its revision once it is). Decision 7 of that record sets the order: spec 002's analyze findings are fixed first, then this spec is built, then spec 002 is implemented, so its build tasks are measured. -->

## Intent

**Problem:** The kit records no token or time figures for agentic work. Today the only per-task trace is one progress-log line with a command and its result (`core/skills/sdlc-implement/SKILL.md:33`, "Append to the *Progress log*: the task ID, the command and its result"; the log's template line is `core/templates/tasks.md:50-54`). A bug record has no usage field (`core/templates/bug.md:30-44`, sections Fix, Regression test, Siblings checked) and a fixed review finding has no record of its own beyond a report row (`core/templates/review-report.md:19-25`). The pilot handoff of 2026-10-27 noted that tokens and cost are recorded nowhere for the team's agentic work.

**Who:** Maintainers and teams who run sdlc tracks and want to see what a task, a bug or a finding fix cost in tokens and time, and the owners of later retro views.

**Why now:** The Claude target already writes the numbers locally: every model turn in the session transcript carries token usage and every event a timestamp, and sub-agents write their own transcripts (decision record, Context). The order in the decision record (decision 7: build this spec first, then implement spec 002, so that its build tasks are measured) was not kept: spec 002 was implemented and merged first, on the user's instruction of 2026-11-03. What this spec can still measure is spec 002's evaluation tasks and every feature built after it. Nothing needs to be built on a service; a switch and one script with the core skills are enough.

## Out of scope

- Cost in money. Derivable later from any price table without changing records (decision, Deferred).
- Totals across units, or a retro view. Wanted after units carry lines (decision, Deferred).
- Copilot usage. Only if Copilot exposes per-session usage locally (decision, Deferred); until then it reports "not available".
- A central log or dashboard. Each figure lives in the record that owns the unit.
- Per-unit-type switches. One switch only.
- Hooks or any background collection. The kit renders no hooks (`bin/sdlc` contains no `hooks` or `settings.json`, checked 2026-11-03), and this feature adds none.
- Reading or storing what was said in a session. Only usage numbers, timestamps, the model name and the turn count are read.
- Units other than a task, a bug and a fixed review finding (for example a whole spec or a whole session). In particular a fix to an **analyze** finding is not measured: it is a document edit made in specify, plan or tasks, which this spec does not instrument. (This narrows the decision record, which said "review or analyze finding"; approval at H1.)

## Glossary terms used

- **Resolved unit**: the thing a usage line describes. One of: a **task** (a task in a feature's task list), a **bug** (an investigated bug, closed by `sdlc-debug`), a **finding** (a review finding that was fixed). New.
- **Owning record**: the document that already owns a unit: the task list's progress log for a task, the bug record for a bug, the fix note for a finding. New.
- **Finding fix**: the work of fixing one **review** finding through `sdlc-implement`. Its unit id is `<pass>-<finding id>` (for example `review1-F3`). Its owning record is the Progress log of its feature's `tasks.md`, where `sdlc-implement` writes the finding's one-line text as the evidence bullet before the stop; the independent review report stays untouched. New.
- **Start mark**: a record in the owning record of the time and the session ID at which work on a unit began or resumed. New.
- **Segment**: the span from one start mark to the next stop, or to the end of that session; a unit has one segment per session it was worked in. New.
- **Usage line**: the line, in one shared format, that gives a unit's figures. It is a bullet of its own in the owning record, written by the stop command. A figure is `0` only when the source was read and held nothing for it, and `not available (<reason>)` otherwise. New.
- **Usage switch**: the one setting in `.sdlc/config.json` that turns the feature on. New.
- **Wall time**: elapsed clock time from the start mark to the stop, summed over segments, including time spent waiting for the user. It is not compute time and the line says "wall". New.
- **Sub-agent usage**: the token usage of sub-agents that ran inside a segment, reported apart from the main session. New.
- **Not available**: the stated result when a figure cannot be found, always with a reason, and never written as 0. New.

## User scenarios

### S1: Measure a task from start to finish (P1)

As a maintainer with usage metrics on, I want each task's tokens and time to be recorded where its result is recorded, so that I can see what a task cost without any separate tooling.

**Independent test:** In a test repo with the switch on and a recorded Claude transcript fixture, run the start command for a task, then the stop command, and read the task's progress-log line. Compare each figure with the sum computed independently from the fixture.

1. **Given** the switch is on, **When** `sdlc-implement` begins a task, **Then** it runs the named start command, and the progress log holds a start mark with the time and session ID.
2. **Given** a task with a start mark, **When** the task is ticked and the named stop command runs, **Then** the progress log holds a usage line for the task (a bullet of its own) with the four token fields (uncached input, cache-read, cache-write, output), sub-agent usage, wall time, turns and model.
3. **Given** a task worked over two sessions (start, handoff, resume), **When** the resumed work begins, **Then** a new start mark is written for the new session, and the stop adds the two segments together into one usage line.
4. **Given** sub-agents ran inside a segment, **When** the stop command runs, **Then** their usage appears as a separate "sub-agents" figure and is not added to the main-session token fields.

### S2: Say "not available" instead of 0 (P1)

As a reader of a usage line, I want a missing figure to say so and why, so that I never read 0 as a measurement.

**Independent test:** Run the stop command against fixtures with no transcript, a session ID that matches no file, and an unsupported target. Check every output.

1. **Given** the target is Copilot, which leaves no comparable transcript, **When** the stop command runs, **Then** the usage line says "not available" with the reason "no transcript on this target", and no figure is 0.
2. **Given** a start mark whose session transcript cannot be found, **When** the stop command runs, **Then** the line says "not available" with the reason "transcript not found".
3. **Given** a unit with no start mark, **When** the stop command runs, **Then** the line says "not available" with the reason "no start mark", and the stop does not guess a start.
4. **Given** one segment of several is unavailable, **When** the stop command runs, **Then** the line reports the figures of the segments it found, names the segment that is missing and why, and marks the totals as partial.

### S3: Turn it on and off with one switch (P1)

As a maintainer, I want the feature off by default and one setting to turn it on, so that no install collects or asks for anything I didn't choose.

**Independent test:** Install the kit with no usage setting and with the setting on; compare installed files, run the skills' start and stop steps in both, and read the records.

1. **Given** no usage setting, or the switch set off, **When** any skill runs, **Then** no skill asks for a start mark or a stop, and no usage line or mark is written.
2. **Given** a kit install made before this feature, **When** it is updated to a kit with this feature and the switch stays unset, **Then** the install behaves exactly as before, and its managed files differ only by the files this feature ships as part of core.
3. **Given** the switch is set on, **When** a skill that resolves a unit runs, **Then** it asks for the start mark and the stop by the named commands.
4. **Given** the switch is on and the script is run by hand, **When** it is asked for a unit's figures, **Then** it works the same whether or not a skill started it.

### S4: Measure a bug and a fixed finding (P2)

As a maintainer, I want bugs and fixed review findings to carry the same usage line, so that all three kinds of work are comparable.

**Independent test:** With the switch on, run `sdlc-debug` on a fixture bug and apply one fix for a review finding; read the bug record and the fix note.

1. **Given** the switch is on and `sdlc-debug` starts work on a bug, **When** it closes the bug, **Then** the bug record holds a usage line in the same format as a task's.
2. **Given** the switch is on and a review finding is fixed, **When** its fix note is written, **Then** the note carries a usage line in the same format.
3. **Given** a bug or finding that the user abandons before it is closed, **When** no stop runs, **Then** the start mark stays in the record and no usage line is written; nothing is invented for it.

### S5: Keep transcript content private (P1)

As a user of the kit, I want the figures taken without anything I wrote or the agent said being copied, so that turning this on adds no new place where content is stored.

**Independent test:** Run the stop command on a fixture transcript whose message text contains a unique sentinel string. Search every output and every file the run wrote for the sentinel.

1. **Given** a transcript whose messages contain a sentinel, **When** the stop command runs, **Then** the sentinel appears in no output and no written record.
2. **Given** a transcript with unreadable or malformed message content but valid usage and timestamps, **When** the stop command runs, **Then** the figures are still produced, because content is never needed.

## Requirements

- **FR-001**: The feature MUST be opt-in, controlled by one usage switch in `.sdlc/config.json`, off when the setting is absent. (S3)
- **FR-002**: With the switch off or absent, no skill MUST ask for a start mark or a stop, nothing MUST write a usage line or mark, and installed files and behaviour MUST be identical to a kit without the feature, apart from the files the feature ships or edits (listed in the plan's Seams). (S3)
- **FR-003**: With the switch on, the skills that resolve a unit (`sdlc-implement` for a task, `sdlc-debug` for a bug, and `sdlc-implement` again for a fixed review finding) MUST record usage for that unit. (S1, S4)
- **FR-004**: A usage line MUST be written in the owning record of the unit: a task and a finding in the Progress log of their feature's `tasks.md`, a bug in a `## Usage` section of its bug record. There MUST be no central log. (S1, S4)
- **FR-005**: All three units MUST use one shared usage-line format. (S1, S4)
- **FR-006**: Recording MUST be a named start command run at the start of the unit, and a named stop command run at its end. The skill text MUST give each command's exact name and arguments; a prose rule without a named command MUST NOT be the means of recording (spec 001 retro lesson L1, `specs/001-dense-agent-protocol/retro.md:27`). (S1, S4)
- **FR-007**: The start command MUST write a start mark holding the time and the session ID into the owning record. (S1)
- **FR-008**: When a unit is resumed in another session, the start command MUST write a new start mark for that session, and the stop command MUST add up every segment of the unit. (S1)
- **FR-009**: The usage line MUST show, as separate fields: uncached input tokens, cache-read tokens, cache-write tokens, output tokens, sub-agent usage, wall time labelled "wall", turns, and model. It MUST NOT show a cost and MUST NOT merge the token fields into one total. (S1)
- **FR-010**: Sub-agent usage MUST be found from the sub-agents' own transcripts (`<session-id>/subagents/agent-<id>.jsonl`) by matching their timestamps to the segment, and MUST be reported apart from the main session's token fields. (S1)
- **FR-011**: Wall time MUST be the clock time from start mark to stop, summed over segments, and MUST be labelled "wall" in the line. (S1)
- **FR-012**: A figure that cannot be found MUST be written as "not available" with a reason, and MUST NOT be written as 0. This includes the whole line on a target with no comparable transcript (today Copilot), a missing transcript, and a missing start mark. (S2) A figure is written as `0` only when the source was read and held nothing for it: a segment with no sub-agent transcript files has `sub-agents 0`, and uncached input can be 0. Whether a source was read is stated by the contract, not guessed. (S2)
- **FR-013**: When some segments of a unit are found and others are not, the line MUST give the figures found, name each missing segment with its reason, and mark the totals as partial. (S2)
- **FR-014**: The script MUST NOT copy, print, write or keep message content, tool input or tool output. It parses each transcript record only to take usage numbers, timestamps, the model name, the message id and the type, and drops the record. (S5)
- **FR-015**: The usage switch, the script and the skill changes MUST ship as core: the switch is read from `.sdlc/config.json`, and the script is installed with the core skills, not as a module. (S3)
- **FR-016**: With the switch on, a unit that is abandoned (a start mark but no stop) MUST leave only its start mark; the stop command MUST NOT be needed to keep the record valid. (S4)
- **FR-017**: The start and stop commands MUST be safe to run twice for the same unit state: a second stop on an already-closed unit MUST NOT change its usage line, and a second start in the same session for a unit with an open start mark MUST NOT add a duplicate mark. (S1)
- **FR-018**: The kit's lint and drift checks MUST keep passing with the feature installed, with the switch on and off. (S3)
- **FR-019**: The script MUST count each model response once: a transcript writes one response as several records, so records MUST be de-duplicated by `message.id`, keeping the last one, before summing (ADR-0002: a naive sum overcounted output by 43% and cache writes by 80% on a measured run). The last record's timestamp places the response in a window. (S1)
- **FR-020**: When a counted transcript record (an `assistant` record with `message.usage`) lacks `message.id`, a parseable timestamp or one of the four usage counters as an integer, the script MUST report the affected figures as "not available" with the reason "unexpected transcript format" and MUST NOT guess or write 0. Other record types are ignored. An unparsable last line is skipped (the file may be mid-write); any other unparsable line makes the segment's figures "unexpected transcript format". When no response from a non-synthetic model falls in a window, the figures are "not available" with the reason "no response in window". (S2)
- **FR-021**: When another unit in the same record has a start mark in the same session inside a unit's window, the unit's line MUST end with `· OVERLAP: <unit>` (several units, comma-separated; units in other records are not seen), because the figures then include the other unit's work. With the switch on, `sdlc-implement` MUST run `[P]` tasks one after another. (S1)
- **FR-022**: A unit is **closed** when its usage line holds at least one token, sub-agent or turn figure. A `stop` on a closed unit MUST NOT change anything. A line without a token, sub-agent or turn figure does not close the unit: the next `stop` replaces it. A unit is matched by its exact id within its section (`T01` never matches `T012`). Rework after a stop is measured as a new unit id (for example `T012-r2`). (S1)

## Non-functional

- **NFR-001** (privacy): The script MUST NOT write, log or print any transcript content, and MUST send nothing anywhere: no network access, no upload. The only things it stores are the figures and marks in the owning records. Yes/no, tested with a sentinel in a fixture transcript and a run with network access blocked. (S5)
- **NFR-002** (offline, non-interactive): Start and stop MUST run offline and without prompts, so an unattended agent session can run them. Yes/no, tested with no network and no terminal input. (S1, S3)
- **NFR-003** (data kept local): The only source read is the session transcripts under `$CLAUDE_CONFIG_DIR` or the user's `~/.claude`, found from the session ID the running session exposes; the kit MUST NOT copy those transcripts. (S5)
- **NFR-004** (containment): The record to write MUST resolve inside the project root (no `..`, no symlink out) and exist; the unit id MUST use letters, digits, `-`, `_` and `.` only; a session ID is used to find a file only if it is hex digits and `-` (from the environment or from a mark; anything else is treated as unknown). A bad argument, record or unit id exits with a usage error and writes nothing. (S5)
- Performance, availability and accessibility: not applicable (a one-shot local command per unit; no runtime service or UI).

## Success criteria

No criterion is a measured threshold, so no value gate is needed for the plan (`core/templates/plan.md:86` asks for one only when an SC is a measured threshold).

- **SC-001**: With the switch on, 100% of closed units in the test run (task, bug and finding) carry a usage line in the shared format. Measured by running the skills' recording steps on fixtures and counting lines.
- **SC-002**: Every token, sub-agent, turn and wall-time figure in a usage line equals the value computed independently from the fixture transcripts, for single-segment, multi-segment and sub-agent fixtures, including a fixture with duplicated records for one response. Exact match, measured by test.
- **SC-003**: In 100% of no-data fixtures (no transcript, Copilot target, missing start mark, partial segments) the line says "not available" with a reason, and no figure is written as 0. Measured by test.
- **SC-004**: With the switch off or absent, the files of an install equal those of a kit without the feature, except the files shipped or edited by this feature (plan, Seams), and no skill run produces a mark or a usage line. Measured by the kit's drift check and a run of each skill. (As spec 002 SC-006.)
- **SC-005**: A sentinel string in a fixture transcript appears in 0 outputs and 0 written records after a stop. Measured by search after the run.
- **SC-006**: Start and stop complete with no network and no input in 100% of test runs. Measured by running the tests with network access blocked and standard input closed.
- **SC-007**: In 100% of skill texts that ask for a mark or a stop (`sdlc-implement`, `sdlc-debug`), the exact command is named (no prose-only rule). Measured by a read of the skill text, and by an unnamed-prompt evaluation row per use (a task, a bug, a finding), following retro lesson L1.
- **SC-008** (reported, not a gate): once a feature is built with the switch on (spec 002's evaluation tasks, or the next feature), the share of its tasks that carry a usage line. Reported at that feature's retro, so a skipped step can be told apart from a missing figure.
- **SC-009**: On a recorded real `claude -p` run with a sub-agent, with a window that spans the whole run, the four main-session token fields equal the CLI's `result.usage`, and the usage line's main fields plus its sub-agent figure equal the sum of `modelUsage` over the four fields. Exact match against a pinned fixture; re-checked when Claude Code's major version changes (ADR-0002).

## Assumptions & dependencies

- Technique: chosen in [ADR-0002](../../docs/adr/0002-usage-metric-technique.md) (2026-11-03) after comparing transcript parsing, hooks and native OpenTelemetry on a measured run: transcripts de-duplicated by `message.id`, between start and stop marks; hooks and OpenTelemetry not required.
- Assumption: the Claude target exposes the session ID to the running session as `CLAUDE_CODE_SESSION_ID` (set in a measured desktop session, but not listed in the env-var docs; hooks and the status line document `session_id`, so the plan must say what the start command does when the variable is absent), and writes the transcript to `~/.claude/projects/<encoded folder>/<session-id>.jsonl` with usage on every model turn and a timestamp on every event; sub-agents write `<session-id>/subagents/agent-<id>.jsonl` (verified 2026-10-30, decision record Context). If the layout changes, token figures become "not available" where a file is missing or malformed; a moved `subagents/` folder would read as zero sub-agents, a residual limit the live check watches (contract, Known limits); the plan should add a fixture-based check so a change is noticed.
- Assumption: the Copilot target has no comparable transcript, so every usage line there is "not available".
- Assumption: units are worked one at a time within a session. Overlap is detected and flagged (FR-021), not separated.
- Assumption: "turns" counts the distinct main-session model responses with usage in the window; sub-agent responses are not added to it.
- Assumption: when a unit's segments used more than one model, the line lists each distinct model rather than one.
- Assumption: wall time includes time waiting for the user (decision record, Defaults); the label "wall" tells the reader.
- Assumption: review-finding fixes run through `sdlc-implement`, and review findings are numbered per pass, so the unit id carries the pass (`review1-F3`); `sdlc-implement` gains the finding step in this spec.
- Dependency: `.sdlc/config.json` exists in an installed project (the kit creates it); `usage.py` reads the `usage` key itself, as `bin/sdlc` reads `spec_dir` (`bin/sdlc:511-512`).
- Dependency: the kit's install and drift check, to show the switch-off install is unchanged (SC-004).
- Dependency: spec 002's analyze findings are fixed before this spec is planned (decision 7); no content dependency on spec 002.

## Clarifications

### Session 2026-10-30

- Q: Which units, and where do the figures live? → A: A task, a bug and a fixed review or analyze finding, each in the record that owns it, one shared line format. Tasks-only and one central log: rejected.
- Q: When does a unit start and end? → A: An explicit start mark, then a stop, both as named commands. A resumed unit gets a new mark in the new session and the stop adds all segments. "From the previous closed unit" and "whole sessions": rejected.
- Q: On or off by default? → A: Off, with one switch in `.sdlc/config.json`. Per-unit-type switches: rejected.
- Q: Which fields? → A: Four token fields separately, sub-agent usage separately, wall time, turns, model; no cost. A single total and an estimated cost: rejected.
- Q: What when there is no data? → A: "not available" with a reason, never 0.
- Q: Where does it live? → A: Core (switch plus one script with the core skills); a module was rejected.
- Q: In what order with spec 002? → A: Fix 002's analyze findings, then spec and build 003, then implement 002 so its tasks are measured.

### Session 2026-11-03 (technique research, after spec writing)

- Q: Which technique reads the figures? → A: Session transcripts, de-duplicated by `message.id`, between start and stop marks (ADR-0002). Measured exact against the CLI's own result on one run with a sub-agent. Hooks (no usage fields, no unit boundary), native OpenTelemetry (not enabled per project, nothing printed in the console test) and headless-per-unit runs: not chosen.
- Q: Does the transcript's usage mean what it says? → A: Yes on the measured run: input and output tokens equal the CLI's figures; the community claim that they are placeholders did not hold. Records are duplicated per response, hence FR-019.

### Session 2026-11-03 (spec writing; no change to the decisions above)

- Q: What is a "fix note" for a finding, since the kit has none? → A: The line in the owning record that says a finding was fixed; this spec requires it carry the usage line, and the plan chooses its home (Assumptions).
- Q: What if a unit is started but never stopped? → A: Only the start mark stays; no line is invented (FR-016).
- Q: Is the privacy limit tested or only promised? → A: Tested with a sentinel in a fixture transcript (SC-005).

## Open questions

None. Every choice that shapes scope, units, defaults and privacy was settled in the decision record; remaining design choices (script location, command names, line position for findings) belong to the plan.
