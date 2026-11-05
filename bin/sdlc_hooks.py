"""Enforcement hooks for Claude Code (spec 006): the entries rendered into .claude/settings.json and their runtime.

A refusal is never an exit code. The host reads exit code 2 as a refusal, and python exits 2 for a missing script or
an unknown subcommand, so every entry ends with `exit 0` and a refusal is a structured deny message on standard output.
"""
import json
import os
import shlex
import types

import sdlc_gate

NAMES = ("bash", "edit", "stop")
MATCHERS = {"bash": "Bash", "edit": "Edit|Write|MultiEdit|NotebookEdit"}
EVENTS = {"bash": "PreToolUse", "edit": "PreToolUse", "stop": "Stop"}
TIMEOUT = 90  # the worst case of `green-at-head` is three git calls of 20 s
INPUT_CAP = 1 << 20
KIT_MISSING = '{"systemMessage": "sdlc: kit not found, hook skipped"}'


def command(cli, name):
    """The one-line shell command of entry `name`; `cli` is the kit's bin/sdlc path."""
    k = shlex.quote(cli)
    return "if [ -f %s ]; then python3 %s hook %s || :; else echo %s; fi; exit 0 # sdlc-kit:%s" % (
        k, k, name, shlex.quote(KIT_MISSING), name)


def group(cli, name):
    g = {"hooks": [{"type": "command", "timeout": TIMEOUT, "command": command(cli, name)}]}
    if name in MATCHERS:
        g = dict([("matcher", MATCHERS[name])] + list(g.items()))
    return g


def render_entries(cli):
    """The `hooks` value the kit adds: {event: [group, ...]}."""
    out = {}
    for name in NAMES:
        out.setdefault(EVENTS[name], []).append(group(cli, name))
    return out


# ---------------------------------------------------------------- runtime

def deny(reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}})


def note(text):
    return json.dumps({"systemMessage": "sdlc: " + text})


def project_root(start):
    """The nearest folder at or above `start` that holds .sdlc/lock.json, or None."""
    d = os.path.realpath(start)
    while True:
        if os.path.isfile(os.path.join(d, ".sdlc", "lock.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def commands_empty(cfg):
    c = cfg.get("commands")
    return not (isinstance(c, dict) and any(isinstance(v, str) and v.strip() for v in c.values()))


def pushes(cmd):
    """True when the command line runs `git push` or `gh pr create`."""
    words = shlex.split(cmd)
    for i, w in enumerate(words):
        if w == "git" and "push" in words[i + 1:]:
            return True
        if w == "gh" and words[i + 1:i + 3] == ["pr", "create"]:
            return True
    return False


def gate(root, cfg, name, safe_path):
    args = types.SimpleNamespace(name=name, spec=None, repo=None, by=None)
    return sdlc_gate.run(root, cfg, args, safe_path)


def on_bash(root, cfg, data, safe_path):
    cmd = (data.get("tool_input") or {}).get("command")
    if not isinstance(cmd, str) or not pushes(cmd):
        return ""
    code, lines = gate(root, cfg, "green-at-head", safe_path)
    if code == 0:
        return ""
    if code != 1:
        return note("green-at-head could not be computed: %s" % (lines[-1] if lines else "no output"))
    reason = "sdlc: refused: %s. Run sdlc verify in its own tool call, quote its last line, then retry." % (
        "; ".join(lines[:-1]) or "tests are not green at HEAD")
    if commands_empty(cfg):
        reason += " The commands in .sdlc/config.json are empty, so verify cannot pass: set them first."
    return deny(reason)


def run(name, raw, env, read_config, safe_path):
    """Standard output for hook `name` given the host's JSON `raw`. Never raises."""
    try:
        if len(raw) > INPUT_CAP:
            return note("hook input too large, skipped")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return note("hook input is not an object, skipped")
        start = env.get("CLAUDE_PROJECT_DIR") or data.get("cwd")
        root = project_root(start) if isinstance(start, str) and start else None
        if root is None:
            return ""
        cfg = read_config(root)
        if cfg.get("enforce") is not True:
            return ""
        if "repos" in cfg:
            return note("workspaces are not supported yet, hook skipped")
        if name == "bash":
            return on_bash(root, cfg, data, safe_path)
        return ""
    except Exception as e:  # a hook never traps the session
        return note("hook %s skipped: %s: %s" % (name, type(e).__name__, str(e)[:120]))
