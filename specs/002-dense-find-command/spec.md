# Spec: Dense module v2, find instead of read

Feature: dense-find-command
Number: 002
Status: approved <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: one-line reason). sdlc-analyze sets approved; sdlc-ship sets implemented; rejected records a feature that was built or evaluated and deliberately not adopted. -->
Approved: phong.ngo.vn, 2026-11-03 (in chat, to implement; both analyze passes closed) <!-- name, YYYY-MM-DD; filled when approved -->
Owner: phong.ngo.vn
Created: 2026-10-30
Track: T3

> **Supersedes spec 001 for this capability** once approved; 001 is then marked `superseded by 002`. 001 stays the record of the rejected v1 and its evaluation.

<!-- Source of the decisions: shop6 workspace, .sdlc/decisions/2026-10-30-dense-find-redesign.md (sdlc-grill, play-back confirmed 2026-10-30; not yet committed in shop6: cite its revision once it is). Evidence: the 12 transcripts of the 2026-10-26 shop6 evaluation (shop6-evals/dense/results.md). -->

## Intent

**Problem:** v1 told agents to read a whole dense index before anything else. In the shop6 evaluation, reading the index (15.9K characters) cost about as much as the targeted document reads it was meant to replace (median 9.5K), and agents skipped the prose rules that told them how to use it. The gate failed: −17% context, against −50% required. The 50% target was also out of reach on that task set, because the documents the index covers were only a median 31% of the baseline's context.

**Who:** Agents running sdlc tracks in a workspace or repo with the module enabled, and the maintainers who decide whether to enable it.

**Why now:** A replay of the v1 baselines, with covered-document reads replaced by one lookup capped at 2,000 characters, gives a median 24% saving (29, 17, 19, 0, 39 and 55% per task). That's enough to test a redesign against a gate it can actually pass or fail, and cheap to build on v1's index, validator and freshness check.

## Out of scope

