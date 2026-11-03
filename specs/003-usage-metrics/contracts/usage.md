# Contract: `usage.py` and the usage line

Spec 003 (FR-005–FR-013, FR-016, FR-017, FR-019–FR-022, NFR-001–NFR-004). Technique: ADR-0002.

## Call

```text
python3 .claude/skills/sdlc-usage/usage.py start <unit> --record <file> [--section <heading>]
python3 .claude/skills/sdlc-usage/usage.py stop  <unit> --record <file> [--section <heading>] [--at <timestamp>]
```

- Skills run the command **from the project root** (the folder that holds `.sdlc/`), using `.github/skills/sdlc-usage/usage.py` when that is the only path that exists (Copilot-only install).
- `<unit>`: a task id (`T012`), a bug slug, or a review finding id with its pass (`review1-F3`). Letters, digits, `-`, `_`, `.` only, starting with a letter or digit.
- `--record`: the owning record, **relative to the project root**: `specs/003-usage-metrics/tasks.md`; in a workspace, `<repo>/specs/<NNN-slug>/tasks.md`. The file must exist (a missing file is exit 2; the skill creates a bug record from the template first). `--section` (default `Progress log`): the `##` heading whose end receives marks and lines; created at the end of the file when absent. A bug uses `--section "Usage"`.
- `--at` (optional, `stop` only): the stop time as a mark timestamp, for a backfilled stop and for tests. Default: now.
- **Project root:** the folder holding the nearest `.sdlc/config.json`, found by walking up from the current directory. In a workspace that is the workspace folder (the kit never writes a child repo's config); only that file's switch counts. No `.sdlc/config.json` found means off.

## Switch

`.sdlc/config.json` → `"usage": {"enabled": true}`. **Only the JSON value `true` is on.** Absent, `false`, a string, `"usage": true`, or invalid JSON is off. Off: both commands print `usage off` and exit 0 without reading a transcript or writing a file. Skills check the switch before calling (the constitution already has them read `.sdlc/config.json` at the start of a track), so an off install adds no call to the script.

## Marks and lines (written at the end of `<section>`)

```text
<!-- usage-start T012 2026-11-03T10:00:00.123Z session=0b8b2d7f-d1c8-4d58-86d4-eb8b0ad184f6 -->
- usage T012: in 1,502 · cache-read 2,103,441 · cache-write 40,118 · out 18,004 · sub-agents 612,300 · 23 min wall · 41 turns · model claude-opus-5-5
<!-- usage-stop T012 2026-11-03T10:23:07.456Z -->
```

- The marks are HTML comments, UTC with a `Z` and **milliseconds**, so the response that ran `start` (its record is stamped before the command runs) falls before the mark and is not counted. **`start` reads the session id from `CLAUDE_CODE_SESSION_ID`** (`session=unknown` when it is not set, or not hex digits and `-`). **`stop` takes every session from the marks, never from its own environment**, so a stop run by hand in a plain terminal still finds the transcripts. A mark with `session=unknown`, or a hand-edited mark whose session is not hex digits and `-`, is treated as unknown and **never counts as "the same session"** as another mark. Skills never edit or remove `<!-- usage-start` or `<!-- usage-stop` lines.
- The usage line is a bullet of its own; the stop mark follows it. The stop time is **stored**, so replacing an open line reuses it and a stop run a day later does not count that day.
- **Exact integers** with thousands separators, never rounded (SC-002). `sub-agents` is one figure: the sum of the four token fields over the sub-agent transcripts in the window. `turns` is the number of distinct main-session responses with usage in the window. `model` lists each distinct valid model name (`^[A-Za-z0-9._:-]{1,64}$`; `<synthetic>` and anything else ignored) in order of first use, comma-separated; `model not recorded` when none.
- `wall`: the segment seconds (floats) are summed over segments, then rounded **once**, half up, with `(total_seconds + 30) // 60` on the integer part of the sum (Python's `round()` rounds half to even and must not be used); under 30 s total it reads `<1 min wall`. The current time is `datetime.datetime.now(datetime.timezone.utc)` (`utcnow()` is deprecated).
- **Zero** is written only when the source was read and held nothing for the figure. `sub-agents 0` is written only when the segment's main transcript was found (so its session folder was looked up) and no sub-agent file has a response in the window; a session that ran no sub-agent writes no `subagents/` folder. A figure whose source could not be read or understood is `not available (<reason>)` in its place, never `0`.

### Exactly what each case writes

When a segment's figures are `not available`, the line groups them: `- usage T012: tokens not available (<reason>) · sub-agents not available (<reason>) · 23 min wall · turns not available (<reason>) · model not available (<reason>)`. `tokens` stands for the four token fields. Wall time stays, from the marks.

Precedence: the first row that applies wins for the whole line (rows 1–2) or for a segment (rows 3–6). `PARTIAL` and `OVERLAP` suffixes come after.

| # | Case | What `stop` writes |
|---|---|---|
| 1 | No start mark for the unit | `- usage T012: not available (no start mark)` |
| 2 | Every mark's session is unknown **and** there is no `$CLAUDE_CONFIG_DIR`/`~/.claude` folder (Copilot, or any non-Claude target) | `- usage T012: not available (no transcript on this target)` |
| 3 | A segment's session is unknown (a Claude folder exists; detection limit: a Copilot user who also has Claude installed lands here) | that segment's token, sub-agent, turn and model fields `not available (session id unknown)`; wall from the marks |
| 4 | A segment's transcript file is missing (or more than one `projects/*/<session>.jsonl` matches: ambiguous) | token, sub-agent, turn and model fields `not available (transcript not found)`; wall from the marks (an earlier segment ends at the next mark, as in row 3) |
| 5 | A record needed for the segment is malformed (see Shape check) | the segment's token, sub-agent, turn and model fields `not available (unexpected transcript format)` |
| 6 | No response from a non-`<synthetic>` model falls in the segment's window (a hand run, or start and stop inside one response) | the segment's token, sub-agent, turn and model fields `not available (no response in window)` |
| 7 | All inputs read | the full line above |

- **PARTIAL:** when some segments are readable and others are not, the line gives the figures of the readable ones, then `· PARTIAL: segment 2 (session <id>): <reason>` per unreadable segment; totals are lower bounds.
- **OVERLAP:** when another unit in the **same record** has a mark in the same session inside the window, the line ends with `· OVERLAP: <unit>[, <unit>…]`. Units in other records are not seen (stated limit).
- A line is **closed** only if it holds at least one token, sub-agent or turn **figure** (a number, not `not available`). A whole-line `not available`, or a line whose only figures are wall time and model, leaves the unit **open**; the next `stop` replaces it in place and keeps the stored stop time.

## Behaviour

| Call | Result | Exit |
|---|---|---|
| `start`, switch on, no mark for the unit in this (known) session, unit not closed | appends a mark | 0 |
| `start`, a mark for the unit from **this** session exists | no change, prints `already started` (a unit that goes A → B → A across sessions keeps its A mark: the work in the second A stretch is inside the first window, a stated limit) | 0 |
| `start`, only marks from other sessions | appends a new mark; older ones stay (resume) | 0 |
| `start`, the unit is already closed | no change, prints `unit already closed (use a new id, for example T012-r2)` | 0 |
| `stop`, marks present, the unit is not closed | computes every segment, writes the line and the stop mark | 0 |
| `stop`, the unit is closed (a line for exactly this unit id holds a figure) | no change, prints `already closed` | 0 |
| `stop`, no start mark | writes the `no start mark` line | 0 |
| bad arguments, a unit id with other characters, a record outside the project root or missing, an unwritable record | one line saying which; no write | 2 |

- A unit that is started and never stopped keeps only its mark (FR-016).
- A line matches a unit only by `- usage <unit>:` at the start, with the exact id, inside the section.
- **Atomic write:** the record is read as bytes, the section located, the text inserted at the end of the section, written as bytes to a temporary file in the same folder and renamed over the record. The mode of the record is kept; a symlinked record is resolved first and its target must be inside the project root. Other sections are kept byte for byte, line endings included. If the write fails, the record is unchanged (exit 2).

## Segments and figures

- A **segment** is one mark. Its window is **half open**, `[start, end)`. It starts at the mark's time. The last mark ends at the stop time (`--at`, the stored stop time, or now). An earlier mark (the unit was resumed in a later session) ends at the earlier of (its own session's last transcript timestamp **plus 1 ms**, so the final response is included; "last" means the latest `timestamp` of any assistant record) and the next mark's time, and never before its own start. An earlier mark whose session is unknown or whose transcript is missing ends at the next mark's time. A repeated `start` in an unknown session appends a mark each time. An earlier segment counts any unrelated work done in its session after the unit paused; the figure is an upper bound and the line says nothing more.
- **Timestamps** are parsed with a regular expression for `YYYY-MM-DDTHH:MM:SS(.fff)?Z` and converted with `datetime.strptime`; Python 3.9's `fromisoformat` rejects `Z`. A timestamp on an assistant record in any other form is `unexpected transcript format`.
- **Transcript lookup** (read-only): `$CLAUDE_CONFIG_DIR` or `~/.claude`, then `projects/*/<session>.jsonl`; sub-agents in `projects/*/<session>/subagents/agent-*.jsonl`. Exactly one `<session>.jsonl` match is required; none or several is row 4.
- **Shape check:** only records with `type` `assistant` and a `message.usage` are checked and counted; every other record type is ignored (most types carry no timestamp). A counted record needs `message.id`, a parseable timestamp and the four integer counters (a boolean is not an integer). `<synthetic>` responses count toward neither tokens, turns nor models. Only the **kept** record of each `message.id` is shape-checked; a superseded duplicate is ignored.
- **Fields taken** from each JSONL record: `type`, `timestamp`, and for `assistant` records `message.id`, `message.model` and the four `message.usage` counters. The record is dropped after parsing (NFR-001).
- **De-duplication:** per file, the last assistant record per `message.id` is kept. **Then** the kept records are placed in windows by their timestamp (the last record's, so a response that straddles a boundary is counted once, in one window).
- **Unparsable lines:** an unparsable **last** line is skipped (the file may be mid-write); any other unparsable line is row 5 for the segments that read that file.
- No network access, no subprocess, no prompts, standard input not read (NFR-002, NFR-003). The script imports only modules from `argparse`, `datetime`, `glob`, `json`, `os`, `re`, `sys`, `tempfile`.
- **Known limits (stated, not hidden):** a missing `subagents/` folder is read as "no sub-agent ran" (`sub-agents 0`), so a Claude Code release that moves that folder would show 0 instead of `not available`; the live check asserts the folder exists in a run that used a sub-agent. Thinking tokens are inside `output_tokens` (equal to the CLI's on the recorded run, which reported 66 thinking tokens). A sub-agent still running at `stop` is counted up to now. Two sessions sharing one unit are windowed by clock.
