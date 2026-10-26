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
6. A value matches a secret pattern: credentials in URLs, private-key blocks, or common token prefixes.

A warning, not an error: the index is larger than 5% of the combined size of its sources (NFR-002).

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
