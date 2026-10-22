# Spec: [Feature name]

Feature: [short name]
Number: [NNN — from `sdlc next-spec`]
Status: draft <!-- draft | approved | implemented | superseded by NNN. sdlc-analyze sets approved; sdlc-ship sets implemented. -->
Approved: <!-- name, YYYY-MM-DD; filled when approved -->
Owner: [name]
Created: [YYYY-MM-DD]
Track: T3

<!-- The requirements contract for this feature. Describe WHAT and WHY, never HOW: no frameworks, tables, classes or endpoints. Keep it current; `sdlc-converge` reconciles it with the code. -->

## Intent

<!-- 3–6 sentences: the problem, who has it, why it matters now. A reader should know whether to care after this section. -->

**Problem:**
**Who:**
**Why now:**

## Out of scope

<!-- What a reasonable reader might expect but this feature will not do. Prevents scope creep in plan and review. -->

-

## Glossary terms used

<!-- Domain terms this spec relies on. Link to the project glossary; define only new terms here and add them to the glossary when agreed. -->

- **[Term]**: [definition or link]

## User scenarios

<!-- Prioritised journeys. Each must be testable on its own and deliver value if it is the only one shipped. P1 first; P1 alone is the minimum viable slice. -->

### S1 — [Title] (P1)

As a [actor], I want [goal], so that [value].

**Independent test:** [how to verify this scenario alone]

1. **Given** [state], **When** [action], **Then** [observable outcome]
2. **Given** [state], **When** [invalid or failing action], **Then** [observable outcome]

### S2 — [Title] (P2)

<!-- Same shape. Delete unused scenarios. -->

## Requirements

<!-- Testable, numbered, technology-free. One behaviour per line. Use MUST / MUST NOT (SHOULD only for non-blocking preferences). Reference scenarios. -->

- **FR-001**: The system MUST [behaviour]. (S1)
- **FR-002**: The system MUST NOT [prohibited behaviour]. (S1)

## Non-functional (optional — delete if N/A)

<!-- Only constraints that change design or tests: performance, availability, security, privacy, accessibility, retention. Each with a number or a clear yes/no. -->

- **NFR-001**:

## Success criteria

<!-- Measurable, technology-agnostic outcomes that prove the feature worked. Say how each is measured. -->

- **SC-001**: [outcome with number] — measured via [method]

## Assumptions & dependencies

<!-- Things taken as true without proof, and systems, contracts or teams this relies on. Each should be checkable. -->

- Assumption:
- Dependency:

## Clarifications

<!-- Written by `sdlc-clarify`. One session per date; record the decision, not the discussion. Update the affected sections above too. -->

### Session YYYY-MM-DD

- Q: [question] → A: [decision]

## Open questions

<!-- Max 3. Each blocks a specific decision. None may remain on a P1 scenario before planning. -->

- [NEEDS CLARIFICATION: question — blocks FR-00x — owner: name]
