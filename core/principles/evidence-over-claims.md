# evidence-over-claims

A statement about the system is either backed by evidence or labelled as an assumption.

- Evidence = the exact command, its exit status/relevant output, and the revision it ran on; or a `path:line` you read.
- Label claims: **verified** (you ran/read it), **inferred** (follows from verified facts), **assumed** (not checked).
- Summaries from subagents, tools or earlier sessions are leads, not proof. Re-check anything you rely on.
- Never write "tests pass", "deployed", or "fixed" without having seen it at the current revision.

**Smell:** "should work now"; a green result from before the last edit.
