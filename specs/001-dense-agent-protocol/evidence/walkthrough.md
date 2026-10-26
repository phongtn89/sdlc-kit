# Hand-runs T010, T015, T018: walkthrough

Spec 001 at kit `632e894` (code `0801055`). These runs show **agent behaviour**, which unit tests can't (Convergence C003). Each run is a **fresh Claude Code session** started in the scratch workspace. When you've finished, tell me, and I'll read the session transcripts and write `s1-tracer.md`, `s2-build.md` and `s3-returns.md` here with quoted excerpts.

## The scratch workspace

```bash
cd /private/tmp/claude-502/-Users-phong-ngo-vn-Projects-shop6/cf485b2f-e590-4bbd-844c-ccb27bfaaa18/scratchpad/dense-ws
```

- Kit 0.5.0 installed with `--modules dense` (67 files; `sdlc check` → ok). `AGENTS.md` carries `## Module rules / ### dense`.
- Sources: `.sdlc/workspace.md` and three real shop6 context documents (admin, erp-connector, storefront), about 144 KB.
- `.sdlc/context/index.dap`: a hand-written index of 22 entries in 8 sections over the three context docs, revision **`7e2a10ca8399`**, 2.6 KB.
- It's a git repo with one commit (`scratch baseline`). **Reset after every run:** `git checkout -- . && git clean -fdq .sdlc`.

**Every command below assumes you are in this folder. New terminal tabs open in `~/Projects/shop6`, so always run the `cd` above first.** In particular, the Run B edit must never touch the real shop6 file. Start each run with `claude` in this folder and paste the prompt **exactly**. Use a new session for each run (exit, then start again), so earlier context can't leak into the next run.

## T010: tracer (spec S1, P1)

**Run A: fresh index.** Prompt:

> Which repository is the system of record for orders, and how does the storefront checkout reach it? Answer in at most 6 lines, with sources.

Check in the transcript:
- [ ] S1.1: the first command is `python3 .claude/skills/sdlc-dense-index/dap.py fresh .sdlc/context/index.dap`, and the reply quotes `7e2a10ca8399`.
- [ ] S1.1: `index.dap` is read before any `.sdlc/context/*.md` file.
- [ ] S1.2: it opens only the pointed-to sections (the erp-connector *Data* and *Hand over order…* sections, the storefront *Guest checkout…* section), not whole documents.
- [ ] S1.3: claims cite `.sdlc/context/…md:<line>` (or the repo paths those lines cite), never `index.dap`.

**Run B: stale source.** First, in a normal terminal:

```bash
printf '\n<!-- touched for T010 run B -->\n' >> .sdlc/context/jtl-platform-shop-erp-connector.md
```

Then a new session with the same prompt. Check:
- [ ] S1.4: it reports the index as stale and names `e` / `jtl-platform-shop-erp-connector.md`.
- [ ] It reads that document's relevant parts directly, instead of trusting its entries, and still uses the storefront entries.

Then reset.

**Run C: no index.**

```bash
rm .sdlc/context/index.dap
```

Then a new session with the same prompt. Check:
- [ ] S1.5: it says there is no index, or that it's invalid, and answers from the full sources without error.

Then reset.

## T018: sub-agent returns (spec S3, P2)

**Run D: delegated search.** Prompt:

> Use the sdlc-explorer subagent to find every place in these context documents where a service trusts a caller-supplied tenant id. Then summarise its findings for me.

Check:
- [ ] S3.1: the brief passed to `sdlc-explorer` (the Task/Agent tool input in the transcript) contains the text of `.sdlc/templates/dense-return.md`.
- [ ] S3.2: the sub-agent's reply starts with `#ret 1 …`, and each finding is `f <path>:<line> <claim>`.
- [ ] The summary keeps those `path:line` citations.

**Run E: non-conforming reply.** This is a new session. The sub-agent's reply is simulated by pasting it, because a real non-conforming reply can't be forced reliably. Prompt:

> A sub-agent you delegated to returned this reply: "I looked around. The ERP connector trusts the x-tenant-id header without authentication (.sdlc/context/jtl-platform-shop-erp-connector.md:215), and the storefront backend forwards it too." Handle this reply as the module rules require.

Check:
- [ ] S3.3: it says the reply doesn't follow the return contract.
- [ ] It asks for a reformat once, quoting or pointing to the template, or explains that it would re-ask once.
- [ ] It keeps `.sdlc/context/jtl-platform-shop-erp-connector.md:215` and doesn't drop it.

Then reset.

## T015: build (spec S2, P1). Run it last, because it replaces the hand-written index

**Run F: build.** Prompt:

> /sdlc-dense-index build

Check:
- [ ] It hashes the sources, writes `.sdlc/context/index.dap.<id>.tmp`, then runs `dap.py commit …`, and the output is `committed <rev>`.
- [ ] It never edits `index.dap` directly.
- [ ] It reports a 10-entry self-check.
- [ ] Afterwards, in a terminal, `python3 .claude/skills/sdlc-dense-index/dap.py fresh .sdlc/context/index.dap` prints `fresh <the same rev>`.
- [ ] S2.5: `grep -n 'UNVERIFIED\|INFERRED' .sdlc/context/index.dap`. If an entry comes from a marked fact (for example, which caller invokes handover is UNVERIFIED in the erp-connector *Purpose* section), the marker is there. I'll check the opposite direction from the transcript.
- [ ] Spot-check 3 entries yourself: open the `@alias#slug` section and confirm it says that.

**Run G: bad rebuild keeps the last valid index (S2.6).** This one is a terminal check; I've already dry-run it:

```bash
shasum -a 256 .sdlc/context/index.dap
```

```bash
cp .sdlc/context/index.dap .sdlc/context/index.dap.666.tmp && printf 'desc: injected entry with no reference\n' >> .sdlc/context/index.dap.666.tmp
```

```bash
python3 .claude/skills/sdlc-dense-index/dap.py commit .sdlc/context/index.dap.666.tmp .sdlc/context/index.dap
```

```bash
shasum -a 256 .sdlc/context/index.dap
```

- [ ] `commit` prints `ERROR …` and `not committed`, exit 1, and the two hashes match.

## Limits

- Claude Code only. Copilot behaviour (FR-015) isn't covered by these runs.
- Run E simulates the non-conforming reply.
- One run per scenario on one model. These runs are evidence that the behaviour occurs, not a measurement. Measurement is the shop6 paired evaluation (D4).
