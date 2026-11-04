import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True  # the module under test must not leave bytecode in the kit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "sdlc")
sys.path.insert(0, os.path.join(ROOT, "bin"))

SPEC = """# Spec: Demo

Feature: demo
Number: 005
Status: draft <!-- draft | approved | implemented | superseded by NNN | rejected (YYYY-MM-DD: reason). sdlc-analyze sets approved. -->
Approved: <!-- name, YYYY-MM-DD; filled when approved -->
Owner: o
Created: 2026-11-04
Track: T3

## Intent

Why.

## Requirements

- **FR-001**: The system MUST do a thing.
"""
PLAN = """# Plan: Demo

Spec: [spec.md](spec.md) · Status: draft · Created: 2026-11-04

## Summary

How.
"""
TASKS = """# Tasks: Demo

Inputs: [spec.md](spec.md), [plan.md](plan.md) · Status: draft · Created: 2026-11-04 · Branch: `feat/x`

Verify:
- Narrow: `x`

Legend: `- [x] T001 [S1] example` is a tick.

## S1

- [ ] T001 [S1] Do the first thing — files: a.py
- [ ] T002 [S1] Do the second thing

## Human steps

- [ ] H1 Approve

## Progress log

- 2026-11-04 start
"""
CONTRACT = "# Contract\n\nExit 0 on success.\n"
APPROVED_RE = re.compile(r"^Approved: (?P<by>[^,\n]+), (?P<date>\d{4}-\d{2}-\d{2}), digest sha256:(?P<hex>[0-9a-f]{64}) "
                         r"\(spec (?P<s>[0-9a-f]{12}), plan (?P<p>[0-9a-f]{12}), tasks (?P<t>[0-9a-f]{12}), "
                         r"contracts (?P<c>[0-9a-f]{12})\)(?:\s*<!--.*-->)?\s*$", re.M)


def run(*args, env=None, timeout=30, cli=CLI):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, "-B", cli] + list(args), capture_output=True, text=True, timeout=timeout, env=e)
    return p.returncode, p.stdout, p.stderr


def git(d, *args):
    subprocess.run(["git", "-C", d, "-c", "user.email=a@b", "-c", "user.name=x"] + list(args),
                   check=True, capture_output=True, text=True)


class Proj(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "proj")
        os.mkdir(self.d)
        self.f = os.path.join(self.d, "specs", "005-demo")
        os.makedirs(os.path.join(self.f, "contracts"))
        self.put("spec.md", SPEC)
        self.put("plan.md", PLAN)
        self.put("tasks.md", TASKS)
        self.put("contracts/c.md", CONTRACT)

    def put(self, rel, text, mode="w"):
        with open(os.path.join(self.f, *rel.split("/")), mode, newline="") as f:
            f.write(text)

    def get(self, rel):
        with open(os.path.join(self.f, *rel.split("/")), newline="") as f:
            return f.read()

    def edit(self, rel, old, new):
        t = self.get(rel)
        self.assertIn(old, t)
        self.put(rel, t.replace(old, new, 1))

    def gate(self, name, *extra, **kw):
        return run("gate", name, self.d, *extra, **kw)

    def approve(self, by="Alice Nguyen"):
        code, out, err = self.gate("approve", "--spec", "005", "--by", by)
        self.assertEqual(code, 0, out + err)
        return out

    def approved(self):
        return self.gate("approved", "--spec", "005")

    def repo(self):
        git(self.d, "init", "-q")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "init")


