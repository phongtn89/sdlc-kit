import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "sdlc")
TEMPLATE = os.path.join(ROOT, "adapters", "ci", "sdlc-gates.yml")
STEPS = ("Check install", "Verify", "Green at HEAD", "Spec gates")


def text(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def steps():
    """{step name: run script} read from the template without a YAML library: a step starts at `- name:`, its
    script is its `run:` line or the `run: |` block that follows."""
    out, name, lines, in_run = {}, None, [], False
    for line in text("adapters", "ci", "sdlc-gates.yml").split("\n"):
        m = re.match(r"^      - name: (.+)$", line)
        if m:
            if name:
                out[name] = "\n".join(lines)
            name, lines, in_run = m.group(1).strip(), [], False
            continue
        inline = re.match(r"^        run: (?!\|\s*$)(.+)$", line)
        if inline:
            lines.append(inline.group(1))
        elif re.match(r"^        run: \|\s*$", line):
            in_run = True
        elif in_run and (line.startswith("          ") or not line.strip()):
            lines.append(line[10:])
        elif in_run:
            in_run = False
    if name:
        out[name] = "\n".join(lines)
    return out


def git(d, *args):
    subprocess.run(["git", "-C", d, "-c", "user.email=a@b", "-c", "user.name=x"] + list(args),
                   check=True, capture_output=True, text=True)


class Template(unittest.TestCase):
    def test_the_template_exists_and_runs_the_steps_in_order(self):
        self.assertTrue(os.path.isfile(TEMPLATE))
        self.assertEqual([s for s in steps() if s in STEPS], list(STEPS))
        body = text("adapters", "ci", "sdlc-gates.yml")
        self.assertIn("pull_request", body)
        self.assertEqual([m.group(1) for m in re.finditer(r"^      - name: (.+)$", body, re.M)][-4:], list(STEPS))

    def test_each_step_calls_the_kit_it_checked_out_not_the_locks_path(self):
        s = steps()
        self.assertIn("$SDLC check .", s["Check install"])
        self.assertIn("$SDLC verify .", s["Verify"])
        self.assertIn("$SDLC gate green-at-head .", s["Green at HEAD"])
        self.assertIn("$SDLC gate approved . --spec", s["Spec gates"])
        self.assertIn("$SDLC gate evidence-for-ticks . --spec", s["Spec gates"])
        body = text("adapters", "ci", "sdlc-gates.yml")
        self.assertNotIn("kit_path", "\n".join(s.values()))
        self.assertRegex(body, r"(?m)^  SDLC: python3 .*sdlc-kit/bin/sdlc$")

    def test_the_kit_checkout_is_pinned_and_kept_out_of_the_tree_check(self):
        body = text("adapters", "ci", "sdlc-gates.yml")
        self.assertRegex(body, r"(?m)^\s+ref: \S+")
        self.assertIn("repository:", body)
        self.assertLess(body.index("info/exclude"), body.index("name: Verify"))

    def test_the_job_is_read_only_and_leaves_no_credentials_behind(self):
        body = text("adapters", "ci", "sdlc-gates.yml")
        self.assertRegex(body, r"(?m)^permissions:\n  contents: read$")
        self.assertEqual(body.count("persist-credentials: false"), 2)

    def test_lint_is_not_a_step(self):
        self.assertNotIn("sdlc lint", "\n".join(steps().values()))
        self.assertNotIn(" lint", "\n".join(steps().values()))
        self.assertIn("sdlc lint", text("adapters", "ci", "sdlc-gates.yml"))  # the comment says why it is absent


class Project(unittest.TestCase):
    """A committed project with the kit installed and one approved spec, and the template's steps run on it."""
    commands = {"test": "true"}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "p")
        os.makedirs(os.path.join(self.d, ".sdlc"))
        os.makedirs(os.path.join(self.d, "specs", "007-demo"))
        subprocess.run(["git", "init", "-q", "-b", "main", self.d], check=True, capture_output=True)
        with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
            json.dump({"commands": self.commands}, f)
        self.sdlc("install", self.d, "--targets", "claude")
        for name, body in (("spec.md", "# Spec: demo\n\nStatus: draft\nApproved:\n"), ("plan.md", "# Plan\n"),
                           ("tasks.md", "# Tasks\n\n- [ ] T001 do it\n")):
            with open(os.path.join(self.d, "specs", "007-demo", name), "w") as f:
                f.write(body)
        self.sdlc("gate", "approve", self.d, "--spec", "007", "--by", "tester")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "init")

    def sdlc(self, *args):
        p = subprocess.run([sys.executable, "-B", CLI] + list(args), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def step(self, name, head_ref="feat/007-demo"):
        env = dict(os.environ, SDLC="%s -B %s" % (sys.executable, CLI), HEAD_REF=head_ref)
        p = subprocess.run(["sh", "-c", steps()[name]], cwd=self.d, env=env, capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def run_all(self, head_ref="feat/007-demo"):
        for name in STEPS:
            code, out = self.step(name, head_ref)
            if code:
                return name, code, out
        return None, 0, ""


class GreenProject(Project):
    def test_all_four_steps_pass_on_a_clean_approved_project(self):
        name, code, out = self.run_all()
        self.assertEqual((name, code), (None, 0), out)

    def test_a_lock_that_names_a_developers_machine_does_not_fail_the_check_step(self):
        lock_path = os.path.join(self.d, ".sdlc", "lock.json")
        with open(lock_path) as f:
            lock = json.load(f)
        lock["kit_path"] = "/home/someone/sdlc-kit"
        with open(lock_path, "w") as f:
            json.dump(lock, f)
        with open(os.path.join(self.d, ".sdlc", "config.json"), "w") as f:
            json.dump({"enforce": True, "commands": self.commands}, f)
        code, out = self.step("Check install")
        self.assertEqual(code, 0, out)
        self.assertIn("KIT-PATH-MISSING", out)

    def test_no_lock_or_a_corrupt_lock_fails_the_check_step(self):
        lock = os.path.join(self.d, ".sdlc", "lock.json")
        with open(lock, "w") as f:
            f.write("{bad")
        code, out = self.step("Check install")
        self.assertNotEqual(code, 0, out)
        os.remove(lock)
        code, out = self.step("Check install")
        self.assertNotEqual(code, 0, out)

    def test_a_crash_of_check_fails_the_step(self):
        env = dict(os.environ, SDLC="false", HEAD_REF="x")
        p = subprocess.run(["sh", "-c", steps()["Check install"]], cwd=self.d, env=env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_first_numbered_segment_of_the_branch_wins_like_in_the_hooks(self):
        code, out = self.step("Spec gates", "feat/007-demo/099-other")
        self.assertEqual(code, 0, out)
        self.assertNotIn("skipped", out)
        self.assertIn("PASS", out)
        code, out = self.step("Spec gates", "feat/12345-x")
        self.assertIn("skipped", out)

    def test_a_modified_kit_file_fails_the_check_step(self):
        with open(os.path.join(self.d, ".claude", "skills", "sdlc", "SKILL.md"), "a") as f:
            f.write("\nlocal edit\n")
        code, out = self.step("Check install")
        self.assertNotEqual(code, 0)
        self.assertIn("MODIFIED", out)

    def test_a_spec_edited_after_approval_fails_the_spec_step(self):
        with open(os.path.join(self.d, "specs", "007-demo", "plan.md"), "a") as f:
            f.write("changed after approval\n")
        git(self.d, "commit", "-qam", "edit")
        code, out = self.step("Spec gates")
        self.assertNotEqual(code, 0, out)

    def test_a_tick_without_evidence_fails_the_spec_step(self):
        path = os.path.join(self.d, "specs", "007-demo", "tasks.md")
        with open(path) as f:
            body = f.read()
        with open(path, "w") as f:
            f.write(body.replace("- [ ] T001", "- [x] T001"))
        git(self.d, "commit", "-qam", "tick")
        code, out = self.step("Spec gates")
        self.assertNotEqual(code, 0, out)

    def test_a_branch_without_a_spec_prefix_skips_the_spec_gates_and_says_so(self):
        code, out = self.step("Spec gates", "dependabot/npm/lodash-4")
        self.assertEqual(code, 0, out)
        self.assertIn("skipped", out)

    def test_a_branch_whose_number_has_no_spec_folder_skips_and_says_so(self):
        code, out = self.step("Spec gates", "feat/099-nothing")
        self.assertEqual(code, 0, out)
        self.assertIn("skipped", out)

    def test_the_spec_step_does_not_skip_a_real_gate_failure(self):
        os.remove(os.path.join(self.d, "specs", "007-demo", "plan.md"))
        git(self.d, "add", "-A")
        git(self.d, "commit", "-qm", "rm")
        code, out = self.step("Spec gates")
        self.assertNotEqual(code, 0, out)
        self.assertNotIn("skipped", out)


class RedProject(Project):
    commands = {"test": "false"}

    def test_a_red_verify_fails_the_verify_step_and_green_at_head(self):
        code, out = self.step("Verify")
        self.assertNotEqual(code, 0, out)
        code, out = self.step("Green at HEAD")
        self.assertNotEqual(code, 0, out)


class Docs(unittest.TestCase):
    def test_readme_and_rendering_explain_adoption_and_limits(self):
        readme, rendering = text("README.md"), text("adapters", "RENDERING.md")
        for body in (readme, rendering):
            self.assertIn("adapters/ci/sdlc-gates.yml", body)
        for needle in ("required check", "Copilot", "SDLC_KIT_TOKEN", "pinned", "KIT-PATH-MISSING", "branch protection",
                       "not rendered", "sdlc lint", "draft", "fork", "dependabot"):
            self.assertIn(needle.lower(), readme.lower(), needle)

    def test_install_output_is_unchanged_by_the_template(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, "-B", CLI, "install", d, "--targets", "claude"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertFalse(os.path.exists(os.path.join(d, ".github", "workflows")))
            with open(os.path.join(d, ".sdlc", "lock.json")) as f:
                self.assertFalse([k for k in json.load(f)["files"] if "sdlc-gates" in k or k.startswith(".github/workflows")])


if __name__ == "__main__":
    unittest.main()
