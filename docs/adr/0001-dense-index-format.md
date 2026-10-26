# ADR 0001: Dense index uses a sectioned line format, not YAML or JSON

- **Status**: Accepted (phong.ngo.vn, 2026-10-26)
- **Date**: 2026-10-26
- **Spec**: [specs/001-dense-agent-protocol](../../specs/001-dense-agent-protocol/spec.md)

## Context

The dense index is read by agents, so size matters (headroom), and checked by a validator, so it must parse deterministically. The kit needs only Python 3.9+ and no network (`README.md:19`), so there is no third-party parser. Measured on the shop6 prototype (`.sdlc/manifest.yaml`, 2026-10-26):

| Format | Bytes | Notes |
|---|---|---|
| YAML (prototype) | 7,503 | Needs PyYAML. Flow style broke parsing twice while it was written; `2026-12-31` silently became a date object |
| Compact JSON | 7,312 | Standard-library parse, but quotes, braces and escapes everywhere; hard to read or edit as text |
| Flat dotted lines | 8,861 | Standard-library parse; +18% from repeating key prefixes on every line |

Every entry also needs a source pointer (spec FR-004), which adds the same amount in any format.

## Decision

Use a sectioned line format: a `[type id]` header line, then one `key: value @alias#slug` entry per line, with `src` lines that declare short aliases and content hashes. The grammar is in [contracts/index-format.md](../../specs/001-dense-agent-protocol/contracts/index-format.md). Values are plain text, never typed. Versioned by the `#dap 1` header.

## Consequences

- The validator is a regex parser of about 150 lines, using only the standard library, with no type conversion.
- Size is close to the YAML prototype, because section headers remove prefix repetition. Aliases keep pointers short.
- Not YAML: the hand-written `.sdlc/manifest.yaml` prototype is not a valid index. It stays as a reference fixture until the first derived index replaces it.
- A breaking grammar change needs a version bump. Agents fall back to full sources on unknown versions.

## Alternatives

- **YAML subset with its own parser**: familiar, but a correct subset parser is larger and repeats YAML's pitfalls.
- **JSON with JSON Schema**: the standard library has no schema validator, so the schema code is needed anyway, and the result is the least readable.
