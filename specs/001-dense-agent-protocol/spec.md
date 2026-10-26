# Spec: Dense Agent Protocol module

Feature: dense-agent-protocol
Number: 001
Status: approved <!-- draft | approved | implemented | superseded by NNN. sdlc-analyze sets approved; sdlc-ship sets implemented. -->
Approved: phong.ngo.vn, 2026-10-26
Owner: phong.ngo.vn
Created: 2026-10-26
Track: T3

<!-- Source of the decisions: shop6 workspace, .sdlc/decisions/2026-10-26-dense-agent-protocol.md (grill, play-back confirmed 2026-10-26). The prototype index is shop6 .sdlc/manifest.yaml (hand-written reference). -->

## Intent

**Problem:** Before an agent can act in a workspace, it reads long context documents. In the shop6 workspace that is about 307 KB of PRD, architecture view, workspace map and per-repo context. Sub-agents then return prose summaries that use up more of the parent's context. Long tracks hit the context budget early and need extra handoffs. The kit has no compact form for either.

**Who:** Agents that run sdlc tracks on both supported targets, and the maintainers who install the kit into a workspace or repo.

**Why now:** A hand-written prototype index for shop6 is about 40 times smaller than its sources, but it isn't tracked for freshness, has no key list and no citations. Before compact context spreads by copy-paste, it needs to be a governed, measurable, opt-in capability.

## Out of scope

- Compressing handoffs (deferred until v1 passes its gate).
- Compressing the kit's own instruction text: skills, roles, principles, `AGENTS.md`.
- Rolling out to fleet repos or to their own process rules (that goes through standards later).
- Serving the index from a central knowledge service (alignment with standards ADR 0038 is deferred).
- Replacing context documents. They stay the record.
- Lossy summarisation that adds, merges or reinterprets facts.

## Glossary terms used

- **Context document**: the cited, freshness-tracked description of one repo that `sdlc-context` writes (existing kit term).
- **DAP (Dense Agent Protocol)**: this module's key list, index format and sub-agent return contract. New.
- **Dense index**: a compact, schema-valid summary of a workspace's or repo's context sources, used to find things, never as evidence. New.
- **Key list**: the fixed set of short keys, their meanings and value forms that dense artifacts may use. New.
- **Source pointer**: the reference on each index entry to the source section it was derived from. New.
- **Return contract**: the required shape of a sub-agent's reply when the module is enabled. New.
- **Context headroom**: context left free for task work after the agent has loaded what it needs. New.
- **Always-loaded instructions**: the kit-managed instruction block every agent loads on every target (today the managed block in `AGENTS.md` and in the Copilot instructions file). Existing kit concept.
- **Index revision**: the short content hash of the index file that the freshness check prints; it identifies which index an agent used. New.
- **Module rules**: rules an installed module adds to the always-loaded instructions, shown in their own section and removed with the module. New.

## User scenarios

### S1 — Orient a track from a fresh dense index (P1)

As an agent starting a track in a workspace with the module enabled, I want to load the dense index instead of every context source, so that most of my context stays free for the task.

**Independent test:** In a workspace with a fresh index, start one routing or impact task in a fresh session. Check the transcript: the index is loaded first, only the sources the task needs are opened afterwards, and the final report cites source locations, never the index.

1. **Given** a fresh, valid index, **When** a track starts, **Then** the agent loads the index before any full context source and quotes the index revision (the short hash the freshness check prints) it used.
2. **Given** a fresh index, **When** the task needs a fact in detail, **Then** the agent opens only the source sections that the relevant entries point to.
3. **Given** a claim in the agent's final report, **When** it was found through the index, **Then** the claim cites the source location, not the index.
4. **Given** a stale index, **When** a track starts, **Then** the agent says the index is stale, names the changed sources, and uses the full sources for those areas.
5. **Given** no index or an invalid one, **When** a track starts, **Then** the agent says so and continues with the full sources exactly as without the module.

### S2 — Build and keep the index honest (P1)

As a maintainer refreshing context with the module enabled, I want the index derived from the context sources and checked automatically, so that it can't drift into a second, unreliable source of truth.

**Independent test:** Run a context build in a test workspace; validate the index; change one source; run the freshness check.

1. **Given** context sources exist, **When** a context build runs with the module enabled, **Then** an index is written that records the revision or content hash of every source it used.
2. **Given** a written index, **When** it is validated, **Then** every key belongs to the key list, every entry has a source pointer that resolves to an existing section, and validation passes.
3. **Given** an index with an unknown key, a missing pointer or a pointer to a missing section, **When** it is validated, **Then** validation fails and names each offending entry and location.
4. **Given** a source changed after the index was built, **When** freshness is checked, **Then** the index is reported stale, with the changed source named.
5. **Given** a source holds a fact marked unverified or inferred, **When** it reaches the index, **Then** the entry keeps that marking.
6. **Given** a valid index exists, **When** a rebuild fails or produces an invalid index, **Then** the last valid index stays in place unchanged, the failure is reported, and the freshness check keeps reporting only source changes.

