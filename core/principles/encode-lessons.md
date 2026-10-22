# encode-lessons

Every repeated mistake is a missing piece of structure.

- When the user corrects you, or a review finds the same class of defect twice, ask: which checklist item, principle, template field, or skill step would have prevented it?
- Propose that change concretely (`sdlc-retro`): to the project (`.sdlc/config.json` → `extra_instructions`, or AGENTS.md outside the managed block) or upstream to the kit.
- Prefer an automated check (test, lint rule, CI step) over prose when one is possible.
- Never edit installed kit files in place; `sdlc check` will flag the drift.

**Smell:** the same review comment on three PRs; "remember to…" in chat.