class Approve(Proj):
    def test_approve_writes_status_and_the_approved_line_and_nothing_else(self):
        before = self.get("spec.md").split("\n")
        out = self.approve()
        after = self.get("spec.md").split("\n")
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(len(before), len(after))
        self.assertEqual(len(changed), 2, changed)
        status = after[changed[0]]
        self.assertTrue(status.startswith("Status: approved <!-- draft | approved |"), status)
        m = APPROVED_RE.match(after[changed[1]])
        self.assertIsNotNone(m, after[changed[1]])
        self.assertEqual(m.group("by"), "Alice Nguyen")
        self.assertIn("<!-- name, YYYY-MM-DD; filled when approved -->", after[changed[1]])  # old comment kept
        last = out.strip().split("\n")[-1]
        self.assertRegex(last, r"^gate approve: PASS \(approved by Alice Nguyen on \d{4}-\d{2}-\d{2}, digest sha256:[0-9a-f]{12}\.\.\.\)$")

    def test_approved_passes_after_approve_and_when_implemented(self):
        self.approve()
        code, out, _ = self.approved()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip().split("\n")[-1], "gate approved: PASS")
        self.edit("spec.md", "Status: approved", "Status: implemented")
        self.assertEqual(self.approved()[0], 0)

    def test_unknown_gate_is_exit_2_with_one_error_line_and_no_gate_line(self):
        code, out, _ = self.gate("bogus", "--spec", "005")
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith("sdlc: error:"))
        self.assertNotIn("gate bogus", out)

    def test_spec_forms(self):
        self.approve()
        self.assertEqual(self.gate("approved", "--spec", "specs/005-demo")[0], 0)
        self.assertEqual(self.gate("approved", "--spec", "specs/005-demo/")[0], 0)
        self.assertEqual(self.gate("approved", "--spec", os.path.join(self.d, "specs", "005-demo"))[0], 2)  # absolute
        os.makedirs(os.path.join(self.d, "elsewhere"))
        shutil.copy(os.path.join(self.f, "spec.md"), os.path.join(self.d, "elsewhere", "spec.md"))
        self.assertEqual(self.gate("approved", "--spec", "elsewhere")[0], 2)  # outside spec_dir
        self.assertEqual(self.gate("approved", "--spec", "../x")[0], 2)
        self.assertEqual(self.gate("approved", "--spec", "009")[0], 2)  # missing
        os.makedirs(os.path.join(self.d, "specs", "005-other"))
        self.assertEqual(self.gate("approved", "--spec", "005")[0], 2)  # ambiguous
        self.assertEqual(self.gate("approved")[0], 2)  # --spec required

    def test_by_is_required_for_approve_and_refused_elsewhere(self):
        self.assertEqual(self.gate("approve", "--spec", "005")[0], 2)
        self.assertEqual(self.gate("approved", "--spec", "005", "--by", "x")[0], 2)
        self.assertEqual(self.gate("green-at-head", "--spec", "005")[0], 2)
        self.assertEqual(self.gate("green-at-head", "--by", "x")[0], 2)


class Digest(Proj):
    def after_approval(self):
        self.approve()
        self.assertEqual(self.approved()[0], 0)

    def fails_naming(self, part):
        code, out, _ = self.approved()
        self.assertEqual(code, 1, out)
        self.assertIn("%s changed since approval" % part, out)
        self.assertEqual(out.strip().split("\n")[-1].split(" (")[0], "gate approved: FAIL")

    def test_edits_that_must_fail(self):
        cases = [
            ("spec", "spec.md", "MUST do a thing", "MUST do another thing"),
            ("plan", "plan.md", "How.", "How, differently."),
            ("contracts", "contracts/c.md", "Exit 0", "Exit 1"),
            ("tasks", "tasks.md", "Do the first thing", "Do the first and a half thing"),
            ("tasks", "tasks.md", "files: a.py", "files: a.py, b.py"),
            ("tasks", "tasks.md", "- Narrow: `x`", "- Narrow: `y`"),
            ("tasks", "tasks.md", "Branch: `feat/x`", "Branch: `feat/y`"),
            ("tasks", "tasks.md", "- [ ] T002 [S1] Do the second thing\n", "- [ ] T002 [S1] Do the second thing\n- [ ] T003 [S1] New task\n"),
        ]
        for part, rel, old, new in cases:
            with self.subTest(part=part, old=old):
                self.setUp()
                self.after_approval()
                self.edit(rel, old, new)
                self.fails_naming(part)

    def test_a_new_and_a_removed_contract_file_fail(self):
        self.after_approval()
        self.put("contracts/d.md", "# D\n")
        self.fails_naming("contracts")
        os.remove(os.path.join(self.f, "contracts", "d.md"))
        self.assertEqual(self.approved()[0], 0)
        os.remove(os.path.join(self.f, "contracts", "c.md"))
        self.fails_naming("contracts")

    def test_text_cannot_hide_behind_a_progress_log_heading_in_spec_or_plan(self):
        for rel in ("spec.md", "plan.md"):
            self.setUp()
            self.after_approval()
            self.put(rel, self.get(rel) + "\n## Progress log\n\nThe system MUST also do evil.\n")
            self.assertEqual(self.approved()[0], 1, rel)

    def test_stray_status_and_approved_lines_are_not_ignored(self):
        self.after_approval()
        self.put("spec.md", self.get("spec.md") + "\nStatus: whatever\nApproved: someone\n")
        self.fails_naming("spec")
        self.setUp()
        self.after_approval()
        self.put("plan.md", self.get("plan.md") + "\nSee x · Status: hidden · more text\n")
        self.fails_naming("plan")
        self.setUp()
        self.after_approval()
        self.put("tasks.md", self.get("tasks.md").replace("## S1", "## S1\n\nNote · Status: hidden · text\n"))
        self.fails_naming("tasks")

    def test_ordinary_work_keeps_the_approval(self):
        self.after_approval()
        self.edit("tasks.md", "- [ ] T001", "- [x] T001")
        self.edit("tasks.md", "- [ ] H1", "- [X] H1")
        self.put("tasks.md", self.get("tasks.md") + "- 2026-11-05 `abc1234` T001 done\n")
        self.edit("tasks.md", "Status: approved", "Status: approved") if "Status: approved" in self.get("tasks.md") else None
        self.edit("tasks.md", "· Status: draft ·", "· Status: approved ·")
        self.edit("plan.md", "· Status: draft ·", "· Status: approved ·")
        self.edit("spec.md", "Status: approved", "Status: implemented")
        code, out, _ = self.approved()
        self.assertEqual(code, 0, out)

    def test_crlf_files_give_the_same_digest(self):
        import sdlc_gate
        a = sdlc_gate.digest(self.f)
        for rel in ("spec.md", "plan.md", "tasks.md", "contracts/c.md"):
            self.put(rel, self.get(rel).replace("\n", "\r\n"))
        self.assertEqual(sdlc_gate.digest(self.f), a)

    def test_numbered_and_table_boxes_are_not_normalised(self):
        self.edit("tasks.md", "## Human steps", "## Human steps\n\n1. [ ] numbered\n| [ ] | cell |")
        self.after_approval()
        self.edit("tasks.md", "1. [ ] numbered", "1. [x] numbered")
        self.fails_naming("tasks")