### S3 — Sub-agents return dense findings (P2)

As a parent agent delegating a search or review, I want sub-agent replies in a fixed dense shape, so that each return costs little context and keeps its evidence.

**Independent test:** Delegate one bounded search with the module enabled; check that the reply follows the return contract and that every finding has a location.

1. **Given** the module is enabled, **When** a parent delegates work to a sub-agent, **Then** the brief includes the return contract.
2. **Given** a brief with the return contract, **When** the sub-agent replies, **Then** each finding consists of a source location and a single-sentence claim, using only keys from the key list.
3. **Given** a reply that does not follow the contract, **When** the parent receives it, **Then** the parent flags it, asks for a reformat at most once, and otherwise uses the reply as is with a note. No evidence in the reply is dropped.

### S4 — Prove the gain before enabling (P2)

As a maintainer, I want a paired evaluation that compares the module against full context, so that enabling it is based on evidence and not on size alone.

**Independent test:** Following the shipped evaluation method, run the workspace's evaluation set once with and once without the module and record the results.

1. **Given** the evaluation set, **When** each task runs in a fresh session with the module and again without it, **Then** a result record shows the pass/fail result for each task and the context used before the first action, for both runs.
2. **Given** the records, **When** the gate is checked, **Then** it passes only if the success rate with the module is at least the success rate without it, **and** median context before the first action is at least 50% lower.

### S5 — Install and remove cleanly (P3)

As a maintainer, I want to switch the module on and off without touching core kit files, so that I can back it out if the evaluation fails.

**Independent test:** Install the kit with and without the module; compare the core file hashes; uninstall the module.

1. **Given** a kit install, **When** the module is added, **Then** no core-managed file changes except that the always-loaded instructions gain the module-rules section and the module's Skills index entry (FR-017), and the lock records the module.
2. **Given** the module is installed, **When** it is removed, **Then** only the module's files are removed, and agents behave as without the module (S1.5).

## Requirements

- **FR-001**: The module MUST be opt-in. Without it, kit behaviour and installed files MUST be identical to a kit without the module. (S5)
- **FR-002**: The module MUST ship a key list that defines, for every allowed key, its meaning and value form, in a form a validator can check. (S2)
- **FR-003**: With the module enabled, its module rules MUST require the dense index to be built or refreshed after every context build: one index per workspace in workspace mode, one per repo in single-repo mode. The module supplies the build step itself; core context-building behaviour is unchanged. (S2)
- **FR-004**: Every index entry MUST carry a source pointer to the section it was derived from. (S2)
- **FR-005**: The index MUST record the revision or content hash of each source it was built from. (S2)
- **FR-006**: The freshness check MUST report the index as stale, naming the changed sources, when any recorded source differs from its current state. (S1, S2)
- **FR-007**: Validation MUST reject an index with an unknown key, a missing source pointer or a pointer to a missing section, and name each failing entry. (S2)
- **FR-008**: The index MUST NOT contain a fact that is absent from its sources, and MUST keep unverified or inferred markings. (S2)
- **FR-018**: A failed or invalid rebuild MUST NOT replace the last valid index. (S2)
- **FR-009**: When a fresh, valid index exists, the module rules MUST require agents to load it before full context sources and to open only the source sections the task needs. (S1)
- **FR-010**: Agents MUST NOT cite the index as evidence. Claims MUST cite the source location. (S1)
- **FR-011**: When the index is stale, missing or invalid, agents MUST say so and use the full sources for the affected areas. They MUST NOT use a stale entry without saying so. (S1)
- **FR-012**: With the module enabled, the module rules MUST require every delegation brief to include the return contract, which the module ships. (S3)
- **FR-013**: The return contract MUST require each finding to be a source location plus a one-sentence claim, using only keys from the key list. (S3)
- **FR-014**: On a non-conforming return, the parent MUST flag it, ask for a reformat at most once, and MUST NOT drop evidence from the reply. (S3)
- **FR-015**: The module MUST behave the same on every target the kit supports (today `claude` and `copilot`). (S1, S3)
- **FR-016**: The module MUST ship an evaluation method: the paired run procedure, the result record format, and a task template with Expect items. The concrete evaluation set (at least 6 tasks covering routing, cross-repo impact and review) and its results MUST live in the target workspace, not in the kit. (S4)
- **FR-017**: Installing or removing the module MUST NOT modify any core-managed file. The only exception is the always-loaded instructions, which change only by gaining or losing the module-rules section and the module's own Skills index entries. Removing it MUST remove only the module's files and rules. (S5)
- **FR-019**: The kit MUST let any installed module contribute module rules to the always-loaded instructions on every target. Without modules that contribute rules, the always-loaded instructions MUST be identical to today's. (S1, S3, S5)

## Non-functional

