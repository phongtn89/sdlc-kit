# Review method (reference)

Load this file when a review needs calibration. It refines `SKILL.md`; it adds no gates.

## Decision rules

- Reject only for a **demonstrated defect** or a **failed existing mandatory requirement** (a spec FR, a CI gate, an `AGENTS.md` rule). Cite the basis.
- Optional improvements, missing optional evidence, unavailable optional tools and absent guidance are **advisory**. Continue with the evidence you have; don't invent a blocker, a new required test, an approval stage or a tool requirement.
- If mandatory evidence is unavailable, apply the existing gate and explain what's missing. An environment limitation is not a code defect.
- Accept valid alternatives. Style, speculative scale and hypothetical extension needs are optional advice.

## Apply your role

| Role | Inspect | Decision evidence |
|---|---|---|
| Correctness | Changed behaviour, callers, consumers, requirements, tests, compatibility | A reachable failure, or a mandatory requirement not met |
| Security | Principal, action, resource and trust boundary; tenant scope, secrets, validation, infrastructure | The allowed operation **and** a denied cross-tenant or unauthorized case; the actual exposure |
| Specification | Actors, inputs/outputs, ownership, acceptance criteria, failure and security requirements | Missing or contradictory outcomes. Don't demand code or tests before they can exist. |
| Conflict | Related requirements, routes, schemas, events, shipped behaviour | Cite both conflicting locations. Shared files alone are not a conflict. |
| Tasks | Requirement-to-task coverage, ordering, write sets, tests, prerequisites, human-only work | A concrete gap or an impossible dependency, plus the smallest corrected sequence |
| Implementation | The final revision, approved scope, non-vacuous regression tests, existing gates | The actual gate outcomes and the requirement coverage |

## Severity

| Level | Meaning |
|---|---|
| P0 | Reachable tenant data leak, auth bypass, destructive unauthorized action, data loss, or a production outage |
| P1 | A broken required flow, an incompatible supported contract, or a failed mandatory gate |
| P2 | A wrong edge-case behaviour, a missing required test for changed behaviour, or a maintainability defect with a concrete cost |
| P3 | Minor: unclear naming, small duplication. Usually advisory. |

Any P0–P2 finding that is demonstrated means `REJECTED`. P3 findings are advisory unless a mandatory rule makes them blocking.

## Examples

**Defect**: an authenticated caller from tenant A can update tenant B's record, because the write is scoped only by record ID.
- **Correction**: reuse the established authorization check, and add the trusted tenant scope to the write predicate.
- **Reason**: it closes the cross-tenant path without changing owner behaviour.
- **Verify**: an owner update succeeds; a cross-tenant update is denied and leaves the stored data unchanged (authorization test command).
- **Clean counterpart**: the caller is already authorized and the query carries the trusted tenant predicate. A downstream helper that takes only an ID doesn't prove a leak; trace its caller.

**Defect**: replaying a message produces a second effect where the contract requires exactly one.
- **Correction**: use the existing idempotency key at the transaction boundary.
- **Verify**: a replay, and a concurrent duplicate delivery, each leave one committed effect, including when a timeout follows the commit.
- **Clean counterpart**: a uniqueness constraint already handles the duplicate. Don't demand another layer.

**Not a finding**: a docs-only change without screenshots or benchmarks.

## Report style

- Plain language and short sentences. The verdict and the most consequential impact come first.
- For each finding: what fails, when, why it matters, the evidence location, the correction, and how to close it.
- Someone reading only the report and the cited code should understand the decision and the next action.
- Name the exact revision, the commands and the working directory. Name missing inputs; never invent commands.
