# sdlc-kit

One portable folder that sets up a lean, evidence-driven SDLC for AI coding agents (Claude Code and GitHub Copilot) in any repository. It combines:

- **Spec Kit**: the artifact chain and the analyze/converge gates.
- **BMad**: scale-adaptive depth.
- **Matt Pocock**: grilling and vertical-slice TDD.
- **Addy Osmani**: lifecycle skills with anti-rationalization tables and required evidence.
- **pstack**: a router, principles, and pause/pickup.

On top of these it keeps the Shop 6 fleet's own engineering rules. See [DESIGN.md](DESIGN.md) for why each piece is here.

## Install into a project

```bash
python3 ~/Projects/sdlc-kit/bin/sdlc install /path/to/repo
```

Options: `--targets claude,copilot` (default: both), `--modules qa,dense`, `--force` (overwrite conflicting unmanaged files). It needs only Python 3.9+ and no network.

Then, in the project, run the `sdlc-setup` skill once. It fills `.sdlc/config.json` with the real build and test commands.

| Command | Does |
|---|---|
| `sdlc install <dir>` | Render the kit into the project and write `.sdlc/lock.json` |
| `sdlc update <dir> [--force]` | Re-render from the current kit; skips files edited locally |
| `sdlc check <dir>` | Report drift (`MODIFIED`, `MISSING`, `DRIFT`), duplicate spec numbers, and an outdated lock. Exits 1 on drift, so it can run in CI. |
| `sdlc uninstall <dir>` | Remove everything the kit wrote; keeps `config.json` and local edits |
| `sdlc next-spec <dir>` | Next free `NNN` spec prefix |
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

You can install the kit into a plain folder that holds several repos, for example `~/Projects/shop6`. The child repos are never written.

```bash
python3 ~/Projects/sdlc-kit/bin/sdlc install ~/Projects/shop6
```

To see the raw facts about every repo:

```bash
python3 ~/Projects/sdlc-kit/bin/sdlc discover ~/Projects/shop6
```

Then open Claude Code in the workspace folder and run `/sdlc-setup`. It detects the workspace and writes `.sdlc/workspace.md` (a map of the repos, their dependencies, commands, specs and agent surfaces) and `repos` in `.sdlc/config.json`, only after you approve. Next, run `/sdlc-context <repo>` to write a cited context file per repo (`.sdlc/context/<repo>.md`). `discover` marks it STALE once the repo moves on. From then on, `/sdlc` first names the repo each task belongs to and works inside it, under that repo's own `AGENTS.md`.

## Use

Start with **`/sdlc <task>`**. It looks at the code, picks a track and opens the steps as a todo list.

| Track | When | Flow |
|---|---|---|
| T0 Trivial | No behaviour change | do → verify → offer ship |
| T1 Bug | Wrong behaviour | `sdlc-debug` → review → ship |
| T2 Change | One session, one seam, no contract, data or security change | grill (light) → mini-spec → `sdlc-tdd` → review → ship |
| T3 Feature | Contract, data model, security, more than one seam | specify → clarify → plan → tasks → analyze → **approval** → implement → converge → review → ship |
| T4 Initiative | Several features, teams or repos | grill → PRD → ADRs → T3 per feature |

Skills: `sdlc`, `sdlc-setup`, `sdlc-context`, `sdlc-grill`, `sdlc-specify`, `sdlc-clarify`, `sdlc-plan`, `sdlc-tasks`, `sdlc-analyze`, `sdlc-implement`, `sdlc-tdd`, `sdlc-debug`, `sdlc-review`, `sdlc-converge`, `sdlc-ship`, `sdlc-handoff`, `sdlc-retro`. The QA module adds `sdlc-qa-plan` and `sdlc-qa-automate`. The `dense` module (Dense Agent Protocol, spec 001) adds `sdlc-dense-index`, which builds and checks `.sdlc/context/index.dap`, a compact source-pointed index of the context documents. Its module rules make agents check the index at track start, cite sources instead of the index, and ask sub-agents for the return format in `.sdlc/templates/dense-return.md`. Enable it in a workspace only after the paired evaluation in `.sdlc/templates/dense-eval.md` passes there.

Roles (subagents): `sdlc-explorer`, `sdlc-planner`, `sdlc-implementer`, `sdlc-reviewer`, `sdlc-security-reviewer`. The model for each role is set in `adapters/models.json` and can be overridden per project in `config.json` → `models`.

## Develop the kit

```bash
python3 bin/sdlc lint
python3 -m unittest discover -s tests -t .
```

- Every skill follows the same sections: When to use, Inputs, Process, Rationalizations, Red flags, Verification, Principles applied. It stays at 200 lines or fewer; put detail in `references/`.
- Shared docs are referenced only as `.sdlc/...`. Lint fails on a path that doesn't exist.
- Bump `VERSION` for each release. `sdlc check` in a project reports `OUTDATED` when its lock is older.
- Lessons from projects arrive via `sdlc-retro` as proposals against this repo.
- `evals/` holds scenario prompts with expected behaviour. Run them by hand against a scratch repo when you change a skill.
