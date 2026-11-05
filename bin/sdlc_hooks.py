"""Enforcement hooks for Claude Code (spec 006): the entries rendered into .claude/settings.json and their runtime.

A refusal is never an exit code. The host reads exit code 2 as a refusal, and python exits 2 for a missing script or
an unknown subcommand, so every entry ends with `exit 0` and a refusal is a structured deny message on standard output.
"""
import json
import os
import re
import shlex
import types

import sdlc_gate
import sdlc_verify

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


PUNCT = ";&|()<>\n"
WRAPPERS = {"sudo": {"-u", "-g"}, "env": {"-u"}, "command": set(), "time": set(), "nohup": set(), "exec": set(),
            "timeout": {"-s", "-k"}, "nice": {"-n"}, "ionice": {"-c", "-n"}, "setsid": set(), "stdbuf": set()}
KEYWORDS = {"{", "!", "if", "then", "else", "elif", "do", "while", "until"}
SHELLS = {"sh", "bash", "zsh"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHELL_C = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")
GIT_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def lexer(cmd):
    """shlex configured for command lines: no comments (a `#` would swallow the newline after it), whitespace
    without newline, and runs of `;&|()<>` and newlines as their own tokens."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=PUNCT)
    lex.whitespace_split = True
    lex.whitespace = " \t\r"
    lex.commenters = ""
    return lex


def segments(cmd):
    """Word lists of the commands in a line; a token of only separator characters ends one. ValueError if unbalanced."""
    words = list(lexer(cmd.replace("\\\n", " ")))
    out, cur = [], []
    for w in words:
        if w and all(c in PUNCT for c in w):
            out.append(cur)
            cur = []
        else:
            cur.append(w)
    out.append(cur)
    return [s for s in out if s]


def strip_prefix(words):
    """Drop leading assignments, shell keywords and wrapper commands with their options."""
    while words:
        w = words[0]
        base = os.path.basename(w)
        if ASSIGNMENT.match(w) or w in KEYWORDS:
            words = words[1:]
        elif base in WRAPPERS:
            takes, words = WRAPPERS[base], words[1:]
            while words and words[0].startswith("-"):
                words = words[2:] if words[0] in takes else words[1:]
            if base == "timeout" and words and re.match(r"^[0-9.]+[smhd]?$", words[0]):
                words = words[1:]
        else:
            break
    return words


def segment_pushes(words, depth):
    words = strip_prefix(words)
    if not words:
        return False
    prog, rest = os.path.basename(words[0]), words[1:]
    helped = "-h" in rest or "--help" in rest
    if prog == "git":
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in GIT_WITH_ARG else rest[1:]
        return bool(rest) and rest[0] == "push" and not helped
    if prog == "gh":
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-R", "--repo") else rest[1:]
        return rest[:2] == ["pr", "create"] and not helped
    if prog in SHELLS and depth < 2:
        for i, w in enumerate(rest):
            if SHELL_C.match(w) and i + 1 < len(rest):
                return line_pushes(rest[i + 1], depth + 1)
    return False


def line_pushes(cmd, depth):
    return any(segment_pushes(s, depth) for s in segments(cmd))


def pushes(cmd):
    """True when the command line runs `git push` or `gh pr create`; None when it cannot be tokenised."""
    try:
        return line_pushes(cmd, 1)
    except ValueError:
        return None


def gate(root, cfg, name, safe_path, spec=None):
    args = types.SimpleNamespace(name=name, spec=spec, repo=None, by=None)
    return sdlc_gate.run(root, cfg, args, safe_path)


BRANCH_RE = re.compile(r"^(?:[^/]+/)*?(\d{3})-")
NOT_SOURCE_TOP = (".sdlc", ".claude", ".github", "docs")
NO_FEATURE_IN_FLIGHT = ("implemented", "rejected", "superseded")


def active_folder(root, cfg, safe_path):
    """The spec folder whose number starts the current branch name, or None. Never a guess: exactly one folder
    holding spec.md, else none."""
    status, out = sdlc_verify.git_run(root, "symbolic-ref", "--short", "-q", "HEAD")
    m = BRANCH_RE.match(out.strip()) if status == "ok" else None
    if not m:
        return None
    try:
        base, spec_dir = sdlc_gate.resolve_base(root, cfg, None, safe_path)
        folder = sdlc_gate.resolve_spec(base, spec_dir, m.group(1), safe_path)
    except Exception:
        return None
    return folder if os.path.isfile(os.path.join(folder, "spec.md")) else None


def active_spec(root, cfg, safe_path):
    folder = active_folder(root, cfg, safe_path)
    return os.path.basename(folder) if folder else None


def source_path(root, cfg, path, cwd):
    """True for a source file, False for a document or kit file, None when the path is not checked (outside the
    project root, also through a symlink)."""
    p = path if os.path.isabs(path) else os.path.join(cwd, path)
    rr, rp = os.path.realpath(root), os.path.realpath(p)
    if rp != rr and not rp.startswith(rr + os.sep):
        return None
    rel = os.path.relpath(rp, rr).replace(os.sep, "/")
    sd = cfg.get("spec_dir") if isinstance(cfg.get("spec_dir"), str) else "specs"
    sd = sd.strip("/") or "specs"
    if rel.split("/")[0] in NOT_SOURCE_TOP or rel == sd or rel.startswith(sd + "/") or rel.endswith(".md"):
        return False
    return True


def on_bash(root, cfg, data, safe_path):
    cmd = (data.get("tool_input") or {}).get("command")
    if not isinstance(cmd, str):
        return ""
    found = pushes(cmd)
    if found is None:
        return note("could not tell whether the command pushes (unbalanced quote), allowed")
    if not found:
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


def on_edit(root, cfg, data, safe_path):
    tool_input = data.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(path, str) or not path:
        return note("no file path in the edit, allowed")
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else root
    if not source_path(root, cfg, path, cwd):  # a document, a kit file, or outside the project (None)
        return ""
    folder = active_folder(root, cfg, safe_path)
    if folder is None:
        return ""
    lines, si, _ = sdlc_gate.header_lines(sdlc_gate.read_doc(os.path.join(folder, "spec.md"), "spec.md"))
    word = sdlc_gate.status_word(lines[si]) if si is not None else None
    name = os.path.basename(folder)
    if word in NO_FEATURE_IN_FLIGHT:
        return ""
    if word not in ("draft", "approved"):
        return note("spec %s has status %s, edit allowed" % (name[:3], word or "missing"))
    code, out = gate(root, cfg, "approved", safe_path, name[:3])
    if code == 0:
        return ""
    if code != 1:
        return note("approved could not be computed: %s" % (out[-1] if out else "no output"))
    rel = os.path.relpath(os.path.realpath(path if os.path.isabs(path) else os.path.join(cwd, path)),
                          os.path.realpath(root)).replace(os.sep, "/")
    return deny("sdlc: refused: %s is source and spec %s is not approved: %s. Get the human's approval and run "
                "sdlc gate approve." % (rel, name[:3], "; ".join(out[:-1]) or "gate failed"))


def on_stop(root, cfg, data, safe_path):
    """Warn, never block. Silent unless the gate computed a failure: the hook fires every turn."""
    folder = active_folder(root, cfg, safe_path)
    if folder is None:
        return ""
    name = os.path.basename(folder)
    try:
        code, out = gate(root, cfg, "evidence-for-ticks", safe_path, name[:3])
    except (sdlc_gate.GateError, OSError, UnicodeDecodeError, ValueError):  # no tasks.md yet, or unreadable
        return ""
    if code != 1:
        return ""
    problems = out[:-1]
    shown = "; ".join(problems[:5]) + ("; and %d more" % (len(problems) - 5) if len(problems) > 5 else "")
    return note("spec %s has ticked tasks without evidence: %s" % (name[:3], shown))


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
        if "repos" in cfg:  # the stop hook fires every turn: silent
            return note("workspaces are not supported yet, hook skipped") if name != "stop" else ""
        if name == "bash":
            return on_bash(root, cfg, data, safe_path)
        if name == "edit":
            return on_edit(root, cfg, data, safe_path)
        if name == "stop":
            return on_stop(root, cfg, data, safe_path)
        return ""
    except Exception as e:  # a hook never traps the session
        return note("hook %s skipped: %s: %s" % (name, type(e).__name__, str(e)[:120]))
