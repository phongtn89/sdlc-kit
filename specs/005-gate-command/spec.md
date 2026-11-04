# Spec: `sdlc gate`, mechanical readiness checks

Feature: gate-command
Number: 005
Status: approved <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: one-line reason). sdlc-analyze sets approved; sdlc-ship sets implemented; rejected records a feature that was built or evaluated and deliberately not adopted. -->
Approved: phong.ngo.vn, 2026-11-04, digest sha256:104928ddbb0fd8b443e5d149faaa736aed99539579c35b2a390ac8cd1b4c7a19 (spec 87ab0751fbb8, plan 519dc9ca4ed2, tasks d0f1f018c92c, contracts 4d902ac5d19c) <!-- name, YYYY-MM-DD; filled when approved -->
Owner: phong.ngo.vn
Created: 2026-11-04
Track: T3

<!-- Roadmap story E1.3 (docs/roadmap/layers-plan.md); ADR-0003 (docs/adr/0003-enforcement-model.md), ladder level 5. Builds on spec 004 (`sdlc verify`). The hooks that act on these gates are E1.4 and the CI recipe is E1.5; neither is in this spec. -->

## Intent

**Problem:** Three rules that matter are prose today: a T3 feature is not implemented before a human approves its spec, plan and tasks; "tests are green" refers to the code that exists now; a ticked task has evidence. An agent can drift from each of them without any command saying so. In spec 003 the approved documents were edited after approval and nothing noticed; spec 004's `verify` now leaves a record, but nothing reads it.

**Who:** Agents about to implement or ship, humans reading their claims, and the hooks and CI recipe of epic E1 that need a command whose exit code answers "may this proceed".

**Why now:** ADR-0003 names these three checks as the level-5 half of the first three "must never happen" rules, and spec 004 supplies the record the second check reads.

## Out of scope

