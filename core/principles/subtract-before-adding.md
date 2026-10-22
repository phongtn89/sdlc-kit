# subtract-before-adding

Before adding code, types, files or dependencies, walk the ladder and stop at the first rung that works:

1. Does this need to exist at all? (YAGNI: no speculative config, wrappers, or abstractions)
2. Is it already in this codebase? Reuse/compose existing types, schemas, helpers.
3. Does the language/platform stdlib cover it?
4. Does an installed dependency solve it?
5. Can it be one clear line inline?
6. Only then write the minimum new code.

Prefer deleting dead or duplicated code you made obsolete. Clear cohesive code beats minimum line count. Canonical contracts (published schemas, SDKs) are imported, not re-declared.

**Smell:** a new `utils/` helper duplicating a library function; a local DTO copying a published contract.
