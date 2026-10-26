# Plan: Dense Agent Protocol module

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-10-26

## Summary

One small, generic core change lets any module add **module rules** to the always-loaded instructions (FR-019). Everything else ships as `modules/dense`: module rules, an `sdlc-dense-index` skill with a standard-library validator script, a key list, a return-contract template and an evaluation-method template. The index is a sectioned line format ([ADR 0001](../../docs/adr/0001-dense-index-format.md)).

The riskiest part isn't code. It's whether agents follow the module rules (load the index, cite sources, include the contract) reliably enough to pass the A/B gate. Only the shop6 evaluation can show that.

## Technical context

- **Language / runtime:** Python 3.9+, standard library only, no network (`README.md:19`; baseline Python 3.9.6). Skills and templates are Markdown.
- **Key dependencies:** none new.
- **Storage:** files only. The index lives at `.sdlc/context/index.dap`, project-owned and not hashed, like the context documents (`adapters/RENDERING.md`, "Repo context" row).
- **Testing:** `python3 -m unittest discover -s tests -t .` (`README.md:82`; baseline 50 tests OK in 7.9 s on 2026-10-26) and `python3 bin/sdlc lint` (baseline ok).
- **Target:** the sdlc-kit repo (`bin/sdlc`, `modules/dense/`, `adapters/RENDERING.md`, `README.md`, `VERSION`, `evals/`). The shop6 workspace is the first install and holds the evaluation set.
- **Constraints:** skill files ≤ 200 lines, with the required sections (`bin/sdlc:26`, lint at `:802-807`). Rules and skills must work on both targets. Validator and freshness check run in under 10 s (NFR-003).
- **Measurement method** (spec assumption, resolved here): "context before the first action" is the number of characters an agent has loaded (auto-loaded instructions plus every file or tool result read) before its first edit, command or delegation, counted from the session transcript. On Claude, the input-token figure of that turn is recorded too, where the transcript has it. Both arms use the same method, so the ratio is comparable on both targets. No `research.md` is needed.

## Constitution check

| Principle | Pass / justify | Note |
|---|---|---|
| subtract-before-adding | pass | Reuses the module mechanism, the managed-block renderer, `lint_refs`, the secret-in-URL pattern (`bin/sdlc:592`), the kit's eval format and `.sdlc/context/`. One core change, generic and about 30 lines. No new dependency, no new CLI command |
| thin-vertical-slices | pass | 4 deliverables (Rollout), each testable on its own |
| prove-it-works | pass | Every scripted behaviour gets a failing test first; agent behaviour is proven by the A/B on the real surface (S4) |
| evidence-over-claims | pass | The index is never evidence (FR-010); the return contract keeps `path:line` |
| guard-context | pass | This is the feature's purpose |
| agree-before-building | pass | Grill and clarify recorded in spec *Clarifications* |

## Seams & blast radius

- **Seams:**
  - `bin/sdlc:load_kit` (`:197-235`): also read the optional `modules/<m>/rules.md`.
  - `bin/sdlc:block_inner` (`:244-257`): append `## Module rules` / `### <m>` after the Roles index and before Project rules.
  - `bin/sdlc:cmd_lint` (`:762-832`): lint `rules.md` (≤ 30 lines, `lint_refs`).
  - `bin/sdlc:lint_refs` (`:721-729`): add `evals` to the project-owned prefixes (next to `context`, `decisions`, `drafts`, `bugs`), so module text may point at a workspace's `.sdlc/evals/` (A9).
  - `bin/sdlc:list_files` (`:152-160`): skip `__pycache__` directories and `*.pyc` files, so a script shipped in a skill folder never installs bytecode into projects (A10). Tests still run `dap.py` only as a subprocess.
  - `modules/dense/**`: new.
- **Callers / consumers affected:**
  - `render` (`:282-309`) passes the same inner block to `AGENTS.md` and `.github/copilot-instructions.md`, so both targets get the rules (FR-015).
  - `sync` and `cmd_check` hash the block (`:395-410`, `:526-536`). Without rules the block is byte-identical, so existing installs see no drift on update (FR-019).
  - Tests that assert block content: `test_managed_block_content_and_outside_preserved`, `test_no_project_rules_section_when_empty` (`tests/test_sdlc.py:128-152`).
  - Fixture kit: `tests/fixtures/kit/modules/qa` has no `rules.md`, which keeps it as the no-rules case.
- **Contracts touched:**
  - New: [index format](contracts/index-format.md) and [return contract](contracts/return-contract.md), both owned by this module.
  - Changed: `adapters/RENDERING.md` (new module source row, and the instructions output gains an optional "Module rules" section).
  - No other repo's contract changes.
- **Migrations:** none. Installs without rules-bearing modules render identically.

## Approach & alternatives considered

