# Contract: dense index format (DAP v1)

Owner: sdlc-kit `modules/dense`. Decision: [ADR 0001](../../../docs/adr/0001-dense-index-format.md). Checked by the module's validator.

## File

- Path: `.sdlc/context/index.dap` in the project (workspace or single repo). It's project-owned and not hashed, like the context documents.
- UTF-8, LF line endings, one record per line. Blank lines and lines starting with `;` (comments) are ignored.

## Grammar

```
file    = header src+ section+
header  = "#dap 1 built " DATE                     ; DATE = YYYY-MM-DD
src     = "src " ALIAS " " PATH " " SHA12          ; PATH relative to .sdlc/; SHA12 = first 12 hex of sha256(file bytes)
section = "[" TYPE " " ID "]" NL entry+            ; e.g. [repo admin], [link storefront-bff>erp-connector]
entry   = KEY ": " VALUE " @" REF                  ; REF = ALIAS "#" SLUG; the LAST " @" on the line starts REF
ALIAS   = [a-z0-9]{1,8}
TYPE    = a section type defined in the key list
KEY     = a key that the key list allows for TYPE
VALUE   = any text, including "@" (e.g. "@jtl/shop-component"); lists are ", "-separated; markers UNVERIFIED / INFERRED are kept verbatim
SLUG    = the GitHub-style slug of a heading in the aliased source
```

Example (abridged from the shop6 prototype):

```
#dap 1 built 2026-10-26
src a context/jtl-platform-shop-admin.md 3f2c9a1b7d40
src w workspace.md 9e01c2d3a4b5
[repo admin]
desc: Shop Manager SPA + control-plane API @a#purpose-and-boundaries
db: shop_admin @a#data
[risk SEC-1]
what: erp-connector trusts bare x-tenant-id, no auth @w#open-questions
sev: high @w#open-questions
```

## Validation (FR-002, FR-004, FR-007, NFR-001)

Each rule is an error, reported as `ERROR <line>: <reason>`; exit code 1 if any:

1. The header is missing or has an unknown version.
2. A `src` alias is duplicated, or its path doesn't exist under `.sdlc/`.
3. A section type is unknown, or `TYPE ID` is duplicated.
4. A key is not allowed for its section type, or is repeated in a section.
5. An entry has no `@ref`, its alias isn't declared, or its slug isn't a heading in that source.
6. A value matches a secret pattern (credentials in URLs, including an empty user part and any scheme case; private-key blocks; GitHub, AWS, Slack, `sk-…` incl. `sk-proj-`/`sk-ant-`, and `sk_`/`rk_` live/test keys) or holds an e-mail address (personal data). `user@host:path` remotes are not e-mail addresses.
7. The file has no `src` line, no section, or a section with no entry (the grammar's `src+`, `section+` and `entry+`). A build cut off mid-write therefore can't be committed.

A warning, not an error: the index is larger than 5% of the combined size of its sources (NFR-002). It applies only when those sources total at least 20 KB; below that the ratio is noise. Printed as `WARNING: index is <n>% of its sources (max 5%)` before `valid`.

## Commit (FR-018)

`commit <tmp> <dest>` accepts only `tmp` = `.sdlc/context/index.dap.<id>.tmp` and `dest` = `.sdlc/context/index.dap` under the root, with symlinks resolved; anything else is refused with exit 1 before reading. It then validates `tmp`. If it's valid, it atomically replaces `dest` (`os.replace`) and prints `committed <IDX12>`, exit 0. Otherwise it prints the `ERROR` lines and `not committed: <dest> unchanged`, exit 1, and leaves both files in place. Builders write `tmp` as `index.dap.<pid>.tmp`, so concurrent builds never share a temporary file.

## Freshness (FR-005, FR-006, FR-009, FR-011)

`fresh` is the single track-start check. It first runs every validation rule, then recomputes SHA12 for every `src`:

| Result | Output | Exit |
|---|---|---|
| Missing index, unknown version or any validation error | `INVALID` plus the `ERROR` lines | 2 |
| Valid, one or more sources changed or missing | `stale <IDX12>`, then `STALE <alias> <path>` per source | 1 |
| Valid and every source unchanged | `fresh <IDX12>` | 0 |

`IDX12` is the first 12 hex characters of the sha256 of the index file itself: the **index revision**. Agents quote it when they use the index (spec S1.1).

## Running the script

The script sits in the installed skill folder, which depends on the targets: `.claude/skills/sdlc-dense-index/dap.py` when `claude` is a target, otherwise `.github/skills/sdlc-dense-index/dap.py` (adapters `RENDERING.md`, Skills row). The module rules name both paths; agents use the one that exists.

## Sources

Default sources for a build: `.sdlc/workspace.md` (when present) and every `.sdlc/context/*.md`. Extra sources (for example a PRD or an architecture view) are passed to the build as paths under `.sdlc/`. A rebuild keeps the previous index's `src` list, minus files that no longer exist, plus any new defaults.

## Versioning

`#dap 1` is the version. A breaking grammar change bumps the version; the validator rejects versions it doesn't know, and agents then fall back to full sources (FR-011).
