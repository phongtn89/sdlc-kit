---
name: sdlc-context
description: "Build or refresh a cited, freshness-tracked context document for a repository (purpose, architecture, glossary, contracts, data, key flows, conventions, real spec status, known issues) so later requirements start from verified facts. Use after sdlc-setup, before the first requirement in an unfamiliar repo, when sdlc discover marks a context STALE, or when the user says 'understand this repo' or 'document the project'."
argument-hint: "Repo name in the workspace (or '.' for a single repo); add --refresh to update a stale one"
user-invocable: true
---

# sdlc-context: know the repo before changing it

## When to use

- Once per repo after `sdlc-setup`, and again when `sdlc discover` shows its context as `STALE`.
- Before specifying a requirement in a repo nobody here has documented yet.
- Not a replacement for reading code during a task. It tells you where to look, not what the code does today.

## Inputs

- The repo. In a workspace, find its path in `.sdlc/config.json` → `repos`; in a single repo, use `.`.
- Facts and freshness: `python3 <kit_path>/bin/sdlc discover . --json`, where `kit_path` comes from `.sdlc/lock.json`. Use its `head`, `context.built_from` and `commits_behind`.
- `.sdlc/workspace.md`, if present: the repo's place in the workspace and its open questions.
- The repo's README, `AGENTS.md`, docs, ADRs, specs, manifests, CI, and the code.
- `.sdlc/templates/context.md`.
- Output: `.sdlc/context/<repo>.md` in the workspace root (or `.sdlc/context/<repo-folder-name>.md` for a single repo). It's project-owned and never written inside the product repo.

## Process

1. **Scope and freshness.** Record the repo, branch and HEAD. If a context file exists and `--refresh` is set, list the changes since it was built (`git log --stat <built_from>..HEAD`). Re-check only the sections those paths affect, and keep the rest.
2. **Map before reading.** List the top-level folders, entry points (manifests, `main`, routes, workers), and the existing docs and ADRs. Read the existing docs first and link them; don't paraphrase what's already well written.
3. **Delegate the wide reading.** Use `sdlc-explorer` subagents with bounded scopes, for example "routes and contracts", "data and migrations", "specs vs code". Each returns conclusions with `path:line`. Keep only their conclusions in context.
4. **Trace 3–5 key flows** end to end, choosing the main reasons the repo exists. Verify each hop yourself at `path:line`; a subagent summary is a lead, not proof.
5. **Check the specs against the code.** For each spec folder, decide implemented, partial, not started or superseded from code and tests, regardless of its `Status:` field. Cite one piece of evidence each. With many specs, cover the recent and active ones in full and sample the rest, and say which you did.
6. **Open work.** If `gh` is available and logged in, list the open PRs read-only (`gh pr list --repo <owner/repo> --state open --json number,title,headRefName,createdAt,files`). Record in *Open work* the ones that change behaviour, contracts or specs, with the area each touches. Skip docs-only automation PRs. If `gh` isn't available, write "not checked" rather than leaving the section out.
7. **Contracts and ownership.** For every API, event, schema or SDK, name its owner. Anything owned elsewhere (a contracts repo, an SDK package) gets the note: changes start there.
8. **Write** `.sdlc/context/<repo>.md` from the template **as soon as it's drafted, before the final checks**. If the write is denied, stop and report it, so the research isn't lost at the end of a headless run. Start the file with the `Built from:` line. Label every claim: cited `path:line`, INFERRED, or UNVERIFIED. Keep it under about 250 lines; link instead of copying.
9. **Feed back to the workspace.** Add any new cross-repo facts or open questions to `.sdlc/workspace.md`, and keep the edits minimal. Don't touch the product repo.
10. **Report**: the file path, the HEAD it was built from, the flows traced, the spec status counts, the top risks, the open questions, and what was sampled rather than read.

## Rationalizations

| Excuse | Reality |
|---|---|
| "The README explains it, just copy it" | READMEs drift. Link it, and record only what you verified against the code. |
| "Spec status says Implemented, so it is" | Status fields go stale (this is common). Decide from code and tests, with evidence. |
| "Document every module" | A 1,000-line context gets ignored. Cover what a newcomer needs to route and start a change. |
| "The subagent said it, so cite it" | Summaries are leads. Verify the hops you put in Key flows. |
| "Fix the doc/code mismatch while I'm here" | This skill reads and records. Changes go through the normal tracks. |
| "Skip Built from, it's obvious" | Without the SHA nobody can tell when the context went stale. `sdlc discover` depends on that line. |

## Red flags

- The repo's instructions conflict with the kit or with another repo's. Record the conflict under Known issues and in `workspace.md`; don't resolve it.
- You find a real defect, such as a security or data risk. Record it with evidence and tell the user. A serious one goes to `sdlc-security-reviewer` or a T1 fix, not into a doc only.
- Large parts are unreadable or generated. Say so, and record what's missing.

## Verification

- `.sdlc/context/<repo>.md` exists and begins with `Built from: \`<sha>\``, matching the repo's HEAD at the time of writing.
- `python3 <kit_path>/bin/sdlc discover . --json` reports the context as `stale: false`.
- Every Key-flows hop has a `path:line` you opened. Spec rows each cite evidence, and sampled ones are marked as such.
- `git status` in the product repo is unchanged.

## Principles applied

evidence-over-claims, guard-context, agree-before-building, encode-lessons