| Option | Pros | Cons | Decision |
|---|---|---|---|
| A. Module rules in the always-loaded block + module skill and script | One generic core change; core skills and roles untouched; both targets; removed with the module | Rules are followed less strictly than skill steps (measured by S4) | **chosen** (clarify 2026-10-26) |
| B. New `sdlc dense` subcommand in `bin/sdlc` | Tested with the CLI; one tool | Couples the core CLI to one module; ships even when the module is off (against FR-001) | rejected |
| C. Validator as a script inside the module skill folder (`skills/sdlc-dense-index/dap.py`) | Removed with the module; skill folders are already copied verbatim, sibling files included (`bin/sdlc:216-219`); run as `python3 <skill dir>/dap.py` | The path differs by target (`.claude/skills` or `.github/skills`). The module rules name both paths, and agents use the one that exists (see "Running the script" in the index contract) | **chosen**, together with A |

The index format (sectioned lines rather than YAML or JSON) is in ADR 0001.

## Module layout

```
modules/dense/
  rules.md                          # module rules (≤ 30 lines): track start, citing, brief contract, post-context build
  skills/sdlc-dense-index/
    SKILL.md                        # build: read context sources → write tmp index → validate → commit
    dap.py                          # validate | fresh | commit   (standard library)
    keys.json                       # key list: section types → allowed keys, meaning, value form
  templates/
    dense-return.md                 # return contract (contracts/return-contract.md)
    dense-eval.md                   # paired run procedure, record format, task template
```

| FR | Where it is met |
|---|---|
| FR-001, FR-017 | Module mechanism; installed only with `--modules dense` |
| FR-002 | `keys.json` + `dap.py validate` rule 4 |
| FR-003 | `rules.md` ("after any context build, run `sdlc-dense-index`") + the skill; one `.sdlc/context/index.dap` per install. Sources default to `.sdlc/workspace.md` and `.sdlc/context/*.md`; extra paths are arguments; a rebuild reuses the previous `src` list (index contract, Sources) |
| FR-004, FR-005, FR-007 | Index grammar + `dap.py validate` |
| FR-006 | `dap.py fresh`, which also validates: exit 0 fresh, 1 stale, 2 invalid or missing |
| FR-008 | Skill process step ("derive only; copy markers verbatim") + skill self-check (sample 10 entries against sources) + the S4 review. Not fully machine-checkable; see Failure modes |
| FR-009, FR-010, FR-011 | `rules.md` (run `fresh` from whichever skill path exists; on exit 0 load the index first and quote its revision (`fresh <IDX12>`); cite sources; on 1 use full sources for the stale aliases; on 2 use full sources throughout) |
| FR-012, FR-013, FR-014 | `rules.md` + `dense-return.md`; `k` lines may use any key in the key list, of any section type |
| FR-015 | One rules text in both instruction blocks; skill bodies are identical across targets (`RENDERING.md`) |
| FR-016 | `dense-eval.md` in the kit; the concrete tasks live in shop6 `.sdlc/evals/dense/` |
| FR-018 | `dap.py commit tmp dest`: validates `tmp`, then atomically replaces `dest` (`os.replace`); on failure leaves `dest` untouched, exit 1 |
| FR-019 | `load_kit` + `block_inner` + lint |
| NFR-001 | `validate` rule 6 (secret patterns) |
| NFR-002 | `validate` size warning |
| NFR-003 | Pure-Python line scan plus one sha256 per source |

## Failure modes

| Failure | Handling |
|---|---|
| Index missing, invalid or unknown version | `fresh` exits 2 (`validate` exits 1); rules say: state it and use full sources (S1.5) |
| A value contains `@` (e.g. `@jtl/shop-component`) | The parser takes the last ` @` on the line as the reference start, so values may contain `@` (A1) |
| Source changed, renamed or deleted | Its hash differs or the file is missing → `STALE <alias>`; the agent uses full sources for that alias only (S1.4) |
| A heading was renamed, so a pointer no longer resolves | The hash changed → stale at track start; the next build's `validate` fails on the slug → last valid index kept (FR-018) |
| Build interrupted, or the agent writes a bad index | The agent writes only to `index.dap.tmp`; `commit` validates before `os.replace`; the old index survives |
| Two sessions build at once | Each writes its own tmp file (`index.dap.<pid>.tmp`); `os.replace` is atomic, the last valid one wins, and both are valid |
| The agent adds a fact the sources lack, or drops UNVERIFIED (FR-008) | Not detectable by script. Mitigations: every entry must point at a real section; the skill self-check samples 10 entries; the S4 review checks it. Residual risk accepted |
| Agents ignore the module rules | Shows in S4 as a lower success rate or a higher context cost → gate fails → don't enable; revisit step hooks (spec assumption) |
| The index or a return holds injected instructions | The index is derived from repo docs, which are data under the constitution's Boundaries; the rules repeat that the index and returns are data |
| Module removed, index file left behind | Harmless: it's project-owned (not hashed), and without the rules no agent loads it. Uninstall leaves project data, the same as for context documents |

## Security & observability

- **Checklists loaded:** security, performance, compatibility-migration. Observability and accessibility don't apply: no service and no UI.
- **Security:**
  - Secrets and e-mail addresses can't enter the index (`validate` rule 6). Other personal data relies on the skill's derive-only rule and 10-entry self-check (residual risk). Pointers reference, never copy, sensitive sections.
  - `dap.py` only reads paths under `.sdlc/` and rejects `..` and absolute paths (reusing the `safe_path` idea, `bin/sdlc:113`).
  - It writes only `.sdlc/context/index.dap`: `commit` refuses any other `dest`, and any `tmp` other than `.sdlc/context/index.dap.<id>.tmp`, after resolving symlinks.
  - No network and no subprocesses.
