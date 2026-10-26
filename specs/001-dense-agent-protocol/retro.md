# Retro: spec 001, Dense Agent Protocol

Date: 2026-10-26 · Kit `main` @ `ff92d5a` · Status: **proposals, none applied** · Owner decision needed: phong.ngo.vn

Inputs: `tasks.md` (Progress log, Convergence, Review fixes, Hand-run fixes, D4 result), `review.md`, `evidence/s1-tracer.md`, `~/Projects/shop6-evals/dense/results.md`, `evals/results/0.5.0.md` (D9).

## Events

| # | Event | Evidence |
|---|---|---|
| E-a | The rule "open only the sections the index points to" was ignored: the agent grepped whole documents | `evidence/s1-tracer.md:29` (F-S1.2, Run A) |
| E-b | The same rule was followed once it became a command, `dap.py show <alias#slug>` | `evidence/s1-tracer.md:105` (Run A2); `tasks.md` R004–R007 |
| E-c | FR-009 "read the index after `fresh` exit 0" ignored in M3 and M4; FR-010 "cite sources, not index entries" broken in M2; `show` called without its argument in M5 | `results.md` rows E2–E5 dense |
| E-d | The review rule ("verdicts are exactly `APPROVED` or `REJECTED`") was ignored in both D4 arms. E6 didn't name the skill, so no Skill call; the first lines were `**Verdict: REJECTED**` and `**REJECTED.**`. E5 said "using this workspace's review rules" and passed | `results.md` rows E5, E6 |
| E-e | The same review rule passed once it named the skill and the exact line: D9 on `fa1abab` passes, control on `dacab66` fails | `evals/results/0.5.0.md` |
| E-f | The evaluation task set leaked: the first baseline E1 run found it inside the workspace with a grep | `tasks.md` progress log (D4 task set); `results.md` row E1 `37603299…` |
| E-g | E4 baseline was asked in the E3 session, so the run was invalid | `results.md` row E4 `880a6918…` |
| E-h | Run B's prompt was pasted twice; E1 dense had a second message typed (not sent) | `evidence/s1-tracer.md:33`; `results.md` row E1 dense |
| E-i | This retro's session: while D9 ran in the background, the agent wrote a "task completed" notice itself and began reading a partial transcript. It caught this before grading | this session (2026-10-26), D9 run `55fe5c29…` |
| E-j | The whole module was specified, built, reviewed and hand-run (T001–T025, R001–R008) before the value gate was measured. The gate then failed on SC-002 (−17% vs −50%). The per-task breakdown shows only routing tasks (E2) could gain, which the task mix alone predicts | `tasks.md` "D4 result"; `results.md` per-task line |
| E-k | T009 was written after T008 and never seen RED (mutation checks compensated); T021 failed first on a spec wording gap; lint was red between T005 and T008 | `tasks.md` progress log (T009, T021, T005) |

## Causes and proposed changes