class ApprovedFailures(Proj):
    def test_draft_and_no_digest_lines(self):
        code, out, _ = self.approved()
        self.assertEqual(code, 1)
        self.assertIn("status is draft, not approved", out)
        self.edit("spec.md", "Status: draft", "Status: approved")
        for line in ("Approved: <!-- name, YYYY-MM-DD; filled when approved -->", "Approved: phong, 2026-11-03 (in chat)",
                     "Approved: a, 2026-11-04, digest sha256:" + "0" * 64,
                     "Approved: a, 2026-11-04, digest sha256:" + "0" * 64 + " (spec 000000000000, plan 000000000000, tasks 000000000000)"):
            lines = self.get("spec.md").split("\n")
            i = next(n for n, l in enumerate(lines) if l.startswith("Approved:"))
            lines[i] = line
            self.put("spec.md", "\n".join(lines))
            code, out, _ = self.approved()
            self.assertEqual(code, 1, line)
            self.assertIn("no approval digest on the Approved line", out)

    def test_hand_edited_combined_digest_with_matching_prefixes(self):
        self.approve()
        t = self.get("spec.md")
        m = re.search(r"digest sha256:([0-9a-f]{64})", t)
        self.put("spec.md", t.replace(m.group(1), m.group(1)[:12] + "f" * 52))
        code, out, _ = self.approved()
        self.assertEqual(code, 1)
        self.assertIn("approval digest does not match the documents", out)

    def test_real_legacy_specs_report_no_digest(self):
        for n in ("002-dense-find-command", "003-usage-metrics", "004-verify-command"):
            code, out, _ = run("gate", "approved", ROOT, "--spec", n if False else n[:3])
            self.assertEqual(code, 1, (n, out))
            self.assertIn("no approval digest", out, n)

    def test_missing_documents_and_status_line(self):
        self.approve()
        self.put("spec.md", self.get("spec.md").replace("Status: approved", "Statu: approved"))
        code, out, _ = self.approved()
        self.assertEqual((code, "status is missing, not approved" in out), (1, True))
        self.setUp()
        self.approve()
        os.remove(os.path.join(self.f, "plan.md"))
        self.assertEqual(self.approved()[0], 2)
        self.setUp()
        self.approve()
        os.remove(os.path.join(self.f, "tasks.md"))
        self.assertEqual(self.approved()[0], 2)

    def test_draft_without_a_plan_is_exit_1_not_2(self):
        os.remove(os.path.join(self.f, "plan.md"))
        self.assertEqual(self.approved()[0], 1)

    def test_body_lines_that_look_like_approval_are_ignored(self):
        self.put("spec.md", self.get("spec.md") + "\nApproved: x, 2026-01-01, digest sha256:" + "a" * 64 + "\n")
        code, out, _ = self.approved()
        self.assertIn("status is draft", out)
        self.edit("spec.md", "Status: draft", "Status: approved")
        self.assertIn("no approval digest", self.approved()[1])

    def test_bad_documents_are_exit_2(self):
        self.approve()
        with open(os.path.join(self.f, "tasks.md"), "wb") as f:
            f.write(b"\xff\xfe not utf8")
        self.assertEqual(self.approved()[0], 2)
        self.put("tasks.md", "x" * (2 * 1024 * 1024 + 1))
        self.assertEqual(self.approved()[0], 2)
        os.remove(os.path.join(self.f, "tasks.md"))
        os.mkfifo(os.path.join(self.f, "tasks.md"))
        self.assertEqual(self.approved()[0], 2)  # a FIFO must not hang the gate


