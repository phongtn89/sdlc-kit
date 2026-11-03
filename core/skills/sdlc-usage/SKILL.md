---
name: sdlc-usage
description: "Record the tokens and wall time a task, a bug or a fixed review finding took, into the record that owns it (a start mark, then one usage line), when the project turned usage metrics on in .sdlc/config.json. Other skills call it; use it by hand to measure a unit of work."
argument-hint: "start | stop <unit> --record <file>"
user-invocable: true
---

# sdlc-usage: what did this unit of work cost

## When to use

- Only when `.sdlc/config.json` has `"usage": {"enabled": true}`. Otherwise do nothing: no mark, no line, no question.
- `sdlc-implement` calls it for each task and each fixed review finding, and `sdlc-debug` for each bug. You can also run it by hand around any unit.
- It records numbers read from the Claude Code session transcript. It never reads or stores what was said.

## Inputs

- The script `usage.py` next to this file. From the **project root** (the folder that holds `.sdlc/`) run `python3 .claude/skills/sdlc-usage/usage.py`, or `python3 .github/skills/sdlc-usage/usage.py` when that is the only path that exists.
- The unit id: a task id (`T012`), a bug slug, or a review finding with its pass (`review1-F3`). Letters, digits, `-`, `_`, `.` only.
- The owning record, relative to the project root, and its section: a task or finding goes in the feature's `tasks.md`, section `Progress log` (the default); a bug goes in its bug record, `--section "Usage"`.

## Process

1. **Check the switch.** If `usage.enabled` is not `true` in `.sdlc/config.json`, stop here.
2. **Start**, before the first edit or command of the unit:
   `python3 .claude/skills/sdlc-usage/usage.py start <unit> --record <record> [--section <heading>]`
   It appends a hidden mark with the time and the session ID. Run it again in a later session when you resume the unit; it adds a mark for that session. Never edit or delete a `<!-- usage-start` or `<!-- usage-stop` line.
3. **Do the unit's work.**
4. **Stop**, after the unit's verify step passed and its evidence line is written, and after any sub-agents have finished:
   `python3 .claude/skills/sdlc-usage/usage.py stop <unit> --record <record> [--section <heading>]`
   It appends one line, for example `- usage T012: in 1,502 · cache-read 2,103,441 · cache-write 40,118 · out 18,004 · sub-agents 612,300 · 23 min wall · 41 turns · model claude-opus-5-5`.
5. **Read the result.** Say in your report what the line shows. A figure that reads `not available (<reason>)` is not zero: report the reason and do not fill it in. `already started`, `already closed` and `usage off` mean nothing was written.
6. **Overlap.** Run one unit at a time. If the line ends `OVERLAP: <unit>`, its figures include that other unit's work; say so.

## Rationalizations

| Excuse | Reality |
|---|---|
| "I'll estimate the tokens" | Never. The script reads them. If it says not available, the answer is not available. |
| "Skip the start, I'll stop later" | A stop with no start mark writes `not available (no start mark)`. The mark is the only start. |
| "Edit the mark's time, the work began earlier" | The window decides what is counted. A changed mark changes the numbers silently. Start a new unit instead. |
| "Run it for every small step" | A unit is a task, a bug or a finding. Smaller steps overlap and double count. |

## Red flags

- The switch is off but you were about to run the script.
- The usage line is missing after the unit closed: the stop did not run. Run it, do not write the line by hand.
- A line says `0` for something that cannot be zero. Report it as a defect in the script.

## Verification

- With the switch on, the unit's record holds one start mark and one `- usage <unit>:` line, and your report quotes that line.
- With the switch off, the record has no mark and no usage line.

## Principles applied

evidence-over-claims, fail-safe-keep-work
