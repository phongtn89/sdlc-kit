---
name: sdlc-grill
description: "Interview the user one question at a time until every decision that shapes architecture, data, tests, security or task split is resolved, then record the outcome. Use before specifying or building, when intent is fuzzy, or when the user says 'grill me' or 'challenge this plan'."
argument-hint: "The idea, plan or spec to pressure-test"
user-invocable: true
---

# sdlc-grill: reach shared understanding

## When to use

- Before `sdlc-specify` (T3/T4), or as the light version for T2.
- When a plan or spec exists but its assumptions haven't been tested.
- Other skills call this as their questioning step (`sdlc-clarify` uses it with a cap of 5).
- Not for T0, and not when the answer can be found in the code or docs. Look it up instead of asking.

## Inputs

- The idea or artifact under discussion.
- Glossary and ADRs (see the `sdlc` inputs). Use the project's terms, and flag any term the user uses differently.
- The code at the seam. Check facts yourself before asking about them.

## Process

1. **Map the decision tree.** List the open decisions in dependency order: scope, actors, data ownership, contracts, failure behaviour, security, test seam, rollout. Mark each as *answerable from the repo* or *the user's call*.
2. **Resolve the answerable ones yourself**, citing `path:line`. Don't ask the user what the code already says.
3. **Ask one question at a time**, highest impact first. Each question:
   - says why it matters (what changes depending on the answer),
   - offers 2–4 concrete options with your **recommended** option first and a one-line trade-off,
   - is answerable in one reply.
4. **Follow the branch.** After each answer, update the tree: new sub-decisions, decisions that are now moot, contradictions with earlier answers (raise those immediately).
5. **Stop** when the remaining questions wouldn't change architecture, data, tests, security or the task split. Light mode (T2): at most 3 questions. Clarify mode: at most 5.
6. **Record the outcome**, not the conversation: decisions, the rejected options and why, new glossary terms, and items deferred to later. Write it into the active artifact (spec *Clarifications*, mini-spec, ADR draft or PRD) or, if there is none yet, into the summary you hand to the next skill.
7. **Play it back**: a 5–10 line summary of what was agreed. Ask the user to confirm or correct it.

## Rationalizations

| Excuse | Reality |
|---|---|
| "I'll just pick sensible defaults" | Fine for routine choices: state them as assumptions. Not fine for data ownership, contracts or security. |
| "Ask everything at once to save turns" | A batch of 10 questions gets shallow answers and hides dependencies. One at a time, with a recommendation. |
| "The user seems sure, so don't challenge it" | Pressure-testing is the job. Name the risk once, clearly, then respect the decision. |
| "Keep grilling until it's perfect" | Stop when answers no longer change the plan. Over-grilling is its own waste. |
| "The transcript is the record" | Nobody re-reads transcripts. Only the recorded decisions survive. |

## Red flags

- The user's answer contradicts `AGENTS.md`, an accepted ADR or the spec. Surface the conflict; don't resolve it silently.
- A decision needs someone who isn't present (another team, security, product). Record it as blocked, with the person to ask.
- More than 3 consecutive answers of "not sure". The work may need a spike or prototype first: say so.

## Verification

- Every decision on the tree is resolved, deferred with a reason, or blocked with an owner.
- The outcome is written to an artifact (give its path) or handed to the next skill verbatim.
- The user confirmed the play-back, or corrected it and the correction is recorded.

## Principles applied

agree-before-building, evidence-over-claims, depth-follows-risk
