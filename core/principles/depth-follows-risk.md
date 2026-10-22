# depth-follows-risk

Match the amount of process to the risk of the change, decided **after** a short look at it, not before.

- Spend a few minutes reading the code at the seam before choosing a track (the `sdlc` router, tracks T0–T4).
- Escalate as soon as new facts appear: a contract, migration, auth/tenant boundary, second repository or >1 seam turns T1/T2 into T3.
- Never de-escalate silently. Say why a lighter track is enough.
- Padding small work with specs is waste; skipping a spec on a contract change is a defect.

**Smell:** a 3-line config change with a plan.md, or a new API endpoint with no spec.
