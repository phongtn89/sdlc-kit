# Contract: `dap.py find`

The agent-facing lookup of the dense module v2 (spec 002, FR-010–FR-015, NFR-001, NFR-002).

**Index format:** unchanged, as in `docs/adr/0001-dense-index-format.md` and spec 001's `contracts/index-format.md`. Of that contract, only Grammar, Validation, Commit and the Freshness outputs apply to v2. Its agent-facing parts no longer apply: `fresh` as "the single track-start check", quoting the index revision, and `show` for agents (spec 002 FR-016).

**Terms used here:**
- **Index section:** a `[TYPE ID]` block of the index.
- **Source section:** the lines under one heading of a source file, which an entry's `@alias#slug` points to.

## Call

```text
dap.py find [<index>] [<term> …] [--root DIR]
```

- `<index>` and the terms are both optional to argparse (`nargs="?"` and `nargs="*"`), and the parser's own errors (a missing argument, an unknown option) exit **3**, not argparse's default 2. So exit 2 always means "index missing or invalid", never "bad call".
- **Order of checks:** usage first (an index argument present, at least one usable term), then the index. So a call with no terms and an invalid index exits 3, not 2.
- **Usable term:** at least 3 characters after trimming. Shorter terms are ignored and named on the first output line (`ignored short terms: id, a`). If no usable term remains, exit 3.

## Results

| Exit | Meaning | Output |
|---|---|---|
| 0 | 1–3 results matched | the results, as below |
| 1 | no entry matched | `no match for: <terms>` |
| 2 | index missing or invalid | `INVALID`, then at most the first 10 validation errors and `… N more; run dap.py validate <index>` |
| 3 | usage error: no index argument, no usable term, or a parser error | one line saying which, and the call form |

- **Budget, every exit:** the whole output, exits 1–3 included, stays within **2,000 characters** (FR-011), enforced by one final guard on every exit. On exit 0 the guard always keeps room for one closing cut line, so the cut marker can't be cut off.
- **No secret echo (NFR-001):** error lines never repeat an offending value. v1's messages already point to the source section instead ("value looks like a secret; point to its source section instead"); `test_invalid_index` asserts it.

## What counts as invalid, and what counts as stale

`find` reuses v1's `check(fresh_mode=True)` and keeps its split:
- **Stale, not invalid:**
  - a source whose content hash differs, or whose file no longer exists (renamed or deleted), is reported stale per source;
  - for a stale source, slugs are not checked against headings, so a heading removed from a changed source never makes the index invalid.
- **Invalid (exit 2):** every other validation rule:
  - a bad header or version;
  - a malformed `src` line, a duplicate alias, or a path outside `.sdlc/`;
  - an unknown section type or key, or a repeated key;
  - an entry without `@ref`;
  - a secret or e-mail value;
  - an unknown alias;
  - a slug that isn't a heading in an **unchanged** source.

## Results on exit 0

A **result** is one source section. Entries that point to the same source section (siblings often share a slug) form **one result**: all their entry lines, one excerpt, and one place among the 3. This way the same excerpt is never printed twice.

```text
[1] <TYPE> <ID> / <key>: <value> @alias#slug
    <TYPE> <ID> / <key>: <value> @alias#slug        (more entries for the same source section)
    .sdlc/<source>:<start>-<end>        (stale: <source> changed since the index was built)
    <n>  <heading line of the source section>
    <n>  <matching line, and one line of context either side, numbered>
    … cut: read .sdlc/<source>:<start>-<end>
```

- **Matching:** each usable term is matched case-insensitively as a substring against the entry's index section TYPE and ID, key, value and slug. An entry's score is the number of distinct terms it matches. A result's score is the best score of its entries. Ties go to more terms matched in a value, then index order. Results with score 0 are never returned.
- **Excerpt:** the source section's heading line, then every line that contains a usable term, each with one line of context either side, numbered. If no line contains a term: the heading line and the section's next **5** lines. When the excerpt is not the whole source section, it ends with the cut line.
- **Cut line:** always `… cut: read .sdlc/<source>:<start>-<end>`, one form everywhere.
- **Budget share:** each result may use at most an even share of what is left of the 2,000 characters.
- **Stale source** (content changed): the result is returned, marked stale with the source named; the excerpt comes from the current file.
- **Source renamed or deleted:** the result is returned, marked stale, and says `source not found: <source>` instead of an excerpt.
- **Heading gone** from a changed source: the result says `no heading <slug> in <source>` instead of an excerpt.
- **Redaction (NFR-001):** an excerpt line that matches the module's secret patterns or its e-mail pattern is printed as `<n>  [redacted: read the source]`.
- **Read-only (FR-015):** the lookup writes no file.
- **Speed (NFR-002):** one lookup in under 2 s for a shop6-size workspace (300 KB of sources, 300 entries).