- **NFR-001**: The index MUST NOT copy secrets, credentials or personal data from its sources. A source that holds them is referenced by pointer only.
- **NFR-002**: The index SHOULD be no larger than 5% of its sources' combined size. The shop6 prototype is about 2.4%.
- **NFR-003**: Validation and the freshness check MUST run offline, non-interactively, and finish within 10 s for a workspace the size of shop6.
- Performance of agents, availability and accessibility: not applicable (no runtime service or UI).

## Success criteria

- **SC-001**: On the shop6 evaluation set, the success rate with the module is ≥ the success rate with full context. Measured via the S4 result record.
- **SC-002**: Median context used before the first action is ≥ 50% lower with the module. Measured via the S4 result record.
- **SC-003**: 100% of index entries in the shop6 index pass validation, including resolving source pointers. Measured by running the validator.
- **SC-004**: In 100% of tested cases (at least one per source type), changing a source makes the next freshness check report the index stale. Measured by test.
- **SC-005**: ≥ 90% of sub-agent returns in the evaluation follow the return contract without a reformat. Measured from the evaluation transcripts.
- **SC-006**: After installing and removing the module, the hashes of all core-managed files, and the always-loaded instructions, equal those of a module-free install. Measured by the kit's drift check.

## Assumptions & dependencies

- Assumption: context documents keep their `Built from` revision line, and sources keep stable headings that section pointers can target.
- Assumption: one workspace index summarises the workspace-level documents (PRD, architecture view, workspace map) and all per-repo context documents; the shop6 prototype has this shape.
- Assumption: "context used before the first action" can be read from session usage figures on both targets. The method is chosen in the plan.
- Assumption: the v1 gate is judged on a shop6 evaluation set, kept in the shop6 workspace and drawn from real shop6 work. A run counts as passed when every Expect item is observable, as in the existing kit evals.
- Dependency: the kit's freshness check (`discover`) and drift check (`check`).
- Dependency: the shop6 workspace as the first target and evaluation ground; the existing prototype index is the reference fixture.
- Dependency: the module mechanism. Today modules add skills, roles, templates and checklists, and their skills are listed in the always-loaded index, but they can't add rules (kit `bin/sdlc:27,212-235,245-260`). FR-019 is the one generic kit change this feature needs.
- Assumption: agents follow module rules less strictly than skill steps. S4's evaluation measures whether this matters (SC-001, SC-005); if it fails, revisit step hooks in core skills (the option rejected in the 2026-10-26 clarify session).

## Clarifications

### Session 2026-10-26 (grill, recorded in shop6 `.sdlc/decisions/2026-10-26-dense-agent-protocol.md`)

- Q: Goal? → A: Context headroom; accuracy first.
- Q: Surfaces in v1? → A: Workspace/repo context index and sub-agent returns.
- Q: Home? → A: Opt-in kit module.
- Q: Index source? → A: Derived during the context build, freshness-tracked; context documents stay the record.
- Q: Keys and evidence? → A: Fixed key list with schema; a source pointer per entry; cite the source, never the index.
- Q: Sub-agent returns? → A: Return contract carried in the brief; core role files untouched.
- Q: Gate? → A: Paired evaluation on ~6 tasks; no loss in success rate and ≥ 50% less context before the first action.

### Session 2026-10-26 (sdlc-clarify)

- Q: Modules can't change core behaviour. How does the module make the context build produce the index and briefs carry the return contract? → A: **Module rules in the always-loaded instructions.** A small, generic kit change lets any module contribute rules in their own section (FR-019). The dense module ships its own index-building step and return-contract template, and its rules require: build the index after a context build, load it at track start, include the contract in every brief. Core skills and roles stay untouched. Rejected: step hooks in core skills (edits core skills, against grill decision 6); explicit module skills only (weakens FR-009 and FR-012); workspace-only rules (not reusable or lock-tracked, against grill decision 3). Changed: glossary, FR-003, FR-009, FR-012, FR-017, new FR-019, SC-006, assumptions and dependencies.

- Q: The module ships the evaluation set, but the tasks come from shop6. Where does it live? → A: **The kit ships the method** (procedure, record format, task template); **the 6 concrete tasks and their results live in the shop6 workspace**, and the gate is judged there. Rejected: all in the kit (JTL-specific content in a generic kit); synthetic fixture tasks only (they don't prove the gain at real scale). Changed: FR-016, SC-001, assumptions.

### Session 2026-10-26 (implementation, T021)

- Q: Installing the module also adds its skill to the always-loaded Skills index (existing kit behaviour for every module, e.g. `qa`). FR-017 and S5.1 said the instructions change only by the module-rules section. → A: Wording corrected to include the module's own Skills index entries. No behaviour change; SC-006 (exact restore on removal) is unchanged. Found by `DenseModule.test_add_and_remove_restores_install`.

## Open questions

None. The core-seam question was resolved in the 2026-10-26 clarify session.
