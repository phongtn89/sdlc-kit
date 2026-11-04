"""sdlc verify: run the project's configured checks once and write an evidence record.

Imported by `bin/sdlc` inside `cmd_verify` only. Contract: specs/004-verify-command/contracts/record.md.
"""
import datetime
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

ORDER = ("test", "lint", "typecheck", "build", "integration")
GIT = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false"]
EXCLUDE = ":(exclude).sdlc/evidence"
RECORD = os.path.join(".sdlc", "evidence", "verify.json")
DEFAULT_TIMEOUT = 600
TAIL_LINES, TAIL_LINE_CHARS, TAIL_CHARS, TAIL_BYTES = 20, 400, 2000, 8192


class VerifyError(Exception):
    """A usage or config problem: exit 2, nothing runs."""


class Interrupted(Exception):
    """SIGINT or SIGTERM reached verify."""


def _on_signal(signum, frame):
    raise Interrupted()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


GIT_TIMEOUT = 20


def git_run(workdir, *args, input=None):
    """(status, stdout) with status `ok`, `fail`, `timeout` or `nogit`; `input` goes to standard input."""
    try:
        p = subprocess.run(GIT + ["-C", workdir] + list(args), capture_output=True, text=True,
                           timeout=GIT_TIMEOUT, input=input, stdin=None if input is not None else subprocess.DEVNULL)
    except FileNotFoundError:
        return "nogit", ""
    except subprocess.TimeoutExpired:
        return "timeout", ""
    except OSError:
        return "fail", ""
    return ("ok" if p.returncode == 0 else "fail"), (p.stdout if p.returncode == 0 else "")


def git_call(workdir, *args):
    """(ok, stdout). A failed or timed-out call is ok=False; no git at all is (None, "")."""
    status, out = git_run(workdir, *args)
    return (None if status == "nogit" else status == "ok"), out


def git_state(workdir):
    """(revision or None, dirty). A failed status reads as dirty; no repository or commit is (None, False)."""
    ok, out = git_call(workdir, "rev-parse", "HEAD")
    rev = out.strip() if ok and out.strip() else None
    if rev is None:
        return None, False
    ok, out = git_call(workdir, "status", "--porcelain", "--untracked-files=normal", "--", ".", EXCLUDE)
    return rev, (not ok) or bool(out.strip())


def resolve(cfg, repo, root, safe_path):
    """(commands, workdir, timeout) from the config, or VerifyError."""
    if not isinstance(cfg, dict):
        raise VerifyError("config.json must be a JSON object")
    node, workdir = cfg, root
    repos = cfg.get("repos")
    if repos is not None and not isinstance(repos, dict):
        raise VerifyError("repos must be an object")
    section = cfg.get("verify")
    if section is not None and not isinstance(section, dict):
        raise VerifyError("verify must be an object")
    timeout = (section or {}).get("timeout_seconds", DEFAULT_TIMEOUT)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise VerifyError("verify.timeout_seconds must be a positive integer")
    if repo is not None:
        if repos is None or repo not in repos:
            raise VerifyError("unknown repo: %s" % repo)
        node = repos[repo]
        if not isinstance(node, dict) or not isinstance(node.get("path"), str):
            raise VerifyError("repos.%s needs an object with a string path" % repo)
        try:
            workdir = safe_path(root, node["path"])
        except Exception as e:
            raise VerifyError(str(e))
        if not os.path.isdir(workdir):
            raise VerifyError("repos.%s.path is not a folder" % repo)
    commands = node.get("commands")
    if commands is None:
        commands = {}
    if not isinstance(commands, dict):
        raise VerifyError("commands must be an object")
    out = []
    for name in ORDER:
        text = commands.get(name)
        if text is None or (isinstance(text, str) and not text.strip()):
            continue
        if not isinstance(text, str) or "\x00" in text:
            raise VerifyError("commands.%s must be a string without NUL" % name)
        out.append((name, text))
    return out, workdir, timeout