class ApproveRefusals(Proj):
    def refused(self, *extra):
        before = self.get("spec.md")
        code, out, _ = self.gate("approve", "--spec", "005", *extra)
        self.assertEqual(code, 2, out)
        self.assertEqual(self.get("spec.md"), before)
        return out

    def test_statuses_that_cannot_be_approved(self):
        for st in ("implemented", "rejected (2026-01-01: no)", "superseded by 007"):
            self.setUp()
            self.edit("spec.md", "Status: draft", "Status: " + st)
            self.refused("--by", "A")
        self.setUp()
        self.edit("spec.md", "Status: draft <!--", "Status: <!--")  # a status whose first token is the comment opener
        self.refused("--by", "A")
        self.setUp()
        self.edit("spec.md", "Status: draft <!-- draft | approved", "Status:")
        self.refused("--by", "A")

    def test_header_lines_must_be_exactly_present(self):
        self.edit("spec.md", "Approved: <!--", "Approvd: <!--")
        self.refused("--by", "A")
        self.setUp()
        self.edit("spec.md", "## Intent", "## Intent\n\nStatus: draft")  # only the header counts: still exactly one
        code, out, _ = self.gate("approve", "--spec", "005", "--by", "A")
        self.assertEqual(code, 0, out)

    def test_missing_plan_or_tasks(self):
        os.remove(os.path.join(self.f, "plan.md"))
        self.refused("--by", "A")
        self.setUp()
        os.remove(os.path.join(self.f, "tasks.md"))
        self.refused("--by", "A")

    def test_bad_names(self):
        for by in ("", "   ", "a,b", "a\nb", "a\rb", "a<!--b", "a-->b", "x" * 81, " lead", "trail ", "a\u2028b", "a\u2029b"):
            with self.subTest(by=by):
                self.refused("--by", by)

    def test_nul_and_other_control_characters_are_not_valid_names(self):
        import sdlc_gate
        for by in ("a\x00b", "a\x1fb", "a\x7fb"):
            self.assertFalse(sdlc_gate.valid_by(by), repr(by))
        self.assertTrue(sdlc_gate.valid_by("Ng\u00f4 Th\u1ebf Phong"))

    def test_symlinked_spec_is_refused(self):
        real = os.path.join(self._tmp.name, "real-spec.md")
        shutil.move(os.path.join(self.f, "spec.md"), real)
        os.symlink(real, os.path.join(self.f, "spec.md"))
        code, out, _ = self.gate("approve", "--spec", "005", "--by", "A")
        self.assertEqual(code, 2)
        self.assertIn("symlink", out)

    def test_re_approve_replaces_the_digest_and_keeps_comments(self):
        self.approve()
        first = self.get("spec.md")
        self.edit("plan.md", "How.", "How, again.")
        self.assertEqual(self.approved()[0], 1)
        self.approve("Bob")
        second = self.get("spec.md")
        self.assertNotEqual(first, second)
        self.assertEqual(self.approved()[0], 0)
        self.assertIn("Bob", second)
        self.assertIn("<!-- name, YYYY-MM-DD; filled when approved -->", second)

    def test_crlf_missing_final_newline_and_mode_are_preserved(self):
        text = self.get("spec.md").replace("\n", "\r\n").rstrip("\r\n")
        self.put("spec.md", text)
        os.chmod(os.path.join(self.f, "spec.md"), 0o644)
        self.approve()
        after = self.get("spec.md")
        self.assertNotIn("\n", after.replace("\r\n", ""))
        self.assertFalse(after.endswith("\n"))
        self.assertEqual(os.stat(os.path.join(self.f, "spec.md")).st_mode & 0o777, 0o644)
        self.assertEqual(self.approved()[0], 0)

    def test_failed_write_leaves_the_spec_and_removes_the_temp_file(self):
        import sdlc_gate
        before = self.get("spec.md")
        def boom(a, b):
            raise OSError("disk full")
        with self.assertRaises(OSError):
            sdlc_gate.approve(self.f, "A", replace=boom)
        self.assertEqual(self.get("spec.md"), before)
        self.assertEqual(sorted(os.listdir(self.f)), ["contracts", "plan.md", "spec.md", "tasks.md"])

    def test_a_non_ascii_name_survives_an_ascii_terminal(self):
        code, out, err = self.gate("approve", "--spec", "005", "--by", "Ngô Thế Phong", env={"PYTHONIOENCODING": "ascii"})
        self.assertEqual(code, 0, out + err)
        self.assertIn("Ngô Thế Phong", self.get("spec.md"))
        self.assertEqual(self.approved()[0], 0)


if __name__ == "__main__":
    unittest.main()
