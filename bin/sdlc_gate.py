"""sdlc gate: mechanical readiness checks (approved, approve, green-at-head, evidence-for-ticks).

Imported by `bin/sdlc` inside `cmd_gate` only. Contract: specs/005-gate-command/contracts/gate.md.
"""
import datetime
import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata

import sdlc_verify

GATES = ("approved", "approve", "green-at-head", "evidence-for-ticks")
DOC_MAX = 2 * 1024 * 1024
APPROVED_RE = re.compile(
    r"^Approved: (?P<by>[^,\n]+), (?P<date>\d{4}-\d{2}-\d{2}), digest sha256:(?P<hex>[0-9a-f]{64}) "
    r"\(spec (?P<spec>[0-9a-f]{12}), plan (?P<plan>[0-9a-f]{12}), tasks (?P<tasks>[0-9a-f]{12}), "
    r"contracts (?P<contracts>[0-9a-f]{12})\)(?:\s*<!--.*-->)?\s*$")
STATUS_RE = re.compile(r"^Status:[ \t]*(\S+)")
PARTS = ("spec", "plan", "tasks", "contracts")


class GateError(Exception):
    """A usage, config or document problem: exit 2."""


def read_doc(path, what):
    """Text of a document: a regular file, at most 2 MiB, strict UTF-8."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > DOC_MAX:
            raise GateError("%s is missing, not a regular file or too large" % what)
        with open(path, "rb") as f:
            return f.read().decode("utf-8")
    except UnicodeDecodeError:
        raise GateError("%s is not valid UTF-8" % what)
    except OSError as e:
        raise GateError("%s is unreadable: %s" % (what, e.strerror or e))


def unify(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def header_end(lines):
    for i, l in enumerate(lines):
        if l.startswith("## "):
            return i
    return len(lines)


def first_index(lines, prefix, end):
    for i in range(end):
        if lines[i].startswith(prefix):
            return i
    return None


def normalise(kind, raw):
    lines = unify(raw).split("\n")
    if kind == "tasks":
        for i, l in enumerate(lines):
            if l.rstrip() == "## Progress log":
                lines = lines[:i]
                break
    if kind == "spec":
        end = header_end(lines)
        si, ai = first_index(lines, "Status:", end), first_index(lines, "Approved:", end)
        if si is not None:
            lines[si] = re.sub(r"^Status:[ \t]*[A-Za-z]+", "Status:", lines[si], count=1)  # the word only; a comment stays covered
        if ai is not None:
            comment = re.search(r"<!--.*-->\s*$", lines[ai])
            lines[ai] = "Approved:" + (" " + comment.group(0).rstrip() if comment else "")
    if kind in ("plan", "tasks"):
        prefix = "Spec:" if kind == "plan" else "Inputs:"
        for i, l in enumerate(lines):
            if l.startswith(prefix):
                lines[i] = re.sub(r"· Status: [A-Za-z]+", "· Status:", l, count=1)
                break
    if kind == "tasks":
        lines = [re.sub(r"^([ \t]*[-*] )\[[xX]\]", r"\1[ ]", l) for l in lines]
    return "\n".join(lines)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def contracts_text(folder):
    names = []
    cdir = os.path.join(folder, "contracts")
    if os.path.isdir(cdir):
        names += ["contracts/" + n for n in os.listdir(cdir) if n.endswith(".md")]
    if os.path.isfile(os.path.join(folder, "data-model.md")):
        names.append("data-model.md")
    out = []
    for n in sorted(names, key=lambda s: s.encode("utf-8")):
        out.append("== %s ==\n%s" % (n, unify(read_doc(os.path.join(folder, n), n))))
    return "".join(out)


def digest(folder):
    """{'spec','plan','tasks','contracts': full hex, 'combined': hex}."""
    h = {
        "spec": sha(normalise("spec", read_doc(os.path.join(folder, "spec.md"), "spec.md"))),
        "plan": sha(normalise("plan", read_doc(os.path.join(folder, "plan.md"), "plan.md"))),
        "tasks": sha(normalise("tasks", read_doc(os.path.join(folder, "tasks.md"), "tasks.md"))),
        "contracts": sha(contracts_text(folder)),
    }
    h["combined"] = sha("spec.md:%s\nplan.md:%s\ntasks.md:%s\ncontracts:%s\n"
                        % (h["spec"], h["plan"], h["tasks"], h["contracts"]))
    return h


def header_lines(raw):
    """(lines, status index or None, approved index or None) for the first such lines before the first `## `."""
    lines = raw.split("\n")
    end = header_end(lines)
    return lines, first_index(lines, "Status:", end), first_index(lines, "Approved:", end)


def status_word(line):
    m = STATUS_RE.match(line) if line is not None else None
    return m.group(1) if m else None


def valid_by(by):
    if by is None or by != by.strip() or not by or len(by) > 80:
        return False
    if "," in by or "<!--" in by or "-->" in by:
        return False
    return not any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") or (c.isspace() and c != " ") for c in by)


def write_bytes_atomic(path, data, replace=os.replace):
    st = os.stat(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".gate-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, stat.S_IMODE(st.st_mode))
        replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def approve(folder, by, today=None, replace=os.replace):
    """Record the approval on spec.md. Returns the PASS line."""
    spec = os.path.join(folder, "spec.md")
    if os.path.islink(spec):
        raise GateError("spec.md is a symlink; refusing to rewrite it")
    if not valid_by(by):
        raise GateError("--by needs a name of at most 80 characters with no comma, control character or comment marker")
    raw = read_doc(spec, "spec.md")
    lines, si, ai = header_lines(raw)
    if si is None or ai is None:
        raise GateError("spec.md needs a Status: line and an Approved: line before its first '## ' heading")
    word = status_word(lines[si])
    if word not in ("draft", "approved"):
        raise GateError("spec.md status is %s; only draft or approved can be approved" % (word or "empty"))
    for other, name in (("plan.md", "plan.md"), ("tasks.md", "tasks.md")):
        read_doc(os.path.join(folder, other), name)
    h = digest(folder)
    date = (today or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))
    cr = "\r" if lines[ai].endswith("\r") else ""
    comment = re.search(r"<!--.*-->\s*$", lines[ai])
    new = "Approved: %s, %s, digest sha256:%s (spec %s, plan %s, tasks %s, contracts %s)" % (
        by, date, h["combined"], h["spec"][:12], h["plan"][:12], h["tasks"][:12], h["contracts"][:12])
    if comment:
        new += " " + comment.group(0).rstrip()
    lines[ai] = new + cr
    lines[si] = re.sub(r"^(Status:[ \t]*)(\S+)", r"\1approved", lines[si], count=1)
    write_bytes_atomic(spec, "\n".join(lines).encode("utf-8"), replace)
    return "gate approve: PASS (approved by %s on %s, digest sha256:%s...)" % (by, date, h["combined"][:12])


def check_approved(folder):
    """List of problems (empty = pass). Raises GateError for unreadable documents."""
    raw = read_doc(os.path.join(folder, "spec.md"), "spec.md")
    lines, si, ai = header_lines(raw)
    word = status_word(lines[si]) if si is not None else None
    if word is None:
        return ["status is missing, not approved"]
    if word not in ("approved", "implemented"):
        return ["status is %s, not approved" % word]
    m = APPROVED_RE.match(lines[ai].rstrip("\r")) if ai is not None else None
    if not m:
        return ["no approval digest on the Approved line"]
    h = digest(folder)
    problems = ["%s changed since approval" % p for p in PARTS if h[p][:12] != m.group(p)]
    if not problems and h["combined"] != m.group("hex"):
        problems.append("approval digest does not match the documents")
    return problems


def resolve_base(target, cfg, repo, safe_path):
    """(base folder, spec_dir name)."""
    if not isinstance(cfg, dict):
        raise GateError("config.json must be a JSON object")
    repos = cfg.get("repos")
    if repos is not None and not isinstance(repos, dict):
        raise GateError("repos must be an object")
    node, base = cfg, target
    if repo is not None:
        if repos is None or repo not in repos:
            raise GateError("unknown repo: %s" % repo)
        node = repos[repo]
        if not isinstance(node, dict) or not isinstance(node.get("path"), str):
            raise GateError("repos.%s needs an object with a string path" % repo)
        try:
            base = safe_path(target, node["path"])
        except Exception as e:
            raise GateError(str(e))
        if not os.path.isdir(base):
            raise GateError("repos.%s.path is not a folder" % repo)
    sd = node.get("spec_dir") if repo is not None and "spec_dir" in node else cfg.get("spec_dir", "specs")
    if not isinstance(sd, str):
        raise GateError("spec_dir must be a string")
    return base, sd.strip("/") or "specs"


def resolve_spec(base, spec_dir, spec, safe_path):
    root = os.path.join(base, *spec_dir.split("/"))
    if re.fullmatch(r"\d{3}", spec or ""):
        found = sorted(n for n in (os.listdir(root) if os.path.isdir(root) else []) if n.startswith(spec + "-")
                       and os.path.isdir(os.path.join(root, n)))
        if len(found) != 1:
            raise GateError("--spec %s matches %d folders under %s" % (spec, len(found), spec_dir))
        path = os.path.join(root, found[0])
        if not os.path.realpath(path).startswith(os.path.realpath(root) + os.sep):
            raise GateError("--spec %s leaves %s (a symlinked folder)" % (spec, spec_dir))
        return path
    rel = (spec or "").rstrip("/")
    try:
        path = safe_path(base, rel)
    except Exception as e:
        raise GateError(str(e))
    real_root = os.path.realpath(root)
    if not os.path.realpath(path).startswith(real_root + os.sep):
        raise GateError("--spec must name a folder inside %s" % spec_dir)
    if not os.path.isfile(os.path.join(path, "spec.md")):
        raise GateError("no spec.md in %s" % spec)
    return path


RECORD_MAX = 1024 * 1024
GIT_REASONS = {"nogit": "git not found", "timeout": "git timed out"}


def read_record(base):
    """(record, None) or (None, reason). The record is not a document: problems are exit 1, never 2."""
    path = os.path.join(base, sdlc_verify.RECORD)
    if not os.path.lexists(path):
        return None, "no record"
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > RECORD_MAX:
            return None, "unreadable record"
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8")), None
    except (OSError, ValueError, RecursionError):
        return None, "unreadable record"


def check_green(base):
    """List of problems (empty = pass): the record is green at HEAD and the tree is still clean."""
    record, err = read_record(base)
    if err:
        return [err]
    status, out = sdlc_verify.git_run(base, "rev-parse", "HEAD")
    if status != "ok" or not out.strip():
        return [GIT_REASONS.get(status, "HEAD unresolved (no repository or no commit)")]
    reason = sdlc_verify.green_reason(record, out.strip())
    if reason:
        return [reason]
    status, out = sdlc_verify.git_run(base, "status", "--porcelain", "--untracked-files=normal", "--", ".",
                                      sdlc_verify.EXCLUDE)
    if status != "ok":
        return [GIT_REASONS.get(status, "git status failed")]
    return ["tree changed since the record"] if out.strip() else []


TICK_RE = re.compile(r"^[ \t]*[-*] \[[xX]\](?P<rest>.*)$")
ID_RE = re.compile(r"^[ \t]*(?P<id>[A-Z]+\d+[a-z]?)(?![0-9A-Za-z_])")
HASH_RE = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,40}(?![0-9A-Za-z])")
RANGE = re.compile(r"(?<![0-9A-Za-z_])([A-Z]+)(\d+)[ \t]*[\u2013\u2014-][ \t]*\1(\d+)(?![0-9A-Za-z_])")


def ranges(line):
    """(prefix, lo, hi) for `T001-T004`: the prefix is repeated; blanks around the dash are allowed."""
    return RANGE.findall(line)


COMMIT_LINE = re.compile(r"^[0-9a-f]{40} commit \d+$")
TOKEN_CAP = 2000


def names_id(line, tid):
    if re.search(r"(?<![0-9A-Za-z_])%s(?![0-9A-Za-z_])" % re.escape(tid), line):
        return True
    m = re.fullmatch(r"([A-Z]+)(\d+)", tid)
    if not m:
        return False
    for prefix, lo, hi in ranges(line):
        if prefix == m.group(1) and int(lo) <= int(hi) and int(lo) <= int(m.group(2)) <= int(hi):
            return True
    return False


def check_ticks(folder, base):
    """List of problems (empty = pass)."""
    lines = unify(read_doc(os.path.join(folder, "tasks.md"), "tasks.md")).split("\n")
    ticks, problems = [], []
    for n, l in enumerate(lines, 1):
        m = TICK_RE.match(l)
        if not m:
            continue
        im = ID_RE.match(m.group("rest"))
        if im:
            ticks.append((n, im.group("id")))
        else:
            problems.append((n, "line %d: checked box without an id" % n))
    log = []
    for i, l in enumerate(lines):
        if l.rstrip() == "## Progress log":
            for l2 in lines[i + 1:]:
                if l2.startswith("## "):
                    break
                log.append(l2)
            break
    tokens = sorted({h for l in log for h in HASH_RE.findall(l)})
    if ticks and len(tokens) > TOKEN_CAP:
        return ["too many revisions to check (%d distinct, at most %d)" % (len(tokens), TOKEN_CAP)]
    commits, shallow = set(), ""
    if ticks and tokens:
        status, out = sdlc_verify.git_run(base, "cat-file", "--batch-check", input="".join(t + "^{commit}\n" for t in tokens))
        if status != "ok":
            return [GIT_REASONS.get(status, "git failed")]
        answers = out.split("\n")
        commits = {tok for tok, a in zip(tokens, answers) if COMMIT_LINE.match(a)}
        if len(commits) < len(tokens):
            status, out = sdlc_verify.git_run(base, "rev-parse", "--is-shallow-repository")
            if status == "ok" and out.strip() == "true":
                shallow = " (shallow repository: history may be missing)"
    for n, tid in ticks:
        if not any(names_id(l, tid) and any(h in commits for h in HASH_RE.findall(l)) for l in log):
            problems.append((n, "%s: no progress-log line with this task and an existing commit%s" % (tid, shallow)))
    return [text for _, text in sorted(problems)]


def verdict(name, problems):
    lines = list(problems)
    lines.append("gate %s: %s" % (name, "PASS" if not problems else "FAIL (%d problems)" % len(problems)))
    return (0 if not problems else 1), lines


def run(target, cfg, args, safe_path):
    """(exit code, lines). `args` has name, spec, repo, by."""
    name = args.name
    if name not in GATES:
        raise GateError("unknown gate %r (one of: %s)" % (name, ", ".join(GATES)))
    if args.by is not None and name != "approve":
        raise GateError("--by is only for approve")
    if name == "approve" and args.by is None:
        raise GateError("approve needs --by <name>")
    if name == "green-at-head" and args.spec is not None:
        raise GateError("green-at-head takes no --spec")
    if name != "green-at-head" and args.spec is None:
        raise GateError("%s needs --spec <NNN or folder>" % name)
    base, spec_dir = resolve_base(target, cfg, args.repo, safe_path)
    if name == "approve":
        return 0, [approve(resolve_spec(base, spec_dir, args.spec, safe_path), args.by)]
    if name == "approved":
        return verdict(name, check_approved(resolve_spec(base, spec_dir, args.spec, safe_path)))
    if name == "green-at-head":
        return verdict(name, check_green(base))
    if name == "evidence-for-ticks":
        return verdict(name, check_ticks(resolve_spec(base, spec_dir, args.spec, safe_path), base))
    raise GateError("gate %s is not implemented yet" % name)