| Lesson | Evidence | Proposed change (cheapest durable) | Where | Cost |
|---|---|---|---|---|
| **L1. A behaviour rule works only when it names the exact action, and only an unnamed-prompt eval shows it** | E-a–E-e: 3 prose rules ignored, 2 fixed by naming a command/skill (both verified) | (1) **Eval rows**: for each always-loaded rule that should trigger a skill, one row whose prompt doesn't name the skill (the D9 pattern). First candidates: the router (`sdlc` on "fix this bug: …" without `/sdlc`) and the principles citation. (2) **Authoring rule** in `adapters/RENDERING.md` → Managed blocks: "A rule that asks for an agent action names the skill, command or file that performs it; a rule without one is a fact, not an instruction." (3) A lint check is **not** proposed: FR-009 named `fresh` and was still ignored, so a backtick check would pass bad rules | kit: `evals/scenarios.md`, `adapters/RENDERING.md` | S |
| **L2. Hand-run evals get contaminated unless one process runs one task** | E-f, E-g, E-h, E-i (4 invalid or nearly invalid runs) | **Automated runner** `evals/run.py <task-file> <target-dir>`: refuses when the task file is under the target (leak check), runs one `claude -p` per task in the foreground with `--output-format stream-json`, saves the transcript, and prints session id, model, tool calls, first line of the answer, `git status` of the target. `scenarios.md` method line points at it. Tests: leak refusal and output parsing on a recorded transcript (no live CLI in tests) | kit: `evals/run.py`, `tests/`, `evals/scenarios.md` | M |
| **L3. Test the value hypothesis before building** | E-j (a full T3 built, then rejected) | **Template field** in `core/templates/plan.md` → Rollout & rollback: "Value gate (only when a success criterion is a measured threshold): the cheapest measurement you can run before implementing (e.g. the baseline arm plus the task-type mix), its kill threshold, and its result." `sdlc-analyze` flags it when an SC is a threshold and the field is empty. Not a new mandatory gate: it only asks for the measurement where the spec already has one | kit: `core/templates/plan.md`, `core/skills/sdlc-analyze/SKILL.md` | S |
| L4. Test-after and interim red lint | E-k (one occurrence each, caught by mutation checks and the next task) | **No change.** Single occurrences, already caught by existing structure; a rule would cost more attention than it saves | — | — |

## Implementation notes (2026-10-26, branch `feat/retro-001-lessons`)

- **Scope change, confirmed by phong.ngo.vn 2026-10-26 (L1):** the change adds an `sdlc lint` rule. It checks that an *eval row exists* for each skill the constitution names (prompt doesn't name it, Expect says ``Loads `<skill>` ``); it does **not** check rule wording, so the rejected backtick check stays rejected. Rows R6 (`sdlc`) and D10 (`sdlc-converge`) were added to satisfy it; D9 covers `sdlc-review`.
- **L2 runner differs from the proposal:** files changed are found by content hashes, not `git status` (git can't see a further edit to an already-uncommitted eval diff), plus a HEAD check for commits. Review F1 (timeout crashed the runner) fixed test-first: a timed-out run keeps its transcript, reports changes and exits 3.
- **Review:** `sdlc-reviewer` REJECTED (F1), then APPROVED after the fix. Its advisories applied afterwards: `killpg` tolerates an already-exited group, output decodes with `errors="replace"`, the timeout branch prints the stderr tail.
- **Live runner evidence (real `claude` CLI, Sonnet 5.5, D9 scratch repo):** sessions `d9c9a734…` and `04bc3ab4…` loaded `Skill sdlc-review` first, opened with `VERDICT: REJECTED`, left the target unchanged, and exited 0. A forced `--timeout 5` run exited 3 with `NO RESULT: timed out after 5 s` and left no `claude -p` process running. It also showed that the CLI waited for the inherited stdin. That is fixed test-first: the CLI now gets `stdin=DEVNULL` (`test_cli_gets_no_stdin`, RED then GREEN). Suite: 74 OK; lint ok.
- **Open advisories (review of the branch):** the leak scan skips symlinked dirs, `.git`, files > 2 MB and escaped prompts; the lint parser assumes 3-column tables and no `|` inside prompt cells. Acceptable today; revisit if they bite.

## What worked (keep)

- **Independent review found real defects.** `sdlc-reviewer` rejected `aac72f1` with F1 (a truncated index replaced the good one) and F2 (missed key formats), both reproduced, fixed test-first and re-approved (`review.md`).
- **Converge caught plan/code drift before review** (C001 path confinement, C002 personal data; `tasks.md` Convergence).
- **A decision rule fixed before the measurement.** The D4 gate and the "uninstall on fail" step were written down before any run, so the rejection was quick and clean (shop6 `b83e1bf`, byte-identical files).
- **A control arm.** D9 against `dacab66` showed that the fix, not an easier prompt, changed the outcome.

## Scope

All three proposals are kit changes (they help any project). No shop6 project-config change is proposed. No installed files were edited.

## Next

On approval, each accepted proposal becomes its own T2 change in the kit, test-first: L3 (template + analyze), L1 (authoring rule + eval rows), then L2 (runner).
