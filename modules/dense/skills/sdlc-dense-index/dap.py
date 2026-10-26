#!/usr/bin/env python3
"""Dense index (DAP v1) validator and freshness check. Standard library only.

  dap.py validate <index> [--root DIR]   exit 0 valid, 1 invalid
  dap.py fresh <index> [--root DIR]      exit 0 fresh, 1 stale, 2 invalid or missing

The grammar is specs/001-dense-agent-protocol/contracts/index-format.md in sdlc-kit.
"""
import argparse
import hashlib
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


def check(index, root, fresh_mode=False):
    """Return (errors, stale, idx12). errors: ["ERROR <line>: <reason>"]; stale: ["STALE <alias> <path>"]."""
    if not os.path.isfile(index):
        return ["ERROR 0: index not found: %s" % index], [], None
    with open(index, "rb") as f:
        raw = f.read()
    errors, stale, srcs, sections = [], [], {}, set()
    header_seen = section = False
    refs = []  # (line, alias, slug)
    for n, line in enumerate(raw.decode("utf-8", "replace").split("\n"), 1):
        line = line.rstrip("\r")
        if not line.strip() or line.startswith(";"):
            continue
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
                if fresh_mode and sha12(data) != h:
                    stale.append("STALE %s %s" % (alias, rel))
                    srcs[alias] = (rel, None)
                else:
                    srcs[alias] = (rel, slugs(data.decode("utf-8", "replace")))
            continue
        m = SECTION_RE.match(line)
        if m:
            section = True
            sections.add(m.groups())
            continue
        m = ENTRY_RE.match(line)
        if not m:
            errors.append("ERROR %d: unrecognised line" % n)
            continue
        if not section:
            errors.append("ERROR %d: entry outside a section" % n)
            continue
        at = line.rfind(" @")
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
    for n, alias, slug in refs:
        if alias not in srcs:
            errors.append("ERROR %d: unknown alias %s" % (n, alias))
        elif srcs[alias][1] is not None and slug not in srcs[alias][1]:
            errors.append("ERROR %d: no heading %s in %s" % (n, slug, srcs[alias][0]))
    return sorted(errors, key=lambda e: int(e.split()[1].rstrip(":"))), stale, sha12(raw)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a dense index or check its freshness.")
    ap.add_argument("command", choices=["validate", "fresh"])
    ap.add_argument("index")
    ap.add_argument("--root", help="folder that holds .sdlc/ (default: nearest one above the index)")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root) if a.root else find_root(a.index)
    errors, stale, idx = check(a.index, root, fresh_mode=a.command == "fresh")
    if a.command == "validate":
        print("\n".join(errors) if errors else "valid")
        return 1 if errors else 0
    if errors:
        print("\n".join(["INVALID"] + errors))
        return 2
    print("\n".join(["%s %s" % ("stale" if stale else "fresh", idx)] + stale))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
