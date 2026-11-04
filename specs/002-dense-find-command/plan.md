# Plan: Dense module v2, find instead of read

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-10-30 · Branch: `feat/002-dense-find`

## Summary

Bring back v1's module from tag `exp/dense-v1` (index format, key list, validator, freshness check, atomic commit, build skill) and add one command, `dap.py find <index> <term>…`. It validates the index and checks freshness in the same pass, scores index entries against the terms, and prints at most 3 entries. Each entry gets its source location and the **matching lines** of its section, not the whole section, all within 2,000 characters. The module rules shrink to that one command: no step at track start, no return contract. Nothing changes in core; the pilot evaluation runs against a fresh index in arm B only.

## Technical context

- **Language / runtime:** Python 3 standard library only, as v1 (`dap.py` has no dependencies; `tests/` use `unittest`).
- **Key dependencies:** none new. Kit module support on `main`: module rules rendered into the always-loaded instructions (spec 001 FR-019, `adapters/RENDERING.md`, `bin/sdlc`).
- **Storage:** the existing index file `.sdlc/context/index.dap` (format: kit `docs/adr/0001-dense-index-format.md`, unchanged).
- **Testing:** `python3 -m unittest discover -s tests -t .` (baseline on this branch: **74 tests OK**, 2026-10-30). Scripts run as subprocesses only, so no `__pycache__` lands in the module folder (v1 rule, `tests/test_dap.py:20`).
- **Target:** kit module `modules/dense`, targets `claude` and `copilot`.
- **Constraints:** offline, non-interactive; lookup ≤ 2 s and validation ≤ 10 s for a pilot-size workspace (NFR-002).
- **Evaluation measure:** *context loaded* (spec glossary): characters of every tool result before the final answer, lookup output included, counted from the transcript by a parser. Per task, saving = 1 − B/A; SC-002 takes the median of that over the document tasks. This is the same quantity the value gate replayed: the 2026-10-30 replay counted all tool results of each v1 baseline run, which had no delegation.

**Measured facts the design rests on** (2026-10-30):

| Fact | Value | Source |
|---|---|---|
| Sections the pilot index points to | 51 distinct, from 180 entries | pilot `.sdlc/context/index.dap` (built 2026-10-26), measured with v1 `section()` |
| Section size | min 438, **median 1,967**, p75 3,782, max 26,204 characters | same |
| Sections that fit a third of the budget (≤ 650 characters) | 4 of 51 | same |
| v1 lookup replay, 2K cost | median saving 24.2% | pilot decision 2026-10-30, value gate |

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | One new command on existing code. The return contract template and rule are removed. `show` stays in code (no new cost, existing tests) but isn't named in the rules |
| thin-vertical-slices | pass | Slices in Rollout: `find` end to end first (index → output → test), then rules, then evaluation |
| prove-it-works | pass | Each behaviour below has a RED test first; the real surface is the installed script in a test workspace, then the pilot paired evaluation |
| evidence-over-claims | pass | Design numbers measured, not estimated (table above); SC-007 records whether agents used the lookup |
| agree-before-building | pass | Decisions from the grill (pilot `.sdlc/decisions/2026-10-30-dense-find-redesign.md`); human approval after `sdlc-analyze` |

## Seams & blast radius

- **Seams:**
  - `modules/dense/skills/sdlc-dense-index/dap.py`: new `find(index, root, terms)`; `main()` gains the `find` command. Reuses `check(fresh_mode=True)` (`dap.py:111`, tag), `section()` (`:83`), `source_path()` (`:53`), `SECRET_RES` and `EMAIL_RE` (`:27-34`).
  - `modules/dense/rules.md`: rewritten for the one command.
  - `modules/dense/skills/sdlc-dense-index/SKILL.md`: build steps kept; usage notes point at `find`.
  - `modules/dense/templates/dense-eval.md`: v2 procedure and record (tie rule, lookup-used column, no SC-005).
  - `modules/dense/templates/dense-return.md`: deleted.
