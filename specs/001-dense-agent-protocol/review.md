VERDICT: REJECTED

# Review: Dense Agent Protocol module (spec 001)

## Scope

- Repository: sdlc-kit, branch `feat/001-dense-agent-protocol`
- Revision: `c3abe38..aac72f1`
- Role: implementation + correctness, with path safety
- Agent: `sdlc-reviewer` subagent (independent, read-only); findings re-verified by the main session
- Inputs: spec.md (approved), plan.md, tasks.md (incl. Convergence), contracts/, ADR 0001, adapters/RENDERING.md

## Summary

If this merged as is, a build interrupted after writing only the header (or the header and `src` lines) would **replace the last good index with an empty one, and `fresh` would call it fresh**. Agents would then orient from an index with no entries. This breaks FR-018 and the approved grammar. Separately, current-format `sk-` API keys (OpenAI `sk-proj-…`, Anthropic `sk-ant-…`) and Stripe `sk_live_…` keys pass the secret check, contrary to NFR-001. Everything else holds: path confinement, managed-block compatibility, and the tested behaviour of validate, fresh and commit.

## Findings

| ID | Severity | Location | What fails & when | Correction | Reason | Verify |
|---|---|---|---|---|---|---|
| F1 | P2 | `modules/dense/skills/sdlc-dense-index/dap.py:186-195` | A tmp holding only `#dap 1 built …`, or a header and `src` lines without sections, or a section without entries, validates. `commit` replaces the good index (reproduced: `committed fd10e2bfc1cb`, then `fresh fd10e2bfc1cb`, exit 0). | After the loop: `ERROR 1: no src lines` when there are none, and `ERROR <last line>: no sections` when there are none. When a section ends with no entries: `ERROR <section line>: section has no entries`. Add the rule to contracts/index-format.md Validation. | Enforces the approved grammar `file = header src+ section+`, `section = … entry+`, and so FR-018 ("an invalid rebuild MUST NOT replace the last valid index"). | RED then GREEN: `Validate.test_header_only_invalid`, `test_no_sections_invalid`, `test_empty_section_invalid` (exit 1, right line), `Commit.test_truncated_tmp_keeps_last_valid_index` (exit 1, dest sha256 unchanged). |
| F2 | P2 | `dap.py:29` | `sk-proj-abcdefghijklmnopqrstuvwxyz0123`, `sk-ant-api03-…` and `sk_live_…` validate as `valid` (reproduced). The hyphen after `proj`/`ant` stops `\bsk-[A-Za-z0-9]{20,}`. | `\bsk-[A-Za-z0-9_-]{20,}` and `\b[sr]k_(live\|test)_[A-Za-z0-9]{16,}`. | Covers the prefixes NFR-001 and contract rule 6 mean to block ("common token prefixes"). | Add the three values to `test_secrets_rejected`; `test_at_signs_that_are_not_email_accepted` and `test_plain_url_is_not_a_secret` stay green. |

## Advisory

- **A1:** URL credentials with an empty user part (`redis://:s3cret@cache:6379`, reproduced as `valid`) and upper-case schemes are missed. Change `[^/\s:@]+` to `*` in the user part, and make the check case-insensitive. Cheap to fold into the F2 fix.
- **A2:** `EMAIL_RE` false positives on `logo@2x.png`, `getty@tty1.service`, `pkg@1.0.0-beta.rc`. This fails safe, but either exclude common file/unit suffixes or tell builders in `SKILL.md` to point to those sections instead.
- **A3:** slug edge cases differ from GitHub:
  - a heading sequence `A`, `A-1`, `A` produces a duplicate `a-1`;
  - `~~~` fences aren't treated as code;
  - setext headings and headings indented 1–3 spaces aren't detected;
  - non-ASCII slugs (`## Übersicht`) can't be referenced, because `REF_RE` is ASCII-only, which matters for German sources.

  Add `test_duplicate_heading_suffix` and `test_heading_in_fence_not_a_target`.
- **A4:** no escape found. Two gaps remain:
  - no test covers a `src` symlink inside `.sdlc/` that points outside (`test_src_symlink_outside_rejected`);
  - `os.replace(a.dest)` should use the resolved path, so that a second symlink inside `context/` that resolves to `index.dap` can't be replaced instead of the index.
- **A5:** `commit` doesn't check the `src` hashes, so an index built with a wrong hash commits and is stale at once. The skill's verification step (`fresh` after `commit`) catches it.
- **A6:** messages: a header with trailing whitespace says "unknown version", and a UTF-8 BOM says "missing header".
- **A7:** there's no golden byte comparison of the managed block against the pre-change output. Today's equality is shown only relative to a module-free install in the same run.
- **A8:** the `one of:` value forms in `keys.json` aren't enforced. The contract doesn't require it.

## Verification performed

| Command / check | Revision | Outcome |
|---|---|---|
| `python3 -m unittest discover -s tests -t .` (Python 3.9.6) | `aac72f1` | 104 OK |
| `python3 bin/sdlc lint` | `aac72f1` | ok |
| F1 reproduction: good index → header-only tmp → `commit` → `fresh` | `aac72f1` | `committed fd10e2bfc1cb`, exit 0; `fresh fd10e2bfc1cb`, exit 0; empty section → `valid` |
| F2/A1 reproduction: `validate` with `sk-proj-…`, `sk-ant-api03-…`, `sk_live_…`, `redis://:s3cret@…` | `aac72f1` | all `valid` |
| `__pycache__` under `modules/` after tests | `aac72f1` | none |

## Gaps / limits

- Agent-behaviour requirements (FR-003, FR-008–FR-014; S1, S3) can't be judged from code. Convergence C003 keeps T010, T015 and T018 open.
- The reviewer didn't read README.md, VERSION, evals/scenarios.md, dense-eval.md or RENDERING.md beyond the test assertions.
- No security review is needed: no auth, tenant data, CI or dependency change. Secret handling is covered by F2 and A1.
