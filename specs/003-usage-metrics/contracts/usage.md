# Contract: `usage.py` and the usage line

Spec 003 (FR-005–FR-013, FR-016, FR-017, FR-019, FR-020, NFR-001–NFR-003). Technique: ADR-0002.

## Call

```text
python3 .claude/skills/sdlc-usage/usage.py start <unit> --record <file> [--section <heading>]
python3 .claude/skills/sdlc-usage/usage.py stop  <unit> --record <file> [--section <heading>]
```

- Skills use `.github/skills/sdlc-usage/usage.py` when that is the only path that exists (Copilot-only install).
- `<unit>`: the unit's id in its record: a task id (`T012`), a bug slug, or a finding id (`F3`). Letters, digits, `-`, `_`, `.` only.
- `--record`: the owning record, relative to the project root. `--section` (default `Progress log`): the `##` heading whose end receives marks and lines; created at the end of the file when absent.
- The script finds the project root by walking up from the current directory to the nearest `.sdlc/config.json`.

## Switch

`.sdlc/config.json` → `"usage": {"enabled": true}`. Absent, `false` or malformed means off. When off, both commands print `usage off` and exit 0 without reading a transcript or writing a file. Skills also check the switch before calling, so an off install adds no tool call.

## Marks and lines (written into `<record>`, at the end of `<section>`)

```text
<!-- usage-start T012 2026-11-03T10:00:00Z session=0b8b2d7f-d1c8-4d58-86d4-eb8b0ad184f6 -->
- usage T012: in 1,502 · cache-read 2,103,441 · cache-write 40,118 · out 18,004 · sub-agents 612,300 · 23 min wall · 41 turns · model claude-opus-5-5
```

- The mark is an HTML comment, so rendered markdown shows only the usage line. `session=unknown` when `CLAUDE_CODE_SESSION_ID` is not set.
- **Exact integers**, with thousands separators, never rounded (SC-002 is an exact match). `sub-agents` is one figure: the sum of the four token fields over the sub-agent transcripts in the window (FR-010). `wall` is whole minutes, rounded to nearest, with `<1 min` below 30 s. `turns` counts distinct main-session model responses with usage in the window; sub-agent turns are excluded. `model` lists each distinct model, comma-separated, `<synthetic>` ignored.
- A figure that can't be found is `not available (<reason>)` in its place, never `0`. A whole-line failure: `- usage T012: not available (<reason>)`.
- Partial: the figures found, then `· PARTIAL: segment 2 (session <id>): <reason>`. Totals are then lower bounds.

Reasons (the only ones): `usage off` (never written), `no start mark`, `no transcript on this target` (no session id and no Claude config folder), `transcript not found`, `unexpected transcript format`, `session id unknown`.

## Behaviour

| Call | Result | Exit |
|---|---|---|
| `start`, switch on, no open mark for the unit | appends a mark (now, session id) | 0 |
| `start`, an open mark exists for this unit **in this session** | no change, prints `already started` (FR-017) | 0 |
| `start`, an open mark from **another** session | appends a new mark; the older stays (FR-008) | 0 |
| `stop`, marks present, no usage line for the unit | computes every segment, appends the line (a figure is `not available` rather than an error) | 0 |
| `stop`, a usage line for the unit exists | no change, prints `already closed` (FR-017) | 0 |
| `stop`, no start mark | appends `- usage <unit>: not available (no start mark)` | 0 |
| bad arguments, unwritable record, unit id with other characters | one line saying which; no write | 2 |

A unit that is started and never stopped keeps only its mark (FR-016).

## Segments and figures

- A **segment** is one mark. Its window starts at the mark's time. The last mark's window ends at the stop time. An earlier mark (the unit was resumed in a later session) ends at the last transcript timestamp of its own session (glossary: "to the end of that session"). A second `start` in the same session adds no mark, so a session holds at most one segment per unit.
- **Transcript lookup** (read-only): `$CLAUDE_CONFIG_DIR` or `~/.claude`, then `projects/*/<session>.jsonl`; sub-agents in `projects/*/<session>/subagents/agent-*.jsonl`.
- **Read only** from each JSONL record: `type`, `timestamp`, and for `assistant` records `message.id`, `message.model`, and the four `message.usage` token counters. No other field is read into a variable that outlives the record, and none is written (NFR-001).
- **De-duplication** (FR-019): per file, the last assistant record per `message.id`. A record is counted in the segment that contains its timestamp.
- **Shape check** (FR-020): an assistant record with `usage` that lacks any of the four counters, or counters that are not integers, makes the affected segment's token fields `not available (unexpected transcript format)`; other segments are still reported.
- No network access, no subprocess, no prompts (NFR-002, NFR-003): the script imports only `argparse`, `json`, `os`, `re`, `sys`, `datetime`, `glob`.
