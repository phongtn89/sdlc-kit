# Requirements quality

Load when writing, clarifying or analyzing a spec. These are unit tests for the requirements, not for the code: each item checks what the spec says, not whether the system works.

## Completeness
- [ ] Every user scenario has at least one requirement that covers it, and every requirement traces to a scenario.
- [ ] Error, empty, loading and permission-denied behaviour is specified for each scenario.
- [ ] Who may perform each action is stated (actor, role, tenant).

## Clarity
- [ ] No vague terms ("fast", "intuitive", "robust", "appropriate") without a number or definition.
- [ ] Each requirement has one interpretation; two readers would write the same test.
- [ ] Domain terms match the project glossary; new terms are defined.
- [ ] Requirements describe behaviour, not implementation (no frameworks, tables or classes).

## Consistency
- [ ] No two requirements contradict each other or the constitution.
- [ ] Each FR references a scenario, and every P1 scenario has at least one FR.

## Measurability
- [ ] Every success criterion has a number, a threshold or a yes/no observation.
- [ ] Each criterion says how it will be measured.

## Scenario coverage
- [ ] Primary, alternate and failure flows are present for every P1 scenario.
- [ ] Recovery is specified: retry, undo, partial completion, resume.
- [ ] Every Given/When/Then has a concrete, observable Then.

## Edge cases
- [ ] Boundaries: zero, one, maximum, just over maximum.
- [ ] Invalid, missing, duplicate and oversized input.
- [ ] Concurrent edits, ordering and repeated submission.
- [ ] Cross-tenant and cross-user access attempts.

## Non-functional
- [ ] Performance, availability, security, privacy and accessibility needs are stated or explicitly not applicable.
- [ ] Data retention and audit needs are stated where data is personal or regulated.

## Dependencies and assumptions
- [ ] External systems, contracts and teams the feature relies on are listed.
- [ ] Every assumption is written down and could be checked; out-of-scope items are explicit.

## Ambiguity
- [ ] At most 3 `[NEEDS CLARIFICATION]` markers remain, each with the decision it blocks.
- [ ] No marker remains on anything a P1 scenario depends on before planning starts.
