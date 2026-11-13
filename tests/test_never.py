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


def clean_env(**extra):
    """The environment without GIT_* (a GIT_DIR from the caller would aim every git call at another repository)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra)
    return env


def sdlc(*args):
    p = subprocess.run([sys.executable, "-B", CLI] + list(args), capture_output=True, text=True, timeout=60,
                       env=clean_env())
    return p.returncode, p.stdout + p.stderr


GIT_CONFIG = ["-c", "user.email=a@b", "-c", "user.name=x", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
              "-c", "maintenance.auto=false", "-c", "gc.auto=0"]


def git(d, *args):
    return subprocess.run(["git", "-C", d] + GIT_CONFIG + list(args), check=True, capture_output=True, text=True,
                          env=clean_env()).stdout.strip()


def denied(out):
    """A refusal as the host reads it: the event, the decision and a reason that starts with `sdlc: refused`."""
    try:
        out = (json.loads(out).get("hookSpecificOutput") or {})
    except ValueError:
        return False
    return (out.get("hookEventName") == "PreToolUse" and out.get("permissionDecision") == "deny"
            and str(out.get("permissionDecisionReason", "")).startswith("sdlc: refused"))


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
        found = [(event, g, h["command"]) for event, groups in settings["hooks"].items() for g in groups
                 for h in g["hooks"] if h["command"].rstrip().endswith("# sdlc-kit:" + name)]
        self.assertEqual(len(found), 1, "no rendered hook entry for %s" % name)
        event, group, command = found[0]
        # The host calls the entry only for its event and, for a tool event, a tool its matcher matches in full.
        self.assertEqual(event, "Stop" if name == "stop" else "PreToolUse", name)
        if event == "PreToolUse":
            self.assertRegex(payload["tool_name"], r"^(?:%s)$" % group.get("matcher", ""), "matcher of %s" % name)
        payload = dict(payload, cwd=self.d)
        p = subprocess.run(["sh", "-c", command], input=json.dumps(payload), cwd=self.d, capture_output=True, text=True,
                           env=clean_env(CLAUDE_PROJECT_DIR=self.d), timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout.strip()

    def push(self, command="git push origin main"):
        return self.hook("bash", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}})

    def edit(self, rel="src/app.py", tool="Edit"):
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        return self.hook("edit", {"hook_event_name": "PreToolUse", "tool_name": tool,
                                  "tool_input": {key: os.path.join(self.d, rel)}})

    def stop(self):
        return self.hook("stop", {"hook_event_name": "Stop", "stop_hook_active": False})


class PushWhileTestsAreRed(Project):
    RULE = "Push while tests are red"

    def test_a_push_without_a_record_is_refused_in_its_everyday_forms(self):
        for command in ("git push origin main", "gh pr create --fill", "git -C . push", "git -c a.b=c push",
                        "sudo git push", "env X=1 git push", "timeout 30 git push", "bash -c 'git push'",
                        "sh -c \"git push origin main\"", "/usr/bin/git push", "gh -R o/r pr create",
                        "git status; git push", "git status\ngit push", "(git push)", "bash -lc 'git push'",
                        "if true; then git push; fi", "sudo -u root git push", "nohup git push", "echo x | git push"):
            with self.subTest(command):
                self.assertTrue(denied(self.push(command)))

    def test_commands_that_do_not_push_are_allowed_without_a_record(self):
        for command in ("git status", "git push --help", "echo git push", "ls"):
            with self.subTest(command):
                self.assertEqual(self.push(command), "")

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

    def test_every_hook_acts_only_when_enforce_is_the_json_true(self):
        self.write("specs/009-demo/tasks.md", "# Tasks\n\n- [x] T001 do it\n\n## Progress log\n\n")
        self.commit("an unlogged tick on a draft spec")
        for value in (None, "true", 1):
            with self.subTest(repr(value)):
                self.config(**({} if value is None else {"enforce": value}))
                self.assertEqual(self.push(), "")
                self.assertEqual(self.edit(), "")
                self.assertEqual(self.stop(), "")
        self.config(enforce=True)
        self.assertTrue(denied(self.push()))
        self.assertTrue(denied(self.edit()))
        self.assertIn("ticked tasks without evidence", message(self.stop()))

    def test_all_three_hooks_are_rendered_when_enforce_is_on(self):
        self.assertEqual(self.push("ls"), "")
        self.assertEqual(self.edit("README.md"), "")
        self.assertEqual(self.stop(), "")


class SourceEditWithoutApproval(Project):
    RULE = "Source edit on a T3 feature without approval"

    def approve(self):
        code, out = sdlc("gate", "approve", self.d, "--spec", "009", "--by", "tester")
        self.assertEqual(code, 0, out)
        self.commit("approve")

    def test_a_source_edit_on_a_draft_spec_is_refused_by_every_edit_tool(self):
        for tool, rel in (("Edit", "src/app.py"), ("Write", "src/app.py"), ("MultiEdit", "src/app.py"),
                          ("NotebookEdit", "src/n.ipynb")):
            with self.subTest(tool):
                self.assertTrue(denied(self.edit(rel, tool)))

    def test_documents_and_kit_files_are_never_refused(self):
        for rel in ("README.md", "specs/009-demo/plan.md", "docs/notes.txt", ".sdlc/config.json", ".claude/settings.json"):
            with self.subTest(rel):
                self.assertEqual(self.edit(rel), "")

    def test_an_approved_spec_allows_source_edits_until_any_approved_document_changes(self):
        for rel, text in (("specs/009-demo/spec.md", "\nA new requirement.\n"), ("specs/009-demo/plan.md", "\nchanged\n"),
                          ("specs/009-demo/tasks.md", "- [ ] T002 more\n"), ("specs/009-demo/contracts/api.md", "\nv2\n")):
            with self.subTest(rel):
                self.setUp()
                self.write("specs/009-demo/contracts/api.md", "# API\n")
                self.commit("contract")
                self.approve()
                self.assertEqual(sdlc("gate", "approved", self.d, "--spec", "009")[0], 0)
                self.assertEqual(self.edit(), "")
                body = self.read(rel)
                cut = body.find("## Progress log")  # the log is outside the digest on purpose: change the task list
                self.write(rel, body[:cut] + text + body[cut:] if cut >= 0 else body + text)
                self.commit("change after approval")
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

    def tick(self, log="", tasks="- [x] T001 do it\n"):
        self.write("specs/009-demo/tasks.md", "# Tasks\n\n" + tasks + "\n## Progress log\n\n" + log)
        return self.commit("tick")

    def test_a_tick_with_no_log_line_or_a_made_up_commit_is_reported_by_the_gate_and_warned_by_stop(self):
        self.tick()
        self.assertEqual(sdlc("gate", "evidence-for-ticks", self.d, "--spec", "009")[0], 1)
        self.assertIn("ticked tasks without evidence", message(self.stop()))
        self.tick("- 2026-11-06 `0000000` T001 done\n")
        self.assertEqual(sdlc("gate", "evidence-for-ticks", self.d, "--spec", "009")[0], 1)
        self.assertIn("ticked tasks without evidence", message(self.stop()))

    def test_a_commit_logged_for_another_task_is_not_evidence(self):
        both = "- [x] T001 do it\n- [x] T002 and this\n"
        sha = self.tick(tasks=both)
        self.tick("- 2026-11-06 `%s` T002 done\n" % sha, tasks=both)
        code, out = sdlc("gate", "evidence-for-ticks", self.d, "--spec", "009")
        self.assertEqual(code, 1, out)
        self.assertIn("T001", out)
        self.assertNotIn("T002:", out)
        self.assertIn("T001", message(self.stop()))

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
    CLAUDE_READ_ONLY = {"Read", "Grep", "Glob"}
    CLAUDE_WITH_CHECKS = CLAUDE_READ_ONLY | {"Bash"}  # a reviewing role, with enforce and a configured command
    COPILOT_READ_ONLY = {"read", "search"}

    def test_the_reviewers_are_among_the_read_only_roles(self):
        self.assertTrue({"reviewer", "security-reviewer"} <= set(read_only_roles()))

    def tools(self, rel):
        parts = self.read(rel).split("\n---\n", 1)
        self.assertTrue(parts[0].startswith("---\n"), rel)
        found = re.findall(r"^tools: (.+?)\s*(?:#.*)?$", parts[0], re.M)  # the front matter only
        self.assertEqual(len(found), 1, "%s: %d tools keys in its front matter (none inherits every tool)" % (rel, len(found)))
        return found[0]

    def test_a_read_only_role_renders_with_read_tools_only_for_both_hosts(self):
        # An allow list, not a deny list: a new tool that writes, runs commands or delegates must not slip through.
        for name in read_only_roles():
            for rel, allowed in ((".claude/agents/sdlc-%s.md" % name, self.CLAUDE_WITH_CHECKS),
                                 (".github/agents/sdlc-%s.agent.md" % name, self.COPILOT_READ_ONLY)):
                with self.subTest(rel):
                    tools = set(re.findall(r"[A-Za-z]+", self.tools(rel)))
                    self.assertTrue(tools, rel)
                    self.assertLessEqual(tools, allowed, rel)

    def test_bash_is_for_the_reviewing_roles_only_and_only_with_enforce_and_a_command(self):
        # This project has enforce and a command: the two reviewing roles hold Bash, no other read-only role does.
        for name in read_only_roles():
            tools = set(re.findall(r"[A-Za-z]+", self.tools(".claude/agents/sdlc-%s.md" % name)))
            self.assertEqual("Bash" in tools, name in ("reviewer", "security-reviewer"), name)
        # Without enforce the same install renders them read-only again.
        self.config(enforce=False, commands={"test": "true"})
        self.assertEqual(sdlc("update", self.d)[0], 0)
        for name in ("reviewer", "security-reviewer"):
            self.assertEqual(self.tools(".claude/agents/sdlc-%s.md" % name), "Read, Grep, Glob")

    def test_a_full_access_role_keeps_its_tools(self):
        self.assertIn("edit", self.tools(".github/agents/sdlc-implementer.agent.md"))

    # Spec 010: the reviewing roles' Bash is limited by the rendered bash hook, driven here as the host drives it.
    ROLES = ("sdlc-reviewer", "sdlc-security-reviewer")

    def as_role(self, command, role="sdlc-reviewer", **extra):
        return self.hook("bash", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "agent_id": "a-1",
                                  "agent_type": role, "tool_input": dict({"command": command}, **extra)})

    def allowed(self, out):
        try:
            out = json.loads(out).get("hookSpecificOutput") or {}
        except ValueError:
            return False
        return out.get("hookEventName") == "PreToolUse" and out.get("permissionDecision") == "allow"

    def edit_settings(self, fn):
        path = os.path.join(self.d, ".claude", "settings.json")
        with open(path, encoding="utf-8") as f:
            settings = json.load(f)
        fn(settings)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

    def test_a_reviewing_role_may_run_exactly_the_configured_command(self):
        for role in self.ROLES:
            with self.subTest(role):
                self.assertTrue(self.allowed(self.as_role("true", role)), role)  # explicit allow: no approval prompt

    def test_anything_else_a_reviewing_role_runs_is_refused(self):
        for role in self.ROLES:
            for command in ("true; touch x", "true && touch x", "true > out.txt", "true | tee x", "true extra",
                            "$(true)", "git status", "touch x", "python3 -c 1", ""):
                with self.subTest(role=role, command=command):
                    self.assertTrue(denied(self.as_role(command, role)), command)

    def test_the_main_session_is_unaffected(self):
        out = self.push("git status")
        self.assertFalse(denied(out), out)
        self.assertFalse(self.allowed(out), out)  # silent: the host's own permission rules decide
        explorer = self.as_role("git status", "sdlc-explorer")  # not a reviewing role: the main-session rules
        self.assertFalse(denied(explorer), explorer)

    def test_the_sandbox_flag_is_refused_even_with_the_exact_command(self):
        for role in self.ROLES:
            with self.subTest(role):
                self.assertTrue(denied(self.as_role("true", role, dangerouslyDisableSandbox=True)), role)

    def test_turning_enforce_off_without_update_refuses_the_roles(self):
        self.config(enforce=False, commands={"test": "true"})  # the role file still lists Bash until the next update
        self.assertEqual(set(re.findall(r"[A-Za-z]+", self.tools(".claude/agents/sdlc-reviewer.md"))),
                         self.CLAUDE_WITH_CHECKS)
        for role in self.ROLES:
            self.assertTrue(denied(self.as_role("true", role)), role)
        self.assertEqual(self.push("git status"), "")

    def test_a_workspace_config_refuses_the_roles(self):
        self.config(enforce=True, commands={"test": "true"}, repos={"a": {"path": "a"}})
        for role in self.ROLES:
            self.assertTrue(denied(self.as_role("true", role)), role)

    def test_an_invalid_config_refuses_the_roles_and_notes_the_main_session(self):
        self.write(".sdlc/config.json", "{not json")
        for role in self.ROLES:
            self.assertTrue(denied(self.as_role("true", role)), role)
        out = self.push("git status")
        self.assertFalse(denied(out), out)
        self.assertIn("sdlc", message(out))

    def test_a_missing_lock_refuses_the_roles(self):
        os.remove(os.path.join(self.d, ".sdlc", "lock.json"))
        for role in self.ROLES:
            self.assertTrue(denied(self.as_role("true", role)), role)
        self.assertFalse(denied(self.push("git status")))

    def test_a_hand_edited_bash_entry_takes_bash_out_at_the_next_update(self):
        self.edit_settings(lambda s: s["hooks"]["PreToolUse"][0]["hooks"][0].update(timeout=5))
        self.assertEqual(sdlc("update", self.d)[0], 2)  # the edited entry is skipped, not overwritten
        for name in ("reviewer", "security-reviewer"):
            self.assertEqual(self.tools(".claude/agents/sdlc-%s.md" % name), "Read, Grep, Glob")

    def test_a_bash_entry_moved_to_another_event_takes_bash_out(self):
        def move(s):
            group = next(g for g in s["hooks"]["PreToolUse"] if "# sdlc-kit:bash" in g["hooks"][0]["command"])
            s["hooks"]["PreToolUse"].remove(group)
            s["hooks"]["PostToolUse"] = [group]
        self.edit_settings(move)
        code, out = sdlc("check", self.d)  # the role files still list Bash: the entry under another event limits nothing
        self.assertEqual(code, 1, out)
        self.assertIn("DRIFT .claude/agents/sdlc-reviewer.md: lists Bash and the bash hook entry is not intact", out)
        sdlc("update", self.d)
        for name in ("reviewer", "security-reviewer"):
            self.assertEqual(self.tools(".claude/agents/sdlc-%s.md" % name), "Read, Grep, Glob")

    def test_an_intact_entry_left_behind_with_enforce_off_gives_no_bash(self):
        # The lock's record no longer matches, so the run keeps the entry as the project's own: still no Bash.
        path = os.path.join(self.d, ".sdlc", "lock.json")
        with open(path, encoding="utf-8") as f:
            lock = json.load(f)
        lock["settings"][".claude/settings.json"]["hooks"]["bash"] = "0" * 64
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lock, f)
        self.config(enforce=False, commands={"test": "true"})
        sdlc("update", self.d)
        self.assertIn("# sdlc-kit:bash", self.read(".claude/settings.json"))  # the entry stayed, intact
        for name in ("reviewer", "security-reviewer"):
            self.assertEqual(self.tools(".claude/agents/sdlc-%s.md" % name), "Read, Grep, Glob")

    def test_enforce_off_with_commands_renders_no_bash_at_install(self):
        project = os.path.join(self._tmp.name, "off")
        os.makedirs(os.path.join(project, ".sdlc"))
        with open(os.path.join(project, ".sdlc", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"enforce": False, "commands": {"test": "true"}}, f)
        self.assertEqual(sdlc("install", project, "--targets", "claude")[0], 0)
        for name in ("reviewer", "security-reviewer"):
            with open(os.path.join(project, ".claude", "agents", "sdlc-%s.md" % name), encoding="utf-8") as f:
                self.assertIn("\ntools: Read, Grep, Glob\n", f.read())


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
