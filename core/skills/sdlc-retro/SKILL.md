---
name: sdlc-retro
description: "Turn what went wrong or slow into structure: collect corrections, review findings and rework from the finished work, find the missing checklist item, principle, template field, skill step or automated check, and propose the concrete change to the project or the kit. Use after shipping a feature, after a repeated correction, or when the user says 'retro', 'reflect' or 'what should we change'."
argument-hint: "Feature folder, PR, or 'session'"
user-invocable: true
---

# sdlc-retro: encode the lesson

## When to use

- After a T3/T4 feature ships, or after any task with notable rework.
- Immediately when the user corrects the same thing a second time.
- When reviews keep raising the same class of finding.

## Inputs

- The feature's `tasks.md` (convergence gaps, blocked items, progress log), its review reports, and the PR comments.
- Corrections the user gave in the session, the handoffs written, and the re-routes made.
- `.sdlc/config.json` (`extra_instructions`), `.sdlc/principles/encode-lessons.md`.

## Process

1. **Collect the events**: each correction, rework, review finding, blocker, re-route or wasted step. Give each one line, with its evidence (a link or `path:line`).
2. **Group by cause, not by symptom.** For each group, ask: which piece of structure, had it existed, would have prevented this?
3. **Pick the cheapest durable fix** for each group, in this order of preference:
   1. An automated check: a test, a lint rule, a CI step, a `sdlc check` rule.
   2. A template field or checklist item.
   3. A skill step or a red flag.
   4. A principle.
   5. A project rule (`.sdlc/config.json` → `extra_instructions`, or `AGENTS.md` outside the managed block).
4. **Choose the scope.** Project-specific lessons go in the project config or `AGENTS.md`. Lessons that would help any project go **upstream to the kit**: draft the change as a diff or issue text against the kit repository. Never edit the installed `.claude/skills`, `.github/skills` or `.sdlc/` files in place; `sdlc check` flags that drift and the next update overwrites it.
5. **Also record what worked**: one or two practices to keep.
6. **Present** a table of the lesson, the evidence, the proposed change, where it goes and its cost. Apply project-config changes only with the user's approval. Kit changes go as proposals.

## Rationalizations

| Excuse | Reality |
|---|---|
| "We'll remember next time" | Memory doesn't transfer between sessions or people. Structure does. |
| "Add a paragraph to AGENTS.md" | Long instructions get skimmed. A check or a checklist item is enforced. |
| "Edit the installed skill directly, it's faster" | The next update overwrites it, and other projects never benefit. Change it upstream. |
| "Every finding needs a new rule" | Rules cost attention. Encode only the repeated or the expensive ones. |

## Red flags

- The proposed fix adds a new mandatory gate. That needs the owner's approval, not just a retro.
- The lesson contradicts the constitution. Raise it as a kit-level discussion.
- The retro blames people instead of finding the missing structure.

## Verification

- Every lesson cites evidence and maps to one concrete change with a destination.
- Approved project changes are applied (list the files). Kit proposals are written down (give the path or link).
- No installed kit files were edited (`sdlc check` is clean).

## Principles applied

encode-lessons, evidence-over-claims
