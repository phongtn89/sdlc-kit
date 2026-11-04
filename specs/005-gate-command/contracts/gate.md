# Contract: `sdlc gate`

Spec 005 (FR-001–FR-014, NFR-001–NFR-003). Builds on spec 004 (`contracts/record.md`). Decision: ADR-0003.

## Call

```text
python3 <kit_path>/bin/sdlc gate <name> <dir> [--spec <NNN|folder>] [--repo <name>] [--by <name>]
```

`<name>`: `approved`, `approve`, `green-at-head`, `evidence-for-ticks`. `<dir>`: the project root. `--spec` is required for `approved`, `approve` and `evidence-for-ticks` and is exit 2 for `green-at-head`: three digits, matched against exactly one `<spec_dir>/<NNN>-*` folder, or a relative folder path (a trailing `/` is stripped) that, after `safe_path`, lies inside `<spec_dir>` and holds `spec.md` (an absolute path or one outside `<spec_dir>` is exit 2). `--repo`: workspace mode: the base folder is `repos.<name>.path` (checked with `safe_path`), `<spec_dir>` is `repos.<name>.spec_dir` if present, else the top-level `spec_dir`, else `specs`, each of them a string (anything else is exit 2; trailing and leading `/` are stripped as `spec_dirs` does, and an empty string falls back to `specs`), and the evidence record is the repo's own (`<base>/.sdlc/evidence/verify.json`). Without `--repo` the base is `<dir>`. `--by` only for `approve`; giving it to another gate is exit 2.

## Exit codes and output

| Code | Meaning |
|---|---|
| 0 | the gate passed (`approve`: the approval was recorded) |
| 1 | the gate failed, or a git question failed or timed out |
| 2 | unknown gate, bad or ambiguous `--spec`, unknown `--repo`, missing `--by` or an invalid one, a missing, unreadable or malformed document, a refused `approve`, a failed write |

One line per problem, then a last line, exactly `gate <name>: PASS` or `gate <name>: FAIL (<n> problems)` (always the plural word, also for 1). Two exceptions: a successful `approve` (below), and exit 2, which prints one `sdlc: error: ...` line and no gate line. For `approve`: `gate approve: PASS (approved by <name> on <date>, digest sha256:<first 12 hex>...)`. Exit-2 messages are returned as lines (`sdlc: error: ...`) and printed on standard output, like `verify`. All lines are printed with replacement for characters the standard output can't encode, and `approve` prints only after its write has succeeded, so an encoding problem can't follow a completed write. An unknown gate name is exit 2 from `cmd_gate` (not from the argument parser). `cmd_gate` also turns `OSError`, `UnicodeDecodeError` and `ValueError` into exit 2.

## The approval digest

Four parts, each with its own SHA-256 `h(...)` (lower-case hex of the UTF-8 bytes): `spec` = normalised `spec.md`; `plan` = normalised `plan.md`; `tasks` = normalised `tasks.md`; `contracts` = for every file `contracts/*.md` and `data-model.md` that exists, sorted by file name (byte order), the text `"== <name> ==\n"` plus the file's text with line endings normalised (step 1 only), concatenated; with none of those files present the part is the hash of the empty text. Combined digest = SHA-256 of `"spec.md:" + h(spec) + "\nplan.md:" + h(plan) + "\ntasks.md:" + h(tasks) + "\ncontracts:" + h(contracts) + "\n"`.

Normalised text for the three documents, applied in this order, with `re.M`:

1. read as UTF-8 (strict; a document over 2 MiB, not a regular file, or not valid UTF-8 is exit 2); `\r\n` and `\r` become `\n`;
2. **`tasks.md` only:** cut everything from the first line that is exactly `## Progress log` (trailing spaces ignored) to the end. In `spec.md` and `plan.md` that heading is ordinary text;
3. **`spec.md` only:** in the first line that matches `^Status:` and in the first that matches `^Approved:`, both only if they occur before the first line starting `## `, remove the status word (`^Status:[ \t]*\S+` becomes `Status:`) and, on the Approved line, everything except its trailing `<!-- ... -->` comment (the line becomes `Approved:` plus that comment). Any other text on those lines, including a comment, stays covered;
4. **`plan.md` and `tasks.md` only:** in the first line that starts with `Spec:` (plan) or `Inputs:` (tasks), replace the first `· Status: \S+` with `· Status:` (only the status word; text after it up to the next `·` stays covered);
5. **`tasks.md` only:** replace `^([ \t]*[-*] )\[[xX]\]` with `\1[ ]`, so a checked box in a bullet list reads as unchecked (numbered lists and table cells are not normalised).

