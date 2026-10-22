# thin-vertical-slices

Cut work into tracer bullets: each slice delivers one narrow path through every layer it needs, and is testable on its own.

- A task names its acceptance check, its write set (files), and what it **blocks** / is **blocked by**.
- Slice by behaviour, not by layer ("create order happy path" — not "all DB models").
- First slice proves the riskiest integration end to end; later slices widen it.
- Tasks whose write sets don't overlap and that don't block each other may run in parallel.

**Smell:** "Phase 1: write all models; Phase 2: write all routes"; tasks with no way to verify them alone.
