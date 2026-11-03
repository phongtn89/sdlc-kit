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
import tempfile

UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SESSION_RE = re.compile(r"^[0-9A-Fa-f-]{8,64}\Z")
TS_RE = re.compile(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?Z\Z")
UTC = datetime.timezone.utc
FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")


def parse_ts(text):
    m = TS_RE.match(text) if isinstance(text, str) else None
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
    """(start, end) line indexes of the `## heading` section (headings inside code fences do not count), or None."""
    want, fenced, start = "## " + heading, False, None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if start is None and line.rstrip() == want:
            start = i
        elif start is not None and line.startswith("## "):
            return start, i
    return (start, len(lines)) if start is not None else None


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
    hits = glob.glob(os.path.join(glob.escape(claude_base()), "projects", "*", glob.escape(session) + ".jsonl"))
    return hits[0] if len(hits) == 1 else None


class FormatError(Exception):
    pass


MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}\Z")


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
        if msg.get("model") == "<synthetic>":
            continue  # counts for nothing, so its shape does not matter
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
    folder = os.path.join(glob.escape(os.path.dirname(main_path)), glob.escape(session), "subagents")
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


def replace_open_line(text, unit, new_lines, heading):
    """Replace the unit's usage line (the last one in the section, and the stop mark after it) in place; None when
    the section has none."""
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(True)
    bounds = section_bounds(lines, heading)
    if bounds is None:
        return None
    hits = [i for i in range(bounds[0] + 1, bounds[1]) if lines[i].startswith("- usage %s:" % unit)]
    if not hits:
        return None
    i = hits[-1]
    j = i + 1
    if j < bounds[1] and lines[j].startswith("<!-- usage-stop %s " % unit):
        j += 1
    return "".join(lines[:i] + [l + nl for l in new_lines] + lines[j:])


MARK_RE = re.compile(r"<!-- usage-start (\S+) (\S+) session=(\S+) -->$")
SEG_ONE_MS = datetime.timedelta(milliseconds=1)


def read_marks(body):
    """[(unit, start datetime, session)] in file order; a session that is not hex digits and '-' is unknown."""
    out = []
    for line in body:
        m = MARK_RE.match(line.rstrip("\r"))
        ts = parse_ts(m.group(2)) if m else None
        if m and ts:
            out.append((m.group(1), ts, m.group(3) if SESSION_RE.match(m.group(3)) else "unknown"))
    return out


def last_assistant_ts(session):
    path = transcript_for(session) if session != "unknown" else None
    last = None
    if path:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                ts = parse_ts(rec.get("timestamp")) if isinstance(rec, dict) and rec.get("type") == "assistant" else None
                if ts and (last is None or ts > last):
                    last = ts
    return last


def unit_marks(body, unit):
    return [m for m in read_marks(body) if m[0] == unit]


