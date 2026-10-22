---
name: sdlc-specify
description: "Create or update a feature specification (what and why, no implementation) in specs/NNN-slug/spec.md. Use for T3 features, when the user says 'spec this' or 'write a spec', or when requirements for existing behaviour change."
argument-hint: "Feature description, or the path of the spec to update"
user-invocable: true
---

# sdlc-specify: the requirements contract

## When to use

- T3 features, and each feature split out of a T4 PRD.
- An existing behaviour's requirements change. **Update its owning spec**; don't create a parallel one.
- Not for T0–T2. T2 uses `.sdlc/templates/mini-spec.md` inside the PR or issue.

## Inputs

- The feature description (`$ARGUMENTS`) and any `sdlc-grill` outcome.
- `.sdlc/config.json` → `spec_dir` (default `specs`).
- Existing specs. Search `spec_dir` for the same capability first.
- The glossary and ADRs.
- `.sdlc/templates/spec.md`, `.sdlc/checklists/requirements-quality.md`.

## Process

1. **Find the owner.** Search existing specs for this capability (titles, FR text, glossary terms).
   - If one owns it, update that spec and bump its status back to `draft`.
   - If two specs overlap, report the overlap before writing anything.
2. **Number it.** Run `sdlc next-spec .` if the kit CLI is available. Otherwise take the highest `NNN-` prefix in `spec_dir` and add 1. Never reuse a number. Slug: 2–4 kebab-case words. Create `spec_dir/NNN-slug/spec.md` from the template.
3. **If the intent is still fuzzy**, run `sdlc-grill` first. Don't paper over gaps with prose.
4. **Write what and why only.** No frameworks, endpoints, tables or class names. Those belong in `plan.md`.
   - User scenarios: Given/When/Then, prioritised P1/P2/P3. Each one can be tested and shipped on its own, so P1 alone is a viable slice.
   - Requirements `FR-001…`: one testable behaviour each, using MUST / MUST NOT (SHOULD only for non-blocking preferences).
   - Success criteria `SC-001…`: measurable and technology-agnostic.
   - Out of scope, assumptions, dependencies (other teams, repos, external services).
5. **Mark unknowns honestly.** Use at most 3 `[NEEDS CLARIFICATION: question]` markers, only for decisions that change scope, security or the user experience. Take reasonable defaults for everything else and list them under *Assumptions*.
6. **Self-check** against `.sdlc/checklists/requirements-quality.md`. Fix what you can. Leave unresolved items as clarification markers.
7. **Report**: the spec path, the scenario count by priority, the open markers, and the next step (`sdlc-clarify` if markers remain, otherwise `sdlc-plan`).

## Rationalizations

| Excuse | Reality |
|---|---|
| "Mention the tech, it saves the planner time" | Tech in a spec locks a design before anyone has compared alternatives. Put it in the plan. |
| "A new spec is cleaner than editing the old one" | Parallel specs are how this fleet ended up with duplicate numbers and conflicting requirements. Update the owner. |
| "List every edge case" | List the ones that change behaviour. Exhaustive prose is the main complaint against spec-driven work. |
| "Ten clarification markers to be safe" | Each marker is a question for a human. Keep three that matter and assume the rest, visibly. |
| "Success = feature works" | That can't be measured. Write it as a number, a time or a user-visible outcome. |

## Red flags

- The capability is already specified in another repo's specs. This is cross-repo: re-route to T4 or confirm ownership first.
- You can't write a P1 scenario that's testable on its own. The scope is wrong; grill again.
- A requirement contradicts an accepted ADR or `AGENTS.md`. Stop and surface it.

## Verification

- `spec.md` exists at a unique `NNN` prefix, and nothing else in `spec_dir` shares that prefix.
- Every FR maps to at least one scenario, and every scenario has an acceptance check.
- The requirements-quality checklist was run. Remaining gaps are listed as markers or assumptions.
- No implementation detail appears in the spec. A grep for framework names and endpoints finds nothing.

## Principles applied

agree-before-building, depth-follows-risk, thin-vertical-slices
