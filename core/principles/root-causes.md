# root-causes

Fix why it broke, not where it showed up.

- Reproduce first (failing test, script, or exact request). No reproduction → you are guessing.
- Ask "why" until you reach a cause you can change; state it in one sentence with evidence.
- Make the smallest fix at the cause; keep the reproduction as a regression test.
- Check for siblings: the same cause elsewhere (search for the pattern).
- Do not disable a check, widen a catch, or add a retry to hide a deterministic failure.

**Smell:** `try/catch` added around the crash site; "flaky" without a measured failure rate.
