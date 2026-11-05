"""sdlc budget: compare the size of the change and a unit's recorded turns with `budget.*` in .sdlc/config.json
(spec 008). Read-only: it runs git and reads files, and writes nothing.

Lines are added plus deleted lines between the merge-base of the base branch and the working tree, committed or not,
untracked files included; the spec folder, `.sdlc/` and `.claude/` are artifacts and are not counted. Turns come from
the unit's `- usage <unit>:` line in the spec's tasks.md, so they exist only for a finished unit.
"""
import os
import re

import sdlc_gate
import sdlc_verify

LEVELS = ("OK", "ABOVE TARGET", "REASSESS")
UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
KIT_DIRS = (".sdlc", ".claude")
UNTRACKED_CAP = 2 * 1024 * 1024  # bytes read per untracked file
BINARY_PROBE = 8000


class BudgetError(Exception):
    """A usage, config or git problem: exit 2."""


def limits(cfg, keys):
    budget = cfg.get("budget") if isinstance(cfg, dict) else None
    if not isinstance(budget, dict):
        raise BudgetError("budget is missing from config.json (an object with %s)" % ", ".join(keys))
    out = {}
    for k in keys:
        v = budget.get(k)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise BudgetError("budget.%s must be a non-negative integer" % k)
        out[k] = v
    if out[keys[0]] > out[keys[1]]:
        raise BudgetError("budget.%s is above budget.%s" % (keys[0], keys[1]))
    return out


def level(value, target, limit, at_limit):
    """0 ok, 1 above target, 2 reassess; `at_limit` says whether reaching the limit already counts."""
    if value > limit or (at_limit and value >= limit):
        return 2
    return 1 if value > target else 0


def git(workdir, *args):
    status, out = sdlc_verify.git_run(workdir, *args)
    return status == "ok", out


def default_base(workdir):
    ok, out = git(workdir, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if ok and out.strip() and git(workdir, "rev-parse", "--verify", "-q", out.strip() + "^{commit}")[0]:
        return out.strip()  # a dangling origin/HEAD falls through to main and master
    for name in ("main", "master"):
        if git(workdir, "rev-parse", "--verify", "-q", name + "^{commit}")[0]:
            return name
    raise BudgetError("no default branch found (origin/HEAD, main or master); pass --base <ref>")


def count_untracked(path):
    """Lines of an untracked regular file; a binary file or a symlink counts 0."""
    if os.path.islink(path) or not os.path.isfile(path):
        return 0
    with open(path, "rb") as f:
        data = f.read(UNTRACKED_CAP)
    if b"\0" in data[:BINARY_PROBE]:
        return 0
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def changed_lines(workdir, spec_dir, base):
    if not git(workdir, "rev-parse", "--verify", "-q", "HEAD^{commit}")[0]:
        raise BudgetError("not a git repository, or it has no commit")
    if base is None:
        base = default_base(workdir)
    elif base.startswith("-"):
        raise BudgetError("--base must be a branch, tag or commit, not an option")
    if not git(workdir, "rev-parse", "--verify", "-q", base + "^{commit}")[0]:
        raise BudgetError("unknown base: %s" % base)
    ok, out = git(workdir, "merge-base", base, "HEAD")
    if not ok or not out.strip():
        raise BudgetError("no common history between %s and HEAD" % base)
    skip = [":(exclude,literal)" + p for p in (spec_dir,) + KIT_DIRS]
    ok, out = git(workdir, "diff", "--numstat", "--no-renames", out.strip(), "--", ".", *skip)
    if not ok:
        raise BudgetError("git diff failed")
    total = 0
    for row in out.splitlines():
        added, deleted = row.split("\t", 2)[:2]
        total += (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0)
    ok, out = git(workdir, "ls-files", "--others", "--exclude-standard", "-z", "--", ".", *skip)
    if not ok:
        raise BudgetError("git ls-files failed")
    for rel in filter(None, out.split("\0")):
        total += count_untracked(os.path.join(workdir, rel))
    return total


def unit_turns(base_dir, spec_dir, spec, unit, safe_path):
    """Turns of the unit's last usage line, or None when there is no line or it has no turn count."""
    folder = sdlc_gate.resolve_spec(base_dir, spec_dir, spec, safe_path)
    text = sdlc_gate.read_doc(os.path.join(folder, "tasks.md"), "tasks.md")
    last = None
    for line in text.split("\n"):
        if line.startswith("- usage %s: " % unit):
            last = line
    if last is None:
        return None, "no usage line for %s" % unit
    m = re.search(r"(\d[\d,]*) turns\b", last)
    if not m:
        return None, "the usage line for %s has no turn count" % unit
    return int(m.group(1).replace(",", "")), ""


def run(root, cfg, args, safe_path):
    """(exit code, lines to print). `args` has repo, base, unit and spec."""
    if (args.unit is None) != (args.spec is None):
        raise BudgetError("--unit and --spec go together")
    if args.unit is not None and not UNIT_RE.match(args.unit):
        raise BudgetError("--unit must be a task or finding id such as T001 or review1-F3")
    try:
        base_dir, spec_dir = sdlc_gate.resolve_base(root, cfg, args.repo, safe_path)
    except sdlc_gate.GateError as e:
        raise BudgetError(str(e))
    keys = ("target_lines", "reassess_lines") + (("target_turns", "max_turns") if args.unit else ())
    lim = limits(cfg, keys[:2])
    if args.unit:
        lim.update(limits(cfg, keys[2:]))
    lines_n = changed_lines(base_dir, spec_dir, args.base)
    worst = level(lines_n, lim["target_lines"], lim["reassess_lines"], False)
    out = ["budget lines: %d (target %d, reassess %d): %s" % (
        lines_n, lim["target_lines"], lim["reassess_lines"], LEVELS[worst].lower())]
    if args.unit:
        try:
            turns, why = unit_turns(base_dir, spec_dir, args.spec, args.unit, safe_path)
        except sdlc_gate.GateError as e:
            raise BudgetError(str(e))
        if turns is None:
            out.append("budget turns %s: unknown (%s)" % (args.unit, why))
        else:
            t = level(turns, lim["target_turns"], lim["max_turns"], True)
            worst = max(worst, t)
            out.append("budget turns %s: %d (target %d, max %d): %s" % (
                args.unit, turns, lim["target_turns"], lim["max_turns"], LEVELS[t].lower()))
    out.append("budget: %s" % LEVELS[worst])
    return (1 if worst == 2 else 0), out