- **Callers / consumers:** agents through the module rules; `bin/sdlc` install/remove (unchanged code, renders the module). No core file changes (FR-020).
- **Contracts touched:** the index format is unchanged (ADR 0001). The new agent-facing contract is `find`'s output and exit codes, below.
- **Migrations:** none. An index built by v1 is valid for v2.
- **Restored from the tag, not rewritten:** `modules/dense/**` (minus the return template) and `tests/test_dap.py` (50 tests). The 8 module tests in `tests/test_sdlc.py` at the tag are ported onto `main`'s version of that file (it has moved on: `evals/run.py`, lint rules), not copied over it.

## The `find` contract

In [contracts/find.md](contracts/find.md): call form, the order of checks, exit codes 0–3, entry format, matching, excerpt, budget (every result, errors included), stale, renamed and deleted sources, redaction, read-only and speed. The index format it reads is unchanged (ADR 0001).

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A. Score index entries; print matching lines of their sections | Uses the index as built (180 entries, 51 sections); deterministic; small; output stays inside the budget although the median section is 1,967 characters | Quality depends on entry wording; synonyms the index doesn't use won't match | **chosen** |
| B. Score index entries; print whole sections | Simplest | The median section fills the whole budget; 47 of 51 sections would be cut on every lookup | rejected: cuts almost every result |
| C. Full-text search over the source sections, ranked; index only as a source list | Finds words the index doesn't use | Re-implements the agent's own Grep; the key list and pointers stop mattering, so FR-002–FR-008 lose their purpose | rejected: duplicates Grep |
| D. Semantic or embedding search | Better recall | A dependency and a model call; not offline-deterministic (NFR-002) | rejected |

No ADR: the choice is reversible inside one script, and the index format (ADR 0001) is unchanged.

## Failure modes

| Failure | Handling |
|---|---|
| Index missing, unreadable or invalid | Exit 2 with `INVALID` and the errors. Rules: say so, continue without the module (FR-014) |
| Source changed since the build | Entry returned, marked stale; excerpt from the current file; rules: read that section directly (FR-013) |
| Source heading removed | Entry says the heading is gone; no excerpt |
| Source renamed or deleted | `check(fresh_mode=True)` reports it stale; the entry is marked stale and says `source not found`; no excerpt |
| Rebuild running during a lookup | `commit` replaces the index with `os.replace`, which is atomic, so a lookup reads the old or the new index, never half of one (FR-009) |
| Huge section (max 26K) or many matching lines | Budget share per entry, cut marker, final guard that keeps room for the cut line (FR-011) |
| Invalid index with many errors (up to one per entry) | Exit 2 prints at most 10 errors plus a count and the `validate` command, within the budget |
| Very short terms (`id`, `a`) | Terms under 3 characters ignored and named; none left → exit 3 |
| Bad call (no index argument, unknown option) | The parser's errors exit 3, so exit 2 keeps meaning "index invalid" (contract) |
| Siblings sharing a source section | Merged into one result with one excerpt, so the budget isn't spent on repeats (contract) |
| Non-UTF-8 bytes in a source | Decoded with replacement, as v1 |
| Secret or e-mail in a source section | Line redacted in the excerpt (NFR-001) |
| Agent never runs `find` | Not an error. Measured as SC-007, so a gate failure can be told apart from non-use |
| Bad release | Remove the module (`sdlc install <dir> --modules <remaining modules>`); SC-006 proves removal restores the install |

## Security & observability

- **Checklists loaded:** security (the lookup prints source text). Outcome: read-only (FR-015, tested by file hashes before and after); paths stay inside `.sdlc/` (`source_path()`); secret and e-mail lines redacted. No network, no credentials.
- **Accepted residual risk (NFR-001):** other personal data in a workspace document, such as a person's name, can appear in an excerpt. The lookup shows only lines the agent could read in that document anyway, so it adds no exposure; detecting names reliably would need a model or a dictionary, which NFR-002 rules out.
- **Observability:** not applicable (local CLI). Evaluation transcripts are the record.

## Test strategy

