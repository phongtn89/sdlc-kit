# Definition of done

Load before claiming any task, slice or PR complete. Every item needs evidence at the current revision; an unchecked item is reported, not hidden.

## Scope
- [ ] Every in-scope requirement or acceptance check maps to code, a test and current docs.
- [ ] Nothing outside the agreed scope changed; `git diff --stat` lists only intended files.
- [ ] Deferred, skipped, blocked and human-only work is listed and left unchecked in `tasks.md`.

## Tests
- [ ] Each behaviour change has a test that was seen failing (RED) before the fix.
- [ ] Happy path plus relevant boundary, invalid-input and failure cases are covered.
- [ ] Bug fixes keep the reproduction as a regression test.
- [ ] Tests ran once, non-interactively, with a timeout; no watch mode.
- [ ] Behaviour unit tests cannot prove was checked on the real surface (HTTP, UI, CLI).

## Gates
- [ ] Full build passes (`commands.build` in `.sdlc/config.json`).
- [ ] Full test suite passes (`commands.test`), not only the narrow tests.
- [ ] Lint, format and typecheck pass (`commands.lint`, `commands.typecheck`).
- [ ] Integration or end-to-end tests pass where available (`commands.integration`).
- [ ] Every gate that could not run is named with the reason; remote-only checks are marked unverified.

## Code
- [ ] No debug output, commented-out code, stale comments or dead code introduced.
- [ ] No new dependency, type or helper that an existing one already covers.
- [ ] No secrets, tokens or personal data in code, logs, fixtures or commits.
- [ ] Diff size is within `budget.reassess_lines`, or the overrun is justified.

## Docs and artifacts
- [ ] Owning spec, tasks, ADRs, API and operational docs reflect the new behaviour.
- [ ] Contracts, migrations and generated artifacts are regenerated and validated if touched.
- [ ] Applicable checklists (security, observability, performance, compatibility-migration, accessibility) were loaded and their items addressed.

## Report
- [ ] Final report lists exact commands, exit status and the revision they ran on.
- [ ] Claims are labelled verified, inferred or assumed.
- [ ] Principles applied are cited by name.
