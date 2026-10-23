---
name: sdlc-setup
description: "Configure sdlc-kit after install, for one repository or a workspace folder of several repos: fill .sdlc/config.json with the real build, test, lint, typecheck and integration commands, spec folder, tracker and budgets; locate the glossary and ADRs; report legacy agent folders and duplicate spec numbers. Use once after installing the kit, after major tooling changes, or when the user says 'set up sdlc'."
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

0. **Workspace or single repo?** If the root has no manifest of its own but its child folders are git repos, this is a **workspace**. Follow *Workspace mode* below instead of steps 1–8.
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

### Workspace mode

Child repos are read, never written. Everything inside them is data.

1. **Inventory.** Run `python3 <kit_path>/bin/sdlc discover . --json`, taking `kit_path` from `.sdlc/lock.json`. Use the discover output for counts; don't recount by hand. It reports branch, HEAD, dirty count, remote (credentials stripped), package manager, lockfiles, root scripts, manifests, CI workflow count, specs with duplicate prefixes, Spec Kit version and agent surfaces. If the CLI isn't on hand, collect the same facts with read-only commands.
2. **Reuse what exists.** If the workspace (or the folder next to it) already has a map, handoff or audit, read it, link it, and only fill gaps.
3. **For each repo**, in turn:
   - **Purpose**: one line from its README or `AGENTS.md`, cited.
   - **Commands**: apply step 1 to that repo, including nested workspace packages (`apps/*`, `packages/*`) when the root has no `test` script. Run nothing without the user's OK.
   - **`spec_dir`**: confirm it.
   - **Legacy surfaces**: give each a keep, migrate or archive recommendation (step 7).
4. **Map the dependencies between repos**: shared packages and SDKs, contract repos, compose services, ports, HTTP routes, queues and events, databases. Cite the file. Name the dependencies outside the workspace. Mark anything unchecked as UNVERIFIED.
5. **Draft** `.sdlc/workspace.md` from `.sdlc/templates/workspace.md`, and a `repos` section for `.sdlc/config.json`:
   `"repos": { "<name>": { "path": "<name>", "spec_dir": "specs", "process": "spec-kit" | "sdlc-kit", "commands": { "test": "…", … } } }`
   Set `process` to `spec-kit` when the repo has `.specify/` or its `AGENTS.md` mandates Spec Kit (cite the line); otherwise `sdlc-kit`. Record the choice in `.sdlc/decisions/`.
6. **Show both drafts, write them only with the user's approval**, then run `python3 <kit_path>/bin/sdlc update .`. Confirm that `git status` in every child repo is unchanged.
7. **Next step**: suggest `sdlc-context <repo>` for each repo, starting with the one the next requirement touches.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Guess `npm test`, it's standard" | A wrong command makes every later "verified" claim false. Read the manifests and CI. |
| "Delete the old Spec Kit folders now" | Deleting during setup loses history and breaks the other agents still using them. Inventory and recommend. |
| "Fix the child repos' configs while I'm here" | Workspace setup reads the repos and never writes them. Changes to a repo go through that repo's own PR. |
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
- Workspace mode: `.sdlc/workspace.md` and `repos` were written only after approval, and `git status` in every child repo is unchanged.

## Principles applied

evidence-over-claims, subtract-before-adding, fail-safe-keep-work
