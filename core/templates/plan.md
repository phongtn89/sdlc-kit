# Plan: [Feature name]

Spec: [spec.md](spec.md) · Status: draft · Created: [YYYY-MM-DD]

<!-- HOW the approved spec will be built. Every section must change a decision or a test; delete anything that only restates the spec. -->

## Summary

<!-- 2–4 sentences: the chosen approach and the riskiest part. -->

## Technical context

<!-- Facts that constrain the design. Write NEEDS CLARIFICATION rather than guess. -->

- Language / runtime:
- Key dependencies:
- Storage:
- Testing:
- Target (service, app, package):
- Constraints (performance, compliance, platform):

## Constitution check

<!-- One row per principle that this plan touches. "justify" rows must appear under Complexity justifications. -->

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | | |
| thin-vertical-slices | | |
| prove-it-works | | |

## Seams & blast radius

<!-- Where the change lands and who is affected. Read the callers; do not guess. -->

- Seams (path:symbol):
- Callers / consumers affected:
- Contracts touched (API, event, SDK, schema):
- Migrations:

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A | | | chosen |
| B | | | rejected because |

## Data model / contracts (optional — delete if N/A)

<!-- Point to data-model.md and contracts/ instead of inlining them. -->

- [data-model.md](data-model.md)
- [contracts/](contracts/)

## Failure modes

<!-- Only the ones that can occur. For each: what happens and how the design handles it. -->

| Failure | Handling |
|---|---|
| Timeout / dependency down | |
| Retry / duplicate request (idempotency) | |
| Concurrent update | |
| Partial failure mid-operation | |
| Rollback of a bad release | |

## Security & observability

<!-- Load .sdlc/checklists/security.md and .sdlc/checklists/observability.md (plus performance, compatibility-migration, accessibility where relevant). List only the items that need design decisions. -->

- Checklists loaded:
- Decisions:

## Test strategy

<!-- Agree the seam for each test before writing it. RED commands must fail before implementation. -->

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| | | unit / integration / e2e | |

## Rollout & rollback

- Rollout order / flags:
- Rollback steps:

## Complexity justifications (only if a principle is violated)

| Principle | Why it is violated | Simpler option rejected because |
|---|---|---|
