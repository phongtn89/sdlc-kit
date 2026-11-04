VERDICT: APPROVED

<!-- One verdict. No blocking findings remain. -->

# Review: Spec 003 usage metrics (re-review after fixes)

## Scope

- Repository: <kit>
- Revision: `main..16a23a4` (branch feat/003-usage-metrics); the fixes are `a02249a..16a23a4`
- Role: implementation (correctness, security, tests)
- Agent: sdlc-reviewer (independent, read-only; experiments in scratch copies under review003/)
- Inputs: specs/003-usage-metrics/{spec,plan,tasks}.md, contracts/usage.md, docs/adr/0002-usage-metric-technique.md; first review of a02249a (REJECTED, F1-F5)

## Summary

All five blocking findings from the first review are fixed and reproduced as fixed. The fixes caused no regression I could find. The suite (228 tests) and lint pass. Of 41 mutants, 39 were killed, 1 is equivalent, and 1 survives (a missing test, advisory). Merging as is breaks nothing.

## Findings

None blocking.

Resolution of the earlier findings (all re-run on 16a23a4):

| ID | Was | Resolution | Evidence |
|---|---|---|---|
| F1 | `--at garbage` exited 1 on stderr | Fixed. `cmd` validates `--at` after the off check and the unit check; exit 2, one line on stdout | `stop T1 --at garbage` gives `(2, 'usage: --at needs a timestamp like 2026-11-03T10:23:07.456Z\n', '')`. Also exit 2 for `…10:00:00.000` (no Z) and `…Z\n`. `…10:00:00Z` is accepted. With the switch off, `--at x` prints `usage off`, exit 0 |
| F2 | non-string timestamp crashed (TypeError) | Fixed. `parse_ts` returns None for non-strings | transcript with `"timestamp":5` → exit 0, line says `unexpected transcript format` |
| F3 | `replace_open_line` rewrote a line in another section | Fixed. Works inside the requested section on the last matching line | Notes section keeps `- usage T1: not available (no start mark)`; the Progress log gets the new line. Two lines for one unit in a section: the last is replaced, the first untouched |
| F4 | bracket in the config dir hid an existing transcript | Fixed. `glob.escape` on config dir, session and sub-agent folder | `CLAUDE_CONFIG_DIR=<proj>/[c*]` finds the main file and the sub-agent file: `in 1 · cache-read 2 · cache-write 3 · out 4 · sub-agents 40 …` |
| F5 | `$` accepted a trailing newline | Fixed. `\Z` in UNIT_RE, SESSION_RE, MODEL_RE, TS_RE | `start $'T01\n'` gives exit 2 with the unit message and the record is unchanged; model `abc\n` no longer reaches the record |
| A1 | heading in a code fence / with trailing spaces | Fixed for ``` fences, indented ``` fences and trailing spaces (CRLF too) | fenced `## Progress log` is skipped; `## Progress log  ` matches |
| A2 | `<synthetic>` record without id broke the segment | Fixed | transcript with a malformed synthetic record plus a good one → `in 1 · cache-read 2 …`, no format error |
| A4 | workspace record path wording | Fixed | `core/skills/sdlc-implement/SKILL.md` step 4 now says the path is relative to the project root, `<repo>/specs/NNN-slug/tasks.md` in a workspace |

## Advisory

- A1b (P3, open) `usage.py` `section_bounds`: only ``` fences are recognised. A heading inside a `~~~` fence is still taken as the section (repro: `# T\n\n~~~\n## Progress log\n~~~\n` → the mark is appended after the fence, no new section). A four-backtick fence that contains a ``` line toggles wrongly (repro `````/```/## Progress log/````` → the heading is treated as real). Not in the contract; document it or handle `~~~` and fence length.
- A3 (P3, open) argparse errors precede the switch check: with the switch off, a call missing an argument exits 2 instead of `usage off`.
- A5 (P3, open) `start --at <valid>` silently ignores `--at`; `start --at <invalid>` now exits 2. The contract says `--at` is for `stop` only.
- A6 (P3) the second `## Progress log` section in a file is ignored (the first is used). Consistent with the contract's "the `##` heading", not specified for duplicates.
- A7 (P3) "1 turns" is not pluralised (matches the contract's format).
- No concurrency lock between two `usage.py` runs on one record (last writer wins); the contract states none.

## Surviving mutations (missing tests)

Run on a scratch copy of 16a23a4: `python3 -m unittest tests.test_usage tests.test_sdlc.UsageSkill`, 41 mutants (the earlier 31 adapted, plus the fix-specific ones: no `glob.escape`, no fence handling, `\Z` back to `$` for unit, model and timestamp, synthetic shape check back, `parse_ts` accepting non-strings, `--at` check removed, section-less replace, first-hit replace, session regex loosened).

- **replace first hit** (`i = hits[-1]` → `hits[0]` in `replace_open_line`): tests stay green. No test has two open lines for one unit. (Real behaviour is right, see F3 evidence.)
- **synthetic keep** (removing the `<synthetic>` filter in `in_window`): green, but it is an equivalent mutant now: `read_responses` skips synthetic records before they reach the window filter.
- The earlier survivors are now killed: tmp left behind after a failed replace, unit-id prefix match, timestamp without Z, row 1 writing an extra line. Atomic write (direct write instead of `os.replace`) is now killed too.
- Removing the explicit `".."` check was an equivalent mutant in the first review (`inside()` resolves paths) and is not re-run.
- All other mutants were killed.

## Verification performed

| Command / check | Revision | Outcome |
|---|---|---|
| `cd <kit> && python3 -m unittest discover -s tests -t . && python3 bin/sdlc lint` | 16a23a4 | `Ran 228 tests … OK`; `lint: ok` |
| Re-run of F1-F5, A1, A2, A4 reproductions (scratch projects under review003/) | 16a23a4 | all fixed (table above) |
| Regression probes: `## Progress log` as last line with no newline; CRLF with fenced heading and heading with trailing spaces; indented ``` fence; fence inside the section; two usage lines for a unit; `insert` and `section_text` agreement (marks and lines land in the same section); `--at` check order vs `usage off`; `--at` on `start` | 16a23a4 | no regression; only A1b and A5 above |
| Randomized comparison against an independent computation (150 cases) | a02249a (the numeric code is unchanged apart from the guarded changes) | 0 mismatches; the figures in the probes above are unchanged on 16a23a4 |
| Install from `git archive 16a23a4`: `sdlc check`; `__pycache__` / `.pyc` count; installed `usage.py` identical to core | 16a23a4 | `ok`; 0 `.pyc`; 64 files written (62 + the two `sdlc-usage` copies); files identical |
| 41-mutant run in a scratch copy | 16a23a4 | 39 killed, 1 equivalent, 1 survivor |
| Real repo untouched | 16a23a4 | `git status --short` empty |

## Gaps / limits

- No live Claude Code session was run; the live check in evals/results was taken as stated.
- Windows paths and concurrent runs were not tested.
- The regression probes cover the cases listed; fence handling beyond ``` (A1b) is open by design of the fix.