- Blocking anything: a gate only reports. Hooks (E1.4) and CI (E1.5) act on its exit code.
- Authenticating the approver. `approve` records the name it is given; it is a record, not a signature (the same stated limit as spec 004's record).
- Specs approved before this feature: 002, 003 and 004 have no digest, so `gate approved` reports them as having none; and spec 004's progress log lacks hashes for T015–T017 and H1, so `gate evidence-for-ticks` fails on it. There is no migration. Spec 005's own approval line is written by hand at H1 (the command does not exist yet) and replaced by `approve` before the merge (task T012).
- Task text added after the progress log: not covered by the digest.
- Review-record validation (`gate review`, E2.3), value gates (E6.3), budgets (E1.6).
- Judging whether the evidence a log line cites is true; only that a line naming the task and a real revision exists.

## Glossary terms used

- **Approval digest**: a SHA-256 over the normalised text of `spec.md`, `plan.md` and `tasks.md` and the text of the feature's `contracts/*.md` and `data-model.md`, recorded on the spec's `Approved` line.
- **Normalised**: with status lines, task checkboxes in bullet lists and the tasks file's progress log removed, so ordinary work (ticking tasks, logging, marking the spec implemented) doesn't change the digest but any change to requirements, plan text or task text does.
- **Evidence for a tick**: a progress-log line that names the task and a revision that exists in the repository.
- **Green at HEAD**: as defined by spec 004.

## User scenarios

### S1: Implementation starts only on documents a human approved (P1)

As a maintainer, I want to know mechanically that the spec, plan and tasks are the ones that were approved, so that an edit after approval can't slip through unreviewed.

**Independent test:** a spec with a recorded digest passes; changing one requirement, plan line or task text makes it fail; ticking a task or adding a log line doesn't.

1. **Given** a spec approved with a digest, **When** I run `sdlc gate approved`, **Then** it passes (exit 0) when the status is approved or implemented and the digest matches.
2. **Given** a requirement, plan line, contract or task text is edited after approval, **When** I run it, **Then** it fails (exit 1) and says which part changed since approval.
3. **Given** a task is ticked and a progress-log line added, **When** I run it, **Then** it still passes.
4. **Given** a draft spec, or an approved one with no digest, **When** I run it, **Then** it fails and says why.

### S2: Recording an approval (P1)

As an agent with a human's yes, I want one command that records the approval, so that the digest is computed by the program, not typed by me.

**Independent test:** `approve` on a draft spec sets the status, the approver, the date and the digest, and changes nothing else.

1. **Given** a draft spec and the approver's name from chat, **When** I run `sdlc gate approve --by <name>`, **Then** the spec's status becomes approved, its `Approved` line holds the name, today's date and the digest, and no other line changes.
2. **Given** the plan was edited after an earlier approval, **When** a human re-approves and I run `approve` again, **Then** the digest is replaced.
3. **Given** the spec is `implemented`, `rejected`, `superseded` or has no plan or tasks file, **When** I run `approve`, **Then** it refuses (exit 2) and changes nothing.

### S3: "Green" refers to the code that exists (P1)

As a reviewer, I want a command that says whether the last `verify` result describes the current `HEAD`, so that a result from older code can't pass.

**Independent test:** after a new commit, the same record fails.

1. **Given** a green `verify` record at the current `HEAD` and a tree that is still clean, **When** I run `sdlc gate green-at-head`, **Then** it passes.
2. **Given** a new commit, a record that was dirty, a tree changed since the record, a failed command or no record, **When** I run it, **Then** it fails and names which.

### S4: Ticks carry evidence (P1)

As a reader of `tasks.md`, I want every ticked task to point to a revision, so that "done" is checkable.

**Independent test:** a tick with no matching log line fails; a tick covered by a line or a range naming a real commit passes.

1. **Given** ticked tasks whose progress-log lines name them and a commit that exists, **When** I run `sdlc gate evidence-for-ticks`, **Then** it passes.
2. **Given** a ticked task with no such line, or whose line names a commit that doesn't exist, **When** I run it, **Then** it fails and lists each task.

### S5: Workspaces and skills (P2)

1. **Given** a workspace, **When** I run a gate with `--repo <name>`, **Then** it works inside that repo's folder and spec folder.
2. **Given** the kit's skills, **When** an agent analyses, implements or ships a T3 feature, **Then** `sdlc-analyze` runs `approve` after the human's approval, and `sdlc-implement` and `sdlc-ship` run the gates and quote their last line.

## Requirements

- **FR-001**: `sdlc gate <name> <dir>` MUST support `approved`, `green-at-head`, `evidence-for-ticks` and `approve`; an unknown name is exit 2. (S1–S4)
- **FR-002**: `approved`, `evidence-for-ticks` and `approve` MUST take `--spec <NNN or folder>` naming a feature folder under the project's `spec_dir` (default `specs`); a missing or ambiguous spec is exit 2. (S1, S2, S4)
- **FR-003**: `<dir>` is the project root, as for every `sdlc` command. Exit codes MUST be 0 when the gate passes, 1 when it fails, 2 for usage or config errors, an unreadable or malformed document, or a refused `approve`. (all)
- **FR-004**: Every gate MUST print one line per problem and a last line `gate <name>: PASS` or `gate <name>: FAIL (<n> problems)`; the exceptions are a successful `approve` (its own PASS line naming the approver, date and digest) and exit 2 (one `sdlc: error:` line, no gate line). (all)
- **FR-005**: The approval digest MUST be a SHA-256 combining the SHA-256 of each of four parts (the normalised `spec.md`, `plan.md` and `tasks.md`, and the feature's contract files), and the `Approved` line MUST also record a short prefix of each part's own SHA-256, so a mismatch can name the part; normalisation (contract) ignores only the status word of the spec's `Status:` header line, the name, date and digest of its `Approved:` line (the rest of both lines stays covered), the status word of the inline `Status:` field of the `Spec:` or `Inputs:` line, checked boxes in bullet lists of `tasks.md`, and the progress log of `tasks.md`. Nothing in `spec.md`, `plan.md` or the contract files may be ignored beyond those lines. An intended edit to an approved document needs a re-approval by the human. (S1)
- **FR-006**: `approved` MUST pass only when the spec's status is `approved` or `implemented`, its `Approved` line holds a name, a `YYYY-MM-DD` date and `digest sha256:<64 hex>`, and the digest equals the one computed now; on a mismatch it MUST name each part (spec, plan, tasks, contracts) whose normalised text changed since approval. A spec with no `Status:` line fails. (S1)
- **FR-007**: `approved` on a spec without a digest, or in draft, MUST fail with the reason. (S1)
- **FR-008**: `approve --by <name>` MUST require a non-empty name, accept only a spec whose status is `draft` or `approved` and whose `plan.md` and `tasks.md` exist, and write the status `approved` and `Approved: <name>, <today UTC>, digest sha256:<hex>`; it MUST NOT change any other line, and MUST write atomically (a failure leaves the file as it was, exit 2). (S2)
- **FR-009**: `green-at-head` MUST read the evidence record of spec 004 (`.sdlc/evidence/verify.json`, or the repo's own with `--repo`), compare it with the current `HEAD`, and pass only under spec 004's green-at-HEAD definition **and** only if the working tree is still clean now (ignoring `.sdlc/evidence/`), so edits made after the check can't ride on it; a failure MUST say which condition failed (no record, unreadable record, record shape or version wrong, git not found, git timed out, HEAD unresolved, other revision, record dirty, tree changed since, no revision, no commands, a failed command, git status failed). The record is not a "document": a missing or unreadable record is exit 1, not 2. It MUST NOT run any command from the record. (S3)
- **FR-010**: `evidence-for-ticks` MUST treat each checked task or human-step box in `tasks.md` as needing evidence: a line in the `## Progress log` section that names the id (as a whole token, alone, in a list, or inside a range such as `T001–T012`) and a hexadecimal revision of 7 to 40 characters that exists in the repository as a commit; each task without it MUST be reported, and a checked box without an id MUST be reported too. (S4)
- **FR-011**: A gate MUST NOT write anywhere except `approve` writing the one spec file; it MUST NOT run any command from the project's config or records, and MUST NOT write outside the project root. (all)
- **FR-012**: Git questions MUST be asked with read-only git (no optional locks, no fsmonitor) and a failed or timed-out git call MUST make the gate fail (exit 1, with the reason), never pass. (S3, S4)
- **FR-013**: In a workspace, `--repo <name>` MUST resolve the repo's path, its `spec_dir` (falling back to the top-level one, then `specs`) and its own evidence record as the contract says; an unknown repo, a non-string path or `spec_dir`, or a path leaving the project root is exit 2. `--spec` MUST name a folder inside that `spec_dir`; an absolute or outside path is exit 2. (S5)
- **FR-014**: `sdlc-analyze` MUST tell the agent to run `approve --by <name>` only after the human's explicit approval in chat, with the name they gave; `sdlc-implement`'s readiness gate MUST run `gate approved` (for a legacy spec that reports no digest it asks the human instead of proceeding), its finish step MUST run `gate evidence-for-ticks`, and `sdlc-ship` MUST run `gate evidence-for-ticks` and, after the post-commit `verify`, `gate green-at-head`, each quoting the gate's last line (`green-at-head` is not run at implement's finish, where the tree is still dirty); the constitution MUST carry one matching rule. (S5)

## Non-functional

- **NFR-001**: Python 3.9+ standard library only, no network, no prompts (checked by a test that scans the module's imports).
- **NFR-002**: A gate runs git at most three times, however many tasks or log lines there are; it reads only the config, the spec folder's documents and contract files, and the record.
- **NFR-003**: The digest is reproducible: the same three documents give the same digest on any machine, including with different line endings (`\r\n` is treated as `\n`).

## Success criteria

- **SC-001**: For the document edits {a requirement, a plan line, a contract line, a task description, a new task} `approved` fails after approval in 100% of test cases, and for {tick a box, add a log line, set the status to implemented} it passes in 100% — measured by unit tests.
- **SC-002**: `green-at-head` agrees with spec 004's definition on the same truth table (current clean pass; new commit; dirty; no revision; failed command; no record) — measured by unit tests.
- **SC-003**: `evidence-for-ticks` reports exactly the ticked ids without evidence on fixtures covering single ids, lists, ranges, a missing commit and a revision that doesn't exist — measured by unit tests.
- **SC-004**: Removing the digest comparison, the commit-exists check, or the record read makes at least one test fail each — measured by mutation checks.

## Assumptions & dependencies

- Assumption: the approval, in the kit's flow, is the human's explicit yes in chat to the T3 gate; the agent passes their name to `approve`.
- Assumption: progress-log lines in the form of specs 002 and 003 (`- 2026-11-04 \`<sha>\` — T001 done …`, ranges allowed) are the evidence format; spec 004's log does not always carry a hash, so the gate fails on it (Out of scope). The tasks template states the format. A squash or rebase merge that makes the cited commits unreachable, or a shallow CI checkout, makes the gate fail; both are stated limits.
- Dependency: spec 004 (`verify`, the record and its green-at-HEAD definition), ADR-0003.

## Clarifications

### Session 2026-11-04

- Q: Where is the approval digest recorded → A: on the spec's `Approved` line, written by `gate approve` (chosen by phong.ngo.vn in chat).
- Q: What counts as evidence for a tick → A: a progress-log line naming the task id and a commit that exists (chosen by phong.ngo.vn in chat).

## Open questions

None.
