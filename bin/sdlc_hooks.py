"""Enforcement hooks for Claude Code (spec 006): the entries rendered into .claude/settings.json and their runtime.

A refusal is never an exit code. The host reads exit code 2 as a refusal, and python exits 2 for a missing script or
an unknown subcommand, so every entry ends with `exit 0` and a refusal is a structured deny message on standard output.
"""
import copy
import hashlib
import json
import os
import re
import shlex
import stat
import tempfile
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


# ---------------------------------------------------------------- settings file

MARKER = re.compile(r"# sdlc-kit:(bash|edit|stop)$")


class SettingsError(Exception):
    """The settings file has a shape the kit will not write into."""


def group_name(group):
    """`bash`, `edit` or `stop` when `group` is one of the kit's entries (one hook, marker last), else None."""
    hooks = group.get("hooks") if isinstance(group, dict) else None
    if not isinstance(hooks, list) or len(hooks) != 1 or not isinstance(hooks[0], dict):
        return None
    cmd = hooks[0].get("command")
    m = MARKER.search(cmd.rstrip()) if isinstance(cmd, str) else None
    return m.group(1) if m else None


def group_hash(group):
    text = json.dumps(group, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_shape(settings):
    if not isinstance(settings, dict):
        raise SettingsError("the top level is not an object")
    if "hooks" not in settings:
        return
    hooks = settings["hooks"]
    if not isinstance(hooks, dict):
        raise SettingsError("hooks is not an object")
    for event, groups in hooks.items():
        if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
            raise SettingsError("hooks.%s is not a list of objects" % event)


def merge(settings, entries, lock, force):
    """(new settings, report lines, skipped count, new lock entry). `lock` is the recorded entry or None.
    Adds the kit's groups, replaces one that is unchanged since the kit wrote it (a moved kit), leaves a hand-edited
    one alone unless `force`. Never modifies `settings`."""
    check_shape(settings)
    new = copy.deepcopy(settings)
    old = (lock or {}).get("hooks", {})
    hooks = new.setdefault("hooks", {})
    lines, skipped, locked = [], 0, {}
    for event, groups in entries.items():
        cur = hooks.setdefault(event, [])
        for g in groups:
            name, want = group_name(g), group_hash(g)
            idx = next((i for i, x in enumerate(cur) if group_name(x) == name), None)
            if idx is None:
                cur.append(copy.deepcopy(g))
                locked[name] = want
                continue
            have = group_hash(cur[idx])
            if have == want:
                locked[name] = have
            elif old.get(name) == have or force:
                cur[idx] = copy.deepcopy(g)
                locked[name] = want
            else:
                lines.append("SKIP .claude/settings.json (kit hook %s modified locally)" % name)
                skipped += 1
                if name in old:
                    locked[name] = old[name]
    return new, lines, skipped, {"hooks": locked, "created": bool((lock or {}).get("created"))}


def remove(settings, lock):
    """(new settings, report lines, None, settings is now empty). Removes only the groups the lock recorded and that
    are unchanged; containers the removal emptied go too. A changed group stays, reported as KEPT, and is the
    project's from then on, so no lock entry remains (the third value, kept for the callers' shape)."""
    check_shape(settings)
    new = copy.deepcopy(settings)
    known = (lock or {}).get("hooks", {})
    hooks = new.get("hooks")
    lines, dropped_any = [], False
    if isinstance(hooks, dict):
        for event in list(hooks):
            keep, dropped = [], False
            for g in hooks[event]:
                name = group_name(g)
                if name in known and group_hash(g) == known[name]:
                    dropped = dropped_any = True
                    continue
                if name in known:
                    lines.append("KEPT .claude/settings.json (kit hook %s modified locally, no longer managed)" % name)
                keep.append(g)
            if keep or not dropped:
                hooks[event] = keep
            else:
                del hooks[event]
        if dropped_any and not hooks:
            del new["hooks"]
    return new, lines, None, new == {}  # a kept entry is the project's now: the lock lets go of it


def load(text):
    try:
        data = json.loads(text)
    except ValueError as e:
        raise SettingsError("not valid JSON: %s" % str(e)[:80])
    if not isinstance(data, dict):
        raise SettingsError("the top level is not an object")
    return data


def dump(settings, original):
    """JSON text keeping the indentation of `original` (tab, or 1 to 8 spaces; else 2) and ending in a newline."""
    m = re.search(r"^([ \t]+)\S", original, re.M)
    indent = 2
    if m:
        indent = "\t" if m.group(1).startswith("\t") else (len(m.group(1)) if len(m.group(1)) <= 8 else 2)
    return json.dumps(settings, indent=indent, ensure_ascii=False) + "\n"


def write_atomic(path, data, replace=os.replace):
    """Write `data` to `path` through a temporary file beside it, keeping an existing file's mode. A failure leaves
    the old file and no temporary file."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.exists(path) else 0o644
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".sdlc-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode)
        replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def settings_plan(text, want, cli, lock, force):
    """What install and update do to the settings file. `text` is its content or None, `want` whether the hooks
    should be there, `lock` the recorded entry. Returns (action, new text, new lock entry, report lines, skipped);
    action is None, `write` or `delete`."""
    try:
        if text is None:
            if not want:
                return None, None, None, [], 0
            new, lines, skipped, entry = merge({}, render_entries(cli), None, force)
            entry["created"] = True
            return "write", dump(new, ""), entry, lines, skipped
        settings = load(text)
        if want:
            new, lines, skipped, entry = merge(settings, render_entries(cli), lock, force)
            return ("write" if new != settings else None), dump(new, text), entry, lines, skipped
        if not lock:
            return None, None, None, [], 0
        new, lines, rest, empty = remove(settings, lock)
        if empty and rest is None and lock.get("created"):
            return "delete", None, None, lines, 0
        return ("write" if new != settings else None), dump(new, text), rest, lines, 0
    except SettingsError as e:
        return None, None, lock, ["SKIP .claude/settings.json (%s)" % e], 1


def drift(text, lock):
    """`check` lines for the kit's recorded entries: `text` is the settings file's content or None, `lock` the
    recorded entry. An entry is `edited` when its hash differs from the lock's, `missing` when it is not there."""
    names = sorted((lock or {}).get("hooks", {}))
    if not names:
        return []
    if text is None:
        return ["DRIFT .claude/settings.json: kit hook %s missing" % n for n in names]
    try:
        settings = load(text)
        check_shape(settings)
    except SettingsError as e:
        return ["DRIFT .claude/settings.json: %s" % e]
    found = {}
    for groups in (settings.get("hooks") or {}).values():
        for g in groups:
            found.setdefault(group_name(g), g)
    lines = []
    for n in names:
        if n not in found:
            lines.append("DRIFT .claude/settings.json: kit hook %s missing" % n)
        elif group_hash(found[n]) != lock["hooks"][n]:
            lines.append("DRIFT .claude/settings.json: kit hook %s edited" % n)
    return lines


# ---------------------------------------------------------------- runtime

def decision(kind, reason):
    """A PreToolUse answer: `allow` (the host asks nothing more) or `deny` (the host refuses and shows the reason)."""
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": kind,
                                              "permissionDecisionReason": reason}})


