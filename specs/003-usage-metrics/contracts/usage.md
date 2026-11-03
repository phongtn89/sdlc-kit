# Contract: `usage.py` and the usage line

Spec 003 (FR-005–FR-013, FR-016, FR-017, FR-019–FR-022, NFR-001–NFR-004). Technique: ADR-0002.

## Call

```text
python3 .claude/skills/sdlc-usage/usage.py start <unit> --record <file> [--section <heading>]
python3 .claude/skills/sdlc-usage/usage.py stop  <unit> --record <file> [--section <heading>]
```

- Skills run the command **from the project root** (the folder that holds `.sdlc/`), using `.github/skills/sdlc-usage/usage.py` when that is the only path that exists (Copilot-only install).
- `<unit>`: a task id (`T012`), a bug slug, or a finding id with its pass (`review1-F3`, `analyze2-A5`). Letters, digits, `-`, `_`, `.` only.
- `--record`: the owning record, **relative to the project root**: `specs/003-usage-metrics/tasks.md`; in a workspace, `<repo>/specs/<NNN-slug>/tasks.md`. `--section` (default `Progress log`): the `##` heading whose end receives marks and lines; created at the end of the file when absent. A bug uses `--section "Usage"`.
- **Project root:** the folder holding the nearest `.sdlc/config.json`, found by walking up from the current directory. In a workspace that is the workspace folder (the kit never writes a child repo's config); only that file's switch counts. No `.sdlc/config.json` found means off.

## Switch

`.sdlc/config.json` → `"usage": {"enabled": true}`. **Only the JSON value `true` is on.** Absent, `false`, a string, `"usage": true`, or invalid JSON is off. Off: both commands print `usage off` and exit 0 without reading a transcript or writing a file. Skills also check the switch before calling, so an off install adds no tool call.

## Marks and lines (written at the end of `<section>`)

```text
<!-- usage-start T012 2026-11-03T10:00:00Z session=0b8b2d7f-d1c8-4d58-86d4-eb8b0ad184f6 -->
- usage T012: in 1,502 · cache-read 2,103,441 · cache-write 40,118 · out 18,004 · sub-agents 612,300 · 23 min wall · 41 turns · model claude-opus-5-5
```

- The mark is an HTML comment, UTC with a `Z` and whole seconds. `session=unknown` when `CLAUDE_CODE_SESSION_ID` is not set or is not hex digits and `-` only. **A mark with `session=unknown` never counts as "the same session" as another mark.** Skills never edit or remove `<!-- usage-start` lines.
- The usage line is a bullet of its own, after the task's evidence line (marks and lines are appended, so order follows the work).
- **Exact integers** with thousands separators, never rounded (SC-002). `sub-agents` is one figure: the sum of the four token fields over the sub-agent transcripts in the window. `turns` is the number of distinct main-session responses with usage in the window. `model` lists each distinct valid model name (`^[A-Za-z0-9._:-]{1,64}$`; `<synthetic>` and anything else ignored) in order of first use, comma-separated; `model not recorded` when none.
- `wall`: seconds are summed over segments, then rounded **once**, half up, to whole minutes; under 30 s total it reads `<1 min wall`.
- **Zero** is written only when the source was read and held nothing for the figure (for example `sub-agents 0` when the session has no `subagents/` folder: a session that ran no sub-agent writes none). A figure whose source could not be read or understood is `not available (<reason>)` in its place, never `0`.

### Exactly what each case writes

| Case | Line written by `stop` |
|---|---|
| All inputs read | the full line above |
| No `CLAUDE_CODE_SESSION_ID` **and** no `$CLAUDE_CONFIG_DIR`/`~/.claude` folder (Copilot, or any non-Claude target) | `- usage T012: not available (no transcript on this target)` |
| No session id, but the Claude folder exists (detection limit: a Copilot user who also has Claude installed lands here) | `- usage T012: in not available (session id unknown) · … · 23 min wall · …` with every token, turns and model field `not available (session id unknown)`; wall from the marks |
| The session's transcript file is missing | token, turns and model fields `not available (transcript not found)`; wall from the marks |
| No response falls in the window, or a record lacks `message.id`, a parseable timestamp or an integer counter | the affected segment's fields `not available (unexpected transcript format)` |
| No start mark for the unit | `- usage T012: not available (no start mark)` |
| Some segments readable, some not | the figures of the readable segments, then `· PARTIAL: segment 2 (session <id>): <reason>` per missing segment; totals are lower bounds |
| Another unit's mark in the same section and session starts inside the window | the line ends with `· OVERLAP: <other unit>` |

A whole-line `not available` or a line with no figure leaves the unit **open**; the next `stop` replaces it in place.

## Behaviour

| Call | Result | Exit |
|---|---|---|
| `start`, switch on, no mark for the unit in this session | appends a mark | 0 |
| `start`, a mark for the unit from **this** session exists (session known) | no change, prints `already started` | 0 |
| `start`, only marks from other sessions | appends a new mark; older ones stay (resume) | 0 |
| `stop`, marks present, the unit is not closed | computes every segment, writes the line | 0 |
| `stop`, the unit is closed (a line for exactly this unit id holds at least one figure) | no change, prints `already closed` | 0 |
| `stop`, no start mark | writes the `no start mark` line | 0 |
| bad arguments, unit id or session id with other characters, a record outside the project root, an unwritable record | one line saying which; no write | 2 |

- A unit that is started and never stopped keeps only its mark (FR-016).
- A line matches a unit only by `- usage <unit>:` at the start, with the exact id, inside the section.
- **Atomic write:** the record is read, the section located, the text inserted at the end of the section, written to a temporary file in the same folder and renamed over the record. Other sections are kept byte for byte.

## Segments and figures

- A **segment** is one mark. Its window is **half open**, `[start, end)`. It starts at the mark's time. The last mark ends at the stop time. An earlier mark (the unit was resumed in a later session) ends at the earlier of its own session's last transcript timestamp and the next mark's time. This counts any unrelated work done in that session after the unit paused; the figure is an upper bound for that segment, and the line says nothing more. When that session's transcript is missing, the segment's wall time is `not available (transcript not found)` and the line is PARTIAL.
- **Timestamps** are parsed with a regular expression for `YYYY-MM-DDTHH:MM:SS(.fff)?Z` and converted with `datetime.strptime`; Python 3.9's `fromisoformat` rejects `Z`. Any other timestamp form is `unexpected transcript format`.
- **Transcript lookup** (read-only): `$CLAUDE_CONFIG_DIR` or `~/.claude`, then `projects/*/<session>.jsonl`; sub-agents in `projects/*/<session>/subagents/agent-*.jsonl`.
- **Fields taken** from each JSONL record: `type`, `timestamp`, and for `assistant` records `message.id`, `message.model` and the four `message.usage` counters. The record is dropped after parsing (NFR-001).
- **De-duplication:** per file, the last assistant record per `message.id` is kept. **Then** the kept records are placed in windows by their timestamp (the last record's, so a response that straddles a boundary is counted once, in one window).
- **Unparsable lines:** an unparsable **last** line is skipped (the file may be mid-write); any other unparsable line makes that segment's token fields `not available (unexpected transcript format)`.
- No network access, no subprocess, no prompts, standard input not read (NFR-002, NFR-003). The script imports only `argparse`, `datetime`, `glob`, `json`, `os`, `re`, `sys`, `tempfile`.
- **Known limits (stated, not hidden):** thinking tokens are inside `output_tokens` (equal to the CLI's on the recorded run, which reported 66 thinking tokens); a sub-agent still running at `stop` is counted up to now; two sessions sharing one unit are windowed by clock.
