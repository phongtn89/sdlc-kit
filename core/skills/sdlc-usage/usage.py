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


def claude_base():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def transcript_for(session):
    """The one transcript of a session, or None when there is none or several."""
    hits = glob.glob(os.path.join(claude_base(), "projects", "*", session + ".jsonl"))
    return hits[0] if len(hits) == 1 else None


class FormatError(Exception):
    pass


MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def read_responses(path):
    """The last assistant record per message id in one transcript: [(timestamp, usage dict, model)], oldest first.
    Raises FormatError for a counted record (an assistant record with usage) that lacks an id, a parseable
    timestamp or four integer counters, and for an unparsable line other than the last."""
    kept = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = [l for l in f.read().split("\n") if l.strip()]
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            if i == len(lines) - 1:
                continue  # the file may be mid-write
            raise FormatError("unparsable line")
        msg = rec.get("message") if isinstance(rec, dict) else None
        if not isinstance(rec, dict) or rec.get("type") != "assistant" or not isinstance(msg, dict) \
                or not isinstance(msg.get("usage"), dict):
            continue
        ts, u, mid = parse_ts(rec.get("timestamp")), msg["usage"], msg.get("id")
        if ts is None or not isinstance(mid, str) or not mid or \
                any(type(u.get(k)) is not int for k in FIELDS):
            raise FormatError("counted record out of shape")
        kept[mid] = (ts, u, msg.get("model"))
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


CLOSED_RE = re.compile(r"(?:\bin |cache-read |cache-write |out |sub-agents )\d|\d[\d,]* turns")


def segment(session, begin, end):
    """('ok', totals, turns, models, sub-agent total) or ('na', reason) for one window of one session."""
    if session == "unknown":
        return ("na", "session id unknown")
    path = transcript_for(session)
    if path is None:
        return ("na", "transcript not found")
    try:
        total, turns, models = read_main(path, begin, end)
        subs = read_subagents(path, session, begin, end)
    except FormatError:
        return ("na", "unexpected transcript format")
    if turns == 0:
        return ("na", "no response in window")
    return ("ok", total, turns, models, subs)


def usage_line(unit, seg, wall):
    if seg[0] == "na":
        r = seg[1]
        return "- usage %s: tokens not available (%s) · sub-agents not available (%s) · %s · turns not available (%s)" \
               " · model not available (%s)" % (unit, r, r, wall, r, r)
    _, total, turns, models, subs = seg
    return "- usage %s: in %s · cache-read %s · cache-write %s · out %s · sub-agents %s · %s · %s turns · model %s" % (
        unit, n(total["input_tokens"]), n(total["cache_read_input_tokens"]), n(total["cache_creation_input_tokens"]),
        n(total["output_tokens"]), n(subs), wall, n(turns), ", ".join(models) if models else "model not recorded")


def wall_text(seconds):
    return "<1 min wall" if seconds < 30 else "%d min wall" % ((int(seconds) + 30) // 60)


def replace_open_line(lines, unit, new_lines):
    """Replace an existing open usage line (and the stop mark after it) in place; None when there is none."""
    for i, line in enumerate(lines):
        if line.startswith("- usage %s:" % unit):
            j = i + 1
            if j < len(lines) and lines[j].startswith("<!-- usage-stop %s " % unit):
                j += 1
            return lines[:i] + new_lines + lines[j:]
    return None


def do_stop(args, text, now):
    unit = args.unit
    body = section_text(text, args.section)
    existing = [l for l in body if l.startswith("- usage %s:" % unit)]
    if existing and CLOSED_RE.search(existing[-1]):
        print("already closed")
        return None
    marks = [re.match(r"<!-- usage-start %s (\S+) session=(\S+) -->$" % re.escape(unit), l) for l in body]
    marks = [m for m in marks if m]
    if not marks:
        new = ["- usage %s: not available (no start mark)" % unit]
    else:
        stored = next((parse_ts(m.group(1)) for m in
                       (re.match(r"<!-- usage-stop %s (\S+) -->$" % re.escape(unit), l) for l in body) if m), None)
        stop = parse_ts(args.at) if args.at else (stored or now)
        if stop is None:
            raise SystemExit("usage: --at needs a timestamp like 2026-11-03T10:23:07.456Z")
        begin, session = parse_ts(marks[-1].group(1)), marks[-1].group(2)
        wall = wall_text((stop - begin).total_seconds())
        if session == "unknown" and not os.path.isdir(claude_base()):
            new = ["- usage %s: not available (no transcript on this target)" % unit]
        else:
            new = [usage_line(unit, segment(session, begin, stop), wall)]
        new.append("<!-- usage-stop %s %s -->" % (unit, fmt_ts(stop)))
    return new


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
        out = insert(text, args.section, ["<!-- usage-start %s %s session=%s -->" % (args.unit, fmt_ts(now), session)])
    else:
        new = do_stop(args, text, now)
        if new is None:
            return 0
        lines = text.split("\n")
        replaced = replace_open_line(lines, args.unit, new)
        out = "\n".join(replaced) if replaced is not None and any(
            l.startswith("- usage %s:" % args.unit) for l in lines) else insert(text, args.section, new)
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
