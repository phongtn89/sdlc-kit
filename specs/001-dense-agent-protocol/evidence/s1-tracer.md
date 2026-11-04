# T010 evidence: tracer (spec S1)

Workspace: scratch `dense-ws` (kit 0.5.0, `--modules dense`), index `7e2a10ca8399` (hand-written, 22 entries). Claude Code v2.1.310, model `claude-sonnet-5-5`, one fresh session per run. Transcripts: `<scratch>/dense-ws/`.

An earlier session in this workspace (`3e0bdfd6…`) only ran `/model` and talked about an update. It isn't a run, and it's excluded.

## Run A: fresh index (`72a645af-0e69-40cb-bd3a-c4b5c24a6605.jsonl`)

Prompt (first message, verbatim): "Which repository is the system of record for orders, and how does the storefront checkout reach it? Answer in at most 6 lines, with sources."

Tool calls, in order:

1. `Bash` `python3 .claude/skills/sdlc-dense-index/dap.py fresh .sdlc/context/index.dap; echo "exit $?"` → `fresh 7e2a10ca8399 | exit 0`
2. `Read` `.sdlc/context/index.dap` (2,714 chars)
3. `Bash` `cd .sdlc/context && grep -n -i -E "orders|system of record|…" context/…` → wrong relative path, "No such file or directory"
4. `Bash` `grep -n -i -E "orders|system of record|hand.?over|checkout/orders|x-hostname|x-tenant-id" .sdlc/context/erp-connector.md .sdlc/context/storefront.md | head -40` → 13,364 chars

Answer excerpts: "(index `7e2a10ca8399`, fresh)"; "Sources: `erp-connector.md:12,57-59`, …"; "Which caller invokes it is unverified (`erp-connector.md:19`)".

| Check | Result | Note |
|---|---|---|
| S1.1: freshness check first; revision quoted | **pass** | Call 1; the answer quotes `7e2a10ca8399` |
| S1.1: index read before any context source | **pass** | Call 2 before calls 3–4 |
| S1.2: only the pointed-to sections opened | **fail** | It didn't follow any `@alias#slug`. It used a keyword `grep` over two whole documents (call 4) and never opened the pointed sections (erp *Data*, *Hand over order…*; storefront *Guest checkout…*) |
| S1.3: claims cite sources, never the index | **pass** | Cites `.md:line` and the code paths behind them. Lines 12 and 57–59 checked: they support the claims. The UNVERIFIED marker was carried over |

Context loaded before answering: about 16.3K chars of tool output, against about 70K for the two documents in full. This is a single run, not a measurement.

**Finding F-S1.2:** the rule "open only the source sections its entries point to" didn't translate into action: the agent searched by keyword instead. Candidate fix, for the owner to decide: a concrete command such as `dap.py show <alias#slug>` that prints exactly one section, with the rule pointing to it.

## Run B: stale source (`b2f6fc60-8205-46d2-b71c-e33f90fbc1a0.jsonl`)

Setup (done by the main session): appended `<!-- touched for T010 run B -->` to the scratch `erp-connector.md`. Before the run, `dap.py fresh` printed `stale 7e2a10ca8399 / STALE e …`, exit 1. Same prompt as Run A. It was pasted twice in the session; the first answer is scored, and the second (no tool calls) agrees with it.

Tool calls, in order:

1. `Bash` `dap.py fresh …` → `stale 7e2a10ca8399 | STALE e context/erp-connector.md | exit 1`. Then it said: "Stale on the connector context; read the index, then that source in full."
2. `Read` `.sdlc/context/index.dap`
3. `Read` `.sdlc/context/erp-connector.md` (whole file, 34,857 chars)
4. `Bash` `grep -n -i -A14 "guest checkout" storefront.md` (3,150 chars), the section the storefront checkout entries point to

Answer excerpts: "The index was stale for that file, so I read it in full."; citations `erp-connector.md:10-12,92`, `:57-59,133-140`, `storefront.md:133-137`.