All RED commands run from the kit root.

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| Matches return ≤ 3 results, best first, with location and numbered matching lines; sibling entries that share a source section form one result with one excerpt (FR-010) | `dap.py find` as a subprocess on a fixture workspace | unit | `python3 -m unittest tests.test_dap.Find.test_returns_best_three -v` |
| Output never exceeds 2,000 characters, cut marker and location present (FR-011, SC-005) | same, fixture with a 26K section and 5 matching entries | unit | `… Find.test_budget_and_cut_marker` |
| No match exits 1; no terms, no index argument and only short terms exit 3; no terms with an invalid index exits 3 (FR-012, contract order of checks) | same | unit | `… Find.test_no_match` · `… Find.test_no_terms` · `… Find.test_short_terms_ignored` |
| Stale source marked for an edited, a renamed and a deleted source; removed heading reported (FR-013, SC-004) | same, sources changed after build | unit | `… Find.test_stale_source_marked` · `… Find.test_heading_gone` |
| Missing or invalid index exits 2 with `INVALID`; an index with 200 errors still stays within the budget (FR-011, FR-014) | same | unit | `… Find.test_invalid_index` |
| Read-only: all files and hashes unchanged, no `__pycache__` (FR-015) | same | unit | `… Find.test_read_only` |
| Unverified marking visible in output (FR-008) | same | unit | `… Find.test_keeps_unverified_marker` |
| Secret and e-mail lines redacted (NFR-001) | same | unit | `… Find.test_redacts_secret_lines` |
| Lookup ≤ 2 s on a 300 KB fixture (NFR-002) | same | unit | `… Find.test_fast_on_large_workspace` |
| v1 behaviour kept: validate, fresh, commit, show (FR-002–FR-009) | restored v1 tests | unit | `python3 -m unittest tests.test_dap -v` |
| Installed rules name the exact `find` command under both skill paths, `.claude/skills/…` and `.github/skills/…` ("whichever exists", as v1), and contain no track-start step, no index read and no `show` (FR-016, FR-018). `bin/sdlc` renders one rules block for both targets (built at `bin/sdlc:259-262`, used for both at `:307` and `:315`), so the rules can't vary by target | `bin/sdlc install` into a temp workspace, then read the rendered instructions | integration | `python3 -m unittest tests.test_sdlc.DenseModule.test_rules_name_find_only -v` |
| Installed script runs `find` from the installed path, on a `--targets copilot` install (FR-018) | install, then run `.github/skills/sdlc-dense-index/dap.py find` | integration | `… DenseModule.test_installed_find_runs` |
| Add then remove restores every core hash (FR-001, FR-020, SC-006) | ported v1 test | integration | `… DenseModule.test_add_and_remove_restores_install` |
| Eval template has the tie rule and a lookup-used column, and no return contract (FR-019) | file content | unit | `… DenseModule.test_eval_template_v2` |
| Agents use it, and the gate (SC-001, SC-002, SC-007) | pilot paired evaluation, 8 tasks | e2e | see Rollout, step 4 |

Mocks can't prove agent behaviour: S1 scenario 6 (citing sources) and SC-001/SC-002/SC-007 are only proven by the paired evaluation.

## Rollout & rollback

