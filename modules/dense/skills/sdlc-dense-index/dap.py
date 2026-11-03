#!/usr/bin/env python3
"""Dense index (DAP v1) validator and freshness check. Standard library only.

  dap.py validate <index> [--root DIR]      exit 0 valid, 1 invalid
  dap.py fresh <index> [--root DIR]         exit 0 fresh, 1 stale, 2 invalid or missing
  dap.py commit <tmp> <dest> [--root DIR]   exit 0 replaced, 1 invalid (dest unchanged)
  dap.py show <index> <alias#slug> [--root DIR]   print one pointed section with line numbers;
                                           exit 0 shown, 1 unknown alias/heading, 2 invalid or missing index
  dap.py find <index> <term> [<term> ...] [--root DIR]   the agent lookup: at most 3 matching entries with an
                                           excerpt of each pointed section, in at most 2,000 characters;
                                           exit 0 results, 1 no match, 2 invalid or missing index, 3 usage

The grammar is specs/001-dense-agent-protocol/contracts/index-format.md in sdlc-kit.
"""
import argparse
import hashlib
import json
import os
import re
import sys

HEADER_RE = re.compile(r"^#dap (\S+) built (\d{4}-\d{2}-\d{2})$")
SRC_RE = re.compile(r"^src ([a-z0-9]{1,8}) (\S+) ([0-9a-f]{12})$")
SECTION_RE = re.compile(r"^\[([a-z][a-z0-9-]*) ([^\]\s][^\]]*)\]$")
ENTRY_RE = re.compile(r"^([a-z][a-z0-9_.-]*): (.*)$")
REF_RE = re.compile(r"^([a-z0-9]{1,8})#([a-z0-9_-]+)$")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
VERSION = "1"
KEYS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")
SECRET_RES = [re.compile(p) for p in (
    r"(?i)[a-z][a-z0-9+.-]*://[^/\s:@]*:[^/\s@]+@",      # credentials in a URL, user part may be empty
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bgh[pousr]_[A-Za-z0-9]{20,}", r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b", r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    r"\bsk-[A-Za-z0-9_-]{20,}", r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}",  # incl. sk-proj-, sk-ant-, Stripe
)]
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b(?!:)")  # not git@host:repo
SIZE_RATIO, SIZE_FLOOR = 0.05, 20 * 1024
BUDGET, MAX_RESULTS, LINE_MAX, CONTEXT_LINES, MAX_ERRORS, MIN_TERM = 2000, 3, 160, 5, 10, 3
CALL = "dap.py find <index> <term> [<term> …] [--root DIR]"


def sha12(data):
    return hashlib.sha256(data).hexdigest()[:12]


