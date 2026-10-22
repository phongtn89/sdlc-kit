---
name: sdlc-qa-plan
description: "Derive manual and automatable test cases, entry and exit criteria, and an execution order from an approved spec into testcases/<NNN-slug>/test-cases.md. Use when a spec is approved and QA needs a test scope, or the user says \"qa plan\", \"test cases\", or \"what should QA test\"."
user-invocable: true
---
# sdlc-qa-plan

Turn an approved spec into a QA-owned set of traceable test cases. QA artifacts sit beside dev artifacts; they never edit them.

## When to use

- A T3 spec (or a T2 mini-spec in `specs/NNN-slug/spec.md`) is approved and needs a QA test scope.
- The spec changed and the existing test cases must be brought back in line.
- Not for: checking requirement quality (that is `sdlc-analyze` with `.sdlc/checklists/requirements-quality.md`); writing automated tests (that is `sdlc-qa-automate`).

## Inputs

- `specs/NNN-slug/spec.md` (required, status approved). The spec directory comes from `.sdlc/config.json` → `spec_dir`.
- `specs/NNN-slug/plan.md` and `contracts/` (optional): read only entry points, affected consumers and endpoints. Ignore architecture and code paths.
- Existing `testcases/NNN-slug/test-cases.md`, if any.
- The template `.sdlc/templates/test-cases.md`.
- User-supplied facts: environment, approver, test data. Nothing else is a source.

## Process

1. Resolve the target. If no spec is named, list the spec folders and ask. If the spec is not approved, stop and say so.
2. If `testcases/NNN-slug/test-cases.md` exists and has any checked box or filled Result or Decision, stop and ask before changing it; then update only the affected cases.
3. Read the spec. Capture each scenario (S#, priority, actor, Given/When/Then), requirements, non-functional items, success criteria and edge cases.
4. Derive cases per scenario, P1 first:
   - one case per acceptance step, keeping the spec's wording;
   - at least one negative case per scenario, only from behaviour the spec states;
   - a cross-tenant denial case for every scenario that touches tenant-scoped data;
   - edge, non-functional and success-criteria cases mapped to their FR/NFR/SC IDs.
5. Trace every case to an S# or requirement ID. Report any requirement with no case.
6. Classify each case `automatable` (an existing suite can drive it end to end and assert observable state) or `manual`, with a one-line reason when manual.
7. Add cross-scenario regression cases only where the spec or plan names an interaction between scenarios.
8. Fill entry criteria, test data, execution order and exit criteria from the template. Unknown facts become `[ACTION REQUIRED: not supplied]`; never assume an environment or approver.
9. Write `testcases/NNN-slug/test-cases.md`. Never write under the spec directory.
10. Report: file path, case counts by priority and type, uncovered requirements, and every `[ACTION REQUIRED]` left.

## Rationalizations

| Excuse | Reality |
|---|---|
| "The spec obviously implies this error message." | If the spec does not state it, the tester cannot fail it. Write `[ACTION REQUIRED]` and send the gap to `sdlc-clarify`. |
| "Happy paths are enough for a first pass." | A scenario with no negative case cannot catch the most common defects. Add one per scenario. |
| "Tenant isolation is a dev concern." | Cross-tenant leaks are the costliest defect class; one denial case per tenant-scoped scenario is cheap. |
| "I'll just fix the spec wording while I'm here." | QA reads specs and never writes them. Route changes through `sdlc-clarify`. |
| "Regenerating is faster than merging." | Overwriting recorded results destroys test evidence. Update only affected cases. |

## Red flags

- The spec is draft or has open `[NEEDS CLARIFICATION]` on a P1 scenario → stop; ask for approval or clarification first.
- A case has no S#/FR trace → delete it or find its source.
- You are about to write under the spec directory → stop.
- More than a third of fields are `[ACTION REQUIRED]` → report that the spec is not ready for QA rather than padding.
- The file has recorded results and you are regenerating it → stop and ask.

## Verification

- `testcases/NNN-slug/test-cases.md` exists and follows `.sdlc/templates/test-cases.md`.
- Every scenario has at least one positive and one negative case; tenant-scoped scenarios have a denial case.
- Every requirement ID is traced by at least one case, or listed as uncovered in the report.
- `git status` shows no change under the spec directory.
- Report lists the open `[ACTION REQUIRED]` items.

## Principles applied

- evidence-over-claims: cases trace to spec text; unknowns are labelled, not guessed.
- agree-before-building: gaps go back through `sdlc-clarify`.
- thin-vertical-slices: cases grouped by scenario, P1 first, each runnable alone.
- guard-context: read only the spec sections and plan facts QA needs.
