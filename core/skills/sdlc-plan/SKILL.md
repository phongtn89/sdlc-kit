---
name: sdlc-plan
description: "Turn an approved spec into a technical plan (plan.md plus, only when needed, research.md, data-model.md, contracts/, ADRs): seams, blast radius, alternatives, failure modes, test strategy, rollout. Use after sdlc-clarify for T3 features, or when the user says 'plan this' or 'how should we build it'."
argument-hint: "Path of spec.md (defaults to the active spec)"
user-invocable: true
---

# sdlc-plan: decide how, at the real seams

## When to use

- T3, once `spec.md` has no blocking markers.
- When the architecture of an existing feature changes. Update its `plan.md` and add an ADR.
- Not for T0–T2. Their design fits in the mini-spec or the PR description.

## Inputs

- `spec.md`, `.sdlc/constitution.md`, `.sdlc/config.json`, `AGENTS.md`, ADRs, glossary.
- `.sdlc/templates/plan.md` and `.sdlc/templates/adr.md`.
- Checklists, loaded only when triggered: `.sdlc/checklists/security.md`, `.sdlc/checklists/observability.md`, `.sdlc/checklists/performance.md`, `.sdlc/checklists/compatibility-migration.md`, `.sdlc/checklists/accessibility.md`.

## Process

1. **Read the seam, not the repo.** For each scenario, find the entry point and trace its callers and consumers: graph tools if available, otherwise bounded search. Delegate wide sweeps to `sdlc-explorer`. Record the blast radius: modules, contracts (APIs, events, schemas, SDKs), migrations, other repos, with `path:line`.
2. **Inventory what exists.** List the types, schemas, helpers and dependencies the solution can reuse. Read `.sdlc/principles/subtract-before-adding.md`. Canonical contracts owned elsewhere are imported, never re-declared.
3. **Compare approaches.** Write a table of 2–3 credible options: how each meets the FRs, risk, cost, compatibility. Pick one and say why. Put a hard-to-reverse choice in an ADR (`docs/adr/NNNN-*.md`, status `proposed`).
4. **Fill `plan.md`** from the template, keeping each section only if it earns its place:
   - Technical context: runtime, dependencies, storage, test tooling, constraints. Unknowns become `research.md` items, resolved before tasks.
   - Constitution check: every principle passes, or the violation is justified under *Complexity justifications*.
   - Failure modes: timeouts, retries, idempotency, concurrency, partial failure, replay, ordering, rollback. Cover only the cases that can actually occur.
   - Security and observability: run the triggered checklists and note the outcomes.
   - Test strategy: the test seam for each scenario (public interface), the RED command for each, and the integration or e2e boundary where mocks can't prove the behaviour.
   - Rollout and rollback: order of deploy across services, flags, the migration expand/contract steps.
5. **Contracts and data, only if the feature changes them.** Write `data-model.md` (entities, ownership, invariants, state transitions) and `contracts/` (request, response and event shapes, error cases, versioning). If the contract lives in another repository, the plan names that dependency and its owner. Don't fork it locally.
6. **Size it.** Estimate the changed lines and the seams against `.sdlc/config.json` → `budget`. Above `reassess_lines`, simplify first. Split only into deliverables that are independent (separate owner, repo or risk), never into "code now, tests later".
7. **Report**: the plan path, the chosen approach in 2 lines, any ADRs drafted, open research items, size estimate, and the next step `sdlc-tasks`.

## Rationalizations

| Excuse | Reality |
|---|---|
| "I know the codebase, skip tracing callers" | Most regressions come from consumers nobody traced. Trace them and cite them. |
| "One option is obviously right" | Then the comparison takes two lines. Writing it down catches the times it isn't. |
| "Add an abstraction for future needs" | Speculative extension points are complexity you pay for now. Use the decision ladder. |
| "Define our own copy of the DTO" | Parallel contract types drift. Import the canonical schema, or record the missing dependency. |
| "Failure modes are an ops problem" | Retries, idempotency and partial failure are design decisions. Make them here or debug them in prod. |

## Red flags

- The plan needs a change in another repository's contract. Record the dependency and its owner. Consider T4.
- Research items are still open but tasks are about to be written. Resolve them first.
- The constitution check fails without a justification.
- The size estimate is far above budget and no simplification has been tried.

## Verification

- Every FR in the spec maps to a part of the plan.
- The blast-radius list cites real paths, and consumers were checked.
- The test strategy names a seam and a RED command for each P1 scenario.
- The triggered checklists were run, with outcomes recorded.
- No open research items remain, or they are listed as blocking with an owner.

## Principles applied

subtract-before-adding, depth-follows-risk, evidence-over-claims, guard-context