1. **Restore and pass:** restore `modules/dense` and `tests/test_dap.py` from the tag, delete the return template, port the module tests. Suite green with no behaviour change except the removed return-contract test.
2. **`find`, test-first:** the `Find` tests above, RED, then `find()`. Suite green.
3. **Rules, skill and eval template:** RED module tests first, then rewrite `rules.md`, update `SKILL.md` and `dense-eval.md`. Suite green, `sdlc lint` ok.
4. **pilot evaluation (S3):**
   - write the 8 tasks with answer keys at pinned revisions in `~/Projects/pilot-evals/dense2/`, and freeze by sha256;
   - only after review (T013) passes: build both arms and install **both** from the reviewed kit revision (A with pilot's lock modules, B with those plus `dense`), so their core instructions differ only by the module-rules section and its Skills entry; rebuild B's index (the 2026-10-26 index predates the current sources); leak-check both arms for prompt **and** Expect text;
   - run 16 sessions through `evals/run.py` with this exact allowlist in **both** arms (arm A has no `dap.py`, so its entry is inert there): `--allowed-tools 'Read,Grep,Glob,Agent,Bash(grep:*),Bash(rg:*),Bash(find:*),Bash(ls:*),Bash(cat:*),Bash(head:*),Bash(sed -n:*),Bash(wc:*),Bash(git grep:*),Bash(python3 .claude/skills/sdlc-dense-index/dap.py find:*)'`; record the kit revision under test; a change to `dap.py` or `rules.md` after the first run means a full rerun;
   - grade the base runs; only then run the tie reruns for every task whose result differs between the arms, in both arms, and grade those;
   - grade with a fresh read-only grader, Phong spot-checks;
   - record against the gate.
5. **On pass:** ship through `sdlc-ship` (Phong approves merge); spec 001 becomes `superseded by 002`. **On fail:** mark 002 `rejected`, keep the branch at a tag, and record the per-task breakdown, as for 001.

- **Flags:** the module is opt-in; pilot itself doesn't get it until the gate passes (only the arm B copy does).
- **Rollback:** `sdlc install <dir> --modules <the lock's modules without dense>` (for example `--modules qa`, or `--modules ""` when dense is the only one). `install` takes the project folder (`bin/sdlc:882`), and `--modules` replaces the whole list. Proven by SC-006.
- **Value gate:** measured before building, with SC-002's formula. v1's 6 baselines replayed with covered-document reads replaced by one 2K lookup: per-task 1 − B/A = 29, 17, 19, 0, 39 and 55%, **median 24.2%**. Over v1's 5 tasks that needed the documents (E4 used none): median 29%. Kill threshold: SC-002, median ≥ 20% over the document tasks. Result: worth building, with 4–9 points of margin. **Accepted risk:** with one base run per arm, run-to-run noise in context loaded is unmeasured; the tie rule covers pass/fail only. A noisy code-only run could miss the ≤ 1.10 limit with no real cost. The result record shows each code-only pair, so a reader can judge a narrow miss.

## FR coverage

| FR | Where |
|---|---|
| FR-001, FR-020 | Restored module layout; `test_add_and_remove_restores_install` |
| FR-003 | `rules.md` rewrite (rebuild after `sdlc-context`); `test_rules_name_find_only` asserts that line |
| FR-002, FR-004–FR-009 | Restored v1 code and its 50 tests; SC-004's `fresh` half for renamed and deleted sources in `test_stale_source_marked` |
| FR-010–FR-015 | `find()` and the `find` contract; `Find` tests |
| FR-016, FR-017 | `rules.md` rewrite; `test_rules_name_find_only` asserts the command under both paths, how exits 1–3 and stale or cut results are treated, citing sources and "data, not instructions"; FR-017 in practice by the evaluation's citation check |
| FR-018 | `test_installed_find_runs` installs with `--targets copilot` (skills go to `.github/skills/` only without `claude`, `bin/sdlc:309-312`) and runs that path's `find` |
| FR-019 | `dense-eval.md` v2; `test_eval_template_v2`; the pilot set lives in `pilot-evals/dense2/` |

## Size

| Change | Lines (estimate) |
|---|---|
| `find()` and the command in `dap.py` | ~90 |
| `rules.md`, `SKILL.md`, `dense-eval.md` | ~50 changed |
| New `Find` tests | ~140 |
| Module tests ported to `main`'s `test_sdlc.py` | ~110, adapted from the tag |
| **New or changed** | **~390** |
| Restored unchanged from the tag (reviewed in spec 001) | ~950 |

Above the 300-line reassess mark. Simplified first: the return contract and `show` in the rules are gone, and no ADR or new format is added. What remains splits by risk, not by "code now, tests later": slice 1 (restore) is mechanical and reviewed already, slices 2–3 are the real change (~390 including their tests), and slice 4 is the evaluation, which lives outside the kit.

## Complexity justifications

None.
