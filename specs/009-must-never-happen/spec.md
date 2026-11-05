# Mini-spec: a "must never happen" test for every enforced rule (E1.7)

Track: T2 · Status: draft · Owner: phong.ngo.vn · Created: 2026-11-05

<!-- Roadmap story E1.7, the last of wave 1; ADR-0003 decision 2 lists four rules (push on red, source edit without approval, tick without evidence, reviewer able to write). Specs 004 to 008 each mutation-checked their own code once, by hand, and the result sits in a progress log. This makes the check a file in the repository that anyone can re-run. No product code changes. -->

## Intent

Each rule of ADR-0003 is enforced by up to three mechanisms (the gate command, the Claude Code hook, the rendered role), and each was tested where it was built. Nothing states, in one place, that every rule has an end-to-end test that fails when its mechanism is removed, and nothing re-runs the mutation check after the next refactor. This adds one test file that drives each rule through the real entry points, a check that the ADR table and the tests cannot drift apart, and a script that removes each mechanism in a temporary copy of the kit and requires the file to fail. The seam is `tests/` only.

## Acceptance

- [ ] `tests/test_never.py` holds one test class per rule of the ADR table, each driving the real entry point on a fixture project (the hook through `sdlc hook <name>` with the host's JSON on standard input, the gate through `sdlc gate`, the role through `sdlc install`): a push on red is refused, a push on green is allowed; a source edit while the active spec is unapproved or changed after approval is refused, and allowed once approved; a tick without a progress-log line with a real commit is reported (`Stop` warns, never blocks), and a tick with one is not; every role marked read-only renders without any write, edit or execute tool for Claude and for Copilot
- [ ] A registry test reads the rules from the table in `docs/adr/0003-enforcement-model.md` and fails when a rule has no test class, or a test class names no rule in the table (adding a rule to the ADR without a test, or the reverse, fails the suite)
- [ ] `tests/mutate_never.py` copies the kit to a temporary folder, applies each listed mutation (one per mechanism, at least the ones the T010 lists of specs 005 and 006 name: the push check, the approval digest comparison, the evidence check, the `Stop` warning, the role's `access` mapping, `enforce` read at run time), runs `tests.test_never` in the copy, and exits 1 if any mutation leaves the file green; it never touches the real kit
- [ ] Negative case, by test: the script reports a survivor and exits 1 when given a mutation that changes nothing (a no-op replacement)
- [ ] No product code or docs of the commands change; README names the script in its develop section; `sdlc lint` still passes

Verify: `python3 -B -m unittest tests.test_never -v`, `python3 -B tests/mutate_never.py` and `python3 bin/sdlc lint`

## Open questions (they decide the shape)

1. **Is the mutation script part of the unit suite?** Recommended no: each mutation re-runs a test file, so the script takes about a minute and a half and would double the suite; it is run by hand before a release and its result is quoted in the PR. A small unit test covers only its no-op survivor case on a trivial fixture.
2. **How do mutations apply to a copy?** Recommended: a table of (file, exact text to find, replacement) in the script; a text that is not found exactly once is a script error (exit 2), so a refactor that moves the code fails loudly instead of silently skipping a mutation.
3. **Scope of the rules.** Recommended: the four rules in the ADR's v1 table only; the "out of v1" list (weakened tests, secrets, untrusted ticket text, merges) stays out. The registry test is what makes a fifth rule impossible to add without a test.
4. **Existing tests.** Recommended: keep them. The new file is end-to-end and shorter; the unit tests in `test_hooks.py`, `test_gate.py` and `test_verify.py` stay because they pin the detail that the end-to-end test does not.
