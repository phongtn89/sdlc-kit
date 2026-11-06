"""One end-to-end test class per "must never happen" rule of docs/adr/0003-enforcement-model.md (spec 009).

Each class drives the real entry point on a fixture project: the hook through the command rendered into
.claude/settings.json (run with `sh -c`, the host's JSON on standard input), the gate through `sdlc gate`, the role
through `sdlc install`. `tests/mutate_never.py` removes each mechanism in a copy of the kit and requires this file to fail.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "sdlc")
ADR = os.path.join(ROOT, "docs", "adr", "0003-enforcement-model.md")


def sdlc(*args):
    p = subprocess.run([sys.executable, "-B", CLI] + list(args), capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout + p.stderr


def git(d, *args):
    return subprocess.run(["git", "-C", d, "-c", "user.email=a@b", "-c", "user.name=x"] + list(args),
                          check=True, capture_output=True, text=True).stdout.strip()


def denied(out):
    try:
        return (json.loads(out).get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"
    except ValueError:
        return False


def message(out):
    try:
        return json.loads(out).get("systemMessage") or ""
    except ValueError:
        return ""


class Project(unittest.TestCase):
    """A committed project on branch feat/009-demo with the kit installed and `enforce` on."""
    targets = "claude"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "p")
        os.makedirs(os.path.join(self.d, ".sdlc"))
        git(self.d, "init", "-q", "-b", "main")
        self.config(enforce=True, commands={"test": "true"})
        code, out = sdlc("install", self.d, "--targets", self.targets)
        self.assertEqual(code, 0, out)
        for rel, text in (("specs/009-demo/spec.md", "# Spec\n\nStatus: draft\nApproved:\n"),
                          ("specs/009-demo/plan.md", "# Plan\n"),
                          ("specs/009-demo/tasks.md", "# Tasks\n\n- [ ] T001 do it\n\n## Progress log\n\n"),
                          ("src/app.py", "a = 1\n"), ("README.md", "# demo\n")):
            self.write(rel, text)
        self.commit("initial")
        git(self.d, "checkout", "-q", "-b", "feat/009-demo")

    def write(self, rel, text):
        path = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self, rel):
        with open(os.path.join(self.d, rel), encoding="utf-8") as f:
            return f.read()

    def config(self, **cfg):
        self.write(".sdlc/config.json", json.dumps(cfg))

    def commit(self, msg="work"):
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", msg)
        return git(self.d, "rev-parse", "--short", "HEAD")

    def hook(self, name, payload):
        """Standard output of the entry rendered into .claude/settings.json for hook `name`; the exit code must be 0."""
        with open(os.path.join(self.d, ".claude", "settings.json"), encoding="utf-8") as f:
            settings = json.load(f)
        found = [h["command"] for groups in settings["hooks"].values() for g in groups for h in g["hooks"]
                 if h["command"].rstrip().endswith("# sdlc-kit:" + name)]
        self.assertEqual(len(found), 1, "no rendered hook entry for %s" % name)
        payload = dict(payload, cwd=self.d)
        p = subprocess.run(["sh", "-c", found[0]], input=json.dumps(payload), cwd=self.d, capture_output=True, text=True,
                           env=dict(os.environ, CLAUDE_PROJECT_DIR=self.d), timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout.strip()

    def push(self, command="git push origin main"):
        return self.hook("bash", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}})

    def edit(self, rel="src/app.py", tool="Edit"):
        return self.hook("edit", {"hook_event_name": "PreToolUse", "tool_name": tool,
                                  "tool_input": {"file_path": os.path.join(self.d, rel)}})

    def stop(self):
        return self.hook("stop", {"hook_event_name": "Stop", "stop_hook_active": False})


class PushWhileTestsAreRed(Project):
    RULE = "Push while tests are red"

    def test_a_push_without_a_record_is_refused(self):
        self.assertTrue(denied(self.push()))
        self.assertTrue(denied(self.push("gh pr create --fill")))

    def test_a_push_on_a_red_record_is_refused_and_a_green_one_is_allowed(self):
        self.config(enforce=True, commands={"test": "false"})
        self.commit("red config")
        self.assertEqual(sdlc("verify", self.d)[0], 1)
        self.assertTrue(denied(self.push()))
        self.assertTrue(denied(self.push("git add -A && git commit -qm x && git push")))
        self.config(enforce=True, commands={"test": "true"})
        self.commit("green config")
        self.assertEqual(sdlc("verify", self.d)[0], 0)
        self.assertEqual(self.push(), "")
        self.assertEqual(self.push("gh pr create --fill"), "")

    def test_a_green_record_goes_stale_with_the_next_commit_and_with_a_dirty_tree(self):
        self.assertEqual(sdlc("verify", self.d)[0], 0)
        self.assertEqual(self.push(), "")
        self.write("src/app.py", "a = 2\n")
        self.assertTrue(denied(self.push()), "a dirty tree")
        self.commit("next")
        self.assertTrue(denied(self.push()), "a record for another revision")

    def test_a_record_made_on_a_dirty_tree_never_counts(self):
        self.write("src/app.py", "a = 2\n")
        self.assertEqual(sdlc("verify", self.d)[0], 0)
        self.write("src/app.py", "a = 1\n")  # the tree is clean again at the same commit
        self.assertTrue(denied(self.push()))

    def test_the_hook_acts_only_when_enforce_is_the_json_true(self):
        for value in (None, "true", 1):
            with self.subTest(repr(value)):
                self.config(**({} if value is None else {"enforce": value}))
                self.assertEqual(self.push(), "")
        self.config(enforce=True)
        self.assertTrue(denied(self.push()))

    def test_all_three_hooks_are_rendered_when_enforce_is_on(self):
        for name in ("bash", "edit", "stop"):
            self.hook(name, {"tool_name": "Bash", "tool_input": {"command": "ls"}})


class SourceEditWithoutApproval(Project):
    RULE = "Source edit on a T3 feature without approval"

    def approve(self):
        code, out = sdlc("gate", "approve", self.d, "--spec", "009", "--by", "tester")
        self.assertEqual(code, 0, out)
        self.commit("approve")

    def test_a_source_edit_on_a_draft_spec_is_refused_by_every_edit_tool(self):
        for tool in ("Edit", "Write", "MultiEdit"):
            with self.subTest(tool):
                self.assertTrue(denied(self.edit(tool=tool)))

    def test_documents_and_kit_files_are_never_refused(self):
        for rel in ("README.md", "specs/009-demo/plan.md", "docs/notes.txt", ".sdlc/config.json", ".claude/settings.json"):
            with self.subTest(rel):
                self.assertEqual(self.edit(rel), "")

    def test_an_approved_spec_allows_source_edits_until_a_document_changes(self):
        self.approve()
        self.assertEqual(sdlc("gate", "approved", self.d, "--spec", "009")[0], 0)
        self.assertEqual(self.edit(), "")
        self.write("specs/009-demo/plan.md", "# Plan\n\nchanged after approval\n")
        self.commit("edit plan")
        self.assertEqual(sdlc("gate", "approved", self.d, "--spec", "009")[0], 1)
        self.assertTrue(denied(self.edit()))

    def test_a_spec_set_back_to_draft_is_not_approved(self):
        self.approve()
        self.write("specs/009-demo/spec.md", self.read("specs/009-demo/spec.md").replace("Status: approved", "Status: draft"))
        self.commit("back to draft")
        self.assertEqual(sdlc("gate", "approved", self.d, "--spec", "009")[0], 1)
        self.assertTrue(denied(self.edit()))

    def test_a_status_word_alone_is_not_an_approval(self):
        self.write("specs/009-demo/spec.md", "# Spec\n\nStatus: approved\nApproved:\n")
        self.commit("claim approval")
        self.assertEqual(sdlc("gate", "approved", self.d, "--spec", "009")[0], 1)
        self.assertTrue(denied(self.edit()))


class TickWithoutEvidence(Project):
    RULE = "Task ticked without evidence"

    def tick(self, log=""):
        self.write("specs/009-demo/tasks.md", "# Tasks\n\n- [x] T001 do it\n\n## Progress log\n\n" + log)
        return self.commit("tick")

    def test_a_tick_with_no_log_line_or_a_made_up_commit_is_reported_by_the_gate_and_warned_by_stop(self):
        self.tick()
        self.assertEqual(sdlc("gate", "evidence-for-ticks", self.d, "--spec", "009")[0], 1)
        self.assertIn("ticked tasks without evidence", message(self.stop()))
        self.tick("- 2026-11-06 `0000000` T001 done\n")
        self.assertEqual(sdlc("gate", "evidence-for-ticks", self.d, "--spec", "009")[0], 1)
        self.assertIn("ticked tasks without evidence", message(self.stop()))

    def test_stop_only_warns_it_never_refuses(self):
        self.tick()
        out = self.stop()
        self.assertFalse(denied(out))
        self.assertNotIn("decision", json.loads(out))

    def test_a_tick_with_a_real_commit_in_the_log_passes_and_stop_is_silent(self):
        sha = self.tick()
        self.tick("- 2026-11-06 `%s` T001 done\n" % sha)
        self.assertEqual(sdlc("gate", "evidence-for-ticks", self.d, "--spec", "009")[0], 0)
        self.assertEqual(self.stop(), "")


def read_only_roles():
    names = []
    for f in sorted(os.listdir(os.path.join(ROOT, "core", "roles"))):
        with open(os.path.join(ROOT, "core", "roles", f), encoding="utf-8") as fh:
            if re.search(r"^access: read-only\s*$", fh.read().split("---")[1], re.M):
                names.append(f[:-3])
    return names


class ReviewerAbleToWrite(Project):
    RULE = "Reviewer able to write"
    targets = "claude,copilot"
    WRITERS = ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "edit", "execute")

    def test_the_reviewers_are_among_the_read_only_roles(self):
        self.assertTrue({"reviewer", "security-reviewer"} <= set(read_only_roles()))

    def tools(self, rel):
        m = re.search(r"^tools: (.+?)\s*(?:#.*)?$", self.read(rel), re.M)
        self.assertIsNotNone(m, "%s has no tools line, so it would inherit every tool" % rel)
        return m.group(1)

    def test_a_read_only_role_renders_without_a_write_or_execute_tool_for_both_hosts(self):
        for name in read_only_roles():
            for rel in (".claude/agents/sdlc-%s.md" % name, ".github/agents/sdlc-%s.agent.md" % name):
                with self.subTest(rel):
                    tools = self.tools(rel)
                    for writer in self.WRITERS:
                        self.assertNotRegex(tools, r"\b%s\b" % writer, rel)

    def test_a_full_access_role_keeps_its_tools(self):
        self.assertIn("edit", self.tools(".github/agents/sdlc-implementer.agent.md"))


def rules_in_the_adr():
    with open(ADR, encoding="utf-8") as f:
        lines = f.read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("| Must never happen"))
    rules = []
    for l in lines[start + 2:]:
        if not l.startswith("|"):
            break
        rules.append(l.split("|")[1].strip())
    return rules


class Registry(unittest.TestCase):
    def classes(self):
        return [c for c in globals().values()
                if isinstance(c, type) and issubclass(c, unittest.TestCase) and getattr(c, "RULE", None)]

    def test_every_rule_in_the_adr_has_a_test_class_and_every_class_names_a_rule(self):
        rules = rules_in_the_adr()
        self.assertEqual(len(rules), 4, rules)
        named = [c.RULE for c in self.classes()]
        self.assertEqual(sorted(named), sorted(rules))

    def test_every_rule_class_has_tests(self):
        for c in self.classes():
            self.assertTrue([n for n in dir(c) if n.startswith("test_")], c.__name__)


if __name__ == "__main__":
    unittest.main()
