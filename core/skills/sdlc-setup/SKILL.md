---
name: sdlc-setup
description: "Configure sdlc-kit for this repository after install: fill .sdlc/config.json with the real build, test, lint, typecheck and integration commands, spec folder, tracker and budgets; locate the glossary and ADRs; report legacy agent folders and duplicate spec numbers. Use once after installing the kit, after major tooling changes, or when the user says 'set up sdlc'."
user-invocable: true
disable-model-invocation: true
---

# sdlc-setup: make the kit fit this repo

## When to use

- Right after `sdlc install`, and again when the build or test tooling changes.
- Not for editing kit content. That goes upstream (see `sdlc-retro`).

## Inputs

- `.sdlc/config.json`: created by the installer. It is project-owned, so you edit it here.
- Manifests and CI definitions (`package.json` scripts, `Makefile`, `pyproject.toml`, `go.mod`, `.github/workflows/*`, and so on), `AGENTS.md`, `README`.
- `sdlc check .` output, if the CLI is available.

## Process

1. **Discover the commands** from the manifests and the CI definitions, not by guessing. For each of `build`, `test`, `lint`, `typecheck` and `integration`:
   - Pick the non-interactive form, with a timeout where the runner supports one (no watch modes).
   - Note the prerequisites: services, credentials (check that they exist; never print them), private registries.
   - Run each one once, if that's safe and the prerequisites are present. Record the result as the baseline. Leave a command empty if the repo has none.
2. **Spec folder and numbering.** Confirm `spec_dir`. Report the duplicate prefixes (`sdlc check` lists them as `DUPLICATE-SPEC`). Don't rename existing folders; new specs take `sdlc next-spec`.
3. **Glossary and ADRs.** Find them: `CONTEXT.md`, `GLOSSARY.md`, `docs/glossary.md`; `docs/adr/`, `docs/decisions/`. If none exist, say so. Offer to create a glossary skeleton; don't create one unasked.
4. **Tracker.** Set `tracker` to `github` when the repo is on GitHub and issues are used, otherwise `none`.
5. **Budget.** Keep the defaults unless the repo's instructions state other limits. If they do, copy them and cite the source.
6. **Project rules.** Move any repo-specific mandatory rules the user wants enforced into `extra_instructions`: short, one line each. Leave the long prose in `AGENTS.md` outside the managed block.
7. **Legacy surfaces.** List any agent folders that overlap the kit: `.specify/`, `speckit-*` skills, old `.claude/agents`, `.github/agents`, `.github/prompts`, `.codex/`, `.agents/skills`, stale `skills-lock.json`. Recommend for each one: keep, migrate, or archive. **Delete nothing.** Migration is a separate change the user approves.
8. **Write the config.** Show the diff of `.sdlc/config.json`, apply it with the user's approval, then run `sdlc update .` so the managed blocks pick up `extra_instructions`.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Guess `npm test`, it's standard" | A wrong command makes every later "verified" claim false. Read the manifests and CI. |
| "Delete the old Spec Kit folders now" | Deleting during setup loses history and breaks the other agents still using them. Inventory and recommend. |
| "Renumber the duplicate specs" | That breaks links, branches and issues. Report them, and prevent new duplicates. |
| "Copy all of AGENTS.md into extra_instructions" | That duplicates it, and the copies drift. Keep one line per enforceable rule. |

## Red flags

- A command needs credentials that aren't present. Record it as blocked (`BLOCKED_<AREA>_AUTH`); don't work around it.
- The CI runs checks with no local equivalent. List them as remote-only in the setup report.
- The repo already has a conflicting process definition. Surface the conflict before activating the kit.

## Verification

- Every command in `.sdlc/config.json` came from a manifest or CI file (cite it), and its baseline result is recorded, or the reason it couldn't run is given.
- `sdlc check .` is clean, apart from warnings that are reported.
- The legacy-surface list has a recommendation per item, and nothing was deleted.

## Principles applied

evidence-over-claims, subtract-before-adding, fail-safe-keep-work