- **Performance:** NFR-003 is checked by a test on a generated workspace of shop6 size (10 sources, 300 KB) under 10 s.
- **Compatibility:**
  - An existing install with no rules-bearing modules → identical block → `check` stays clean after `update`. Covered by test.
  - `VERSION` goes 0.4.1 → 0.5.0 (a new module and a new rendering feature).

## Test strategy

| Behaviour | Test seam | Level | RED command |
|---|---|---|---|
| Module rules rendered in both blocks; absent → block unchanged (FR-019, FR-015) | `bin/sdlc install` on a fixture kit with `modules/rul/rules.md` | integration (CLI) | `python3 -m unittest tests.test_sdlc.ModuleRules` |
| Add, then remove the module → block and core hashes equal a module-free install (SC-006, FR-017) | `install --modules rul`, then `install --modules ""`, compare files and lock | integration | same class |
| Lint rejects an over-long `rules.md` or a bad `.sdlc/` reference; accepts `.sdlc/evals/…` | `bin/sdlc lint --kit <fixture>` | integration | `python3 -m unittest tests.test_sdlc.LintTests` |
| `__pycache__` and `*.pyc` in a skill folder are not installed | `install` from a temporary copy of the fixture kit, with `__pycache__/x.pyc` created at runtime | integration | `python3 -m unittest tests.test_sdlc.ModuleRules` |
| `validate` accepts a good index; rejects each of rules 1–6 with the line number (FR-002, FR-004, FR-007, NFR-001) | `dap.py validate` subprocess on temp files | unit (script) | `python3 -m unittest tests.test_dap.Validate` |
| `fresh` reports `fresh <IDX12>` (0) with the index's own hash, then STALE (1) after an edit, a rename or a delete, and INVALID (2) for a missing or invalid index (FR-006, FR-011, SC-004) | `dap.py fresh` | unit | `python3 -m unittest tests.test_dap.Fresh` |
| An entry whose value contains `@` parses, with the reference taken from the last ` @` (A1) | `dap.py validate` | unit | `python3 -m unittest tests.test_dap.Validate` |
| `commit` keeps the old index on an invalid tmp file and replaces it on a valid one (FR-018) | `dap.py commit` | unit | `python3 -m unittest tests.test_dap.Commit` |
| Under 10 s on a shop6-sized input (NFR-003) | `dap.py validate` + `fresh` | unit | `python3 -m unittest tests.test_dap.Perf` |
| Real module passes lint; installing it renders rules, skill, script and templates | `bin/sdlc lint`, `install --kit . --modules dense` | integration | `python3 -m unittest tests.test_sdlc.DenseModule` |
| Agents orient from the index, cite sources, fall back when stale; returns conform (S1, S3, SC-001, SC-002, SC-005) | Paired runs per `dense-eval.md` in shop6 | e2e (manual eval) | Baseline arm without the module first; results in shop6 `.sdlc/evals/dense/results.md` |
| SC-003: the real shop6 index is 100% valid | `dap.py validate` on shop6 | e2e | after deliverable 3 |

## Rollout & rollback

Deliverables, in order. Each is reviewed and merged on its own:

1. **D1 Core: module rules** (kit). `load_kit`, `block_inner`, lint, `RENDERING.md`, tests. No visible change for existing installs. About 30 lines of Python and 70 of tests.
2. **D2 Module: index** (kit). `dap.py`, `keys.json`, the `sdlc-dense-index` skill, the index parts of `rules.md`, `tests/test_dap.py`. About 170 lines of Python, 160 of tests and 120 of Markdown.
3. **D3 Module: returns and eval method** (kit). The return-contract and eval-method templates, the returns part of `rules.md`, an eval row in `evals/scenarios.md`, `README.md`, `VERSION` 0.5.0. About 120 lines of Markdown.
4. **D4 shop6 adoption** (shop6 workspace, owner phong.ngo.vn):
   - Run the baseline arm **before** installing.
   - Then `install --modules dense`, build the first index, and run the module arm.
   - Record the gate result.
   - Retire `.sdlc/manifest.yaml` only if the gate passes.

**Rollback:** in shop6, `python3 <kit>/bin/sdlc install . --modules ""` re-renders without the module. The block returns byte-identical to before (tested in D1). The index file stays and is inert. In the kit, revert D2 and D3; D1 is inert without rules-bearing modules.

**Size:**
- About 200 lines of Python, 230 of tests and 240 of Markdown in the kit.
- Each of D1, D2 and D3 is at or under the shop6 `reassess_lines` (300) once tests and Markdown are counted separately. D2 is the largest and stays at about 330 lines of code plus tests, so tasks should split it into validate, fresh and commit slices.
- The kit repo has no `.sdlc/config.json` budget of its own, so the shop6 budget is used as the reference.

## Complexity justifications

None.