def do_stop(args, text, now):
    unit = args.unit
    body = section_text(text, args.section)
    existing = [l for l in body if l.startswith("- usage %s:" % unit)]
    if existing and CLOSED_RE.search(existing[-1]):
        print("already closed")
        return None
    marks = unit_marks(body, unit)
    if not marks:
        return ["- usage %s: not available (no start mark)" % unit]
    stored = next((parse_ts(m.group(1)) for m in
                   (re.match(r"<!-- usage-stop %s (\S+) -->$" % re.escape(unit), l.rstrip("\r")) for l in body) if m), None)
    stop = parse_ts(args.at) if args.at else (stored or now)
    stop_mark = "<!-- usage-stop %s %s -->" % (unit, fmt_ts(stop))
    if all(m[2] == "unknown" for m in marks) and not os.path.isdir(claude_base()):
        return ["- usage %s: not available (no transcript on this target)" % unit, stop_mark]
    segs, seconds = [], 0.0
    for i, (_, begin, session) in enumerate(marks):
        if i == len(marks) - 1:
            end = stop
        else:
            last = last_assistant_ts(session)
            end = marks[i + 1][1] if last is None else min(last + SEG_ONE_MS, marks[i + 1][1])
        end = max(end, begin)
        seconds += (end - begin).total_seconds()
        segs.append((session, begin, end, segment(session, begin, end)))
    oks = [x for x in segs if x[3][0] == "ok"]
    if oks:
        total = dict.fromkeys(FIELDS, 0)
        turns, subs, models = 0, 0, []
        for _, _, _, (_, t, k, ms, sb) in oks:
            for f in FIELDS:
                total[f] += t[f]
            turns, subs = turns + k, subs + sb
            models += [m for m in ms if m not in models]
        figures = ("ok", total, turns, models, subs)
    else:
        figures = segs[-1][3]
    line = usage_line(unit, figures, wall_text(seconds))
    for k, (session, _, _, seg) in enumerate(segs, 1):
        if seg[0] == "na" and (oks or k < len(segs)):
            line += " · PARTIAL: segment %d (session %s): %s" % (k, session, seg[1])
    others = []
    for ou, ots, osess in read_marks(body):
        if ou != unit and osess != "unknown" and any(
                osess == session and begin <= ots < end for session, begin, end, _ in segs) and ou not in others:
            others.append(ou)
    if others:
        line += " · OVERLAP: " + ", ".join(others)
    return [line, stop_mark]


def write_atomic(root, record, data):
    """Write bytes to the record through a temporary file in its folder; the record keeps its mode and a symlink is
    followed. Returns an error text, or None."""
    target = os.path.realpath(record)
    try:
        mode = os.stat(target).st_mode & 0o7777
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".usage-", suffix=".tmp")
    except OSError as e:
        return "could not write the record (%s)" % e.strerror
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return "could not write the record (%s)" % e.strerror
    return None


def inside(root, path):
    """True when the path, with symlinks resolved, lies inside the project root."""
    base, real = os.path.realpath(root), os.path.realpath(path)
    return os.path.commonpath([base, real]) == base


def cmd(args):
    root = find_root(os.getcwd())
    if root is None or not switch_on(root):
        print("usage off")
        return 0
    if not UNIT_RE.match(args.unit):
        print("usage: unit id may use letters, digits, '-', '_' and '.' only (and must start with a letter or digit)")
        return 2
    if args.at is not None and parse_ts(args.at) is None:
        print("usage: --at needs a timestamp like 2026-11-03T10:23:07.456Z")
        return 2
    record = os.path.join(root, args.record)
    if os.path.isabs(args.record) or ".." in args.record.replace("\\", "/").split("/") or not inside(root, record):
        print("usage: the record must be a path inside the project: %s" % args.record)
        return 2
    if not os.path.isfile(record):
        print("usage: record not found: %s" % args.record)
        return 2
    with open(record, "rb") as f:
        text = f.read().decode("utf-8", "surrogateescape")
    now = datetime.datetime.now(UTC)
    if args.command == "start":
        body = section_text(text, args.section)
        existing = [l for l in body if l.startswith("- usage %s:" % args.unit)]
        session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        session = session if SESSION_RE.match(session) else "unknown"
        if existing and CLOSED_RE.search(existing[-1]):
            print("unit already closed (use a new id, for example %s-r2)" % args.unit)
            return 0
        if session != "unknown" and any(m[2] == session for m in unit_marks(body, args.unit)):
            print("already started")
            return 0
        out = insert(text, args.section, ["<!-- usage-start %s %s session=%s -->" % (args.unit, fmt_ts(now), session)])
    else:
        new = do_stop(args, text, now)
        if new is None:
            return 0
        out = replace_open_line(text, args.unit, new, args.section)
        if out is None:
            out = insert(text, args.section, new)
    err = write_atomic(root, record, out.encode("utf-8", "surrogateescape"))
    if err:
        print("usage: " + err)
        return 2
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
