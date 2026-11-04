VERDICT: APPROVED

# Review: spec 005 `sdlc gate`

Two independent passes by fresh read-only agents (2026-11-04), against spec.md, contracts/gate.md and plan.md, with experiments in scratch directories outside the repository.

## Pass 1 on `0297255`: VERDICT: REJECTED

| Id | Finding | Outcome |
|---|---|---|
| F1 (high) | A range regex let `T001 — 57 tests pass` give evidence to T002..T57 | Fixed test-first: a range needs the prefix on both ends (later narrowed again, see R1) |
| F2 (medium) | A symlinked spec folder found by `--spec NNN` let `approve` write outside the project | Fixed test-first: the number form gets the same realpath containment check |
| F3 (medium) | A deeply nested `verify.json` raised `RecursionError` and printed a traceback | Fixed test-first: reported as `unreadable record` |
| F4 (medium) | Free text on the `Status:` line and after the inline status word was outside the digest | Fixed test-first: only the status word is ignored; the rest of the line stays covered |
| A1 | `--by` accepted U+0085 and zero-width characters | Fixed: Cc, Cf, Zl, Zp and non-space whitespace refused |
| A2 | A test depended on the live repository's history | Removed; the rebuilt-history snapshot test stays |
| A3, A5, A6 | Tick-id style, implementer role, analyze "read-only" text | Fixed in the template, role and skill |
| A4 | Text after the progress log is not covered | Stated limit (contract) |

## Pass 2 on `32e01b0`: VERDICT: APPROVED

F1–F4 and A1 reproduced and closed; ordinary work (tick, log line, status to `implemented`, CRLF, no-space status) still passes; legacy specs still report no digest. Two low advisories, both fixed at `fe9f773`:

| Id | Finding | Outcome |
|---|---|---|
| R1 | The bare `T001-100` form still let a number give evidence to the tasks in between | Fixed test-first: the bare form is gone, a range needs the prefix twice |
| R2 | `· Status: \S+` could hide non-space text | Fixed test-first: only the letters of the status word are ignored |

Not covered: Windows (POSIX only), an ambiguous short hash with git warnings on standard error, a branch named like a hash.
