VERDICT: APPROVED | REJECTED

<!-- Keep exactly one verdict on the first line. REJECTED requires at least one blocking finding (P0–P2) that cites a demonstrated defect or a failed mandatory requirement. Non-blocking concerns go under Advisory and never change the verdict. -->

# Review: [Change title]

## Scope

- Repository:
- Revision: `[base]..[head]`
- Role: correctness | security | spec | conflict | tasks | implementation
- Agent: [sdlc-reviewer | sdlc-security-reviewer | main session]
- Inputs: [spec, plan, tasks, PR, issue]

## Summary

<!-- Impact first: what would break, for whom, if this merged as is. Then a one-line overall assessment. -->

## Findings

<!-- Blocking findings only. P0 = data loss, security breach or outage; P1 = wrong behaviour in a main path or failed mandatory requirement; P2 = wrong behaviour in an edge path or missing required test; P3 = minor, non-blocking (prefer Advisory). Every row needs Correction, Reason and Verify. -->

| ID | Severity | Location | What fails & when | Correction | Reason | Verify |
|---|---|---|---|---|---|---|
| F1 | P1 | `path:line` | | smallest change that fixes it | why the correction fixes the cause (cite the violated requirement) | command or observation that proves it fixed |

## Advisory

<!-- Non-blocking suggestions. Optional improvements, style, follow-ups. -->

-

## Verification performed

| Command / check | Revision | Outcome |
|---|---|---|
| | | |

## Gaps / limits

<!-- What was not reviewed or could not be verified (remote-only checks, credentials, environments), and residual risks. -->

-