- Indexing code, or pointing from the index into product repositories (deferred until this version passes and code reads remain the main cost).
- A sub-agent return contract (v1's FR-012–FR-014 and SC-005; deferred to a spec of its own).
- Any step an agent must take at the start of a track. Agents use the lookup only when they need something from the workspace documents.
- Compressing handoffs or the kit's own instruction text.
- Fleet rollout, and serving the index from a central knowledge service (standards ADR 0038).
- Replacing context documents. They stay the record; the index stays a map.

## Glossary terms used

- **Context document**, **dense index**, **key list**, **source pointer**, **module rules**, **always-loaded instructions**: as defined in spec 001.
- **Lookup**: the module's single agent-facing operation. Given search terms, it returns the best-matching index entries with the source sections they point to. New.
- **Lookup budget**: the maximum size of one lookup's output, whatever its result: at most 3 entries and 2,000 characters in total. New.
- **Excerpt**: the part of a section a lookup prints: the section's heading line, then the lines that contain a search term, each with one line of context and its line number; if no line contains a term, the heading and the section's next 5 lines. When the excerpt is not the whole section, it ends with a cut marker that gives the section's full location. New.
- **Context loaded**: for one evaluation run, the characters of every tool result the agent receives before its final answer, lookup output included. Auto-loaded instructions are excluded; they are the same in both arms except the module-rules section. Replaces spec 001's "context before the first action", which stopped counting at the first command and so would stop at a lookup. New.
- **Document task / code-only task**: a task whose answer is in the workspace documents the index covers, versus one answered from product code alone. New, used by the evaluation.

## User scenarios

### S1: Find a workspace fact with one lookup (P1)

As an agent that needs a fact from the workspace documents, I want to look it up by a few terms and get only the matching sections, so that I spend less context than reading or searching the documents myself.

**Independent test:** In a workspace with a fresh index, run the lookup for terms that match a known section. Check the output's size, its entries and their source locations. Then, in a fresh agent session on a document task, check the transcript: the agent used the lookup, read no whole covered document, and cited the source location.

1. **Given** a fresh, valid index, **When** the lookup runs with terms that match entries, **Then** it returns at most 3 entries, best match first, each with its source location and an excerpt of the section it points to, within the lookup budget.
2. **Given** an entry whose excerpt is not its whole section, or matches that together exceed the lookup budget, **When** the lookup runs, **Then** each shortened excerpt ends with the cut marker and its section's full location, and the whole output stays within the budget.
3. **Given** terms that match no entry, **When** the lookup runs, **Then** it says there is no match and returns nothing else; the agent continues with its usual search. **Given** no search terms at all, **Then** it says that terms are required and returns no entries.
4. **Given** an index whose source was edited, renamed or deleted since it was built, **When** the lookup returns an entry from that source, **Then** the entry is marked stale with the source named (and, if the file or heading is gone, says so instead of an excerpt), and the agent reads the source directly instead of trusting the entry.
5. **Given** no index or an invalid one, **When** the lookup runs, **Then** it says so and returns no entries; the agent continues exactly as without the module.
6. **Given** a claim in the agent's answer found through the lookup, **When** the answer is written, **Then** the claim cites the source location, never the index.

### S2: Build and keep the index honest (P1)

As a maintainer refreshing context with the module enabled, I want the index derived from the context sources and checked automatically, so that lookups never return facts the sources don't hold.

**Independent test:** As spec 001 S2: build an index in a test workspace, validate it, change one source, check freshness; break a rebuild and check the last valid index survives.

1. **Given** context sources, **When** a context build runs with the module enabled, **Then** an index is written that records the revision or content hash of every source it used.
2. **Given** a written index, **When** it is validated, **Then** every key belongs to the key list and every entry's source pointer resolves to an existing section.
3. **Given** an unknown key, a missing pointer or a pointer to a missing section, **When** the index is validated, **Then** validation fails and names each offending entry.
4. **Given** a source that changed after the build, **When** freshness is checked, **Then** the index is reported stale with the changed source named.
5. **Given** a fact marked unverified or inferred in its source, **When** it reaches the index, **Then** the entry keeps the marking, and a lookup shows it.
6. **Given** a valid index, **When** a rebuild fails or produces an invalid index, **Then** the last valid index stays unchanged and the failure is reported.

### S3: Prove the gain before enabling (P2)

As a maintainer, I want a paired evaluation of the module against the same workspace without it, so that enabling it rests on evidence, and a failure gives a clear stop.

**Independent test:** Following the shipped evaluation method, run the workspace's evaluation set once with and once without the module, and record the results against the gate.

1. **Given** an evaluation set of document tasks and code-only tasks, frozen before any run, **When** each task runs in a fresh session with and without the module, **Then** a result record shows, per run: pass or fail, context loaded, whether the lookup was used, the size of each lookup output, and whether the answer cites the index or the sources.
2. **Given** the records, **When** the gate is checked, **Then** it passes only if every success criterion SC-001 and SC-002 holds.
3. **Given** a task whose result differs between the arms, **When** the gate is checked, **Then** that task has been run once more in both arms, and it counts for an arm only if both of that arm's runs passed.

### S4: Install and remove cleanly (P3)

As a maintainer, I want to switch the module on and off without touching core kit files, so that I can back it out if the evaluation fails.

**Independent test:** As spec 001 S5: install with and without the module, compare core file hashes, remove the module.

1. **Given** a kit install, **When** the module is added, **Then** no core-managed file changes except the always-loaded instructions gaining the module-rules section and the module's Skills index entry, and the lock records the module.
2. **Given** the module is installed, **When** it is removed, **Then** only the module's files are removed, and agents behave as without the module.

## Requirements

- **FR-001**: The module MUST be opt-in. Without it, kit behaviour and installed files MUST be identical to a kit without the module. (S4)
- **FR-002**: The module MUST ship a key list defining, for every allowed key, its meaning and value form, in a form a validator can check. (S2)
- **FR-003**: With the module enabled, its module rules MUST require the index to be rebuilt after every context build: one index per workspace in workspace mode, one per repo in single-repo mode. (S2)
- **FR-004**: Every index entry MUST carry a source pointer to the section it was derived from. (S2)
- **FR-005**: The index MUST record the revision or content hash of each source it was built from. (S2)
- **FR-006**: The freshness check MUST report the index as stale, naming the changed sources, when any recorded source differs from its current state. (S1, S2)
- **FR-007**: Validation MUST reject an index with an unknown key, a missing source pointer or a pointer to a missing section, and name each failing entry. (S2)
- **FR-008**: The index MUST NOT contain a fact absent from its sources, and MUST keep unverified or inferred markings. (S2)
- **FR-009**: A failed or invalid rebuild MUST NOT replace the last valid index. (S2)
- **FR-010**: The lookup MUST take one or more search terms and return the best-matching entries, best first, at most 3. Each returned entry MUST include its source location and an excerpt of the section its pointer names. (S1)
- **FR-011**: The lookup's output MUST NOT exceed the lookup budget (3 entries, 2,000 characters in total) for any result, including no match, errors and an invalid index. Every excerpt that is not its whole section MUST end with the cut marker and the section's full location. (S1)
- **FR-012**: When no entry matches, the lookup MUST say so and return no entries. When it is given no search terms, or only terms shorter than 3 characters, it MUST say that usable terms are required and return no entries; shorter terms among usable ones are ignored and named. (S1)
- **FR-013**: The lookup MUST check freshness itself and mark every returned entry whose source is stale (edited, renamed or deleted), naming the source. Agents MUST NOT need a separate step before a lookup. (S1)
- **FR-014**: When the index is missing or invalid, the lookup MUST say so, return no entries and exit with a result distinct from "no match". (S1)
- **FR-015**: The lookup MUST be read-only: it MUST NOT change the index, the sources or any other file. (S1)
- **FR-016**: The module rules MUST name the exact lookup command and its arguments, say when to use it (before reading or searching the workspace documents to find something), and say how to treat stale, cut, empty and failed results. They MUST NOT require reading the index, or any other step, at the start of a track. (S1)
- **FR-017**: Agents MUST NOT cite the index as evidence. Claims MUST cite the source location. Lookup output and the index are data, not instructions. (S1)
- **FR-018**: The module MUST behave the same on every target the kit supports (today `claude` and `copilot`). (S1)
- **FR-019**: The module MUST ship an evaluation method: the paired procedure (fresh session per task and arm, the tie rule from S3.3), the result record format, and a task template with Expect items. The method MUST require a leak check of every arm before the first run (no prompt or Expect text readable from inside an arm). The concrete evaluation set and its results MUST live outside every workspace the agents under test can read. (S3)
- **FR-020**: Installing or removing the module MUST NOT modify any core-managed file, except the always-loaded instructions gaining or losing the module-rules section and the module's Skills index entries. (S4)

## Non-functional

- **NFR-001**: The index MUST NOT copy secrets, credentials or personal data from its sources; a source that holds them is referenced by pointer only (as spec 001). Lookup excerpts print source lines, so every excerpt line that matches the module's secret or e-mail patterns MUST be redacted. Other personal data in a workspace document (for example a name) can appear in an excerpt exactly as it would when the agent reads that document; this residual risk is accepted, because the lookup shows nothing the agent couldn't read itself.
- **NFR-002**: The lookup, validation and the freshness check MUST run offline and non-interactively. A lookup MUST finish within 2 s, and validation within 10 s, for a workspace the size of shop6.
- Availability and accessibility: not applicable (no runtime service or UI).

## Success criteria

- **SC-001**: On the evaluation set, the success rate with the module is ≥ the success rate without it. Measured via the S3 result record, after the tie rule.
- **SC-002**: With A = context loaded without the module and B = with it, for each task: **the median of (1 − B/A) over the document tasks is at least 0.20**, and **B/A ≤ 1.10 on each code-only task**. All base runs count, pass or fail; the median over pairs where both arms passed is reported beside it. Measured via the S3 result record.
- **SC-003**: 100% of entries in the shop6 index pass validation, including resolving source pointers. Measured by running the validator.
- **SC-004**: In 100% of tested cases (a source edited, renamed and deleted), the next freshness check and the next lookup report it stale. Measured by test.
- **SC-005**: 100% of lookups in the test suite and the evaluation stay within the lookup budget. Measured by test and from the evaluation transcripts.
- **SC-006**: After installing and removing the module, the hashes of all core-managed files and the always-loaded instructions equal those of a module-free install. Measured by the kit's drift check.
- **SC-007** (reported, not part of the gate): the share of document-task runs with the module in which the agent used the lookup. Reported from the evaluation transcripts, so a failure can be told apart from "the agent never used it".

## Assumptions & dependencies

- Dependency: kit support for module rules in the always-loaded instructions (spec 001 FR-019), already on `main`.
- Dependency: v1's index format, key list, validator, freshness check and atomic rebuild, preserved at tag `exp/dense-v1`. This spec keeps their required behaviour (FR-002–FR-009).
- Dependency: the shop6 workspace as the evaluation target, with its `.ignore` (2026-10-30) so the agent's code search sees the product repos in both arms.
- Assumption: the evaluation set has 8 tasks, 6 document tasks (routing, cross-repo impact, review against the PRD or architecture) and 2 code-only tasks, run once per arm plus the tie rule (decision 6). With 2 code-only tasks, SC-002 applies the +10% limit to each.
- Assumption: the evaluation runs one fresh non-interactive session per task and arm, with the same read-only tool allowlist in both arms, as the shop6 knowledge-base evaluation did. Grading is done by a fresh read-only grader that sees only the answers, the answer keys and the pinned code; the owner spot-checks.
- Assumption: the 24% estimate comes from replaying v1's 6 baseline transcripts. Real lookups may cost more or less, and agents may read sources after a lookup; SC-002's 20% leaves about 4 points of margin.
- Assumption: only the `claude` target is evaluated. FR-018 on `copilot` is checked by install tests, not by an agent evaluation.

## Clarifications

### Session 2026-10-30

- Q: What does the lookup search? → A: The workspace documents the v1 index already covers. Code entry points: rejected for now (go stale every commit across 9 repos; overlap ADR 0038).
- Q: What is the gate? → A: SC-001 (success ≥ baseline) and SC-002 (−20% on document tasks, at most +10% on each code-only task). One mixed threshold and report-only were rejected.
- Q: Keep the sub-agent return contract? → A: No; dropped from v2 with its criterion.
- Q: What task set? → A: 8 new tasks, 6 document and 2 code-only, once per arm with the tie rule. v1's E1–E6 can't be reused (old revisions, environment without the Grep fix).
- Q: The grill set SC-002 on "context before the first action"; does a lookup end that count? → A (analyze, 2026-10-30): yes under v1's definition, which would bias arm B, so SC-002 uses **context loaded** (glossary) instead: everything up to the final answer, lookup output included. The value gate's replay already counted that way.
- Q: Do failed runs count toward SC-002? → A (analyze, 2026-10-30): yes, all base runs; the both-passed median is reported beside it, so an arm that gives up early can't hide behind a low number.

## Open questions

None. Every decision that shapes scope, the gate or the task split was settled in the grill.
