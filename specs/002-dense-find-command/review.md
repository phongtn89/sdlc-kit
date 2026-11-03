VERDICT: APPROVED

# Review: dense module v2, "find instead of read" (spec 002, T001-T012 plus review fixes)

## Scope

- Repository: /Users/phong.ngo.vn/Projects/sdlc-kit, branch feat/002-dense-find
- Revision: `0ee9391..5f3d44b` (head 5f3d44b; earlier reviewed heads 0561f13 and 8fb24b7)
- Role: implementation (correctness + spec)
- Agent: independent read-only reviewer
- Inputs: specs/002-dense-find-command/{spec,plan,tasks}.md, contracts/find.md; spec 001; v1 dap.py from tag exp/dense-v1

## Summary

Nothing blocks. The `find` lookup meets its contract on all four exits, within 2,000 characters on every exit, with stale, renamed, deleted, heading-gone and path-escape sources handled, nothing written, and v1 commands unchanged. The four defects found in review (a broken SKILL.md, an unbudgeted entry list, two secret echoes through a heading slug) are fixed and now have tests that fail without the fix. Two small P3 items remain as advisories.

## Findings

No blocking findings at 5f3d44b. Resolved findings, for the record:

| ID | Severity | Location | What failed | Resolution (verified at) |
|---|---|---|---|---|
| F1 | P1 | SKILL.md:40-58 | Duplicate Inputs/Process; v1 text "read the index first and quote `<rev>`" contradicted FR-016/FR-017 | Fixed at 8fb24b7: one `## Inputs` (18), one `## Process` (25), steps 1-11, no "read the index first"; test_skill_is_v2_and_well_formed |
| F2 | P2 | dap.py entry lines | Sibling entry lines unbudgeted; guard cut a cut line and dropped results 2 and 3 | Fixed at 8fb24b7: re-run prints 1,189 characters, 3 results, `… 11 more entries for this section`, intact cut lines |
| F3 | P2 | dap.py entry lines | A secret in a heading slug printed in the entry line while `validate` said valid | Fixed at 8fb24b7: entry line prints `[redacted: read the source]`; INVALID lines carry no values |
| F4 | P2 | tests/test_dap.py | Secret-only redaction and guard() mutations survived | Fixed at 8fb24b7: secret and e-mail tests split, guard has its own test; coordinator ran the mutations |
| F5 | P2 | dap.py find(), "no heading" line | Stale source with the heading gone printed the secret slug | Fixed at 5f3d44b: re-run prints `no heading [redacted] in context/s.md`; test_secret_slug_not_echoed_when_the_heading_is_gone |

## Advisory

- A1 (P3): `find IDX --root . widget` exits 3 `unrecognized arguments: widget`; terms starting with `-` need `--`. Within the contract (`--root` last); the message could hint at both.
- A2 (P3): `test_rules_and_skill_cover_building` asserted the v1 `dap.py show` phrase in SKILL.md; with F1 fixed this is harmless, but the assertion could target the build self-check text.
- A3: the limit is in characters; output can be up to 2,028 bytes because `…` is 3 bytes in UTF-8.
- Carried P3 (a): `validate` still accepts a slug that holds a secret (output is redacted, but `check` could reject it at the source).
- Carried P3 (b): the source path is printed unredacted in the location and cut lines. Repro: a source file named `sk-abcdefghijklmnopqrstuvwxyz1234.md` under `.sdlc/context/` is valid and `find` prints `.sdlc/context/sk-abcdefghijklmnopqrstuvwxyz1234.md:2-3`. It needs a secret-shaped file name, and the agent could list that directory anyway.

## Where `find` prints index or source data (final scan)

Checked every format in `find`, `entry_lines`, `cut_line` and `find_main`:
- entry lines (type, id, key, value, alias, slug): all pass `redact()` as one line;
- `no heading <slug>`: redacted (F5);
- excerpt lines including the heading: redacted per line;
- INVALID lines: redacted per line, clipped to 120 characters, capped at 10;
- source path (`rel`) in location, cut and `source not found` lines: not redacted (carried P3 b);
- user terms in `no match for:` and usage errors: echo of what the caller typed, clipped.

## Verification performed

| Command / check | Revision | Outcome |
|---|---|---|
| `python3 -m unittest discover -s tests -t .` | 5f3d44b | Ran 152 tests, OK |
| `python3 bin/sdlc lint` | 5f3d44b | `lint: ok` |
| F5 repro (stale source, secret slug) | 5f3d44b | `no heading [redacted] in context/s.md` |
| Secret-shaped source file name repro | 5f3d44b | path printed (carried P3 b) |
| Earlier checks at 0561f13 and 8fb24b7 (exit codes and order, budgets on all exits, stale cases, escapes, read-only, v1 parity in 8 comparisons, rules/SKILL/template consistency) | 0561f13, 8fb24b7 | as in review.md and review2.md; no later change touches those paths except the diffs reviewed |

## Gaps / limits

- Mutation tests for F4 were run by the coordinator, not by me.
- Speed (NFR-002) relies on the existing 300 KB test.
- The Copilot-only install is covered by the existing test only.
