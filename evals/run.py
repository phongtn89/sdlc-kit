#!/usr/bin/env python3
"""Run one eval prompt in one fresh, non-interactive Claude Code session.

One process per task, so no reused session, pasted prompt or stray message can
contaminate the run (spec 001 retro, L2). Refuses to run when the prompt leaks
into the target. Exit: 0 finished, 2 refused (leak, empty prompt, --out inside the target), 3 no result event or timed out.
"""
import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys

SKIP_DIRS = {".git", "node_modules"}


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def leaks(prompt_file, prompt, target):
    real_target = os.path.realpath(target) + os.sep
    found = []
    if os.path.realpath(prompt_file).startswith(real_target):
        found.append(os.path.relpath(prompt_file, target) + " (the prompt file itself)")
    needle = norm(prompt)[:60]
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            path = os.path.join(root, f)
            try:
                if os.path.getsize(path) > 2_000_000:
                    continue
                with open(path, encoding="utf-8") as fh:
                    if needle and needle in norm(fh.read()):
                        found.append(os.path.relpath(path, target))
            except (UnicodeDecodeError, OSError):
                continue
    return sorted(set(found))


def snapshot(target):
    # Content hashes, not git status: an eval diff is often uncommitted, and git can't see a further edit to it.
    state = {}
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            path = os.path.join(root, f)
            try:
                with open(path, "rb") as fh:
                    state[os.path.relpath(path, target)] = hashlib.sha256(fh.read()).hexdigest()
            except OSError:
                continue
    return state


def git_head(target):
    # snapshot() skips .git, so commits are checked separately.
    p = subprocess.run(["git", "-C", target, "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def summarize(lines):
    info = {"tools": [], "result": None}
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            info["session"], info["model"] = d.get("session_id"), d.get("model")
        content = (d.get("message") or {}).get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    arg = b.get("input") or {}
                    first = next(iter(arg.values()), "") if arg else ""
                    info["tools"].append("%s %s" % (b.get("name"), str(first).split("\n")[0][:100]))
        if d.get("type") == "result":
            info["result"] = d
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prompt_file", help="file holding the prompt, verbatim; must be outside the target")
    ap.add_argument("target", help="scratch repo the session runs in")
    ap.add_argument("--out", required=True, help="where to save the stream-json transcript")
    ap.add_argument("--model")
    ap.add_argument("--allowed-tools")
    ap.add_argument("--claude", default="claude", help="CLI to run (tests pass a fake)")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds")
    a = ap.parse_args(argv)

    with open(a.prompt_file, encoding="utf-8") as f:
        prompt = f.read().strip()
    if not prompt:
        print("refused: empty prompt")
        return 2
    if os.path.realpath(a.out).startswith(os.path.realpath(a.target) + os.sep):
        print("refused: --out is inside the target; the transcript would show up as a change and a leak")
        return 2
    found = leaks(a.prompt_file, prompt, a.target)
    if found:
        for f in found:
            print("LEAK %s" % f)
        print("refused: the prompt is readable from the target; move it out")
        return 2

    cmd = [a.claude, "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if a.model:
        cmd += ["--model", a.model]
    if a.allowed_tools:
        cmd += ["--allowedTools", a.allowed_tools]
    before, head_before = snapshot(a.target), git_head(a.target)
    # Own process group, so a timeout also stops the CLI's children and the pipes close.
    p = subprocess.Popen(cmd, cwd=a.target, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         encoding="utf-8", errors="replace", start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = p.communicate(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # exited on its own after the timeout fired
        stdout, stderr = p.communicate()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(stdout)
    after, head_after = snapshot(a.target), git_head(a.target)

    info = summarize(stdout.split("\n"))
    print("transcript: %s" % a.out)
    print("session: %s" % info.get("session"))
    print("model: %s" % info.get("model"))
    for t in info["tools"]:
        print("tool: %s" % t)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if changed:
        print("TARGET CHANGED")
        for k in changed:
            print("  %s" % k)
    else:
        print("target unchanged")
    if head_before != head_after:
        print("HEAD MOVED %s -> %s" % (head_before, head_after))
    r = info["result"]
    if timed_out:
        print("NO RESULT: timed out after %d s; not a finished run" % a.timeout)
        if stderr.strip():
            print(stderr.strip()[-500:])
        return 3
    if r is None:
        print("NO RESULT: the session ended without a result event (exit %d); not a finished run" % p.returncode)
        if stderr.strip():
            print(stderr.strip()[-500:])
        return 3
    text = r.get("result") or ""
    print("first line: %s" % (text.split("\n")[0] if text else ""))
    print("turns: %s  cost_usd: %s  subtype: %s" % (r.get("num_turns"), r.get("total_cost_usd"), r.get("subtype")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