def tail_of(f):
    f.flush()
    size = f.seek(0, os.SEEK_END)
    f.seek(max(0, size - TAIL_BYTES))
    text = f.read().decode("utf-8", "replace")
    lines = [l[:TAIL_LINE_CHARS] for l in text.splitlines()[-TAIL_LINES:]]
    return "\n".join(lines)[-TAIL_CHARS:]


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def run_command(name, text, workdir, timeout):
    """(entry for the record, output tail)."""
    entry = {"name": name, "command": text}
    t0 = time.monotonic()
    with tempfile.TemporaryFile() as out:
        try:
            p = subprocess.Popen(text, shell=True, cwd=workdir, stdin=subprocess.DEVNULL, stdout=out,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            entry.update(exit="not started", error=str(e), seconds=0.0, result="fail")
            return entry, ""
        try:
            code = p.wait(timeout)
            entry.update(exit=code, result="pass" if code == 0 else "fail")
        except subprocess.TimeoutExpired:
            kill_group(p.pid)
            p.wait()
            entry.update(exit="timeout", result="timeout")
        finally:
            kill_group(p.pid)
        entry["seconds"] = round(time.monotonic() - t0, 1)
        return entry, tail_of(out)


def summary_line(e, timeout):
    secs = "%.1f s" % e["seconds"]
    if e["result"] == "pass":
        return "verify %s: pass (%s)" % (e["name"], secs)
    if e["result"] == "timeout":
        return "verify %s: TIMEOUT after %d s" % (e["name"], timeout)
    if e["exit"] == "not started":
        return "verify %s: NOT STARTED (%s)" % (e["name"], e["error"])
    return "verify %s: FAIL exit %s (%s)" % (e["name"], e["exit"], secs)


def final_line(ok, revision, dirty):
    word = "PASSED" if ok else "FAILED"
    if revision is None:
        return "verify: %s (no revision, not verified at HEAD)" % word
    if dirty:
        return "verify: %s at %s (dirty tree, not verified at HEAD)" % (word, revision[:7])
    return "verify: %s at %s (clean tree)" % (word, revision[:7])


def write_record(path, data, replace=os.replace):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".verify-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run(root, cfg, repo, safe_path):
    """(exit code, lines to print)."""
    cmds, workdir, timeout = resolve(cfg, repo, root, safe_path)
    if not cmds:
        return 2, ["verify: NOTHING VERIFIED (no command configured)"]
    old = {}
    try:
        for s in (signal.SIGINT, signal.SIGTERM):
            old[s] = signal.signal(s, _on_signal)
    except ValueError:  # not the main thread (tests that call run() directly)
        old = {}
    try:
        return _run(cmds, workdir, timeout)
    except Interrupted:
        sys.stderr.write("verify: interrupted, no record written\n")
        return 1, []
    finally:
        for s, h in old.items():
            signal.signal(s, h)


def _run(cmds, workdir, timeout):
    started = utc_now()
    rev0, dirty0 = git_state(workdir)
    lines, entries = [], []
    for name, text in cmds:
        entry, tail = run_command(name, text, workdir, timeout)
        entries.append(entry)
        lines.append(summary_line(entry, timeout))
        if entry["result"] != "pass" and tail:
            lines.append(tail)
    ok = all(e["result"] == "pass" for e in entries)
    rev1, dirty1 = git_state(workdir) if rev0 else (None, False)
    revision = rev0 if rev1 == rev0 else None
    dirty = dirty0 or dirty1
    lines.append(final_line(ok, revision, dirty))
    record = {"version": 1, "started": started, "finished": utc_now(), "revision": revision, "dirty": dirty,
              "commands": entries}
    try:
        write_record(os.path.join(workdir, RECORD), record)
    except OSError as e:
        lines.append("verify: record NOT written (%s); not verified" % (e.strerror or e))
        return (2 if ok else 1), lines
    return (0 if ok else 1), lines


def green_reason(record, head):
    """None when the record is green at `head`, else the first reason it is not. Never raises."""
    try:
        if not isinstance(record, dict) or record.get("version") != 1:
            return "record shape or version wrong"
        rev, dirty, cmds = record.get("revision"), record.get("dirty"), record.get("commands")
        if not (rev is None or isinstance(rev, str)) or not isinstance(dirty, bool) or not isinstance(cmds, list) \
                or not all(isinstance(c, dict) for c in cmds):
            return "record shape or version wrong"
        if not rev:
            return "record has no revision"
        if rev != head:
            return "record is for another revision"
        if dirty:
            return "record was dirty"
        if not cmds:
            return "no commands in the record"
        if not all(isinstance(c.get("name"), str) and c.get("exit") == 0 and c.get("result") == "pass" for c in cmds):
            return "a command did not pass"
        return None
    except Exception:
        return "record shape or version wrong"


def green_at_head(record, head):
    """The definition E1.3 reads: a current, clean, all-pass record."""
    return green_reason(record, head) is None
