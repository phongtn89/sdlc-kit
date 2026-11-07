# sdlc-kit: plan to cover the missing layers

Date: 2026-11-03 · Owner: phong.ngo.vn · Status: **approved** by phong.ngo.vn on 2026-11-03 (in chat). Approval covers the plan as a whole; no story is started, and each **D** story still needs its decision before a spec · Track: T4 (initiative). Every story below becomes its own T2 change or T3 feature, with its own spec number from 004, and goes through the kit's own flow.

**Sources.** The three documents of 2026-11-03 in the pilot workspace (`.sdlc/onboarding/`): `agentic-workflow-comparison.md` (15 factors, the matrix, §5.3 sdlc-kit, §6.3 what the kit can take), `agentic-workflow-design-decisions.md` (the 10 decisions, the enforcement ladder, the golden-task recipe, §13 the next version of sdlc-kit), and `the pilot workflow canvas` (how the kit fits the pilot workspace's routes). Plus the kit's own evidence from specs 001–003 and the live check.

**Honest status of the inputs.** §13 of the design-decisions document is labelled *suggestions, not agreed decisions*. This plan turns them into stories, but each epic starts with a grill or an ADR before any spec is written (marked **D**).

## 1. What "missing layer" means here

The comparison scores sdlc-kit on 15 factors. Strong (●): intake, alignment, planning, context, human-in-the-loop, distribution, adoption. Partial or weak (◐ ○) are the layers this plan covers:

| Factor (matrix #) | Today | Gap to close | Epic |
|---|---|---|---|
| Entry point (§5.3 weakness 1) | The constitution says "start with `sdlc`"; the router has `disable-model-invocation: true` (`core/skills/sdlc/SKILL.md:5`). Evidence from the live check: three unnamed prompts loaded `sdlc-implement` or `sdlc-debug` directly and never `sdlc` | Router reachable without `/sdlc` | E0 |
| Verification (6), Bounded failure (10), Safety (9) | Rules are prose; budgets are self-reported; no hooks (`bin/sdlc` renders none); no CI gate on process artifacts | Move the top gates up the enforcement ladder (levels 3, 5, 6) | E1 |
| Independent review (7) | Verdict rules are strict. Roles are already read-only by tool allow-list (`bin/sdlc:271-274`: `tools: Read, Grep, Glob`), so the comparison's "not enforced" is **partly wrong**. The real gap: a reviewer cannot run a check; same model family as the implementer | Reviewer that can run allow-listed checks; model diversity | E2 |
| Observability (11) | Spec 003 records tokens and time per unit. No stage lead times, no gate pass rates, no aggregation | Typed events and a report | E3 |
| Workflow testability (15) | 19 scenarios at n=1 plus the live checks; Copilot never tested; "quality" is untested in all three systems | Golden-task set, n≥3, two models, a score that can regress | E4 |
| Execution (5), Autonomy (8) | Interactive only; `[P]` parallelism has no isolation; no autonomy dial; no route to an autonomous runner | Modes per route; worktree isolation; handoff | E5 |
| Ceremony (14), Artifacts (6 in the decisions doc) | T3 is ten steps; spec 001 was built before its value gate failed; analyze passes did not converge on spec 003 (34, 18, 24 findings) | Lighter path for small features; stop rules; value gate enforced | E6 |
| Learning loop (12) | `sdlc-retro` works by hand; one retro became a lint rule | Triggered, tracked, linked to evals | E7 |
| Distribution (13), lock-in (decision 10) | Strong for Claude; Copilot rendered but unverified; no LICENSE; internal names in `specs/` | Host capability matrix, release process, public readiness | E8 |
| "Missing in all three" | Nobody checks that the shipped feature met the need | Outcome check after ship | E9 |

## 2. Epics at a glance

| Epic | Outcome (how we know it is done) | Stories | Size | Wave |
|---|---|---|---|---|
| **E0 Foundations** | The router is reachable by plain language; the README states what is and is not supported; open loose ends from 002/003 closed or parked on purpose | 5 | S | 0 |
| **E1 Mechanical enforcement** | Every item on the "must never happen" list sits at ladder level 2 or higher on Claude Code; CI runs the same checks for every host | 7 | L | 1 |
| **E2 Review independence** | A reviewer can reproduce a failing check itself; the reviewer's model differs from the implementer's by configuration; a review record is machine-checked | 4 | M | 2 |
| **E3 Observability** | `sdlc report` shows stage lead time, gate pass rate and usage per feature, from typed events | 6 | M | 2 |
| **E4 Quality evals** | A kit change can be called better or worse by a score on a golden-task set (n≥3, two models), before and after | 6 | L | 2–3 |
| **E5 Orchestration and modes** | `[P]` tasks run isolated; autonomy is a per-track setting that the host enforces; a ready spec exports to an autonomous runner | 4 | L | 3 |
| **E6 Ceremony and artifacts** | A small T3 has a lighter documented path; analyze stops by rule; value gates are checked, not remembered | 4 | M | 3 |
| **E7 Learning loop** | Retro is triggered by evidence; every accepted lesson is a check, a template field or a skill step with an eval row | 4 | M | 4 |
| **E8 Portability and release** | A host capability table, a release process with a changelog, and a repository fit to share | 3 | M | 4 |
| **E9 Outcome verification** | A shipped feature has a dated check that it met its need; overdue checks are visible | 2 | S | 5 |

**Dependencies** (from the decisions document's map: route → control flow → enforcement → verification → tests, and metrics → tests):

```
E0 ──▶ E1 ──▶ E2          E3 (events) ──▶ E4 (needs usage + gates to score)
        │      │                │
        ▼      ▼                ▼
        E5 ◀── E6          E7 (learning) ──▶ E9
E8 spans all (host matrix feeds E1's rendering)
```

E3 can start next to E1, because spec 003 already exists. E4 needs E1's `verify`/`gate` (what to score) and E3's events (how to score cost). E5 and E6 need enforcement first.

## 3. Stories

Format: **ID** · story · acceptance (observable) · track and size (S ≈ one session, M ≈ 2–4, L ≈ a multi-lane T3) · depends on · ladder level or evidence. **D** = needs a grill or an ADR before the spec.

### E0 Foundations (wave 0)

**Progress 2026-11-04.** D decisions taken in chat: E0.1 model-invocable flag; E0.3 MIT and scrub internal names; E0.4 park. Done: E0.2, E0.3 (history still holds the old names), E0.4, E0.5 (text and tests). Live evals ran the same day (`evals/results/wave0-live.md`): E0.5 met (U2 3/3); E0.1 first failed (R6 `sdlc` first 0/6), then met after strengthening the router wording (R6 6/6, R7 6/6). Wave 0 is complete.

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E0.1 | As a user, I type a normal engineering request and the router runs without `/sdlc` **(D: model-invocable router, or a hook, or a thin always-loaded rule)** | Eval R6 at n=3 on two models: for a non-trivial prompt the first skill call is `sdlc`; for a one-line typo it is not. Lint keeps constitution and flag consistent | T2 · S · — | Eval; today `core/skills/sdlc/SKILL.md:5` contradicts `core/constitution.md:3` |
| E0.2 | As a maintainer, the README says which host is first-class and which is unverified | Support table (Claude Code: first-class; Copilot: rendered, not evaluated) and the three limits already found (transcript format is internal, `--resume` keeps the session id, no concurrency lock) | T0 · S · — | Reviewable text |
| E0.3 | As the owner, I can share the repository **(D: licence, and what to do with internal names in `specs/`, `docs/adr/`)** | A `LICENSE` file; either the specs are scrubbed of pilot internals or moved to a private branch; `sdlc install` into a clean repo does not copy them (already true) | T2 · S · owner decision | Checklist |
| E0.4 | As the owner, spec 002's evaluation (T014–T020) has a recorded outcome or an explicit parked status | `specs/002-…/tasks.md` shows either the gate result and decision, or `Status: parked (reason, date)`; README matches | T3 tail · M or S · needs pilot access | Gate from spec 002 SC-001/002 |
| E0.5 | As a user, `sdlc-debug` starts usage recording before the first reproduction | Eval U2 at n=3: `start` precedes the first run of the failing test; skill text updated test-first | T2 · S · — | Live-check follow-up 1 |

### E1 Mechanical enforcement (wave 1)

**Progress 2026-11-04.** E1.1 done: [ADR-0003](../adr/0003-enforcement-model.md) (opt-in `enforce`; v1 covers push on red, T3 edits without approval, ticks without evidence, reviewer cannot write). E1.2 done: spec 004 (`sdlc verify`, evidence record, merged 2026-11-04; SC-004 6/6). E1.3 done: spec 005 (`sdlc gate`: approved, approve, green-at-head, evidence-for-ticks; merged 2026-11-04). E1.4 built: spec 006 (the three Claude Code hooks behind opt-in `enforce`; independent review approved; live eval V2 on 2026-11-05 met SC-003, a push on red refused 6 times and a push on green allowed 2 of 2; awaiting the merge approval). E1.4 merged 2026-11-05. E1.5 done: spec 007 (template CI workflow `adapters/ci/sdlc-gates.yml`, two review passes, merged 2026-11-05). E1.6 done: spec 008 (`sdlc budget`, read-only, one review pass, merged 2026-11-05). E1.7 done: spec 009 (an end-to-end test per must-never-happen rule and a re-runnable mutation script, 46 mutations; three review passes; merged 2026-11-06). Wave 1 is complete. E2.1 is in progress: spec 010 (the reviewer may run the project's configured check commands, limited by the hook through `agent_type`; approved 2026-11-07, T001 to T004 of 15 done: the hook gate, the command match and the `checks` role key; nothing renders `Bash` into a role yet, so the feature is inert until T006; the live eval T014 is a hard merge gate and is still to do). Open follow-ups: four low test advisories (spec 009 review) and `gate approved` allowing source edits when an approved spec's `tasks.md` is deleted.

Starting list of "must never happen" (decisions §4): push on red · T3 edits without approval · ticks without evidence · budget overrun reported by the agent itself · reviewer able to write · untrusted text run as instructions.

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E1.1 | As a maintainer, an ADR fixes the enforcement model per host **(D)** | ADR with the ladder, the "must never happen" list with a target level each, and which levels each host supports (Claude: 2, 3, 5, 6; Copilot: 2, 5, 6) | ADR · S · E0.1 | — |
| E1.2 | As an agent, I run `bin/sdlc verify` and quote its result instead of claiming it | Runs the configured commands once, non-interactively; writes a JSON evidence record with exit codes and `HEAD`; the record is stale after the next commit; unit tests with a red and a green command | T3 · M · E1.1 | Level 5 |
| E1.3 | As a maintainer, `bin/sdlc gate <name>` checks readiness mechanically | Gates `approved` (the spec's `Approved` line **and** the digest of spec, plan and tasks recorded at approval, so edits after approval fail), `green-at-head`, `evidence-for-ticks` (every ticked task has evidence at a revision); exit 1 on failure so CI can use it | T3 · M · E1.2 | Level 5 (digest idea from the pilot workspace's triage) |
| E1.4 | As a Claude Code user, installing renders three hooks into `.claude/settings.json` | Opt-in switch `enforce` in `.sdlc/config.json`; hooks: block `git push` and `gh pr create` unless `gate green-at-head`; block edits under the source tree on T3 without `gate approved`; at `Stop` warn on ticks without evidence. Rendering is merge-safe with the project's own settings, hashed in the lock, removed by `uninstall`, tested with fake hook JSON | T3 · L · E1.3 | Level 3 |
| E1.5 | As a team, a CI recipe runs the same gates for any host | A template workflow running `sdlc lint`, `sdlc check`, `sdlc gate approved` and `green-at-head`; documented as the required-check route for Copilot | T2 · S · E1.3 | Level 6 |
| E1.6 | As a maintainer, budgets are computed, not self-reported | `bin/sdlc budget` reads `git diff --stat` at HEAD and the usage lines (E3) against `budget.*`; `sdlc-implement` calls it | T2 · S · E1.2 | Level 5 |
| E1.7 | As a maintainer, a "must never happen" test exists for every enforced rule | One test per rule that fails when the mechanism is removed (mutation-style, as done for spec 002 and 003) | T2 · M · E1.4 | Tests |

### E2 Review independence (wave 2)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E2.1 | As a reviewer role, I can run the project's allow-listed check commands but still cannot write **(D)** | Role rendering adds `Bash` limited to configured test and lint commands; eval: the reviewer reproduces a failing test it was told about; a write attempt is refused by the host | T3 · M · E1.1 | Level 2 |
| E2.2 | As an owner, the reviewer's model family differs from the implementer's by configuration | `models` default or lint warning when equal; documented trade-off; no behaviour change when unset | T2 · S · — | Lint |
| E2.3 | As a maintainer, a review record is validated | `bin/sdlc gate review <file>`: first line is exactly `VERDICT: APPROVED` or `REJECTED`; the reviewed revision is in the header; every rejection row has Correction, Reason and Verify | T2 · S · E1.3 | Level 5 |
| E2.4 | As a reviewer, finding ids trace to the fix | Fix lines carry the finding id (`review1-F3`, spec 003 already) and `gate` reports rejected findings without a fix line | T2 · S · E2.3, E3.2 | Level 5 |

### E3 Observability (wave 2; builds on spec 003)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E3.1 | As a maintainer, an ADR fixes the event schema **(D)** | Typed events modelled on Agentry's `stage.cost` and `gate.result`: stage start/end, gate result, usage line, verdict; append-only JSONL in `.sdlc/events.jsonl`; content-free; opt-in under the same switch family as `usage` | ADR · S · — | — |
| E3.2 | As a user, gates and usage emit events | `usage.py`, `verify` and `gate` append events; off means nothing written; tests as in spec 003 | T3 · M · E3.1, E1.2 | Tests |
| E3.3 | As a maintainer, `sdlc report <feature>` aggregates | Per feature: stage lead times, gate pass rate, rework count, usage totals (read-only; markdown and CSV) | T3 · M · E3.2 | Golden output test |
| E3.4 | As a maintainer, stage lead time exists from the first run | Timestamps for specify, plan, tasks, analyze, approval, implement, review, ship derived from events | T2 · S · E3.2 | Test |
| E3.5 | As a retro author, `sdlc-retro` reads the report | Skill input list names `sdlc report`; eval row | T2 · S · E3.3 | Eval |
| E3.6 | As a maintainer, spec 003's open advisories are closed | `~~~` and long fences, `usage off` before argparse errors, `start --at`, a test for the first-versus-last open line, pluralisation | T2 · S · — | Tests |

### E4 Quality evals (waves 2–3)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E4.1 | As an owner, a golden-task set exists **(D: which tasks)** | 10–20 tasks: base commit, task text, hidden tests; easy and hard, backend and UI, 3+ that should end in a question or a refusal; kept outside the target (leak check as in `evals/run.py`) | T3 · M · owner picks | Set frozen with a hash |
| E4.2 | As a maintainer, a batch runner scores runs | Extends `evals/run.py`: n≥3 per task, two models, hidden tests pass, gates pass, diff size vs the human PR, usage cost (E3), correct refusals; JSON and markdown results | T3 · L · E1.2, E3.2, E4.1 | Runner tests with a fake CLI |
| E4.3 | As a maintainer, a score regression is visible **before** a change merges | Baseline per kit version in `evals/results/`; a decision rule written before the first run (the spec 001 lesson): warn at −X points, fail at −Y | T2 · M · E4.2 | Rule in the spec |
| E4.4 | As a maintainer, today's 19 scenarios run at n=3 on two models | Variance recorded; deterministic rows marked; rows that fail on one model get an issue | T2 · M · E4.2 | Results file |
| E4.5 | As the owner, Copilot has a verdict **(D)** | Either an eval pass on the golden set, or the README says "rendered, not evaluated" and the host matrix (E8.1) shows it | T2 · S · E4.2 | Decision recorded |
| E4.6 | As a maintainer, a safety eval set runs per release | Injection in a ticket body, a secret in the environment, a cross-tenant write, a push on red; expected refusals per host | T2 · M · E1.4 | Results per release |

### E5 Orchestration and modes (wave 3)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E5.1 | As a maintainer, an ADR states the modes per route **(D)** | Interactive (default), planning-only, and "handoff to an autonomous runner" (the pilot workspace's routes; Agentry); what the kit owns in each and what it does not (it will not build a runner) | ADR · S · E1.1 | — |
| E5.2 | As a user, `[P]` tasks run isolated | With `isolate` on, each parallel task runs in its own worktree through a subagent; the merge step is explicit; usage overlap flags (spec 003) stay valid; test with a fixture repo | T3 · L · E1.4 | Level 2 and 5 |
| E5.3 | As an owner, autonomy is a per-track setting the host enforces | `autonomy.T0…T4` in config (`ask`, `confirm`, `auto`) rendered into permission settings (Claude) or documented limits (Copilot); eval per level | T3 · M · E1.4, E5.1 | Level 2 and 3 |
| E5.4 | As a lead, a ready T3 exports to an autonomous runner **(D: the pilot workspace `create-implementation-issue` shape)** | `bin/sdlc export <feature>` writes a runner-ready issue from spec, plan and tasks with the approval digest; round-trip test against a fixture schema | T3 · M · E1.3, E5.1 | Schema test |

### E6 Ceremony and artifacts (wave 3)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E6.1 | As an author, a small feature has a lighter path **(D: criteria)** | "T3-lite": spec with decisions and acceptance plus tasks; no separate plan unless a contract changes; criteria written in `sdlc` and the track table; measured on the golden set (E4) for first-pass rate, not by feel | T3 · M · E4.3 | Score |
| E6.2 | As a maintainer, `sdlc-analyze` stops by rule | Pass 1 full; later passes check only regressions and earlier HIGH items; a stop rule ("no CRITICAL, HIGHs fixed or accepted") is in the skill. Evidence: spec 003's three passes found 34, 18 and 24 | T2 · S · — | Eval row |
| E6.3 | As a maintainer, a value gate is checked | `gate value`: when a success criterion is a measured threshold, `plan.md` must hold the gate's result before `implement` (spec 001 lesson L3, until now only a template field) | T2 · S · E1.3 | Level 5 |
| E6.4 | As a reader, specs stay short and carry their decisions | Lint: a `Decisions` or `Clarifications` section is present; spec length cap with an override reason | T2 · S · — | Lint |

### E7 Learning loop (wave 4)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E7.1 | As a user, `sdlc-ship` prompts a retro when there was rework | Trigger when the report (E3.3) shows a rejected review or a failed gate; a skill step, not a hook | T2 · S · E3.3 | Eval row |
| E7.2 | As a maintainer, retro proposals are tracked | `docs/lessons.md`: id, source, status (open, accepted, rejected), the change that implements it; lint fails an accepted lesson that points at nothing | T2 · M · — | Lint |
| E7.3 | As an owner, specs 002 and 003 have retros | `specs/00N-…/retro.md` through `sdlc-retro`, with proposals entered in E7.2 | T2 · S · E7.2 | Files |
| E7.4 | As a maintainer, each accepted lesson has an eval row | Extends the spec 001 L1 lint ("each skill named by the constitution has an unnamed-prompt eval") to lessons | T2 · M · E7.2, E4.2 | Lint |

### E8 Portability and release (wave 4)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E8.1 | As an adopter, a host capability table exists | Per host: skills, roles, hooks, permissions, transcripts, usage; what the kit does where a capability is missing (ladder level reached) | T0 · S · E1.1 | Table |
| E8.2 | As a maintainer, releases follow a process | `CHANGELOG.md`; semver rules (what is a breaking change: contract formats, command names, section names); update notes for `sdlc update`; tags | T2 · S · — | Checklist in `sdlc-ship` |
| E8.3 | As an adopter, contributing is documented | `CONTRIBUTING.md`: the develop loop, how to propose a skill change (retro first), how to run evals | T0 · S · E0.3 | — |

### E9 Outcome verification (wave 5)

| ID | Story | Acceptance | Track · size · deps | Level / evidence |
|---|---|---|---|---|
| E9.1 | As an owner, a shipped feature has a dated outcome check | `pr.md` and `sdlc-ship` gain "outcome check: metric, owner, date"; `sdlc-retro` asks for the result | T2 · S · E7.1 | Template field (level 1) |
| E9.2 | As an owner, overdue checks show up | `docs/outcomes.md` index; `sdlc check` warns on overdue entries; SC-008 of spec 003 is the first entry | T2 · M · E9.1 | Warning |

## 4. Sequence and cadence

| Wave | Content | Exit criterion |
|---|---|---|
| 0 | E0 (all) | Router reachable at n=3; README and licence settled; 002 outcome recorded |
| 1 | E1.1 → E1.2 → E1.3 → E1.4, then E1.5–E1.7 | The three hooks refuse a push on red, a T3 edit without approval, and ticks without evidence, each proven by a test that fails when the hook is removed |
| 2 | E2, E3 in parallel with each other (different files), E4.1 starts | `sdlc report` runs on spec 003's own history; a reviewer reproduces a failing test |
| 3 | E4.2–E4.6, E5, E6 | A score for kit 0.6.0 and for the next kit; `[P]` isolation works on a fixture |
| 4 | E7, E8 | Every accepted lesson has an eval row; the first changelog release |
| 5 | E9 | Outcome checks tracked |

45 stories: 25 small (S), 17 medium (M) and 3 large (L: E1.4, E4.2, E5.2). At the pace of specs 002 and 003 (one T3 per several sessions) this is a quarter of work, not a sprint. Order inside a wave is by value per effort: E0.1, E1.2, E1.3 and E1.4 first.

## 5. Managing it

- **One epic = one T4 record** here, with a short ADR when its **D** story is decided. **One story = one spec folder** `specs/NNN-slug/` (T3) or a mini-spec in the PR (T2), numbered by `bin/sdlc next-spec`. The story id goes in the spec header (`Story: E1.3`).
- **Status** per story: `idea → grilled → specified → analyzed → approved → building → reviewed → shipped → verified`. The last state is E9's outcome check. Keep the table in `docs/roadmap/status.md` (one line per story: status, spec number, revision, date) or mirror epics and stories into Jira with the same ids.
- **Definition of ready:** acceptance is observable, the dependency stories are shipped, and a **D** story has its ADR. **Definition of done:** the kit's own (tests green, lint ok, independent review APPROVED, evals recorded, docs updated) plus, from E1 on, `bin/sdlc gate` green.
- **WIP limit:** one T3 building at a time per owner (the kit's own history: parallel T3s were not tried; spec 002 and 003 ran with one implementation each). Stories marked S can interleave.
- **Cadence:** a wave ends with a review of this plan: re-score the matrix, reorder, drop stories whose evidence moved. Measure with E3 once it exists; until then with `evals/results/`.
- **Rule from specs 001–003:** write the decision rule for any measured criterion before the first run (E4.3, E6.1), and run analyze with the stop rule of E6.2.

## 6. Decisions the owner must make (the **D** items)

1. **E0.1** How the router becomes reachable: model-invocable flag, a hook, or a thin always-loaded rule. Trade-off: the flag may trigger the router on trivial prompts.
2. **E0.3** Licence, and whether `specs/` and `docs/adr/` stay public.
3. **E0.4** Run spec 002's pilot evaluation, or park it.
4. **E1.1** Which "must never happen" items are in scope for v1 of enforcement, and whether `enforce` is opt-in (recommended).
5. **E4.1** Which closed tickets form the golden set, and who may see the hidden tests.
6. **E4.5** Copilot: evaluate or declare unverified.
7. **E5.1 / E5.4** Whether the kit exports to an autonomous runner at all, and which schema.
8. **E6.1** Criteria for a lighter T3.

## 7. Risks

| Risk | Handling |
|---|---|
| Hooks are host-specific; Copilot has no equivalent | Level 6 (CI) is the common floor; the host table (E8.1) says what each host gets; the kit never pretends parity |
| Transcript and hook formats are internal to Claude Code | Pinned fixtures plus a re-check row on a major version (spec 003's UR1); `not available` instead of wrong |
| Enforcement frustrates users | `enforce` is opt-in; every block prints the gate and the command that clears it |
| Golden set leaks into agents | Same leak check as `evals/run.py`; set kept outside targets and hashed |
| Scope creep into a runner | E5.1 states the kit does not build one; it exports |
| The plan outruns its evidence (spec 001's failure) | Value gates and decision rules before the first run; E4 score decides E6.1 |

## 8. Corrections to the comparison documents

- §4 row 7 and §5.3 say reviewers are "read-only and not enforced". In the code, `bin/sdlc` renders `tools: Read, Grep, Glob` (Claude) and `tools: ['read', 'search']` (Copilot) for every role with `access: read-only` (`bin/sdlc:271-280`), so read-only is enforced by the host's tool allow-list. The remaining gap is that the reviewer cannot run checks (E2.1).
- The comparison was written at kit `e2f0e19` (v0.5.0, spec 003 a draft). At 0.6.0 spec 003 is shipped, so factor 11 moves from ○ to ◐ (usage per unit exists; no aggregation or stage times).
- The live check found the entry-point problem is real in practice: U1–U3 never loaded `sdlc`.
