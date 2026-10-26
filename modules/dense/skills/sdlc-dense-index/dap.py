#!/usr/bin/env python3
"""Dense index (DAP v1) validator and freshness check. Standard library only.

  dap.py validate <index> [--root DIR]      exit 0 valid, 1 invalid
  dap.py fresh <index> [--root DIR]         exit 0 fresh, 1 stale, 2 invalid or missing
  dap.py commit <tmp> <dest> [--root DIR]   exit 0 replaced, 1 invalid (dest unchanged)

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


def slugs(text):
    """GitHub-style heading anchors, with -1, -2 … for repeats; fenced code is skipped."""
    out, seen, fenced = set(), {}, False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        m = None if fenced else HEADING_RE.match(line)
        if not m:
            continue
        s = re.sub(r"[^\w\- ]", "", m.group(1).strip().lower()).replace(" ", "-")
        n = seen.get(s, 0)
        seen[s] = n + 1
        out.add(s if n == 0 else "%s-%d" % (s, n))
    return out


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
    """Return (errors, stale, idx12, warnings). errors: ["ERROR <line>: <reason>"]; stale: ["STALE <alias> <path>"]."""
    if not os.path.isfile(index):
        return ["ERROR 0: index not found: %s" % index], [], None, []
    keys = load_keys()
    if keys is None:
        return ["ERROR 0: key list missing or unreadable: %s" % KEYS], [], None, []
    with open(index, "rb") as f:
        raw = f.read()
    errors, stale, srcs, sections, warnings = [], [], {}, set(), []
    header_seen = section = False
    src_bytes = 0
    stype, used = None, set()  # current section type (None if unknown) and keys used in it
    refs = []  # (line, alias, slug)
    src_lines, last, open_section = 0, 1, None  # open_section: [line of the section header, entries so far]
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
    return sorted(errors, key=lambda e: int(e.split()[1].rstrip(":"))), stale, sha12(raw), warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a dense index or check its freshness.")
    ap.add_argument("command", choices=["validate", "fresh", "commit"])
    ap.add_argument("index", help="the index (for commit: the temporary index to validate)")
    ap.add_argument("dest", nargs="?", help="commit only: the index to replace")
    ap.add_argument("--root", help="folder that holds .sdlc/ (default: nearest one above the index)")
    a = ap.parse_args(argv)
    if (a.command == "commit") != (a.dest is not None):
        ap.error("dest is required for commit and only allowed there")
    root = os.path.abspath(a.root) if a.root else find_root(a.index)
    if a.command == "commit" and not commit_paths_ok(root, a.index, a.dest):
        print("ERROR 0: commit only writes .sdlc/context/index.dap from .sdlc/context/index.dap.<id>.tmp "
              "(got %s -> %s)\nnot committed: %s unchanged" % (a.index, a.dest, a.dest))
        return 1
    errors, stale, idx, warnings = check(a.index, root, fresh_mode=a.command == "fresh")
    if a.command == "validate":
        print("\n".join(warnings + (errors or ["valid"])))
        return 1 if errors else 0
    if a.command == "commit":
        if errors:
            print("\n".join(errors + ["not committed: %s unchanged" % a.dest]))
            return 1
        os.replace(a.index, a.dest)
        print("\n".join(warnings + ["committed %s" % idx]))
        return 0
    if errors:
        print("\n".join(["INVALID"] + errors))
        return 2
    print("\n".join(["%s %s" % ("stale" if stale else "fresh", idx)] + stale))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
