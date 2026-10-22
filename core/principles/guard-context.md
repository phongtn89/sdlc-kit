# guard-context

Context is the scarcest resource; spend it on the task.

- Read the exact seam: symbol lookups or line-bounded slices, not whole large files. Don't re-read unchanged files.
- Delegate wide searches to an `sdlc-explorer` subagent with an explicit scope, and keep only its conclusion.
- Keep command output compact (filters, `--quiet`, tails). Don't paste full logs.
- At ~70% of the budget in `.sdlc/config.json` → `budget`, or when switching phases, write a handoff (`sdlc-handoff`) and continue fresh.

**Smell:** the same 600-line file read three times; a subagent asked to "look around the repo".
