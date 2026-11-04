# sdlc-kit

One portable folder that sets up a lean, evidence-driven SDLC for AI coding agents (Claude Code and GitHub Copilot) in any repository. It combines:

- **Spec Kit**: the artifact chain and the analyze/converge gates.
- **BMad**: scale-adaptive depth.
- **Matt Pocock**: grilling and vertical-slice TDD.
- **Addy Osmani**: lifecycle skills with anti-rationalization tables and required evidence.
- **pstack**: a router, principles, and pause/pickup.

On top of these it keeps a few hard-won engineering rules (a decision ladder, a readiness gate, fail-safe checkpoints, evidence-based review). See [DESIGN.md](DESIGN.md) for why each piece is here.

## Status

| | |
|---|---|
| Version | **0.6.0** (see `VERSION`); unreleased changes on `main`: licence, router model-invocable, debug usage order, `sdlc verify`, `sdlc gate` |
| State | Usable. Last checked 2026-11-03 on `main` after the spec 003 merge: `sdlc lint` is clean and 228 tests pass. Install, check and uninstall are verified on a fresh repo. |
| Targets | Claude Code (first-class) and GitHub Copilot (rendered, not evaluated); see [Supported hosts](#supported-hosts) |
| Requirements | Python 3.9+, stdlib only, no network |
| Evidence | Behaviour evals in `evals/` (one fresh `claude -p` per prompt via `evals/run.py`). Results are in `evals/results/`: n = 1 per arm, Sonnet 5.5 only. Usage metrics have a live check on real sessions, `evals/results/usage-live-check.md` |
| Experimental | The opt-in `dense` module (spec 002, `find` instead of read) is built and independently reviewed, but its paired evaluation on a real workspace is **parked** (owner decision, 2026-11-04), so the gain is unproven: don't enable it for real work. Spec 001's v1 was rejected (tag `exp/dense-v1`). |

## Capabilities

- **One source, many tools.** Skills, roles, principles, checklists and templates are rendered per tool, with a lockfile (`.sdlc/lock.json`) and drift detection.
- **Scale-adaptive process.** A router (`/sdlc`) investigates, then picks track T0–T4, so a typo gets no spec and a feature gets the full chain with a human approval gate.
- **18 core skills** across the lifecycle: setup, context, grill, specify, clarify, plan, tasks, analyze, implement, TDD, debug, review, converge, ship, handoff, retro, usage, plus the router. Each has Rationalizations, Red flags and required Verification evidence.
- **5 subagent roles** with per-role model routing (`adapters/models.json`, overridable per project).
- **Workspace mode.** Install once over a folder of repos, map them with `sdlc discover` and `/sdlc-context`, and work in each repo under its own rules.
- **Optional modules.** `qa` adds test-case planning and automation skills. `dense` (experimental, unevaluated) adds a one-command lookup, `dap.py find`, over a source-pointed index of the workspace documents. A module can add rules to the always-loaded instructions.
- **Usage metrics (opt-in).** One switch in `.sdlc/config.json` records the tokens and wall time of each task, bug and fixed review finding, read from the Claude Code session transcript. See [Usage metrics](#usage-metrics-opt-in).
- **Self-checking kit.** `sdlc lint` enforces skill structure, valid `.sdlc/` references, and an unnamed-prompt eval for every skill the constitution names.
- **Safe updates.** `update` skips files edited locally; project rules live in `.sdlc/config.json`, never in kit-owned files.

## Supported hosts

| Host | Status | What that means |
|---|---|---|
| Claude Code | first-class | Skills, roles (read-only roles rendered as tool allow-lists), the usage metric and every eval result are on this host. |
| GitHub Copilot | rendered, not evaluated | Instructions, skills and roles are written to `.github/`; no eval row has run there, and usage metrics report `not available`. |

Limits found so far, not hidden:

- The Claude Code transcript format is internal to Claude Code and can change; usage metrics read it, pin a fixture, and say `not available` instead of guessing.
- `--resume` keeps the session id, so work resumed in the same session can't be told apart by id; the windows are separated by clock.
- There is no concurrency lock: two agents writing the same record at once can lose a write.

## Sharing the kit

The kit has no dependency on this machine or on any one project. To use it on another project, or to give it to a teammate:

1. Share the folder, ideally as a git repository (`git clone <url> ~/sdlc-kit`). A zip also works, but a repo gives you `VERSION` and history for `update`.
2. In the other project: `python3 <kit>/bin/sdlc install <repo>`, then run `/sdlc-setup` once.
3. To take a newer kit later: `git pull` in the kit, then `sdlc update <repo>`.

The kit is under the [MIT licence](LICENSE). `specs/` and `docs/adr/` hold this kit's own history; internal names were replaced in the files (2026-11-04), but earlier git history still contains them, so make the repository public only after rewriting the history or publishing a fresh copy. Neither folder is installed into projects.

## Install into a project

```bash
python3 ~/Projects/sdlc-kit/bin/sdlc install /path/to/repo
```

Options: `--targets claude,copilot` (default: both), `--modules qa` (and the experimental `dense`), `--force` (overwrite conflicting unmanaged files). It needs only Python 3.9+ and no network.

Then, in the project, run the `sdlc-setup` skill once. It fills `.sdlc/config.json` with the real build and test commands.

| Command | Does |
|---|---|
| `sdlc install <dir>` | Render the kit into the project and write `.sdlc/lock.json` |
| `sdlc update <dir> [--force]` | Re-render from the current kit; skips files edited locally |
| `sdlc check <dir>` | Report drift (`MODIFIED`, `MISSING`, `DRIFT`), duplicate spec numbers, and an outdated lock. Exits 1 on drift, so it can run in CI. |
| `sdlc uninstall <dir>` | Remove everything the kit wrote; keeps `config.json` and local edits |
| `sdlc next-spec <dir>` | Next free `NNN` spec prefix |
| `sdlc gate <name> <dir> --spec <NNN> [--repo <name>] [--by <name>]` | Mechanical readiness checks. `approve --by <name>` records the human's approval with a digest of spec, plan, tasks and contracts; `sdlc gate approved` passes only while those documents are unchanged since; `green-at-head` passes only for a clean, current, all-pass `verify` record on a still-clean tree; `evidence-for-ticks` needs a progress-log line with a real commit for every ticked task. Exit 0 pass, 1 fail, 2 usage error. They report; hooks and CI (later stories) act on the exit code. |
| `sdlc verify <dir> [--repo <name>]` | Run the configured `commands` once each and write `.sdlc/evidence/verify.json` (revision, dirty flag, exit codes, no output). Exits 0 only if everything that ran passed. Last line: `verify: PASSED at <hash> (clean tree)` is the only verified-at-HEAD result. POSIX only; no lock if two runs overlap. `uninstall` keeps `.sdlc/evidence/` (the record is local state: add it to `.gitignore` if you don't want it committed). |
| `sdlc discover <dir> [--json]` | Read-only inventory of the git repos in a workspace folder |
| `sdlc lint` | Validate the kit itself |

### What lands in the project

| Path | Owner |
|---|---|
| `.claude/skills/sdlc*/` (or `.github/skills/` when the only target is Copilot; Copilot also reads `.claude/skills`) | kit |
| `.claude/agents/sdlc-*.md`, `.github/agents/sdlc-*.agent.md` | kit |
| `.sdlc/constitution.md`, `principles/`, `checklists/`, `templates/` | kit |
| The block between `<!-- BEGIN sdlc-kit -->` and `<!-- END sdlc-kit -->` in `AGENTS.md` and `.github/copilot-instructions.md` | kit |
| Everything outside those blocks; `.sdlc/config.json` | project |
| `specs/`, `docs/adr/`, glossary | project |

Never edit kit-owned files in place. Change the kit and run `update`, or put project rules in `.sdlc/config.json` → `extra_instructions`.

## Multi-repo workspace

You can install the kit into a plain folder that holds several repos, for example `~/Projects/pilot`. The child repos are never written.

```bash
python3 ~/Projects/sdlc-kit/bin/sdlc install ~/Projects/pilot
```

To see the raw facts about every repo:

```bash
python3 ~/Projects/sdlc-kit/bin/sdlc discover ~/Projects/pilot
```

Then open Claude Code in the workspace folder and run `/sdlc-setup`. It detects the workspace and writes `.sdlc/workspace.md` (a map of the repos, their dependencies, commands, specs and agent surfaces) and `repos` in `.sdlc/config.json`, only after you approve. Next, run `/sdlc-context <repo>` to write a cited context file per repo (`.sdlc/context/<repo>.md`). `discover` marks it STALE once the repo moves on. From then on, `/sdlc` first names the repo each task belongs to and works inside it, under that repo's own `AGENTS.md`.

## Use it in plain language

After install and `/sdlc-setup`, you can just say what you want. You don't need to remember skill names. The skill descriptions and the rules in `AGENTS.md` let the agent pick the right one.

| You say | What happens |
|---|---|
| "Review this PR / my diff / this spec" | Loads `sdlc-review`, runs the checks, and starts the report with `VERDICT: APPROVED` or `VERDICT: REJECTED` (verified, `evals/results/0.5.0.md` D9) |
| "GET /v1/products/x returns 500 instead of 404. Fix it." | Loads `sdlc-debug`: reproduce, find the root cause, write a failing test, then the smallest fix (started correctly in one run; the fix itself wasn't observed, R6 in `evals/results/0.5.0.md`) |
| "We need a spec for X" / "Plan this feature" / "Break this plan into tasks" | Loads `sdlc-specify`, `sdlc-plan` or `sdlc-tasks` from their descriptions (not yet eval-tested in plain language) |
| "Pause here, I'll continue tomorrow" / "Pick up where we left off" | `sdlc-handoff` writes or reads a compact handoff (not yet eval-tested in plain language) |
| "What did we learn from this feature?" | `sdlc-retro` turns the corrections into proposed changes (not yet eval-tested in plain language) |

**For a bigger or unclear task, just describe it, or start with `/sdlc <task>`, in words like "/sdlc add sorting to the categories list".** The router skill is model-invocable (unreleased, after 0.6.0), so a non-trivial plain-language request should open it and a one-line typo should not; eval rows R6 and R7 checked that on 2026-11-04 with n = 3 on two models: a plain-language bug loaded `sdlc` first in 6/6 runs, a typo never did (6/6); see `evals/results/wave0-live.md`. `/sdlc` still works as before. It investigates, tells you which track (T0 to T4) it chose and why, and opens the steps as a todo list.

Tips:

- Say the outcome and the constraint, not the process: "fix the 500 on unknown product ids, keep the response shape" beats "run the debug skill".
- Approve at the stops. A T3 feature pauses for your approval before any code, and a review never edits.
- If the agent skips a step, name it: "use sdlc-review on this" or "grill me on this first".

## Use

Start with **`/sdlc <task>`**. It looks at the code, picks a track and opens the steps as a todo list.

| Track | When | Flow |
|---|---|---|
| T0 Trivial | No behaviour change | do → verify → offer ship |
| T1 Bug | Wrong behaviour | `sdlc-debug` → review → ship |
| T2 Change | One session, one seam, no contract, data or security change | grill (light) → mini-spec → `sdlc-tdd` → review → ship |
| T3 Feature | Contract, data model, security, more than one seam | specify → clarify → plan → tasks → analyze → **approval** → implement → converge → review → ship |
| T4 Initiative | Several features, teams or repos | grill → PRD → ADRs → T3 per feature |

Skills: `sdlc`, `sdlc-setup`, `sdlc-context`, `sdlc-grill`, `sdlc-specify`, `sdlc-clarify`, `sdlc-plan`, `sdlc-tasks`, `sdlc-analyze`, `sdlc-implement`, `sdlc-tdd`, `sdlc-debug`, `sdlc-review`, `sdlc-converge`, `sdlc-ship`, `sdlc-handoff`, `sdlc-retro`, `sdlc-usage`. The QA module adds `sdlc-qa-plan` and `sdlc-qa-automate`. A module may also ship a `rules.md`, rendered into the instructions under "Module rules" (`adapters/RENDERING.md`).

Roles (subagents): `sdlc-explorer`, `sdlc-planner`, `sdlc-implementer`, `sdlc-reviewer`, `sdlc-security-reviewer`. The model for each role is set in `adapters/models.json` and can be overridden per project in `config.json` → `models`.

## Usage metrics (opt-in)

Off by default. To record what a task, a bug or a fixed review finding cost, add this to `.sdlc/config.json`:

```json
{ "usage": { "enabled": true } }
```

Only the JSON value `true` turns it on. Then `sdlc-implement` (tasks and review findings) and `sdlc-debug` (bugs) run two commands around each unit, from the project root:

```bash
python3 .claude/skills/sdlc-usage/usage.py start <unit> --record <file> [--section <heading>]
python3 .claude/skills/sdlc-usage/usage.py stop  <unit> --record <file> [--section <heading>]
```

`start` writes a hidden mark with the time and the session id. `stop` reads the session transcript (and the sub-agent transcripts) and adds one line to the record that owns the unit: the feature's `tasks.md` Progress log for a task or a finding (`review1-F3`), and a `## Usage` section of the bug record for a bug.

```text
- usage T012: in 1,502 · cache-read 2,103,441 · cache-write 40,118 · out 18,004 · sub-agents 612,300 · 23 min wall · 41 turns · model claude-opus-5-5
```

- **Exact, not rounded.** Figures are the four token fields separately, sub-agents as one figure, wall time (clock time, including waiting for you), turns, and the models used. No cost.
- **`not available (<reason>)`, never 0.** If a transcript is missing or its shape is unexpected, the field says so and why. Copilot leaves no transcript, so it reports `not available (no transcript on this target)`.
- **Private and offline.** The script reads only ids, timestamps, model names and usage counters; it copies no message text, opens no network connection and starts no process.
- **Measured.** On recorded and live Claude Code runs the figures equal the CLI's own totals to the token, sub-agents included (`evals/results/usage-live-check.md`, `tests/fixtures/usage/real-run/`).
- **Limits.** The transcript format is documented by Claude Code as internal: re-run the UR1 check in `evals/scenarios.md` after a major version change. Wall time includes idle time. `claude --resume` keeps the session id, so one window spans the runs; a new session id adds a mark. Run one unit at a time: overlapping units are flagged `OVERLAP`. Fixes to `sdlc-analyze` findings are not measured.

Design and evidence: [spec 003](specs/003-usage-metrics/spec.md), [ADR-0002](docs/adr/0002-usage-metric-technique.md).

## Develop the kit

```bash
python3 bin/sdlc lint
python3 -m unittest discover -s tests -t .
```

- Every skill follows the same sections: When to use, Inputs, Process, Rationalizations, Red flags, Verification, Principles applied. It stays at 200 lines or fewer; put detail in `references/`.
- Shared docs are referenced only as `.sdlc/...`. Lint fails on a path that doesn't exist.
- Bump `VERSION` for each release. `sdlc check` in a project reports `OUTDATED` when its lock is older.
- Lessons from projects arrive via `sdlc-retro` as proposals against this repo.
- `evals/` holds scenario prompts with expected behaviour. When you change a skill, run its prompt against a scratch repo with `python3 evals/run.py <prompt-file> <scratch-repo> --out <transcript.jsonl>` (see `evals/scenarios.md`).
