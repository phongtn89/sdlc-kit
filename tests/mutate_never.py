#!/usr/bin/env python3
"""Mutation check for the "must never happen" tests (spec 009).

Copies the kit to a temporary folder, removes one enforcement mechanism at a time (an exact text replacement) and runs
`tests.test_never` in the copy; every mutation must make it fail. The real kit is never written. Takes about a minute
and a half, so it is not part of the unit suite: run it by hand before a release and quote the result.

Exit 0: every mutation was caught. 1: at least one survived. 2: the script itself is out of date (the baseline fails, or
a text to replace is not found exactly once).
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".worktrees", ".sdlc", "specs", "evals", "*.pyc")
TEST_COMMAND = [sys.executable, "-B", "-m", "unittest", "tests.test_never"]

HOOKS = "bin/sdlc_hooks.py"
GATE = "bin/sdlc_gate.py"
VERIFY = "bin/sdlc_verify.py"
CLI = "bin/sdlc"

# (label, [(file, text that occurs exactly once, replacement), ...])
MUTATIONS = [
    ("push on red: the bash hook never refuses", [(HOOKS, "    return deny(reason)\n", '    return ""\n')]),
    ("push on red: the bash hook sees no push", [(HOOKS, "    found = pushes(cmd)", "    found = False")]),
    ("push on red: a failed command in the record passes",
     [(GATE, "    reason = sdlc_verify.green_reason(record, out.strip())", "    reason = None")]),
    ("push on red: a record for another revision is accepted", [(VERIFY, "        if rev != head:", "        if False:")]),
    ("push on red: a dirty record is accepted", [(VERIFY, "        if dirty:\n", "        if False:\n")]),
    ("push on red: the clean-tree check is dropped",
     [(GATE, '    return ["tree changed since the record"] if out.strip() else []', "    return []")]),
    ("opt-in: enforce is not read at run time", [(HOOKS, 'if cfg.get("enforce") is not True:', "if False:")]),
    ("opt-in: any truthy enforce counts", [(HOOKS, 'if cfg.get("enforce") is not True:', 'if not cfg.get("enforce"):')]),
    ("hooks: one of the three entries is not rendered",
     [(HOOKS, "    for name in NAMES:\n        out.setdefault", "    for name in NAMES[:2]:\n        out.setdefault")]),
    ("source edit: the edit hook never refuses",
     [(HOOKS, '    return deny("sdlc: refused: %s is source', '    return "" and deny("sdlc: refused: %s is source')]),
    ("source edit: every file counts as a document", [(HOOKS, "if not source_path(root, cfg, path, cwd):", "if True:")]),
    ("source edit: no active spec is ever found",
     [(HOOKS, 'm = BRANCH_RE.match(out.strip()) if status == "ok" else None', "m = None")]),
    ("source edit: a draft status counts as approved", [(GATE, "    if word not in (\"approved\", \"implemented\"):", "    if False:")]),
    ("source edit: the digest comparison is dropped",
     [(GATE, '    problems = ["%s changed since approval" % p for p in PARTS if h[p][:12] != m.group(p)]', "    problems = []"),
      (GATE, '    if not problems and h["combined"] != m.group("hex"):', "    if False:")]),
    ("tick: any tick passes the gate",
     [(GATE, "        if not any(names_id(l, tid) and any(h in commits for h in HASH_RE.findall(l)) for l in log):",
       "        if False:")]),
    ("tick: a made-up commit counts as evidence", [(GATE, "commits = {tok for tok, a in zip(tokens, answers) if COMMIT_LINE.match(a)}",
                                                    "commits = set(tokens)")]),
    ("tick: the stop hook never warns", [(HOOKS, '    if code != 1:\n        return ""\n    problems = out[:-1]',
                                          '    if True:\n        return ""\n    problems = out[:-1]')]),
    ("tick: the stop hook refuses", [(HOOKS, '    return note("spec %s has ticked tasks', '    return deny("spec %s has ticked tasks')]),
    ("reviewer: the Claude role keeps every tool", [(CLI, '        if ro:\n            lines.append("tools: Read, Grep, Glob")',
                                                      '        if False:\n            lines.append("tools: Read, Grep, Glob")')]),
    ("reviewer: the Copilot role keeps every tool",
     [(CLI, "lines.append(\"tools: ['read', 'search']\" if ro else", "lines.append(\"tools: ['read', 'search']\" if False else")]),
    ("reviewer: the read-only flag is never read", [(CLI, '    ro = fm.get("access") == "read-only"', "    ro = False")]),
]


class MutationError(Exception):
    """The script is out of date: a text to replace is not in the file exactly once."""


def apply(work, edits):
    for rel, old, new in edits:
        path = os.path.join(work, *rel.split("/"))
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if text.count(old) != 1:
            raise MutationError("%s: expected exactly one occurrence, found %d of: %s" % (rel, text.count(old), old.strip()[:70]))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new))


def tests_pass(work, command):
    p = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=600)
    return p.returncode == 0


def run(kit, mutations, command=TEST_COMMAND, say=print):
    """(survivors, results): the labels of mutations the tests did not catch. Raises MutationError."""
    survivors = []
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "base")
        shutil.copytree(kit, base, ignore=IGNORE)
        if not tests_pass(base, command):
            raise MutationError("the tests fail on the unmutated copy")
        for n, (label, edits) in enumerate(mutations):
            work = os.path.join(tmp, "m%d" % n)
            shutil.copytree(base, work)
            apply(work, edits)
            if tests_pass(work, command):
                survivors.append(label)
                say("SURVIVED %s" % label)
            else:
                say("killed   %s" % label)
            shutil.rmtree(work)
    return survivors


def main():
    try:
        survivors = run(ROOT, MUTATIONS)
    except MutationError as e:
        print("mutate_never: %s" % e)
        return 2
    print("mutate_never: %d of %d mutations caught" % (len(MUTATIONS) - len(survivors), len(MUTATIONS)))
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
