# Test cases: [Feature name]

Source: [specs/NNN-slug/spec.md](../../specs/NNN-slug/spec.md) · Spec status: approved
Created: [YYYY-MM-DD] · Status: draft <!-- draft | ready | executed | signed-off -->
Tester: [name] · Approver: [ACTION REQUIRED: not supplied]

<!-- QA-owned. Lives in testcases/<NNN-slug>/ and never edits specs/. Every case traces to a spec scenario (S#) or requirement (FR-/NFR-/SC-). Never invent behaviour the spec does not state: write [ACTION REQUIRED: …] instead. A gap found while testing goes back to the spec via sdlc-clarify; a missing variant of defined behaviour is added here as a new case. -->

## Entry criteria

<!-- What must be true before execution starts. Do not assume an environment; confirm it. -->

- [ ] Build under test: [revision / version]
- [ ] Environment: [ACTION REQUIRED: not supplied]
- [ ] Test data: [seeded per Test data below]

## Test data

<!-- Accounts, roles, tenants and records the cases need. Mark tenant-scoped data. No real secrets or personal data. -->

| Data | Role / tenant | Notes |
|---|---|---|
| | | |

## Cases

<!-- One block per case. Type: manual | automatable. Automatable = an existing test suite can drive it end to end and assert on observable state. Each scenario needs at least one negative case; tenant-scoped data needs a cross-tenant denial case. -->

### S1 — [Scenario title] (P1)

| ID | Traces to | Type | Given / When / Then | Result |
|---|---|---|---|---|
| TC-001 | S1, FR-001 | automatable | **Given** … **When** … **Then** … | [ ] Pass [ ] Fail [ ] Blocked |
| TC-002 | S1, FR-002 | manual | **Given** … **When** [invalid action] **Then** [stated error] | [ ] Pass [ ] Fail [ ] Blocked |
| TC-003 | S1 (tenant) | automatable | **Given** tenant A is signed in **When** they request tenant B's [record] by ID **Then** it is denied or not visible | [ ] Pass [ ] Fail [ ] Blocked |

### Edge cases (optional — delete if N/A)

| ID | Traces to | Type | Case | Expected | Result |
|---|---|---|---|---|---|
| TC-0xx | FR-00x | manual | [boundary / empty / concurrent] | [concrete value or behaviour] | [ ] Pass [ ] Fail |

### Non-functional (optional — delete if N/A)

| ID | Traces to | Type | Check | Measured via | Result |
|---|---|---|---|---|---|
| TC-0xx | NFR-001 / SC-001 | manual | | | [ ] Pass [ ] Fail |

## Cross-scenario regression (optional — delete if N/A)

<!-- Interactions between scenarios that no single-scenario case covers. -->

| ID | Scenarios | Given / When / Then | Result |
|---|---|---|---|
| TC-0xx | S1 × S2 | | [ ] Pass [ ] Fail |

## Automated coverage

<!-- Filled by sdlc-qa-automate. One row per automated case. -->

| Case | Test file | Command | Status |
|---|---|---|---|
| | | | passing / failing (defect link) / skipped (reason) |

## Execution order

- [ ] Q1 Confirm entry criteria
- [ ] Q2 Run P1 cases, then P2, then P3
- [ ] Q3 Run edge, non-functional and regression cases
- [ ] Q4 Record defects as bugs with case IDs
- [ ] Q5 Record sign-off

## Exit criteria & sign-off

- All P1 and P2 cases pass; P3 failures documented with accepted risk.
- No open P0/P1-severity defect (review-method severity scale, not scenario priority).
- **Decision**: [ ] Go  [ ] No-go · **Approver**: · **Date**:
