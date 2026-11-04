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


class GreenProj(Proj):
    """A project with a configured test command and real git, plus helpers for `verify` records."""
    def setup_repo(self, test_cmd=None):
        cmd = test_cmd or "%s -c pass" % sys.executable
        os.makedirs(os.path.join(self.d, ".sdlc"), exist_ok=True)
        with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
            json.dump({"commands": {"test": cmd}}, f)
        self.repo()

    def verify(self):
        return run("verify", self.d)

    def green(self, *extra, **kw):
        return run("gate", "green-at-head", self.d, *extra, **kw)

    def reason_lines(self, out):
        return [l for l in out.strip().split("\n")[:-1]]

    def record_path(self):
        return os.path.join(self.d, ".sdlc", "evidence", "verify.json")

    def fake_git(self, body, name="fakebin"):
        d = os.path.join(self._tmp.name, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "git"), "w") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(os.path.join(d, "git"), 0o755)
        return {"PATH": d + os.pathsep + os.environ["PATH"]}


class GreenAtHead(GreenProj):
    def test_passes_for_a_clean_current_green_record(self):
        self.setup_repo()
        self.assertEqual(self.verify()[0], 0)
        code, out, _ = self.green()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "gate green-at-head: PASS")

    def test_each_failure_names_its_reason(self):
        self.setup_repo()
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["no record"]))
        self.verify()
        with open(os.path.join(self.d, "new.txt"), "w") as f:
            f.write("x")
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["tree changed since the record"]))
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "n")
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["record is for another revision"]))
        with open(os.path.join(self.d, "more.txt"), "w") as f:
            f.write("x")
        self.verify()  # taken on a dirty tree
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["record was dirty"]))

    def test_a_failed_command_in_the_record(self):
        self.setup_repo("%s -c 'import sys; sys.exit(1)'" % sys.executable)
        self.assertEqual(self.verify()[0], 1)
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["a command did not pass"]))

    def test_unreadable_records_are_exit_1_and_never_hang(self):
        self.setup_repo()
        os.makedirs(os.path.dirname(self.record_path()), exist_ok=True)
        with open(self.record_path(), "w") as f:
            f.write("{not json")
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["unreadable record"]))
        os.remove(self.record_path())
        os.mkfifo(self.record_path())
        code, out, _ = self.green(timeout=10)
        self.assertEqual((code, self.reason_lines(out)), (1, ["unreadable record"]))
        os.remove(self.record_path())
        with open(self.record_path(), "w") as f:
            f.write("[" + " " * (1024 * 1024 + 10) + "]")
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["unreadable record"]))
        os.remove(self.record_path())
        with open(self.record_path(), "w") as f:
            json.dump({"version": 2}, f)
        self.assertEqual(self.reason_lines(self.green()[1]), ["record shape or version wrong"])

    def test_no_repository_and_no_commit_are_head_unresolved(self):
        os.makedirs(os.path.join(self.d, ".sdlc"))
        with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
            json.dump({"commands": {"test": "%s -c pass" % sys.executable}}, f)
        self.verify()
        code, out, _ = self.green()
        self.assertEqual((code, self.reason_lines(out)), (1, ["HEAD unresolved (no repository or no commit)"]))
        git(self.d, "init", "-q")
        self.assertEqual(self.reason_lines(self.green()[1]), ["HEAD unresolved (no repository or no commit)"])

    def test_the_commands_in_a_record_are_never_run(self):
        self.setup_repo()
        self.verify()
        marker = os.path.join(self._tmp.name, "pwned")
        with open(self.record_path()) as f:
            rec = json.load(f)
        rec["commands"][0]["command"] = "touch " + marker
        with open(self.record_path(), "w") as f:
            json.dump(rec, f)
        self.assertEqual(self.green()[0], 0)
        self.assertFalse(os.path.exists(marker))

    def test_git_failures_fail_closed_with_their_reason(self):
        self.setup_repo()
        self.verify()
        env = {"PATH": os.path.join(self._tmp.name, "nowhere")}
        code, out, _ = self.green(env=env)
        self.assertEqual((code, self.reason_lines(out)), (1, ["git not found"]))
        env = self.fake_git("exit 1")
        code, out, _ = self.green(env=env)
        self.assertEqual((code, self.reason_lines(out)), (1, ["HEAD unresolved (no repository or no commit)"]))
        real = subprocess.run(["git", "-C", self.d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        env = self.fake_git('case "$*" in *rev-parse*) echo %s;; *status*) exit 1;; esac' % real)
        code, out, _ = self.green(env=env)
        self.assertEqual((code, self.reason_lines(out)), (1, ["git status failed"]))

    def test_a_timed_out_git_call_has_its_own_reason(self):
        import sdlc_gate, sdlc_verify
        from unittest import mock
        self.setup_repo()
        self.verify()
        with mock.patch.object(sdlc_verify, "git_run", return_value=("timeout", "")):
            problems = sdlc_gate.check_green(self.d)
        self.assertEqual(problems, ["git timed out"])

    def test_two_git_calls(self):
        self.setup_repo()
        self.verify()
        log = os.path.join(self._tmp.name, "calls.log")
        real = subprocess.run(["git", "-C", self.d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        env = self.fake_git('echo "$*" >> %s\ncase "$*" in *rev-parse*) echo %s;; esac' % (log, real))
        self.assertEqual(self.green(env=env)[0], 0)
        self.assertEqual(len(open(log).read().strip().split("\n")), 2)


class Ticks(GreenProj):
    def commits(self, n):
        """n real commits; returns their short hashes."""
        self.repo()
        out = []
        for i in range(n):
            git(self.d, "commit", "-q", "--allow-empty", "-m", "c%d" % i)
            out.append(subprocess.run(["git", "-C", self.d, "rev-parse", "--short=9", "HEAD"], capture_output=True,
                                      text=True).stdout.strip())
        return out

    def tasks(self, body, log):
        self.put("tasks.md", "# Tasks\n\nInputs: x \u00b7 Status: approved \u00b7 y\n\n" + body + "\n## Progress log\n\n" + log)

    def ticks(self, **kw):
        return run("gate", "evidence-for-ticks", self.d, "--spec", "005", **kw)

    def problems(self, out):
        return out.strip().split("\n")[:-1]

    def test_single_ids_lists_ranges_and_human_steps_are_evidence(self):
        h = self.commits(4)
        self.tasks("- [x] T001 a\n- [x] T002 b\n- [X] T003 c\n- [x] T004 d\n- [x] T005 e\n- [x] T006b f\n- [x] H1 g\n- [ ] T009 open\n",
                   "- 2026-11-04 `%s` \u2014 T001 done\n- `%s`+ T002, T003 done\n- %s: T004\u2013T005 done\n- %s T006b and H1\n" % (h[0], h[1], h[2], h[3]))
        code, out, _ = self.ticks()
        self.assertEqual((code, out.strip()), (0, "gate evidence-for-ticks: PASS"), out)

    def test_range_spellings(self):
        h = self.commits(1)
        for spelling in ("T001\u2013T003", "T001-T003", "T001\u2013003", "T001 - T003"):
            self.tasks("- [x] T002 b\n", "- `%s` %s done\n" % (h[0], spelling))
            self.assertEqual(self.ticks()[0], 0, spelling)
        self.tasks("- [x] T002 b\n", "- `%s` T003\u2013T001 done\n" % h[0])  # reversed: not a range, T002 not named
        self.assertEqual(self.ticks()[0], 1)

    def test_each_kind_of_missing_evidence_is_one_line(self):
        h = self.commits(1)
        self.tasks("- [x] T001 a\n- [x] T002 b\n- [x] T003 c\n- [x] no id here\n- [x] T0011 near\n",
                   "- `%s` T001 done\n- T002 done without a hash\n- `abcdef0123` T003 done\n- `%s` T0011x\n" % (h[0], h[0]))
        code, out, _ = self.ticks()
        self.assertEqual(code, 1)
        want = ["T002: no progress-log line with this task and an existing commit",
                "T003: no progress-log line with this task and an existing commit",
                "line 8: checked box without an id",
                "T0011: no progress-log line with this task and an existing commit"]
        self.assertEqual(self.problems(out), want)
        self.assertEqual(out.strip().split("\n")[-1], "gate evidence-for-ticks: FAIL (4 problems)")

    def test_a_non_commit_object_is_not_a_commit(self):
        self.commits(1)
        blob = subprocess.run(["git", "-C", self.d, "rev-parse", "--short=9", "HEAD:specs/005-demo/plan.md"], capture_output=True, text=True).stdout.strip()
        self.tasks("- [x] T001 a\n", "- `%s` T001 done\n" % blob)
        self.assertEqual(self.ticks()[0], 1)

    def test_no_ticks_passes_with_no_git_call_even_outside_git(self):
        self.tasks("- [ ] T001 open\n", "- no hashes\n")
        log = os.path.join(self._tmp.name, "calls.log")
        env = self.fake_git('echo "$*" >> %s' % log)
        self.assertEqual(self.ticks(env=env)[0], 0)
        self.assertFalse(os.path.exists(log))

    def test_no_progress_log_heading_fails_every_tick(self):
        h = self.commits(1)
        self.put("tasks.md", "# Tasks\n\n- [x] T001 a\n\nT001 done `%s`\n" % h[0])
        self.assertEqual(self.ticks()[0], 1)

    def test_exactly_one_cat_file_call_and_a_shallow_probe_only_when_a_token_is_missing(self):
        h = self.commits(2)
        self.tasks("- [x] T001 a\n- [x] T002 b\n", "- `%s` T001\n- `%s` T002\n" % (h[0], h[1]))
        log = os.path.join(self._tmp.name, "calls.log")
        real = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
        env = self.fake_git('echo "$*" >> %s\nexec %s "$@"' % (log, real))
        self.assertEqual(self.ticks(env=env)[0], 0)
        calls = open(log).read().strip().split("\n")
        self.assertEqual(len([c for c in calls if "cat-file" in c]), 1, calls)
        self.assertEqual(len(calls), 1)
        os.remove(log)
        self.tasks("- [x] T001 a\n", "- `deadbeef12` T001\n")
        self.assertEqual(self.ticks(env=env)[0], 1)
        calls = open(log).read().strip().split("\n")
        self.assertEqual(len(calls), 2)
        self.assertIn("--is-shallow-repository", calls[1])

    def test_git_failures_fail_closed(self):
        h = self.commits(1)
        self.tasks("- [x] T001 a\n", "- `%s` T001\n" % h[0])
        for env, want in ((self.fake_git("exit 1"), "git failed"),
                          ({"PATH": os.path.join(self._tmp.name, "nowhere")}, "git not found")):
            code, out, _ = self.ticks(env=env)
            self.assertEqual(code, 1, out)
            self.assertIn(want, out)

    def test_more_than_2000_distinct_tokens_is_a_failure(self):
        self.commits(1)
        log = "\n".join("- %07x T001" % (0x1000000 + i) for i in range(2001)) + "\n"
        self.tasks("- [x] T001 a\n", log)
        code, out, _ = self.ticks()
        self.assertEqual(code, 1)
        self.assertIn("too many revisions to check", out)

    def test_snapshots_of_specs_002_003_004_against_a_rebuilt_history(self):
        for n, want in (("002", []), ("003", []), ("004", ["T015", "T016", "T017", "H1"])):
            with self.subTest(spec=n):
                self.setUp()
                with open(os.path.join(ROOT, "tests", "fixtures", "gate", "tasks-%s.md" % n), encoding="utf-8") as f:
                    text = f.read()
                log = text[text.index("## Progress log"):]
                toks = sorted(set(re.findall(r"(?<![0-9A-Za-z])[0-9a-f]{7,40}(?![0-9A-Za-z])", log)))
                self.repo()
                real = {}
                for tok in toks:
                    git(self.d, "commit", "-q", "--allow-empty", "-m", tok)
                    real[tok] = subprocess.run(["git", "-C", self.d, "rev-parse", "--short=9", "HEAD"], capture_output=True, text=True).stdout.strip()
                head, tail = text.split("## Progress log", 1)
                tail = re.sub(r"(?<![0-9A-Za-z])[0-9a-f]{7,40}(?![0-9A-Za-z])", lambda m: real.get(m.group(0), m.group(0)), tail)
                self.put("tasks.md", head + "## Progress log" + tail)
                code, out, _ = self.ticks()
                got = [l.split(":")[0] for l in self.problems(out)]
                self.assertEqual(got, want, out)
                self.assertEqual(code, 1 if want else 0)

    def test_live_files_smoke(self):
        shallow = subprocess.run(["git", "-C", ROOT, "rev-parse", "--is-shallow-repository"], capture_output=True, text=True).stdout.strip()
        if shallow != "false":
            self.skipTest("shallow or non-git checkout")
        self.assertEqual(run("gate", "evidence-for-ticks", ROOT, "--spec", "002")[0], 0)
        self.assertEqual(run("gate", "evidence-for-ticks", ROOT, "--spec", "003")[0], 0)


class Cli(GreenProj):
    def listing(self, d):
        return sorted(os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs)

    def test_repo_resolution_spec_dir_lookup_and_type_errors(self):
        child = os.path.join(self.d, "api")
        os.makedirs(os.path.join(child, "docs", "005-demo"))
        for name in ("spec.md", "plan.md", "tasks.md"):
            shutil.copy(os.path.join(self.f, name), os.path.join(child, "docs", "005-demo", name))
        def cfg(**repo):
            os.makedirs(os.path.join(self.d, ".sdlc"), exist_ok=True)
            with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
                json.dump({"repos": {"api": dict({"path": "api"}, **repo)}}, f)
        cfg(spec_dir="docs")
        code, out, err = run("gate", "approve", self.d, "--repo", "api", "--spec", "005", "--by", "A")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Approved: A,", open(os.path.join(child, "docs", "005-demo", "spec.md")).read())
        self.assertNotIn("Approved: A,", self.get("spec.md"))
        self.assertEqual(run("gate", "approved", self.d, "--repo", "api", "--spec", "docs/005-demo/")[0], 0)
        cfg(spec_dir="/docs/")  # slashes are stripped
        self.assertEqual(run("gate", "approved", self.d, "--repo", "api", "--spec", "005")[0], 0)
        cfg(spec_dir="")  # empty falls back to specs: the child has none
        self.assertEqual(run("gate", "approved", self.d, "--repo", "api", "--spec", "005")[0], 2)
        for bad in ({"spec_dir": 5}, {"path": 5}, {"path": "../x"}, {"path": "/tmp"}, {"path": "nope"}):
            os.makedirs(os.path.join(self.d, ".sdlc"), exist_ok=True)
            with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
                json.dump({"repos": {"api": dict({"path": "api"}, **bad)}}, f)
            self.assertEqual(run("gate", "approved", self.d, "--repo", "api", "--spec", "005")[0], 2, bad)
        self.assertEqual(run("gate", "approved", self.d, "--repo", "ghost", "--spec", "005")[0], 2)
        with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
            json.dump({"spec_dir": 5}, f)
        self.assertEqual(self.approved()[0], 2)  # a non-string spec_dir is exit 2, not a traceback

    def test_green_at_head_uses_the_repos_own_record(self):
        child = os.path.join(self.d, "api")
        os.makedirs(child)
        with open(os.path.join(child, "x.txt"), "w") as f:
            f.write("x")
        git(child, "init", "-q")
        git(child, "add", "-A")
        git(child, "commit", "-q", "-m", "i")
        os.makedirs(os.path.join(self.d, ".sdlc"), exist_ok=True)
        with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
            json.dump({"repos": {"api": {"path": "api", "commands": {"test": "%s -c pass" % sys.executable}}}}, f)
        self.assertEqual(run("verify", self.d, "--repo", "api")[0], 0)
        self.assertEqual(run("gate", "green-at-head", self.d, "--repo", "api")[0], 0)
        self.assertEqual(self.green()[0], 1)  # the workspace root has no record

    def test_last_line_grammar(self):
        self.approve()
        for args, last in (((("approved", "--spec", "005")), "gate approved: PASS"),):
            self.assertEqual(run("gate", args[0], self.d, *args[1:])[1].strip().split("\n")[-1], last)
        self.edit("plan.md", "How.", "Else.")
        out = self.approved()[1].strip().split("\n")
        self.assertEqual(out[-1], "gate approved: FAIL (1 problems)")

    def test_hostile_environment_runs_nothing_and_gates_write_nothing_but_approve_writes_only_the_spec(self):
        marker = os.path.join(self._tmp.name, "pwned")
        env = {k: "touch " + marker for k in ("SDLC_GATE_COMMAND", "COMMANDS_TEST", "GIT_EXTERNAL_DIFF")}
        before = self.listing(self._tmp.name)
        self.assertEqual(self.gate("approve", "--spec", "005", "--by", "A", env=env)[0], 0)
        after = self.listing(self._tmp.name)
        self.assertEqual(before, after)  # approve only rewrote spec.md: no new file
        self.approved()
        self.gate("evidence-for-ticks", "--spec", "005", env=env)
        self.green(env=env)
        self.assertEqual(self.listing(self._tmp.name), after)
        self.assertFalse(os.path.exists(marker))

    def test_runs_through_a_symlink_and_writes_no_bytecode(self):
        link = os.path.join(self._tmp.name, "sdlc-link")
        os.symlink(CLI, link)
        self.approve()
        self.assertEqual(run("gate", "approved", self.d, "--spec", "005", cli=link)[0], 0)
        self.assertFalse(os.path.isdir(os.path.join(ROOT, "bin", "__pycache__")))

    def test_the_module_imports_only_the_standard_library_and_sdlc_verify(self):
        import ast
        allowed = {"datetime", "hashlib", "json", "os", "re", "stat", "tempfile", "sdlc_verify"}
        with open(os.path.join(ROOT, "bin", "sdlc_gate.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertEqual(names - allowed, set())

    def test_no_directory_and_unknown_options_are_exit_2(self):
        self.assertEqual(run("gate", "approved", os.path.join(self._tmp.name, "nope"), "--spec", "005")[0], 2)
        self.assertEqual(self.gate("approved", "--spec", "005", "--bogus")[0], 2)


if __name__ == "__main__":
    unittest.main()
