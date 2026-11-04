---
name: sdlc-analyze
description: "Read-only consistency gate across spec.md, plan.md and tasks.md before implementation: requirement quality, coverage, contradictions, constitution violations, terminology drift. Reports findings; edits nothing. Use after sdlc-tasks and before asking for implementation approval, or when the user says 'analyze' or 'check the spec'."
argument-hint: "Feature folder (defaults to the active feature)"
user-invocable: true
---

# sdlc-analyze: test the requirements before the code

## When to use

- T3, after `sdlc-tasks` and before the human approval gate.
- Again after any material spec or plan edit.
- **Read-only.** It reports; fixes happen in the owning skill (specify, plan, tasks).

## Inputs

- `spec.md`, `plan.md`, `tasks.md`, plus `data-model.md` and `contracts/` if present.
- `.sdlc/constitution.md`, `.sdlc/checklists/requirements-quality.md`, glossary, ADRs.

## Process

1. **Build the traceability table**: FR / SC → scenario → plan section → task IDs.
2. **Run the passes** and record each finding with an ID (`A1…`), a severity, and its location (`file:line` or ID):
   - **Coverage**: an FR with no task; a task with no FR or plan item; an SC with no verification.
   - **Consistency**: the spec, plan and tasks disagree (names, counts, behaviour, data shapes); terms are used differently from the glossary.
   - **Quality**: run the requirements-quality checklist over the spec (vague, unmeasurable, untestable or missing failure cases).
   - **Constitution**: a principle is violated without a justification (layer-phased tasks, tests deferred, speculative abstraction, unverified steps).
   - **Feasibility**: a verify step that can't run; a blocked-by cycle; `[P]` tasks with overlapping files; unresolved research; an SC that is a measured threshold while plan.md's Value gate is missing or has no result (HIGH: the value is untested before building).
   - **Conflicts**: contradiction with an accepted ADR, `AGENTS.md`, or another spec that owns the same capability (search `spec_dir`).
3. **Severity**:
   - CRITICAL: a constitution violation, a missing P1 coverage, or a contradiction that blocks implementation.
   - HIGH: wrong or ambiguous behaviour likely.
   - MEDIUM: quality gap.
   - LOW: wording.
   Don't inflate.
4. **Report** in chat (write nothing to disk before approval): the findings table (at most 40 rows; aggregate the rest), the coverage percentage, and the counts by severity. For each finding, give the **smallest fix** and which skill applies it.
5. **Gate**: with any CRITICAL finding, recommend fixing before approval. With none, list what the human approver should check, then ask for approval to run `sdlc-implement`.
6. **Record approval**: only after the human's explicit approval in chat, run `python3 <kit_path>/bin/sdlc gate approve . --spec <NNN> --by "<name>"` (`kit_path` from `.sdlc/lock.json`; the name is the one the human gave; add `--repo <repo>` in a workspace) and quote its PASS line. It sets `Status: approved` and writes the `Approved` line with a digest of the spec, plan, tasks and contracts. This is the only edit this skill makes. If any of those documents is edited afterwards, the approval no longer holds: ask the human and run `approve` again.

## Rationalizations

| Excuse | Reality |
|---|---|
| "I wrote all three files, they're consistent" | The author is the worst checker. Run the passes anyway. |
| "Just fix the findings while analyzing" | Silent fixes skip the owning skill's checks and erase the audit trail. Report, then fix via specify, plan or tasks. |
| "Everything is HIGH to be safe" | Inflated severity hides the real blocker. Calibrate. |
| "Approval is a formality, skip asking" | Human approval before implementation is the T3 contract. Ask. |

## Red flags

- The same capability is owned by another spec. Raise it as a CRITICAL conflict and stop.
- Coverage of P1 is below 100%.
- Analysis needs code changes to resolve. You're in the wrong phase.

## Verification

- The traceability table covers every FR and SC.
- Every pass ran. If a pass found nothing, say so.
- No files were modified (`git status` unchanged by this skill), apart from the approval line once the approval was given.
- The approval request lists the open non-critical findings.

## Principles applied

evidence-over-claims, agree-before-building