| Check | Result | Note |
|---|---|---|
| S1.4: says the index is stale and names the changed source | **pass** | After call 1, and again in the answer |
| S1.4: reads the stale source itself, not its entries | **pass** | Call 3 |
| Uses the index for the non-stale rest | **pass** | Call 4 targets the pointed *Guest checkout* section of the storefront source, not the whole document |
| S1.3: cites sources, never the index | **pass** | All citations are `.md:line` |

The workspace was reset afterwards (`git checkout -- .`).

## Run C: no index (`0bb2fed4-9aa1-4a86-89f8-15287a1e5065.jsonl`)

Setup (main session): `rm .sdlc/context/index.dap`. Before the run, `dap.py fresh` printed `INVALID / ERROR 0: index not found`, exit 2. Same prompt, sent once.

Tool calls, in order:

1. `Bash` `dap.py fresh …; cat .sdlc/config.json | head -50; ls` → `INVALID | ERROR 0: index not found: .sdlc/context/index.dap | exit 2`. Then it said: "The index is missing (exit 2), so I'm working from the full sources."
2. `Bash` `ls -la …; grep -rIil "order" …`
3. `Bash` `grep -n -i -E "system of record|source of truth|checkout|order" workspace.md`
4. `Bash` `sed -n 36,44p workspace.md; grep … erp-connector.md`

Answer excerpt: "**Caveat:** the dense index is missing (`dap.py fresh` exited 2), so I read the context docs directly." Citations: `.sdlc/workspace.md:41-42,220`.

| Check | Result | Note |
|---|---|---|
| S1.5: says there is no index or that it's invalid | **pass** | After call 1, and as the answer's first line |
| S1.5: answers from the full sources without error | **pass** | No errors; context sources only |

Observation, not scored: without the index, the answer named JTL-WaWi (through the connector) as the system of record, while runs A and B named the erp-connector. One run can't attribute that to the index; the paired evaluation (D4) measures answer quality.

The index was restored afterwards (`git checkout -- .`).

## Run A2: re-run after `dap.py show` (`2eed25ee-81a1-4e22-bff5-343e2078ee69.jsonl`)

Kit `d88cbd9` installed into the scratch workspace (`sdlc update`: 4 files; `check` ok; scratch baseline 2). Same hand-written index `7e2a10ca8399`, same model, same prompt (sent once).

Tool calls, in order:

1. `Bash` `dap.py fresh …` → `fresh 7e2a10ca8399 | exit 0`
2. `Bash` `cat .sdlc/context/index.dap | head -80`
3. `Bash` `for a in @e#data @e#purpose-and-boundaries @s#guest-checkout-identify--delivery--draft-order-partial; do python3 .claude/skills/sdlc-dense-index/dap.py show .sdlc/context/index.dap $a | head -25; …; done` → `.sdlc/context/erp-connector.md:88-100 | 88	## Data | …`

Answer excerpts: "(`.sdlc/context/erp-connector.md:12,92`)", "(`.sdlc/context/storefront.md:135`)" … ":139", "Which caller invokes handover is unverified (`…erp-connector.md:19`)", "I read the dense index first (fresh, rev `7e2a10ca8399`) and cited the context documents it points to, not the index."

| Check | Result | Note |
|---|---|---|
| S1.1 | **pass** | Freshness first, revision quoted, index read first |
| S1.2: only pointed sections opened | **pass** | Only `dap.py show` for three pointed sections; no grep, no whole-document read |
| S1.3 | **pass** | Every citation lies inside a section `show` printed |

Context loaded: about 9.4K chars of tool output (Run A: about 16.3K).

## T010 result

| Scenario | Result |
|---|---|
| S1.1 freshness first, revision quoted, index read first | pass (Run A) |
| S1.2 only pointed sections opened | Run A **fail** (keyword grep); **pass in Run A2** after `dap.py show` (R004/R006) |
| S1.3 sources cited, never the index | pass (runs A, B, C) |
| S1.4 stale source named and read in full | pass (Run B) |
| S1.5 missing index handled | pass (Run C) |

**T010 passes** (S1.1–S1.5 all observed; S1.2 in Run A2). Finding F-S1.2 was closed by `dap.py show` (kit `d88cbd9`).
