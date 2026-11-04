# Contract: `sdlc gate`

Spec 005 (FR-001–FR-014, NFR-001–NFR-003). Builds on spec 004 (`contracts/record.md`). Decision: ADR-0003.

## Call

```text
python3 <kit_path>/bin/sdlc gate <name> <dir> [--spec <NNN|folder>] [--repo <name>] [--by <name>]
```

`<name>`: `approved`, `approve`, `green-at-head`, `evidence-for-ticks`. `<dir>`: the project root. `--spec` is required for all but `green-at-head`: three digits, matched against exactly one `<spec_dir>/<NNN>-*` folder, or a folder path under the project root (checked with `safe_path`) that holds `spec.md`. `--repo`: workspace mode, as for `verify` (the repo's path, its `spec_dir`, its own evidence record). `--by` only for `approve`; giving it to another gate is exit 2.

## Exit codes and output

| Code | Meaning |
|---|---|
| 0 | the gate passed (`approve`: the approval was recorded) |
| 1 | the gate failed, or a git question failed or timed out |
| 2 | unknown gate, bad or ambiguous `--spec`, unknown `--repo`, missing `--by` or an invalid one, a missing, unreadable or malformed document, a refused `approve`, a failed write |

One line per problem, then a last line, exactly `gate <name>: PASS` or `gate <name>: FAIL (<n> problems)`. For `approve`: `gate approve: PASS (approved by <name> on <date>, digest sha256:<first 12 hex>…)`. Exit-2 messages are returned as lines (`sdlc: error: …`) and printed on standard output, like `verify`.

## The approval digest

Per file `F` in `spec.md`, `plan.md`, `tasks.md`: `h(F)` = SHA-256 (lower-case hex) of the UTF-8 bytes of the normalised text of `F`. Combined digest = SHA-256 of `"spec.md:" + h(spec) + "\nplan.md:" + h(plan) + "\ntasks.md:" + h(tasks) + "\n"`.

Normalised text, applied in this order:

1. read as UTF-8; `\r\n` and `\r` become `\n`;
2. cut everything from the first line that is exactly `## Progress log` (trailing spaces ignored) to the end;
3. delete every line matching `^Status:.*$` and `^Approved:.*$` (the spec's header lines);
4. replace the regular expression `· Status: [^·\n]*` with `· Status:` (the inline field of the `Inputs` line in plan and tasks);
5. replace `^(\s*[-*] )\[[xX]\]` (multiline) with `\1[ ]` so a checked box reads as unchecked.

Nothing else is normalised: any other change to a requirement, plan paragraph or task description changes the digest.

## The `Approved` line

```text
Status: approved <!-- … -->
Approved: <name>, <YYYY-MM-DD>, digest sha256:<64 hex> (spec <12 hex>, plan <12 hex>, tasks <12 hex>) <!-- … -->
```

The 64 hex are the combined digest; the three 12-hex groups are the first 12 characters of each `h(F)`, so a mismatch can name the files that changed. Parsed with `^Approved: (?P<by>[^,\n]+), (?P<date>\d{4}-\d{2}-\d{2}), digest sha256:(?P<hex>[0-9a-f]{64}) \(spec (?P<s>[0-9a-f]{12}), plan (?P<p>[0-9a-f]{12}), tasks (?P<t>[0-9a-f]{12})\)(?:\s*<!--.*-->)?\s*$`. Anything else (the free-text lines of specs 002–004, the empty template line) is "no digest". The status word is the first token after `Status:` (`^Status:\s*(\S+)`).

`approve --by <name>`: `<name>` non-empty, at most 80 characters, none of `,`, a newline, `<!--`. It rewrites the status word to `approved` (keeping any trailing comment) and the whole `Approved:` line to the format above (keeping a trailing `<!-- … -->` comment if the old line had one), today's UTC date; every other byte of `spec.md` is kept, line endings included. The write is atomic (temporary file beside it, then rename; the file's mode is kept; a symlinked spec is refused). Allowed only for status `draft` or `approved`, with `plan.md` and `tasks.md` present. The digest is computed over the files as they are **after** the status rewrite, which normalisation makes irrelevant.

## `approved`

Checks in order, one problem line per failure, stopping at the first failing step among 1–3 and listing every mismatch in step 4:

1. status word is `approved` or `implemented`, else `status is <word>, not approved`;
2. the `Approved` line parses (a name, a date, a digest), else `no approval digest on the Approved line`;
3. `plan.md` and `tasks.md` exist and are readable, else exit 2;
4. each file's 12-hex prefix is compared with the recorded one: `<file> changed since approval` for each that differs; then, if none differs but the combined digest does (a hand-edited line), `approval digest does not match the documents`.

## `green-at-head`

Reads `<root>/.sdlc/evidence/verify.json` (or the repo's), then: record missing → fail `no record`; unreadable or not JSON → fail `unreadable record`; `sdlc_verify.green_at_head(record, head)` false → fail with the first true reason in the order: version or shape wrong, `revision` is null (`no revision`), revision differs from `HEAD` (`other revision`), record `dirty`, a command not `pass`, no commands; then the tree is read again (`git status --porcelain --untracked-files=normal -- . ':(exclude).sdlc/evidence'`) and a non-empty or failed status is `tree changed since the record`. Git calls: `rev-parse HEAD`, `status`.

## `evidence-for-ticks`

In `tasks.md`, every line matching `^\s*[-*] \[[xX]\] (?P<id>[A-Z]+\d+)\b` is a tick. The log is the `## Progress log` section (to the next `## ` heading or the end). A log line is **evidence for** an id when it contains (a) the id as a whole token, or an id range `P<n>–P<m>` (also `-`, and `P<n>–<m>`) with the same prefix `P` and `n ≤ id ≤ m`, and (b) a 7–40 character lower-case hex token that git resolves to a commit. All hex tokens of all log lines are checked with **one** `git cat-file --batch-check` call (`<token>^{commit}`); `missing` lines are not commits. A tick without evidence is one problem line: `T012: no progress-log line with this task and an existing commit`. A tasks file with no ticks passes.

## Writes and isolation

Only `approve` writes, and only `spec.md`. No gate runs any command from config, tasks or the record. Git runs as in spec 004 (`--no-optional-locks -c core.fsmonitor=false`). A failed or timed-out git call is exit 1 with the reason.
