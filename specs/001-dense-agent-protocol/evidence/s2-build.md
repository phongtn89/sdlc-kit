# T015 evidence: build (spec S2)

Same workspace, model (`claude-sonnet-5-5`) and Claude Code version as `s1-tracer.md`. Starting index: the hand-written `7e2a10ca8399` (3 sources, 8 sections, 22 entries).

## Run F: `/sdlc-dense-index build` (`6b4eb394-fa23-4c74-b86a-2b87c26ea3c7.jsonl`)

The first message was the slash command with argument `build`. The skill loaded from `.claude/skills/sdlc-dense-index`.

Tool calls (8, all `Bash`), in order:

1. List the sources, run `fresh`, read `keys.json`, count lines.
2. Read the current index, and hash each source with the skill's one-liner.
3–6. Read `workspace.md`, the context headings, and the sections it meant to index.
7. Wrote `T=.sdlc/context/index.dap.$$.tmp` from a script, then `dap.py commit $T .sdlc/context/index.dap; dap.py fresh …`.
8. Re-read sections for the self-check.

There were no `Write` or `Edit` calls on `index.dap`. The only write to it was through `commit`.

Its report (excerpts): "`dap.py commit` printed `committed 4bb293220edb`, and `dap.py fresh` then exited 0 with the same revision."; "there are now 4, up from 3. I added `.sdlc/workspace.md` (alias `w`)…"; "**Self-check:** I opened the pointed sections for 10 entries and all of them were supported by their source, so I corrected nothing."; "I changed only `.sdlc/context/index.dap`. The temporary file was committed through `dap.py`."

Independent checks by the main session:

| Check | Result |
|---|---|
| `dap.py fresh` | `fresh 4bb293220edb` (exit 0), the same revision as the commit |
| `dap.py validate` | `valid` |
| `git status` | only `M .sdlc/context/index.dap`; no tmp left behind |
| Size | 5,797 bytes of 144,436 bytes of sources = **4.0%** (NFR-002 ≤ 5%) |
| Shape | **21 sections, 61 entries**. The report said "31 sections and about 85 entries", which is wrong |
| Entries vs sources (new ones checked by the main session) | The release-import risk, the Permit risk, the components pin skew, the admin → erp-connector proxy, the bus topics and blob, the repo descriptions and stacks, and the spec counts (85/55/27/45/43/0/0): all match `workspace.md` (*Repositories*, *How they fit together*, *Specs*, *Open questions*) |
| Markers (S2.5) | No `UNVERIFIED` or `INFERRED` in the index. None of the new entries comes from a marked statement, and the hand-written entries had none, so **no marker was dropped, and none was carried either**. S2.5 wasn't exercised |

| Check | Result | Note |
|---|---|---|
| S2.1: index written with the hash of every source | **pass** | 4 `src` lines; `fresh` is 0 against all four |
| S2.2: valid index; every pointer resolves | **pass** | `validate` → `valid` |
| Skill steps: tmp + commit, no direct edit, 10-entry self-check reported | **pass** | Calls 7–8; no `Write`/`Edit` |
| S2.5: markers kept | **not exercised** | No marked fact was indexed |
| Report accuracy | **issue** | Section and entry counts were misreported (31/85 vs 21/61). The skill asks for these counts in the report; the agent estimated instead of counting |

## Run G: bad rebuild keeps the last valid index (S2.6), run by the main session

```
before 4bb293220edba031
ERROR 88: key desc not allowed in a risk section
ERROR 88: entry has no @ref
not committed: .sdlc/context/index.dap unchanged
exit 1
after  4bb293220edba031
UNCHANGED
fresh 4bb293220edb
```

| Check | Result |
|---|---|
| S2.6: an invalid rebuild doesn't replace the last valid index | **pass** |

## Run H: marker check after `dap.py show` and counts (`120845de-32c0-4772-b2ed-0512a6e5882c.jsonl`)

Kit `d88cbd9` (scratch baseline 2), starting from the hand-written index `7e2a10ca8399`. Setup (main session): added a **synthetic** fixture `.sdlc/context/payments.md` with two marked facts. One is in *Purpose and boundaries* ("UNVERIFIED: no signed agreement or sandbox access exists yet"), the other in *Data* ("INFERRED from the admin connection-status design; no Terraform for it exists yet"). First message: `/sdlc-dense-index build`.

Tool calls: 7 `Bash`. Calls 1–4 read the sources and hash them; call 5 wrote `index.dap.1.tmp` and ran `commit` → `not committed: .sdlc/context/index.dap unchanged` (one entry without a `@ref`); call 6 fixed the tmp and ran `commit` → `committed e737dd93b359 (5 sources, 16 sections, 37 entries)`, then `fresh`; call 7 ran a 10-section self-check with `dap.py show`. There were no `Write` or `Edit` calls on `index.dap`.

Report excerpts: "The index is rebuilt: `committed e737dd93b359 (5 sources, 16 sections, 37 entries)`."; "A separate payments risk entry for the unsigned JTL Pay agreement, carrying `UNVERIFIED` verbatim."; "The Key Vault secrets entry, carrying `INFERRED` verbatim."; "`show` output was cut to the first lines of each section, so for the long ones … I did not re-read every line."

Independent checks by the main session:

| Check | Result |
|---|---|
| `fresh` / `validate` | `fresh e737dd93b359` / `valid` |
| Counts in the file | 5 `src`, 16 sections, 37 entries: exactly as reported |
| Marked facts in the index | `secrets: Azure Key Vault, one secret per shop for JTL Pay credentials; INFERRED from the admin connection-status design, no Terraform for it exists yet @p#data` and `what: the first PSP adapter is JTL Pay; UNVERIFIED: no signed agreement or sandbox access exists yet @p#purpose-and-boundaries` |

| Check | Result | Note |
|---|---|---|
| S2.5: markers kept | **pass** | Both markers carried verbatim, pointing at the sections that hold them |
| Counts quoted from `commit` | **pass** | Matches the file exactly (Run F's estimate was wrong) |
| S2.6 in a real build | **pass** | The first commit was refused, the old index stayed, and the fix was committed afterwards |
| tmp + commit only; self-check with `show` | **pass** | Calls 5–7 |

Advisory: the tmp was named `index.dap.1.tmp` rather than a per-run id. That's harmless for one build; concurrent builds would share the name.

## T015 result

The T015 acceptance holds: the build wrote a valid index whose hashes match its sources, and an injected bad entry failed `commit` and left the old index in place.

**Update:** both reasons below were closed by kit `d88cbd9` and Run H, and **T015 passes** (S2.1, S2.2, S2.5, S2.6 and the skill steps). The original reasons it was held back:

- S2.5 (markers kept), which T015 names explicitly, wasn't exercised.
- The report-accuracy issue is new.

Options for the owner:

1. A short **Run H**: add one source with a clearly marked fact (UNVERIFIED) to the workspace and build again, then check the entry keeps the marker.
2. Accept S2.5 as covered by the skill rule plus review, and tick T015 with this limit noted.

For the counts, a candidate fix is to have `dap.py commit` print the section and entry counts, so the report can quote them rather than estimate.