Nothing else is normalised. **Any other change to any of the four parts changes the digest and needs a re-approval**: a requirement, a plan paragraph, a contract, a task description (including updating a task line while implementing), the `Verify` block, the `Branch:` field, even trailing blanks or a changed final newline. Ticking a bullet box, adding progress-log lines and setting the spec's status do not. The remedy for a failed `approved` after an intended edit is to ask the human and run `approve` again (`sdlc-implement` says so). Baseline test counts go in the progress log, not the `Verify` block. A `## Convergence` section and its tasks go **after** the progress log, as `sdlc-converge` already does, and an agent appending to the end of the file lands in that section, so the evidence line for a convergence task must be written inside the log (above the section); text after the log is not covered, a stated limit.

## The `Approved` line

```text
Status: approved <!-- … -->
Approved: <name>, <YYYY-MM-DD>, digest sha256:<64 hex> (spec <12 hex>, plan <12 hex>, tasks <12 hex>, contracts <12 hex>) <!-- … -->
```

The 64 hex are the combined digest; the four 12-hex groups are the first 12 characters of each part's hash, so a mismatch can name the parts that changed. Parsed with `^Approved: (?P<by>[^,\n]+), (?P<date>\d{4}-\d{2}-\d{2}), digest sha256:(?P<hex>[0-9a-f]{64}) \(spec (?P<s>[0-9a-f]{12}), plan (?P<p>[0-9a-f]{12}), tasks (?P<t>[0-9a-f]{12}), contracts (?P<c>[0-9a-f]{12})\)(?:\s*<!--.*-->)?\s*$`. Anything else (the free-text lines of specs 002–004, the empty template line) is "no digest". Both `approve` and `approved` use the **first** `Status:` and the first `Approved:` line before the first line starting `## `; a body line that merely looks like one is ignored. The status word is the first token after `Status:` on that line (`^Status:[ \t]*(\S+)`; `Status:draft` is accepted; an empty `Status:` has no word and is refused; `approve` replaces only that first token and keeps the rest of the line, including a comment that contains the words draft or approved). A spec with no `Status:` line fails `approved` as `status is missing, not approved` (exit 1) and is refused by `approve` (exit 2).

`approve --by <name>`: `<name>`, after stripping blanks, non-empty, at most 80 characters, with no `,`, no character of Unicode category Cc, Cf, Zl or Zp (control, format such as zero-width, line and paragraph separators) and no whitespace other than a plain space, no `<!--` or `-->`, and unchanged by `str.strip()`. `spec.md` must have exactly one `Status:` and one `Approved:` line before its first `## ` heading, else exit 2. It rewrites the status word to `approved` (keeping any trailing comment) and the whole `Approved:` line to the format above (keeping a trailing `<!-- … -->` comment if the old line had one), today's UTC date; every other byte of `spec.md` is kept (the file is read and written as bytes: CRLF, a missing final newline and its mode, which is copied to the temporary file, are all preserved). The write is atomic (temporary file beside it, then rename; a symlinked spec is refused). Allowed only for status `draft` or `approved`, with `plan.md` and `tasks.md` present. The digest is computed over the files as they are **after** the status rewrite, which normalisation makes irrelevant.

## `approved`

Checks in order, one problem line per failure, stopping at the first failing step among 1–3 and listing every mismatch in step 4:

1. status word is `approved` or `implemented`, else `status is <word>, not approved`;
2. the `Approved` line parses (a name, a date, a digest), else `no approval digest on the Approved line`;
3. `plan.md` and `tasks.md` exist and are readable, else exit 2 (reached only when steps 1 and 2 pass, so a draft spec without a plan is exit 1 from step 1);
4. each part's 12-hex prefix is compared with the recorded one: `<spec|plan|tasks|contracts> changed since approval` for each that differs; then, if none differs but the combined digest does (a hand-edited line), `approval digest does not match the documents`.

