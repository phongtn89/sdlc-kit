# ADR-0002: Usage is read from the session transcripts, between start and stop marks

Status: accepted <!-- proposed | accepted | superseded by ADR-NNNN -->
Date: 2026-11-03 · Deciders: phong.ngo.vn (accepted in chat, 2026-11-03: "I choose the recommended option") · Related: [spec 003](../../specs/003-usage-metrics/spec.md); shop6 decision record `.sdlc/decisions/2026-10-30-usage-metrics.md` (decision 2: explicit start and stop as named commands)

## Context

Spec 003 needs, per task, bug and fixed finding: the four token fields, sub-agent usage, wall time, turns and model. The constraints are the kit's own: Python 3.9 stdlib only, offline, no server or account, no conversation content copied, opt-in per project, and "not available" instead of 0.

**Research (2026-11-03).** Two agents read the official Claude Code docs and the community and standards material; every claim below is marked as verified (primary doc, or measured here) or not.

| Family | Popular use | Verified facts |
|---|---|---|
| Transcript parsing | `ccusage` and similar tools; the most common community approach | Path and sub-agent layout documented (`sessions.md`, `sub-agents.md`); the entry format is documented as internal and may change |
| Native OpenTelemetry | Dashboards, fleets | `claude_code.token.usage` by type, `cost.usage`, `api_request` events with `session.id`; documented (`monitoring-usage`). **Project and local settings ignore the OTEL variables**; user or managed settings or the shell set them. Needs a collector, or the console exporter. Prompt text is off by default |
| Hooks and status line | Ledgers, status bars | 33 hook events; every hook gets `session_id` and `transcript_path`; **no hook carries tokens, cost or turns**. The status line carries session-level cost and duration, and its token totals describe the current context, not billing |
| Proxy or gateway (LiteLLM, Helicone, Portkey) | Teams that route all traffic | Exact per request; needs a running service, usually a database and keys. Unverified for subscription logins |
| Observability platforms (Langfuse, LangSmith, Phoenix) | Prompt and eval tracing | Server or account; store content by design |

Proxies and platforms fail three constraints at once (no server, no account, no content) and are not evaluated further.

**Measurements on this machine (Claude Code, Opus 5.5, 2026-11-03).** One headless run with two file reads and one sub-agent; ground truth is the CLI's own `result` event (`usage` for the main session, `modelUsage` for everything):

| Method | Input | Output | Cache read | Cache write |
|---|---|---|---|---|
| Ground truth, main session (`usage`) | 6 | 573 | 103,919 | 17,271 |
| Transcript, naive sum of every assistant record | 8 | 818 (+43%) | 128,468 (+24%) | 31,019 (+80%) |
| Transcript, last record per `message.id` | 6 | 573 | 103,919 | 17,271 |
| Transcript, only records with a `stop_reason` | 8 | 818 | 128,468 | 31,019 |
| Ground truth, all models (`modelUsage`) | 12 | 1,347 | 169,358 | 52,629 |
| Main (de-duplicated) + sub-agent file (de-duplicated) | 12 | 1,347 | 169,358 | 52,629 |

- The de-duplicated transcript matches the CLI to the token, sub-agent included. The community claim that the transcript's input and output tokens are placeholders did not hold here.
- Without de-duplication a transcript overcounts by up to 80%: one API response is written as several records. This session's own transcript has 234 usage records for 108 message ids. A `stop_reason` filter does not fix it.
- Hooks (`SessionStart`, `SubagentStop`, `Stop`) fired with `session_id`, `transcript_path` and, for sub-agents, `agent_transcript_path`. At `Stop` the transcript already held the final output total (605 = the CLI's figure), so no lag showed in this run. No hook field carried usage.
- The console OpenTelemetry exporter printed no metrics in a short headless run with the documented variables; per-project enabling is not possible. Not shown to work offline here.
- `CLAUDE_CODE_SESSION_ID` is set in this desktop session. The docs do not list it; hooks and the status line document `session_id` instead.

## Decision

We will measure a unit by reading the Claude Code session transcripts (the main file and the sub-agent files under `<session-id>/subagents/`), de-duplicated by `message.id` (keep the last record), between an explicit start mark and stop that the skills run as named commands. The marks hold the time and the session ID, so the commands need no hook. When the transcript or session ID cannot be found, or its shape is not the expected one, the figure is "not available" with a reason. Hooks and native OpenTelemetry are not required; OpenTelemetry stays a documented user-level cross-check.

## Consequences

- Positive: exact on the one run measured (including the sub-agent); offline, stdlib-only, no content copied (only `usage`, `timestamp`, `model` and ids are read), works per project with one switch in `.sdlc/config.json`, and needs nothing installed outside the kit.
- Negative: the entry format is documented as internal, so a Claude Code update can break the parser; the guard is a shape check that yields "not available", plus a fixture test pinned to a recorded transcript. Attribution is by clock window within a session, so overlapping units or parallel sub-agents in one session are not separated (spec 003 already excludes overlap). The measurement is n = 1 session on one model; the plan must add a fixture check on a second shape (resume, several models, thinking tokens).
- Follow-up: (1) spec 003 gets the de-duplication rule and the sub-agent source as requirements, and a pinned fixture; (2) the plan tests resume and multi-model sessions against `claude -p` ground truth; (3) re-run the comparison when Claude Code's major version changes; (4) Copilot stays "not available".

## Alternatives

| Option | Why not chosen |
|---|---|
| Hooks write a ledger | Hooks carry no usage numbers, so the transcript is read anyway. None of the 33 events marks a task boundary inside a session (`Stop` ends a turn, not a unit), so the skills still need start and stop commands. It adds a settings.json rendering step, and `bin/sdlc` renders no hooks today. Kept as a possible later way to record sub-agent ends |
| Native OpenTelemetry (console or collector) | Per-project enabling is not supported (project settings ignore the variables), so a project switch could not turn it on. It needs a collector or stdout capture, and the console run here showed nothing. Exact and documented, but it breaks "one switch in `.sdlc/config.json`, nothing else to run". Documented as an optional cross-check keyed by `session.id` |
| One fresh headless session per unit (`claude -p`, read `result.usage`) | Exact and documented, but only for work the kit itself launches. Interactive and desktop sessions, which are the normal case, are not covered |
| Status line totals | Session-level, and the token totals are context size, not billing |
| Proxy, gateway, observability platform | Need a server or account and store content; fail the kit's constraints |
