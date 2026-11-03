#!/usr/bin/env python3
"""Per-unit usage for sdlc-kit (spec 003). Standard library only, offline, never reads message content.

  usage.py start <unit> --record <file> [--section <heading>]
  usage.py stop  <unit> --record <file> [--section <heading>] [--at <timestamp>]

Writes a start mark and, at stop, one usage line into the unit's owning record. Contract:
specs/003-usage-metrics/contracts/usage.md in sdlc-kit. Off unless .sdlc/config.json has "usage": {"enabled": true}.
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SESSION_RE = re.compile(r"^[0-9A-Fa-f-]{8,64}$")
TS_RE = re.compile(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?Z$")
UTC = datetime.timezone.utc
FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")


def parse_ts(text):
    m = TS_RE.match(text or "")
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) for x in m.groups()[:6])
    micro = int((m.group(7) or "0").ljust(6, "0"))
    return datetime.datetime(y, mo, d, h, mi, s, micro, tzinfo=UTC)


def fmt_ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def find_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, ".sdlc", "config.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def switch_on(root):
    try:
        with open(os.path.join(root, ".sdlc", "config.json"), encoding="utf-8") as f:
            usage = json.load(f).get("usage")
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(usage, dict) and usage.get("enabled") is True


def section_bounds(lines, heading):
    """(start, end) line indexes of the `## heading` section, or None."""
    want = "## " + heading
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == want:
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
            return i, end
    return None


def insert(text, heading, new_lines):
    """Append lines at the end of a section, creating the section at the end of the file when absent."""
    lines = text.splitlines(True)
    nl = "\r\n" if "\r\n" in text else "\n"
    new = [l + nl for l in new_lines]
    b = section_bounds(lines, heading)
    if b is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += nl
        return "".join(lines) + nl + "## " + heading + nl + nl + "".join(new)
    start, end = b
    at = start + 1
    for j in range(start + 1, end):
        if lines[j].strip():
            at = j + 1
    if at > 0 and not lines[at - 1].endswith("\n"):
        lines[at - 1] += nl
    return "".join(lines[:at] + new + lines[at:])


def section_text(text, heading):
    lines = text.splitlines()
    b = section_bounds(text.splitlines(True), heading)
    return lines[b[0] + 1:b[1]] if b else []


def transcript_for(session):
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    hits = sorted(glob.glob(os.path.join(base, "projects", "*", session + ".jsonl")))
    return hits[0] if hits else None


MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def read_responses(path):
    """The last assistant record per message id in one transcript: [(timestamp, usage dict, model)], oldest first."""
    kept = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") if isinstance(rec, dict) else None
            if rec.get("type") != "assistant" or not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
                continue
            ts = parse_ts(rec.get("timestamp"))
            if ts is not None:
                kept[msg.get("id")] = (ts, msg["usage"], msg.get("model"))
    return sorted(kept.values(), key=lambda r: r[0])


def in_window(responses, start, end):
    return [r for r in responses if start <= r[0] < end and r[2] != "<synthetic>"]


def read_main(path, start, end):
    """Sum the counted responses of one transcript inside [start, end): (totals, turns, models)."""
    total, models = dict.fromkeys(FIELDS, 0), []
    rows = in_window(read_responses(path), start, end)
    for _, u, model in rows:
        for k in FIELDS:
            total[k] += u[k]
        if isinstance(model, str) and MODEL_RE.match(model) and model not in models:
            models.append(model)
    return total, len(rows), models


def read_subagents(main_path, session, start, end):
    """Sum of the four token fields over the sub-agent transcripts of the session inside the window."""
    folder = os.path.join(os.path.dirname(main_path), session, "subagents")
    total = 0
    for f in sorted(glob.glob(os.path.join(folder, "agent-*.jsonl"))):
        for _, u, _ in in_window(read_responses(f), start, end):
            total += sum(u[k] for k in FIELDS)
    return total


def n(value):
    return "{:,}".format(value)


def cmd(args):
    root = find_root(os.getcwd())
    if root is None or not switch_on(root):
        print("usage off")
        return 0
    if not UNIT_RE.match(args.unit):
        print("usage: unit id may use letters, digits, '-', '_' and '.' only (and must start with a letter or digit)")
        return 2
    record = os.path.join(root, args.record)
    if not os.path.isfile(record):
        print("usage: record not found: %s" % args.record)
        return 2
    with open(record, encoding="utf-8", newline="") as f:
        text = f.read()
    now = datetime.datetime.now(UTC)
    if args.command == "start":
        session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        session = session if SESSION_RE.match(session) else "unknown"
        mark = "<!-- usage-start %s %s session=%s -->" % (args.unit, fmt_ts(now), session)
        out = insert(text, args.section, [mark])
    else:
        marks = [re.match(r"<!-- usage-start %s (\S+) session=(\S+) -->$" % re.escape(args.unit), l)
                 for l in section_text(text, args.section)]
        marks = [m for m in marks if m]
        if not marks:
            print("usage: no start mark for %s" % args.unit)
            return 2
        stop = parse_ts(args.at) if args.at else now
        if stop is None:
            print("usage: --at needs a timestamp like 2026-11-03T10:23:07.456Z")
            return 2
        begin = parse_ts(marks[-1].group(1))
        path = transcript_for(marks[-1].group(2))
        total, turns, models = read_main(path, begin, stop)
        subs = read_subagents(path, marks[-1].group(2), begin, stop)
        minutes = (int((stop - begin).total_seconds()) + 30) // 60
        wall = "%d min wall" % minutes if (stop - begin).total_seconds() >= 30 else "<1 min wall"
        line = "- usage %s: in %s · cache-read %s · cache-write %s · out %s · sub-agents %s · %s · %s turns · model %s" % (
            args.unit, n(total["input_tokens"]), n(total["cache_read_input_tokens"]),
            n(total["cache_creation_input_tokens"]), n(total["output_tokens"]), n(subs), wall, n(turns), ", ".join(models))
        out = insert(text, args.section, [line, "<!-- usage-stop %s %s -->" % (args.unit, fmt_ts(stop))])
    with open(record, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Record token and time usage per unit of work.")
    ap.add_argument("command", choices=["start", "stop"])
    ap.add_argument("unit")
    ap.add_argument("--record", required=True, help="the owning record, relative to the project root")
    ap.add_argument("--section", default="Progress log")
    ap.add_argument("--at", help="stop time (backfill and tests); default now")
    return cmd(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
