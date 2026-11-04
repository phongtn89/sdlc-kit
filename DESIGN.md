# sdlc-kit — design (draft for approval)

Status: **approved** 2026-10-22 (all §9 recommendations accepted) · v0.1.0 built · 2026-10-22 · Author: phong.ngo.vn (with Claude)
Targets: Claude Code, GitHub Copilot. Location: `~/Projects/sdlc-kit` (one folder, installed into any project).

## 1. Problem

The the pilot workspace fleet runs Spec Kit and a shared agent policy, but the copies have drifted:

- Spec Kit is at **four versions** (0.12.4, 0.12.8, 0.12.12.dev0, plus storefront's own fork); current upstream is **1.2.2**.
- The same skill exists on 3 surfaces (`.claude/skills`, `.agents/skills`, `.github/agents`) and **every Claude copy differs from its Antigravity copy**. Some `.github/agents` and `impl-reviewer` copies diverge between repos.
- Spec numbers collide (admin: 23 duplicate prefixes; storefront: 12; erp: 6; components: 5).
- There are two verdict vocabularies (`APPROVED/REJECTED` in the policy, `PASS | PASS_WITH_CONCERNS | FAIL` in the reviewers).
- Stale material: the caveman `skills-lock.json` points at skill folders that don't exist; the erp-connector constitution is an unfilled template.
- Generated Spec Kit skills are long (`speckit-specify` is 348 lines, mostly extension-hook boilerplate). The useful local ideas (decision ladder, readiness gate, preservative fail-fast, review method) are buried in a 270–340-line `AGENTS.md`.

The root cause is that there is **no single source and no drift check**. Each surface is generated or edited by hand, at a different time.

## 2. Goals / non-goals

**Goals**
1. One canonical source: a small set of skills, principles, checklists, templates and roles.
2. A thin rendering step for each tool (Claude Code and Copilot now; others later).
3. Process depth that matches the work: a typo shouldn't get a spec, and an epic shouldn't skip one.
4. Install, update and drift-check into any repo, with a lockfile and project overrides that survive updates.
5. Existing `specs/NNN-slug/` folders stay valid. No mass rewrite of the 215 spec folders.

**Non-goals (v1)**
- Changing product repos. Adoption happens later, one PR per repo, as the governance plan requires.
- Replacing GitHub agentic workflows (`.github/workflows/*-agent.md`).
- Named personas, party mode, game/creative modules.

## 3. What we take from each source — and what we leave

| Source | Take | Leave |
|---|---|---|
| **Spec Kit** (1.2.2) | Artifact chain `spec → plan → tasks`; `clarify` capped at 5 questions, answers written back into the spec; read-only **analyze** and **converge** gates that add tasks instead of editing code; checklists as "unit tests for requirements"; one canonical source rendered per agent; `specs/NNN-slug/` layout | The Python CLI as a runtime dependency; extension-hook boilerplate in every skill; 8+ verbose files per feature; the full pipeline for bugs and small changes |
| **BMad** (v6.12 / v7 α) | **Choose depth *after* investigating** (scale-adaptive); named size tracks with explicit criteria; a PRD only when several people must agree; use the handwritten `AGENTS.md` as project context; a fresh session per phase; layered overrides that survive reinstall; `status: draft` until validated | Persona roster and menu codes; frequent breaking renames; alpha channel; installer leaving stale folders |
| **Matt Pocock** skills | A **grilling** primitive: interview until every branch of the design tree is resolved; **TDD in vertical slices** (one test → one implementation, never all tests first); agree the test seam before writing tests; **tracer-bullet tickets with blocking edges**; a project glossary and ADRs read automatically; `handoff`; split user-invoked vs model-invoked skills | Frequent renames; the assumed tracker/label setup; TS-only phrasing; full grilling on trivial work |
| **Addy Osmani** agent-skills | Lifecycle **Define → Plan → Build → Verify → Review → Ship**; fixed SKILL.md sections; an **anti-rationalization table** and **required verification evidence** in every skill; reference checklists loaded on demand (DoD, security, observability, perf); reviewer roles as separate agents; `evals/` | 25 overlapping skills; frontend/webperf-specific skills in the core; its own spec/plan skills (Spec Kit covers them) |
| **pstack** (Lauren Tan, `cursor/plugins/pstack`) | **One router** that classifies the task and opens the matching playbook as a todo list; **principles as tiny files, cited in the reply**; `blast-radius` before cross-cutting edits; `pause-safely` / `session-pickup`; `reflect` → *encode lessons in structure*; router not model-invocable | Persona voice and prose style rules; Cursor-only packaging; "no planning" stance (conflicts with spec-anchored work); 47+ skills |
| **Fleet (keep)** | Lazy Senior Engineer decision ladder; readiness gate / Definition of Done; preservative fail-fast; `BLOCKED_PACKAGE_REGISTRY_AUTH`; review method (reject only demonstrated defects, every rejection = Correction / Reason / Verify); role routing (explorer, planner, implementer, reviewer, security-reviewer); QA lifecycle | Token estimates in the AIC budget (they can't be checked — keep the line and turn bounds); duplicated surfaces; mixed verdict vocabularies |

## 4. Philosophy (the kit's constitution, ~10 lines)

1. **Depth follows risk.** Investigate first, then choose the track. Escalate when the work turns out bigger than it looked; never pad a small change.
2. **Agree before building.** Resolve the decisions that matter by grilling. Write down what was agreed, not the conversation.
3. **Specs are anchored, not disposable.** `spec.md` stays the living requirements record for its feature. `converge` keeps the code and the spec honest with each other.
4. **Thin vertical slices.** Each task delivers one testable path end to end and names its blocking edges.
5. **Prove it works.** No claim without evidence: a command, its output and the revision. Skipped means not done.
6. **Subtract before you add.** Use the decision ladder before writing new code, types or dependencies.
7. **Root causes, not symptoms.** Reproduce first, then make the smallest fix and add a regression test.
8. **Guard the context window.** Read only what's needed, delegate wide searches, hand off cleanly.
9. **Fail safe, keep work.** On a blocker, checkpoint and stop. Never discard work.
10. **Encode lessons in structure.** A repeated correction becomes a principle, a checklist item or a skill change in the kit, not a memory.

## 5. Tracks (chosen by the router after a short investigation)

| Track | Signals | Artifacts | Flow |
|---|---|---|---|
| **T0 Trivial** | Typo, config value, pin bump; no behaviour change | none | do → verify |
| **T1 Bug** | Observable wrong behaviour | `specs/bugs/<slug>.md` only if non-obvious | reproduce → root cause → failing test → fix → verify |
| **T2 Change** | One session, ≤1 seam, no contract/data/security change | `mini-spec` (2 sections: *Intent* + *Acceptance*) inside the PR or `specs/NNN-slug/spec.md` | grill-lite → TDD slices → review → ship |
| **T3 Feature** | New behaviour, contract/API/event/data-model, security-sensitive, >1 seam | `spec.md`, `plan.md`, `tasks.md` (+ `contracts/`, `data-model.md`, ADR only when needed) | specify → clarify → plan → tasks → analyze → **human approval** → implement → converge → review → ship |
| **T4 Initiative** | Many features, several teams or repos, ~20+ sessions | `prd.md` + ADRs, then T3 features | grill → prd → architecture/ADR → split into T3 features |

Escalation rule: if a T1/T2 touches a contract, migration, auth/tenant boundary or a second repo, stop and re-route to T3. These mirror the fleet's existing "Spec Kit required" triggers.

## 6. Contents

```
sdlc-kit/
  VERSION                     # semver; the lockfile records it
  README.md                   # install, update, check, tracks at a glance
  core/
    constitution.md           # §4 — projects extend it, never edit it
    principles/               # one short file each, cited by name in replies
      depth-follows-risk.md  agree-before-building.md  prove-it-works.md
      subtract-before-adding.md  root-causes.md  thin-vertical-slices.md
      guard-context.md  fail-safe-keep-work.md  encode-lessons.md  evidence-over-claims.md
    skills/                   # Agent Skills format: SKILL.md + optional references/
      sdlc/        (router)              grill/       specify/     clarify/
      plan/        tasks/       analyze/      implement/   tdd/
      debug/       review/      converge/     ship/        handoff/
      retro/       setup/
    checklists/               # loaded on demand
      definition-of-done.md  requirements-quality.md  security.md  observability.md
      performance.md  compatibility-migration.md  accessibility.md
    templates/
      spec.md  mini-spec.md  plan.md  tasks.md  adr.md  prd.md  bug.md
      handoff.md  review-report.md  pr.md
    roles/                    # tool-neutral role definitions
      explorer.md  planner.md  implementer.md  reviewer.md  security-reviewer.md
  modules/                    # opt-in, same format
    qa/                       # ports fleet speckit-qa-* (testcases lifecycle)
  adapters/
    claude/   render rules + agent frontmatter (model per role)
    copilot/  render rules + .agent.md / .prompt.md frontmatter
  bin/sdlc                    # python3 stdlib only (macOS ships 3.9)
  evals/                      # scenario prompts + expected behaviour per skill
  tests/                      # installer + linter tests
```

**16 core skills** in place of 18–19 Spec Kit + local skills per repo. The Spec Kit `checklist` step folds into `analyze` plus `checklists/requirements-quality.md`. `taskstoissues` becomes an option on `tasks` (upstream also moved it out of core). `constitution` becomes `setup`.

### Skill format (lint-enforced)

```markdown
---
name: implement
description: Execute approved tasks.md with TDD vertical slices... Use when the user says "implement", "build task", or an approved tasks.md exists.
user-invocable: true            # Claude; mapped to a Copilot prompt
disable-model-invocation: false # true only for a skill the constitution does not name (lint rejects it on the router)
---
## When to use / not use
## Inputs (files read automatically: AGENTS.md, glossary, ADRs, active spec)
## Process (numbered; becomes the todo list)
## Rationalizations (excuse → reality)
## Red flags (stop and escalate)
## Verification (evidence required to call this done)
## Principles applied
```

Each SKILL.md stays under about 150 lines. Detail goes in `references/`.

## 7. Rendering and install

`bin/sdlc install <repo> [--targets claude,copilot] [--modules qa]`

| Kit source | Claude Code | GitHub Copilot |
|---|---|---|
| `core/skills/*` | `.claude/skills/<name>/` | the same `.claude/skills/` when both targets are set. Copilot reads `.claude/skills`, `.github/skills` and `.agents/skills`, and shows skills as slash commands, so no prompt shims are needed. `.github/skills/<name>/` is used only when Copilot is the only target. |
| `core/roles/*` | `.claude/agents/sdlc-<role>.md` (model from adapter map) | `.github/agents/sdlc-<role>.agent.md`, with `target: github-copilot` when both targets are set, because VS Code already reads `.claude/agents` |
| constitution + principles index | managed block in `AGENTS.md` (`CLAUDE.md` = `@AGENTS.md`) | managed block in `.github/copilot-instructions.md` |
| checklists, templates | `.sdlc/` (shared by both tools; read on demand) | same |

- **One copy per tool, rendered from one source.** Skill bodies are identical across tools. Only frontmatter differs.
- **`.sdlc/lock.json`** records the kit version, targets and the sha256 of every file written.
  - `sdlc check` reports drift: edited, missing or extra files. It exits non-zero, so it can run in CI.
  - `sdlc update` refuses to overwrite locally edited files unless `--force` is passed.
- **`.sdlc/config.json`** holds project overrides, which survive updates:
  - test, lint and build commands
  - spec numbering
  - tracker (`github` or `none`)
  - extra principles and checklist items
  - role → model map
  Skills read it, so repo specifics never get edited into kit files.
- **Managed blocks** use `<!-- BEGIN sdlc-kit -->` … `<!-- END sdlc-kit -->`. Text outside them is never touched. This is the same pattern `sync-agent-policy.py` already uses.
- **Spec numbering:** `sdlc next-spec` hands out the next free number. `sdlc check` flags duplicate prefixes. Existing duplicates are reported, not renamed.
- `sdlc uninstall` removes only files listed in the lockfile.

## 8. Fleet migration map (later, per repo, human-approved)

| Today | Becomes |
|---|---|
| `speckit-{specify,clarify,plan,tasks,analyze,implement,converge}` × 3 surfaces | kit skills of the same names (no `speckit-` prefix), 2 rendered surfaces |
| `speckit-checklist`, `speckit-taskstoissues`, `speckit-constitution` | `analyze` + checklist · `tasks --issues` · `setup` |
| `speckit-qa-*` (admin, storefront) | `modules/qa` |
| `create-implementation-issue` (Shop Standards) | `tasks --issues` + `templates/` issue body |
| `.claude/agents/<prefix>-*`, `.codex/agents/*`, `.github/agents/<prefix>-*` | `core/roles/*` rendered (`.codex` dropped while Codex is out of scope; **decision**) |
| AGENTS.md policy block (decision ladder, readiness gate, fail-fast, AIC) | `core/constitution.md` + principles + `implement`. AGENTS.md shrinks to repo facts + managed block |
| `docs/review-method.md`, `review-governance.md` | `review` skill + `references/review-method.md` (kept verbatim at first) |
| `doc-coauthoring`, `i-have-adhd`, `vercel-react-best-practices`, caveman lock | out of core; keep per repo if wanted (origin unverified) |

## 9. Decisions (resolved 2026-10-22: all recommendations accepted)

Build-time additions:
- All skills are prefixed `sdlc-`, and the router is `sdlc`. This avoids clashes with built-in commands such as `/review` and `/plan`, and with other skill packs.
- Copilot prompt shims were dropped (see §7).
- The exact rendering contract is in `adapters/RENDERING.md`.

The original decision list follows.

1. **Spec Kit CLI: replace or layer?** *Recommend replace.* The kit owns lean skills that write the same `specs/` layout, so there's no Python CLI and no 0.12.x drift. The alternative is to keep Spec Kit 1.2.2 as the engine and ship the kit as a Spec Kit preset and extension: less to write, but the verbose generated skills stay and it adds an upgrade dependency.
2. **Verdict vocabulary.** *Recommend* `APPROVED | REJECTED`, which matches the policy. Concerns go in an advisory section, so `PASS_WITH_CONCERNS` is retired.
3. **Codex / Antigravity:** out of scope now (your choice). The adapter design leaves room to add them back. `.codex/agents` and `.agents/skills` in the repos would then be unmanaged until an adapter exists.
4. **Home:** start as `~/Projects/sdlc-kit` (local git repo). Later it could move into `a shared standards repository`, which already syncs policy. Confirm, or name the owner.
5. **AIC:** keep the line and turn bounds and drop the token estimates. OK?

## 10. Build plan (after approval)

1. Scaffold the folders, constitution and principles.
2. Write the 16 skills, starting with the `sdlc` router, `grill`, `specify`, `tasks`, `implement`, `review` and `converge`, then the rest.
3. Write the checklists, templates and roles.
4. Write `bin/sdlc` (install, update, check, uninstall, next-spec; `verify` added by spec 004, with its logic in `bin/sdlc_verify.py`, and `gate` by spec 005 in `bin/sdlc_gate.py`), a skill linter and tests.
5. Validate: install into a scratch copy of a repo, run `check`, and verify both Claude and Copilot outputs load (frontmatter and paths).
6. Port the QA module.
7. Write the README. Keep the evals as written scenarios for now.

Estimated size: about 2.5–3.5k lines of markdown plus about 400 lines of Python and tests. It is one coherent deliverable, built phase by phase in this order.

## Sources

Spec Kit https://github.com/github/spec-kit (v1.2.2, 2026-10-19) · Böckeler critique https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html · BMad https://github.com/bmad-code-org/BMAD-METHOD, https://docs.bmad-method.org/plan/choose-a-planning-path/ · Matt Pocock https://github.com/mattpocock/skills · Addy Osmani https://github.com/addyosmani/agent-skills · pstack https://github.com/cursor/plugins/tree/main/pstack · Fleet inventory: `~/Projects/pilot-learning/governance/`.
Research was gathered by sub-agents from READMEs and docs. Counts and versions should be re-checked at build time.