def find_root(index):
    d = os.path.dirname(os.path.abspath(index))
    while True:
        if os.path.isdir(os.path.join(d, ".sdlc")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.getcwd()
        d = parent


def source_path(root, rel):
    """Absolute path of a src entry, or None when it points outside .sdlc/."""
    if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
        return None
    base = os.path.realpath(os.path.join(root, ".sdlc"))
    full = os.path.realpath(os.path.join(base, rel))
    return full if os.path.commonpath([base, full]) == base else None


def headings(text):
    """[(line, level, slug)]: GitHub-style anchors, with -1, -2 … for repeats; fenced code is skipped."""
    out, seen, fenced = [], {}, False
    for n, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        m = None if fenced else HEADING_RE.match(line)
        if not m:
            continue
        s = re.sub(r"[^\w\- ]", "", m.group(1).strip().lower()).replace(" ", "-")
        k = seen.get(s, 0)
        seen[s] = k + 1
        out.append((n, len(line) - len(line.lstrip("#")), s if k == 0 else "%s-%d" % (s, k)))
    return out


def slugs(text):
    return {s for _, _, s in headings(text)}


def section(text, slug):
    """(first, last) line of the section under the heading with this slug, or None."""
    hs = headings(text)
    for i, (n, level, s) in enumerate(hs):
        if s == slug:
            nxt = next((m for m, lv, _ in hs[i + 1:] if lv <= level), None)
            last = (nxt - 1) if nxt else len(text.rstrip("\n").split("\n"))
            return n, last
    return None


def commit_paths_ok(root, tmp, dest):
    """commit may only read .sdlc/context/index.dap.*.tmp and replace .sdlc/context/index.dap (symlinks resolved)."""
    ctx = os.path.realpath(os.path.join(root, ".sdlc", "context"))
    t, d = os.path.realpath(tmp), os.path.realpath(dest)
    name = os.path.basename(t)
    return (d == os.path.join(ctx, "index.dap") and os.path.dirname(t) == ctx
            and name.startswith("index.dap.") and name.endswith(".tmp"))


def load_keys():
    try:
        with open(KEYS, encoding="utf-8") as f:
            return {t: set(keys) for t, keys in json.load(f)["types"].items()}
    except (OSError, ValueError, KeyError, AttributeError):
        return None


def check(index, root, fresh_mode=False):
    """Return (errors, stale, idx12, warnings, counts). errors: ["ERROR <line>: <reason>"]; stale: ["STALE <alias> <path>"]."""
    if not os.path.isfile(index):
        return ["ERROR 0: index not found: %s" % index], [], None, [], None
    keys = load_keys()
    if keys is None:
        return ["ERROR 0: key list missing or unreadable: %s" % KEYS], [], None, [], None
    with open(index, "rb") as f:
        raw = f.read()
    errors, stale, srcs, sections, warnings = [], [], {}, set(), []
    header_seen = section = False
    src_bytes = 0
    stype, used = None, set()  # current section type (None if unknown) and keys used in it
    refs = []  # (line, alias, slug)
    src_lines, last, open_section, entries = 0, 1, None, 0  # open_section: [line of the section header, entries so far]
    for n, line in enumerate(raw.decode("utf-8", "replace").split("\n"), 1):
        line = line.rstrip("\r")
        if not line.strip() or line.startswith(";"):
            continue
        last = n
        if not header_seen:
            header_seen = True
            m = HEADER_RE.match(line)
            if not m:
                errors.append("ERROR %d: %s" % (n, "unknown version" if line.startswith("#dap ") else "missing header '#dap 1 built YYYY-MM-DD'"))
            elif m.group(1) != VERSION:
                errors.append("ERROR %d: unknown version %s" % (n, m.group(1)))
            if m:
                continue
        if line.startswith("src "):
            src_lines += 1
            m = SRC_RE.match(line)
            if not m:
                errors.append("ERROR %d: malformed src line (want 'src ALIAS PATH SHA12')" % n)
                continue
            alias, rel, h = m.groups()
            full = source_path(root, rel)
            if section:
                errors.append("ERROR %d: src line after the first section" % n)
            elif alias in srcs:
                errors.append("ERROR %d: duplicate src alias %s" % (n, alias))
            elif full is None:
                errors.append("ERROR %d: src path outside .sdlc/: %s" % (n, rel))
            elif not os.path.isfile(full):
                if fresh_mode:
                    stale.append("STALE %s %s" % (alias, rel))
                    srcs[alias] = (rel, None)
                else:
                    errors.append("ERROR %d: source not found: %s" % (n, rel))
            else:
                with open(full, "rb") as f:
                    data = f.read()
                src_bytes += len(data)
                if fresh_mode and sha12(data) != h:
                    stale.append("STALE %s %s" % (alias, rel))
                    srcs[alias] = (rel, None)
                else:
                    srcs[alias] = (rel, slugs(data.decode("utf-8", "replace")))
            continue
        m = SECTION_RE.match(line)
        if m:
            if open_section and open_section[1] == 0:
                errors.append("ERROR %d: section has no entries" % open_section[0])
            section, used, open_section = True, set(), [n, 0]
            stype = m.group(1) if m.group(1) in keys else None
            if stype is None:
                errors.append("ERROR %d: unknown section type %s" % (n, m.group(1)))
            if m.groups() in sections:
                errors.append("ERROR %d: duplicate section [%s %s]" % ((n,) + m.groups()))
            sections.add(m.groups())
            continue
        m = ENTRY_RE.match(line)
        if not m:
            errors.append("ERROR %d: unrecognised line" % n)
            continue
        if not section:
            errors.append("ERROR %d: entry outside a section" % n)
            continue
        open_section[1] += 1
        entries += 1
        key = m.group(1)
        if stype is not None and key not in keys[stype]:
            errors.append("ERROR %d: key %s not allowed in a %s section" % (n, key, stype))
        elif key in used:
            errors.append("ERROR %d: repeated key %s in this section" % (n, key))
        used.add(key)
        at = line.rfind(" @")
        value = line[:at] if at >= 0 else line
        if any(r.search(value) for r in SECRET_RES):
            errors.append("ERROR %d: value looks like a secret; point to its source section instead" % n)
        if EMAIL_RE.search(value):
            errors.append("ERROR %d: value holds an e-mail address (personal data); point to its source section instead" % n)
        if at < 0:
            errors.append("ERROR %d: entry has no @ref" % n)
            continue
        r = REF_RE.match(line[at + 2:])
        if not r:
            errors.append("ERROR %d: malformed @ref %r (want @alias#slug)" % (n, line[at + 2:]))
            continue
        refs.append((n, r.group(1), r.group(2)))
    if not header_seen:
        errors.append("ERROR 1: missing header '#dap 1 built YYYY-MM-DD'")
    if not src_lines:
        errors.append("ERROR 1: no src lines")
    if open_section is None:
        errors.append("ERROR %d: no sections" % last)
    elif open_section[1] == 0:
        errors.append("ERROR %d: section has no entries" % open_section[0])
    for n, alias, slug in refs:
        if alias not in srcs:
            errors.append("ERROR %d: unknown alias %s" % (n, alias))
        elif srcs[alias][1] is not None and slug not in srcs[alias][1]:
            errors.append("ERROR %d: no heading %s in %s" % (n, slug, srcs[alias][0]))
    if src_bytes >= SIZE_FLOOR and len(raw) > SIZE_RATIO * src_bytes:
        warnings.append("WARNING: index is %.1f%% of its sources (max 5%%)" % (100.0 * len(raw) / src_bytes))
    counts = "(%d sources, %d sections, %d entries)" % (src_lines, len(sections), entries)
    return sorted(errors, key=lambda e: int(e.split()[1].rstrip(":"))), stale, sha12(raw), warnings, counts


def show(index, root, ref):
    m = REF_RE.match(ref[1:] if ref.startswith("@") else ref)
    if not m:
        print("ERROR: malformed reference %r (want @alias#slug)" % ref)
        return 1
    alias, slug = m.groups()
    with open(index, encoding="utf-8", errors="replace") as f:
        srcs = {s.group(1): s.groups()[1:] for s in (SRC_RE.match(l.rstrip("\r\n")) for l in f) if s}
    if alias not in srcs:
        print("ERROR: unknown alias %s" % alias)
        return 1
    rel, h = srcs[alias]
    full = source_path(root, rel)
    if not full or not os.path.isfile(full):
        print("ERROR: source not found: %s" % rel)
        return 1
    with open(full, "rb") as f:
        data = f.read()
    text = data.decode("utf-8", "replace")
    span = section(text, slug)
    if span is None:
        print("ERROR: no heading %s in %s" % (slug, rel))
        return 1
    out = []
    if sha12(data) != h:
        out.append("WARNING: %s changed since this index was built; check the section still says this" % rel)
    lines = text.split("\n")
    out.append(".sdlc/%s:%d-%d" % (rel, span[0], span[1]))
    out += ["%d\t%s" % (n, lines[n - 1]) for n in range(span[0], span[1] + 1)]
    print("\n".join(out))
    return 0


def guard(text):
    """The final budget guard: at most BUDGET characters with the newline print adds. Over budget, the text is
    shortened but a closing cut line, if it has one, is kept."""
    if len(text) < BUDGET:
        return text
    last = text.rsplit("\n", 1)[-1]
    tail = "\n" + last if last.startswith("    … cut:") else ""
    return text[:BUDGET - len(tail) - 2] + "…" + tail


def redact(text):
    return any(r.search(text) for r in SECRET_RES) or bool(EMAIL_RE.search(text))


def cut_line(rel, span):
    return "    … cut: read .sdlc/%s:%d-%d" % (rel, span[0], span[1])


def clip(text, n=LINE_MAX):
    return text if len(text) <= n else text[:n - 1] + "…"


def index_entries(index):
    """(srcs, entries) of a valid index: srcs {alias: rel}; entries [(order, TYPE, id, key, value, alias, slug)]."""
    srcs, entries, sec = {}, [], None
    with open(index, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            m = SRC_RE.match(line)
            if m:
                srcs[m.group(1)] = m.group(2)
                continue
            m = SECTION_RE.match(line)
            if m:
                sec = m.groups()
                continue
            m = ENTRY_RE.match(line)
            at = line.rfind(" @")
            if sec and m and at >= 0:
                ref = REF_RE.match(line[at + 2:])
                if ref:
                    entries.append((len(entries), sec[0], sec[1], m.group(1), line[len(m.group(1)) + 2:at],
                                    ref.group(1), ref.group(2)))
    return srcs, entries


def excerpt(lines, span, terms, room, cut):
    """([formatted lines], whole): the section heading, then the lines holding a term with one line of context
    either side, else the next CONTEXT_LINES lines; as many as fit in `room` characters. Unless it is the whole
    section, it keeps room for the cut line `cut`."""
    first, last = span
    want = [first]
    hits = [n for n in range(first + 1, last + 1) if any(t in lines[n - 1].lower() for t in terms)]
    if hits:
        want += sorted({k for n in hits for k in (n - 1, n, n + 1) if first < k <= last})
    else:
        want += list(range(first + 1, min(last, first + CONTEXT_LINES) + 1))
    rows = ["    %d  %s" % (n, "[redacted: read the source]" if redact(lines[n - 1]) else clip(lines[n - 1]))
            for n in want]
    whole = len(want) == last - first + 1 and all(clip(lines[n - 1]) == lines[n - 1] or redact(lines[n - 1])
                                                  for n in want)
    if whole and sum(len(r) + 1 for r in rows) <= room:
        return rows, True
    out, used = [], 0
    for r in rows:
        if used + len(r) + 1 > room - len(cut) - 1:
            break
        out.append(r)
        used += len(r) + 1
    return out, False


def find(index, root, terms, stale=(), ignored=()):
    """The agent lookup. Prints at most BUDGET characters. Returns the exit code."""
    terms = [t.lower() for t in terms]
    srcs, entries = index_entries(index)
    first = ["ignored short terms: %s" % clip(", ".join(ignored), 120)] if ignored else []
    scored = []
    for e in entries:
        hay = " ".join((e[1], e[2], e[3], e[4], e[6])).lower()
        in_value = sum(1 for t in terms if t in e[4].lower())
        matched = sum(1 for t in terms if t in hay)
        if matched:
            scored.append((matched, in_value, e))
    if not scored:
        print(guard("\n".join(first + ["no match for: %s" % clip(" ".join(terms), 200)])))
        return 1
    groups = {}
    for matched, in_value, e in scored:
        groups.setdefault((e[5], e[6]), []).append((matched, in_value, e))
    ranked = sorted(groups.items(), key=lambda kv: (-max(m for m, _, _ in kv[1]), -max(v for _, v, _ in kv[1]),
                                                   min(e[0] for _, _, e in kv[1])))[:MAX_RESULTS]
    blocks, left = [], BUDGET - sum(len(l) + 1 for l in first)
    for i, ((alias, slug), items) in enumerate(ranked):
        share = left // (len(ranked) - i)
        rel = srcs[alias]
        is_stale = any(x.split()[1] == alias for x in stale)
        head = ["[%d] %s" % (i + 1, clip("%s %s / %s: %s @%s#%s" % (items[0][2][1].upper(), items[0][2][2], items[0][2][3],
                                                                     items[0][2][4], alias, slug)))]
        head += ["    " + clip("%s %s / %s: %s @%s#%s" % (e[1].upper(), e[2], e[3], e[4], alias, slug))
                 for _, _, e in items[1:]]
        full = source_path(root, rel)
        note = "(stale: %s changed since the index was built)" % rel
        if not full or not os.path.isfile(full):
            block = head + ["    (stale: %s) source not found: %s" % (rel, rel)]
        else:
            with open(full, encoding="utf-8", errors="replace") as f:
                lines = f.read().split("\n")
            span = section("\n".join(lines), slug)
            if span is None:
                block = head + ["    %s" % note, "    no heading %s in %s" % (slug, rel)]
            else:
                loc = "    .sdlc/%s:%d-%d%s" % (rel, span[0], span[1], ("        " + note) if is_stale else "")
                room = share - sum(len(l) + 1 for l in head) - len(loc) - 1
                cut = cut_line(rel, span)
                body, whole = excerpt(lines, span, terms, room, cut)
                block = head + [loc] + body + ([] if whole else [cut])
        text = "\n".join(block)
        blocks.append(text)
        left -= len(text) + 1
    print(guard("\n".join(first + blocks)))
    return 0


def usage_error(message):
    print(guard("usage error: %s\ncall: %s" % (message, CALL)))
    return 3


def find_main(a):
    """find: usage first, then the index (spec 002 contract order of checks)."""
    if a.index is None:
        return usage_error("an index argument is required")
    terms = [t.strip() for t in a.rest]
    usable = [t for t in terms if len(t) >= MIN_TERM]
    ignored = [t for t in terms if len(t) < MIN_TERM]
    if not usable:
        return usage_error("at least one search term of %d or more characters is required%s"
                           % (MIN_TERM, (" (ignored: %s)" % clip(", ".join(ignored), 80)) if ignored else ""))
    root = os.path.abspath(a.root) if a.root else find_root(a.index)
    errors, stale, _, _, _ = check(a.index, root, fresh_mode=True)
    if errors:
        shown = [clip(e, 120) for e in errors[:MAX_ERRORS]]
        if len(errors) > MAX_ERRORS:
            shown.append("… %d more; run dap.py validate %s" % (len(errors) - MAX_ERRORS, clip(a.index, 80)))
        print(guard("\n".join(["INVALID"] + shown)))
        return 2
    return find(a.index, root, usable, stale, ignored)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    is_find = bool(argv) and argv[0] == "find"

    class Parser(argparse.ArgumentParser):
        def error(self, message):  # find reports its own usage errors as exit 3, so exit 2 means "bad index"
            if is_find:
                sys.exit(usage_error(message))
            super().error(message)

    ap = Parser(description="Validate a dense index, check its freshness, or look things up in it.")
    ap.add_argument("command", choices=["validate", "fresh", "commit", "show", "find"])
    ap.add_argument("index", nargs="?", help="the index (for commit: the temporary index to validate)")
    ap.add_argument("rest", nargs="*", help="commit: the index to replace; show: the @alias#slug to print; "
                                           "find: the search terms")
    ap.add_argument("--root", help="folder that holds .sdlc/ (default: nearest one above the index)")
    a = ap.parse_args(argv)
    if a.command == "find":
        return find_main(a)
    if a.index is None:
        ap.error("an index argument is required")
    if (a.command in ("commit", "show")) != (len(a.rest) == 1 or (len(a.rest) > 1 and ap.error("too many arguments"))):
        ap.error("a second argument is required for commit and show, and only allowed there")
    a.dest = a.rest[0] if a.command in ("commit", "show") else None
    root = os.path.abspath(a.root) if a.root else find_root(a.index)
    if a.command == "commit" and not commit_paths_ok(root, a.index, a.dest):
        print("ERROR 0: commit only writes .sdlc/context/index.dap from .sdlc/context/index.dap.<id>.tmp "
              "(got %s -> %s)\nnot committed: %s unchanged" % (a.index, a.dest, a.dest))
        return 1
    errors, stale, idx, warnings, counts = check(a.index, root, fresh_mode=a.command in ("fresh", "show"))
    if a.command == "validate":
        print("\n".join(warnings + (errors or ["valid"])))
        return 1 if errors else 0
    if a.command == "commit":
        if errors:
            print("\n".join(errors + ["not committed: %s unchanged" % a.dest]))
            return 1
        os.replace(a.index, a.dest)
        print("\n".join(warnings + ["committed %s %s" % (idx, counts)]))
        return 0
    if errors:
        print("\n".join(["INVALID"] + errors))
        return 2
    if a.command == "show":
        return show(a.index, root, a.dest)
    print("\n".join(["%s %s" % ("stale" if stale else "fresh", idx)] + stale))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
