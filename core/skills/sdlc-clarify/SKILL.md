---
name: sdlc-clarify
description: "Resolve the open questions in a draft spec with at most 5 targeted questions and write each answer back into the spec. Use after sdlc-specify when [NEEDS CLARIFICATION] markers or material ambiguities remain, or when the user says 'clarify'."
argument-hint: "Path of spec.md (defaults to the active spec)"
user-invocable: true
---

# sdlc-clarify: close the gaps that matter

## When to use

- A draft `spec.md` has `[NEEDS CLARIFICATION]` markers, or an ambiguity that would change architecture, data, tests, security or the task split.
- Before `sdlc-plan`. If the user explicitly skips it, record that the ambiguity risk was accepted.
- Not for wording polish or preferences.

## Inputs

- The active `spec.md` (the newest `spec_dir/NNN-*/` with status `draft`, unless a path is given).
- `.sdlc/checklists/requirements-quality.md`, glossary, ADRs.

## Process

1. **Scan** the spec against the requirements-quality checklist. Collect the candidates: explicit markers, vague words ("fast", "secure", "intuitive"), missing failure behaviour, unclear data ownership, scenarios with no acceptance check.
2. **Rank** by impact × uncertainty. Drop anything the repo answers (resolve those yourself and cite `path:line`) and anything that wouldn't change the plan.
3. **Ask at most 5 questions, one at a time**, using the `sdlc-grill` format: why it matters, 2–4 options, your recommendation first. Accept "use your recommendation".
4. **Write back after every answer**, so a session cut off midway loses nothing:
   - Under `## Clarifications` → `### Session YYYY-MM-DD`, add `- Q: … → A: …`.
   - Edit the affected FR, scenario or success criterion so it says what was agreed. Remove the resolved marker.
   - Add any new term to the glossary section.
5. **Stop** after 5 questions or when nothing material remains. Anything left becomes an *Assumption* or stays as a marker with an owner.
6. **Report**: the questions asked, the sections changed, the remaining markers, and a recommendation: `sdlc-plan`, or another clarify round with the stakeholder named.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Ask all five at once" | Later questions depend on earlier answers. One at a time. |
| "I'll write the answers up at the end" | A session interrupted midway loses every answer. Write back each one immediately. |
| "Ask about naming and formatting" | Spend the 5-question budget only on decisions that change the plan. |
| "No markers, so skip clarify" | Vague words and missing failure cases are ambiguity even without markers. Scan first. |

## Red flags

- An answer contradicts another FR or an accepted ADR. Raise it, and don't continue until it's resolved.
- The user defers every question. Keep `Status: draft`, put the blocker and the stakeholder under *Open questions*, and don't plan on guesses.
- The answers expand scope beyond the intent. Suggest splitting it into a second spec.

## Verification

- Every asked question appears under *Clarifications* with its answer, and the affected requirement text changed to match.
- The marker count went down, and the remaining ones have an owner.
- At most 5 questions were asked in this session.

## Principles applied

agree-before-building, evidence-over-claims
