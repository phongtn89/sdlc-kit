# Mini-spec: CI recipe for the gates (E1.5)

Track: T2 · Status: implemented · Owner: phong.ngo.vn · Created: 2026-11-05

<!-- Roadmap story E1.5 (docs/roadmap/layers-plan.md); ADR-0003 decision 4: CI is the common floor, ladder level 6, the required-check route for GitHub Copilot, which has no hook. Acts on `lint`, `check` (spec 001 era), `verify` (spec 004), `gate` (spec 005). Promote to a full spec (T3) if a question below ends in a new command, a new lock key or a rendered file. -->

## Intent

A team that uses Copilot (no hooks) or wants a second line behind the Claude Code hooks needs the kit's gates to run on every pull request and to be a required check. Today `lint`, `check`, `verify` and `gate` exist but nothing calls them from CI. This adds one template workflow and the text that explains how to use it. The seam is documentation plus one template file; no command changes.

## Acceptance

- [ ] A template workflow (GitHub Actions) in the kit runs, in order: `sdlc check`, `sdlc verify`, `sdlc gate green-at-head`, and for a branch whose name starts with `NNN-` that has a spec folder, `sdlc gate approved --spec NNN` and `sdlc gate evidence-for-ticks --spec NNN`; the job fails on any non-zero exit
- [ ] `sdlc lint` runs only in the kit's own CI (it validates the kit, not a project), and the template says so
- [ ] A negative case, shown by test: on a fixture project, a red `verify` and a spec edited after approval each make the template's steps exit non-zero (the same commands, run by hand in the test)
- [ ] README and `adapters/RENDERING.md` say how to adopt it, that it is the required-check route for Copilot (branch protection is set by the repository owner, outside the kit), and which rules it cannot see (an unapproved edit that never reaches a commit, a shell edit)
- [ ] No behaviour change outside the docs, the template and their tests: `install`, `update`, `check` and `uninstall` output is unchanged

Verify: `python3 -B -m unittest tests.test_ci -v` and `python3 bin/sdlc lint`

Red first, then green: 14 of the first 15 tests in `tests/test_ci.py` failed (2 failures, 12 errors) before `adapters/ci/sdlc-gates.yml` and the docs existed; nine mutations of the template (check never fails, the kit-path line also failing, `MODIFIED` dropped, a skip that swallows a gate failure, a skip on any exit 2, no evidence gate, verify and green-at-head replaced by `true`, the kit left in the tree check) each fail at least one test. After review pass 1 four more tests were added (19 in all), red first, and the redundant `sdlc: error` match was removed.

## Decisions (2026-11-05, phong.ngo.vn accepted all four recommendations in chat; the track stays T2)

1. **How does CI get the kit?** The lock's `kit_path` is a path on one developer's machine. The kit repo is private. Options: the workflow checks the kit out (a second `actions/checkout` with a token or deploy key, pinned to the lock's `kit_version` tag), or the project vendors the kit. Recommended: the template checks out the kit at a pinned ref and passes its path; a project with the kit elsewhere edits one line. A rendered or vendored copy would be a new contract (T3).
2. **Is the template rendered by `install`?** Recommended no: it lives in the kit (`adapters/ci/`) and the README tells you to copy it, so install output and the lock do not change (that keeps this T2). Rendering it would add a managed file and make a drift case.
3. **Which CI systems?** Recommended GitHub Actions only, as the roadmap names "a template workflow"; the same commands in the README as a shell list cover any other system.
4. **Branch to spec mapping in CI.** The hooks use the branch name prefix `NNN-` (spec 006). The template uses the same rule so the two agree; a branch with no spec folder skips the spec gates, and says so.
