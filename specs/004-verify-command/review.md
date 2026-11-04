VERDICT: APPROVED

# Review: spec 004 `sdlc verify`

Reviewed: `bcaeb62..96524f2` on `feat/004-verify-command` by a fresh read-only agent (2026-11-04), against spec.md, contracts/record.md and plan.md. Checks run by the reviewer: `tests.test_verify` 41 OK, `sdlc lint` ok, experiments in temp dirs (float and huge timeouts, missing repo folder, null sections, install then commit then verify then check then uninstall).

No demonstrated defect against FR-001–FR-015. Advisory findings, all low, and what was done (fixed after the review, at the commit following `96524f2`):

| Id | Finding | Outcome |
|---|---|---|
| A1 | Timeout test used 1 s and wrote its pid file after two interpreter starts: flaky on a loaded machine | Fixed: 3 s limit |
| A2 | Isolation test listed the whole OS temp folder: could fail for unrelated files, and could not see a leftover (the file is unlinked at creation) | Fixed: only the kit and the project's parent are listed |
| A3 | "After a new commit" test only proved git changed HEAD | Fixed: it now asserts `green_at_head` is false |
| A4 | A signal right after the record is written can print "no record written" | Not changed: window is tiny, not reachable in a test; stated here |
| A5 | `uninstall` keeps `.sdlc/evidence/`, README said it removes everything | Fixed in README (test first); the folder is local state |
| A6 | `sdlc-ship` ran the suite twice (step 2 and step 4) and the commit-message guidance read oddly | Fixed (test first): step 2 points to step 4 |
| A7 | A read-only reviewer can't learn the current head | Fixed (test first): the caller passes the head SHA |
| A8 | `killpg` on a reaped leader could in theory hit a reused group id | Not changed: required by the spec; noted |

Not covered by the review: Windows (documented as POSIX only), SC-004 (live eval, task T017), a mutation check for SC-001 (done by the owner's agent in T015: six mutations, each caught).