## `green-at-head`

Steps, each a fail with its own reason, in this order (git calls: `rev-parse HEAD` then `status`, made with `sdlc_verify.git_run`, which returns `(status, stdout)` with status `ok`, `fail`, `timeout` or `nogit`; `git_call` stays as a thin wrapper so spec 004's callers are unchanged; 2 calls):

1. the record `<base>/.sdlc/evidence/verify.json`: not a regular file or over 1 MiB, too deeply nested or not JSON → `unreadable record`; missing → `no record` (the record is not a "document": these are exit 1, not 2);
2. `git` not found → `git not found`; `rev-parse HEAD` fails or empty → `HEAD unresolved (no repository or no commit)`; a call that timed out → `git timed out`;
3. `sdlc_verify.green_reason(record, head)` (which never raises and returns `record shape or version wrong` for a record whose `version`, `revision`, `dirty` or `commands` has the wrong type, `dirty` included) returns the first reason (or None when green): `record shape or version wrong`, `record has no revision`, `record is for another revision`, `record was dirty`, `no commands in the record`, `a command did not pass`; `green_at_head(record, head)` in spec 004 becomes `green_reason(...) is None`, so there is one definition;
4. `status --porcelain --untracked-files=normal -- . ':(exclude).sdlc/evidence'`: a failed or timed-out call → `git status failed`; a non-empty output → `tree changed since the record`.

## `evidence-for-ticks`

In `tasks.md` every line that starts (after blanks) with `- [x]`, `- [X]`, `* [x]` or `* [X]` is a tick; it must continue with an id `[A-Z]+\d+[a-z]?` (so `T006b` is an id, and a range applies to plain numeric ids only) followed by a non-word character, else it is reported as `line <n>: checked box without an id`. The log is the `## Progress log` section (to the next `## ` heading or the end); a file with no such heading has no evidence. A log line is **evidence for** an id when it contains (a) the id as a whole token (not preceded or followed by `[0-9A-Za-z_]`, so `T001` is not found in `T0011` or `T001_x`, but is found in `T001-review` and beside backticks), or an id range with the same prefix `P` and `n ≤ id ≤ m`: `P<n>–P<m>` (the prefix repeated; a hyphen or an en or em dash; blanks around the dash allowed) or the bare `P<n>–<m>` (no blanks, both numbers of the same digit width). `T001 – 57` and `T001-3` are not ranges, so a result such as "57 tests pass" can't give evidence to other tasks, and (b) a **hash token**: a maximal run of `[0-9a-f]` of length 7 to 40 not adjacent to `[0-9A-Za-z]` (a backtick or `+` beside it is fine), that git resolves to a commit. All hash tokens of all log lines (at most 2,000 distinct; more is the failure `too many revisions to check`) go to **one** `git cat-file --batch-check` call, one input line `<token>^{commit}` each; output lines map to inputs by position and only `<oid> commit <size>` counts, so `missing`, `ambiguous` and any other type mean "not a commit". With no tick or no hash token there is no git call (a non-git folder passes when it has no ticks). A failed or timed-out call is exit 1 `git failed`. When some token is missing, one more call `git rev-parse --is-shallow-repository` is made and, if it prints `true`, each problem line ends `(shallow repository: history may be missing)`. Reachability from `HEAD` is not required and a hash in an unrelated branch counts (the gate checks that a commit exists, not that the evidence is true). A tick without evidence is one line: `T012: no progress-log line with this task and an existing commit`. A tasks file with no ticks passes. The kit's gate needs the cited commits in the local object database, so a CI checkout must fetch enough history (E1.5 notes it).

The 2,000-token cap counts distinct tokens including any UUID-like groups that usage marks put in the log; exceeding it is a failure, not a pass.

## Writes and isolation

Only `approve` writes, and only `spec.md`. No gate runs any command from config, tasks or the record. Git runs as in spec 004 (`--no-optional-locks -c core.fsmonitor=false`). A failed or timed-out git call is exit 1 with the reason.