def deny(reason):
    return decision("deny", reason)


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
    sd = os.path.normpath(sd).replace(os.sep, "/").strip("/") or "specs"
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


# The roles whose source says `checks: true` (spec 010): read-only reviewers that may run the project's check commands.
CHECK_ROLES = ("sdlc-reviewer", "sdlc-security-reviewer")


def check_role(data):
    """The reviewing role making this Bash call (the host sets `agent_type`), else None: the main session."""
    role = data.get("agent_type")
    return role if isinstance(role, str) and role in CHECK_ROLES else None


def check_commands(cfg):
    """{name: command string} of the usable configured check commands: the names `sdlc verify` runs."""
    commands = cfg.get("commands")
    if not isinstance(commands, dict):
        return {}
    return {k: commands[k].strip(" \t\r\n") for k in sdlc_verify.ORDER
            if isinstance(commands.get(k), str) and commands[k].strip(" \t\r\n")}


ROLE_NAMED = re.compile(r'"agent_type"\s*:\s*"(?:%s)"' % "|".join(re.escape(r) for r in CHECK_ROLES))


def refuse_role(role, why):
    return deny("sdlc: refused: the %s may not run commands%s" % (role.replace("sdlc-", "", 1), why))


def unreadable(name, raw, text):
    """The answer to input the hook cannot use: a note for the main session, a deny when the raw text names a reviewing
    role as the caller (that role's shell is limited only by this hook, so it fails closed)."""
    if name == "bash" and ROLE_NAMED.search(raw):
        return refuse_role(ROLE_NAMED.search(raw).group(0).split('"')[-2], ": the hook's input could not be read")
    return note(text)


def role_gate(root, data, role, read_config, safe_path):
    """The reviewing roles' Bash calls, judged before the gates of run() that return early, and failing closed."""
    unread = ": the project's config or lock could not be read"
    try:
        cfg = read_config(root)  # a non-object config raises on `.get` below, and fails closed too
        enforced = cfg.get("enforce") is True
        if not enforced:
            return refuse_role(role, " while enforce is off; run sdlc update")
        if "repos" in cfg:
            return refuse_role(role, " in a workspace config; run sdlc update")
        tool_input = data.get("tool_input")
        if isinstance(tool_input, dict) and tool_input.get("dangerouslyDisableSandbox"):
            return refuse_role(role, " outside the sandbox")
        return role_bash(root, cfg, data, role, safe_path)
    except Exception:
        return refuse_role(role, unread)


def role_bash(root, cfg, data, role, safe_path):
    """A reviewing role's Bash call: only an exact configured check command is allowed, and said so explicitly,
    because a silent hook leaves the host's permission rules in charge and a test command is not read-only."""
    cmd = (data.get("tool_input") or {}).get("command")
    allowed = check_commands(cfg)
    if isinstance(cmd, str) and cmd.strip(" \t\r\n") in allowed.values():
        out = on_bash(root, cfg, data, safe_path)
        if not out:
            return decision("allow", "sdlc: a configured check command")
        message = json.loads(out).get("systemMessage")
        if message:  # a note means the push check could not decide: the main session is let through, a role is not
            return refuse_role(role, ": " + message.replace("sdlc: ", "", 1).replace(", allowed", ""))
        return out
    return deny("sdlc: refused: the %s may only run the project's configured check commands (%s)" % (
        role.replace("sdlc-", "", 1), ", ".join(sorted(allowed)) or "none is configured"))


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
            return unreadable(name, raw, "hook input too large, skipped")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return unreadable(name, raw, "hook input is not an object, skipped")
        start = env.get("CLAUDE_PROJECT_DIR") or data.get("cwd")
        root = project_root(start) if isinstance(start, str) and start else None
        role = check_role(data) if name == "bash" else None
        if root is None:
            return refuse_role(role, ": the project's config or lock could not be read") if role else ""
        if role:  # before the gates below, which return early, so a role file's Bash is never left unchecked
            return role_gate(root, data, role, read_config, safe_path)
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
        return unreadable(name, raw, "hook %s skipped: %s: %s" % (name, type(e).__name__, str(e)[:120]))
