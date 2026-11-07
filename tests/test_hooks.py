import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True  # the module under test must not leave bytecode in the kit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "sdlc")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "hooks")
sys.path.insert(0, os.path.join(ROOT, "bin"))


def run(*args, env=None, timeout=30, cwd=None, cli=CLI):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, "-B", cli] + list(args), capture_output=True, text=True,
                       timeout=timeout, env=e, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def git(d, *args):
    subprocess.run(["git", "-C", d, "-c", "user.email=a@b", "-c", "user.name=x"] + list(args),
                   check=True, capture_output=True, text=True)


def slurp(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def fixture(name, cwd):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read().replace("__CWD__", cwd)


class Proj(unittest.TestCase):
    """A git project with the kit installed (claude target), enforce on and a passing test command."""

    config = {"enforce": True, "commands": {"test": "true"}}
    branch = "main"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "proj")
        os.mkdir(self.d)
        git(self.d, "init", "-q", "-b", self.branch)
        code, out, err = run("install", self.d, "--targets", "claude")
        self.assertEqual(code, 0, out + err)
        self.write_config(self.config)
        self.write_settings()
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "init")

    def write_config(self, cfg):
        p = os.path.join(self.d, ".sdlc", "config.json")
        with open(p, encoding="utf-8") as f:
            merged = json.load(f)
        merged.update(cfg)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(merged, f)

    def write_settings(self, cli=CLI):
        import sdlc_hooks
        os.makedirs(os.path.join(self.d, ".claude"), exist_ok=True)
        with open(os.path.join(self.d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"hooks": sdlc_hooks.render_entries(cli)}, f)

    def entry(self, name):
        """The command of the kit's hook entry `name` (bash, edit or stop), as rendered into settings."""
        with open(os.path.join(self.d, ".claude", "settings.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        for groups in hooks.values():
            for g in groups:
                for h in g["hooks"]:
                    if h["command"].rstrip().endswith("# sdlc-kit:" + name):
                        return h["command"]
        self.fail("no entry " + name)

    def fire(self, name, payload, env=None):
        """Run the rendered command with `sh -c`, the host's JSON on stdin. Returns (rc, stdout, stderr)."""
        e = dict(os.environ)
        e["CLAUDE_PROJECT_DIR"] = self.d
        e.update(env or {})
        p = subprocess.run(["/bin/sh", "-c", self.entry(name)], input=payload, capture_output=True, text=True,
                           timeout=60, env=e, cwd=self.d)
        return p.returncode, p.stdout, p.stderr


def deny_reason(out):
    """The deny reason of a PreToolUse hook's stdout, or None when it is not a deny."""
    if not out.strip():
        return None
    d = json.loads(out).get("hookSpecificOutput") or {}
    return d.get("permissionDecisionReason") if d.get("permissionDecision") == "deny" else None


class BashHook(Proj):
    def push(self):
        return self.fire("bash", fixture("bash-push.json", self.d))

    def test_push_without_record_is_refused(self):
        rc, out, err = self.push()
        self.assertEqual(rc, 0)
        reason = deny_reason(out)
        self.assertIsNotNone(reason, out)
        self.assertIn("sdlc verify", reason)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["hookEventName"], "PreToolUse")

    def test_push_after_clean_verify_is_allowed(self):
        code, vout, verr = run("verify", self.d)
        self.assertEqual(code, 0, vout + verr)
        self.assertIn("(clean tree)", vout.strip().splitlines()[-1])
        rc, out, err = self.push()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_push_after_a_new_commit_is_refused_again(self):
        run("verify", self.d)
        with open(os.path.join(self.d, "x.txt"), "w") as f:
            f.write("x")
        git(self.d, "add", "x.txt")
        git(self.d, "commit", "-q", "-m", "more")
        self.assertIsNotNone(deny_reason(self.push()[1]))

    def test_other_commands_are_allowed(self):
        payload = json.loads(fixture("bash-push.json", self.d))
        payload["tool_input"]["command"] = "git status"
        rc, out, err = self.fire("bash", json.dumps(payload))
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_empty_commands_refusal_says_to_set_them(self):
        self.write_config({"commands": {"test": ""}})
        reason = deny_reason(self.push()[1])
        self.assertIn("commands", reason)

    def test_pr_create_is_refused_too(self):
        payload = json.loads(fixture("bash-push.json", self.d))
        payload["tool_input"]["command"] = "gh pr create --fill"
        self.assertIsNotNone(deny_reason(self.fire("bash", json.dumps(payload))[1]))

    def test_a_chained_push_is_refused(self):
        payload = json.loads(fixture("bash-push.json", self.d))
        payload["tool_input"]["command"] = "git add -A\ngit commit -m x && git -C . push origin main"
        self.assertIsNotNone(deny_reason(self.fire("bash", json.dumps(payload))[1]))

    def test_an_untokenisable_command_is_allowed_with_a_note(self):
        payload = json.loads(fixture("bash-push.json", self.d))
        payload["tool_input"]["command"] = "echo don't\ngit push"
        rc, out, err = self.fire("bash", json.dumps(payload))
        self.assertEqual(rc, 0)
        self.assertIn("systemMessage", json.loads(out))

    def test_a_command_that_is_not_a_push_runs_no_gate(self):
        kit = os.path.join(self._tmp.name, "kit")
        shutil.copytree(os.path.join(ROOT, "bin"), os.path.join(kit, "bin"), ignore=shutil.ignore_patterns("__pycache__"))
        marker = os.path.join(self._tmp.name, "gate-ran")
        with open(os.path.join(kit, "bin", "sdlc_gate.py"), "w") as f:
            f.write("import os\nclass GateError(Exception):\n    pass\n"
                    "def run(*a):\n    open(os.environ['STUB_MARKER'], 'w').close()\n    return 0, ['gate green-at-head: PASS']\n")
        self.write_settings(os.path.join(kit, "bin", "sdlc"))
        env = {"STUB_MARKER": marker}
        for c, ran in (("git status", False), ("git push", True)):
            payload = json.loads(fixture("bash-push.json", self.d))
            payload["tool_input"]["command"] = c
            self.fire("bash", json.dumps(payload), env=env)
            self.assertEqual(os.path.exists(marker), ran, c)
            if os.path.exists(marker):
                os.remove(marker)


class ReviewerBash(Proj):
    """Spec 010: a reviewing role's Bash calls are judged by `agent_type`; the main session is not."""

    TEST_COMMAND = "python3 -m unittest discover -s tests -t ."
    config = {"enforce": True, "commands": {"test": TEST_COMMAND}}

    def call(self, command=None, agent="sdlc-reviewer", **extra):
        d = json.loads(fixture("agent-bash.json", self.d))
        if command is not None:
            d["tool_input"]["command"] = command
        if agent is None:
            d.pop("agent_type")
            d.pop("agent_id")
        else:
            d["agent_type"] = agent
        d.update(extra)
        rc, out, err = self.fire("bash", json.dumps(d))
        self.assertEqual(rc, 0, out + err)
        return out.strip()

    def decision(self, out):
        return (json.loads(out).get("hookSpecificOutput") or {}) if out else {}

    def test_the_exact_configured_command_gets_an_explicit_allow(self):
        d = self.decision(self.call())
        self.assertEqual((d.get("hookEventName"), d.get("permissionDecision")), ("PreToolUse", "allow"), d)
        self.assertTrue(d.get("permissionDecisionReason"))

    def test_any_other_command_is_refused_with_the_reason(self):
        reason = deny_reason(self.call("git status"))
        self.assertIsNotNone(reason)
        self.assertTrue(reason.startswith("sdlc: refused"), reason)
        self.assertIn("configured check commands", reason)
        self.assertIn("test", reason)  # the name of the configured command, never its string
        self.assertNotIn(self.TEST_COMMAND, reason)

    def test_the_main_session_is_judged_as_before(self):
        self.assertEqual(self.call(agent=None), "")  # the same command, no agent_type: silence
        self.assertEqual(self.call("git status", agent=None), "")
        self.assertIsNotNone(deny_reason(self.call("git push origin main", agent=None)))  # a push on red still denied

    def set_config(self, **cfg):
        with open(os.path.join(self.d, ".sdlc", "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)

    def reason(self, out):
        r = deny_reason(out)
        self.assertIsNotNone(r, out)
        self.assertTrue(r.startswith("sdlc: refused"), r)
        return r

    def test_the_security_reviewer_is_judged_like_the_reviewer(self):
        self.assertEqual(self.decision(self.call(agent="sdlc-security-reviewer")).get("permissionDecision"), "allow")
        self.reason(self.call("git status", agent="sdlc-security-reviewer"))

    def test_other_agents_and_odd_agent_types_are_the_main_session(self):
        for agent in ("sdlc-explorer", "sdlc-planner", "sdlc-implementer", "", 7, ["sdlc-reviewer"], None):
            with self.subTest(repr(agent)):
                self.assertEqual(self.call("git status", agent=agent), "")
                self.assertEqual(self.decision(self.call(agent=agent)), {})  # not allowed explicitly either
                self.assertIsNotNone(deny_reason(self.call("git push origin main", agent=agent)))

    def test_a_missing_agent_type_key_is_the_main_session(self):
        d = json.loads(fixture("agent-bash.json", self.d))
        d.pop("agent_type")
        d["tool_input"]["command"] = "git status"
        self.assertEqual(self.fire("bash", json.dumps(d))[1].strip(), "")

    def test_enforce_not_exactly_true_refuses_the_role_and_not_the_main_session(self):
        for cfg in ({"enforce": False}, {"enforce": "true"}, {"enforce": 1}, {}):
            with self.subTest(repr(cfg)):
                self.set_config(commands={"test": self.TEST_COMMAND}, **cfg)
                self.assertIn("enforce", self.reason(self.call()))
                self.assertEqual(self.call("git status", agent=None), "")

    def test_a_workspace_config_refuses_the_role(self):
        self.set_config(enforce=True, commands={"test": self.TEST_COMMAND}, repos={"a": {"path": "a"}})
        self.assertIn("workspace", self.reason(self.call()))
        self.assertIn("workspaces are not supported", json.loads(self.call("git status", agent=None))["systemMessage"])

    def test_a_call_outside_the_sandbox_is_refused_for_the_role_only(self):
        d = json.loads(fixture("agent-bash.json", self.d))
        d["tool_input"]["dangerouslyDisableSandbox"] = True
        self.assertIn("sandbox", self.reason(self.fire("bash", json.dumps(d))[1].strip()))
        d.pop("agent_type")
        self.assertEqual(self.fire("bash", json.dumps(d))[1].strip(), "")

    def test_an_unreadable_config_refuses_the_role_and_only_notes_for_the_main_session(self):
        for text in ("{not json", "[1, 2]", ""):
            with self.subTest(text):
                with open(os.path.join(self.d, ".sdlc", "config.json"), "w", encoding="utf-8") as f:
                    f.write(text)
                self.assertIn("could not be read", self.reason(self.call()))
                out = self.call("git status", agent=None)
                self.assertIn("systemMessage", json.loads(out) if out else {})

    def test_no_lock_refuses_the_role_and_is_silent_for_the_main_session(self):
        os.remove(os.path.join(self.d, ".sdlc", "lock.json"))
        self.assertIn("could not be read", self.reason(self.call()))
        self.assertEqual(self.call("git status", agent=None), "")

    def test_an_exception_inside_the_gate_refuses_the_role(self):
        import sdlc_hooks
        def broken(root):
            raise RuntimeError("boom")
        raw = fixture("agent-bash.json", self.d)
        out = sdlc_hooks.run("bash", raw, {"CLAUDE_PROJECT_DIR": self.d}, broken, None)
        self.assertIn("could not be read", self.reason(out))
        main = json.loads(raw)
        main.pop("agent_type")
        self.assertIn("RuntimeError", json.loads(sdlc_hooks.run("bash", json.dumps(main), {"CLAUDE_PROJECT_DIR": self.d}, broken, None))["systemMessage"])

    def test_input_the_hook_cannot_read_but_that_names_a_role_is_refused(self):
        import sdlc_hooks
        env = {"CLAUDE_PROJECT_DIR": self.d}
        big = '{"agent_type": "sdlc-reviewer", "pad": "' + "x" * sdlc_hooks.INPUT_CAP + '"}'
        for label, raw in (("over the cap", big), ("not json", 'oops "agent_type": "sdlc-security-reviewer" oops'),
                           ("not an object", '["agent_type", "x"] "agent_type":"sdlc-reviewer"')):
            with self.subTest(label):
                self.assertIn("could not be read", self.reason(sdlc_hooks.run("bash", raw, env, lambda r: {}, None)))
        for label, raw in (("over the cap", '{"agent_type": "sdlc-explorer", "pad": "' + "x" * sdlc_hooks.INPUT_CAP + '"}'),
                           ("not json", "oops"), ("a role name inside a value", 'oops "x": "sdlc-reviewer"')):
            with self.subTest("no role, " + label):
                self.assertIn("systemMessage", json.loads(sdlc_hooks.run("bash", raw, env, lambda r: {}, None)))

    def test_the_edit_and_stop_hooks_do_not_judge_a_role_by_its_agent_type(self):
        d = json.loads(fixture("edit-file.json", self.d))
        d["agent_type"] = "sdlc-reviewer"
        self.assertEqual(self.fire("edit", json.dumps(d))[1].strip(), "")
        s_ = json.loads(fixture("stop.json", self.d))
        s_["agent_type"] = "sdlc-reviewer"
        self.assertEqual(self.fire("stop", json.dumps(s_))[1].strip(), "")

    def allowed(self, command):
        return self.decision(self.call(command)).get("permissionDecision") == "allow"

    def test_every_string_under_a_verify_name_is_allowed_and_nothing_else_is(self):
        cmds = {"test": "run-test", "lint": "run-lint", "typecheck": "run-types", "build": "run-build",
                "integration": "run-it", "deploy": "run-deploy", "format": "run-format"}
        self.set_config(enforce=True, commands=cmds)
        for name in ("test", "lint", "typecheck", "build", "integration"):
            with self.subTest(name):
                self.assertTrue(self.allowed(cmds[name]))
        for name in ("deploy", "format"):
            with self.subTest(name):
                self.assertFalse(self.allowed(cmds[name]))  # not a name `sdlc verify` runs

    def test_non_strings_and_blank_values_are_ignored(self):
        self.set_config(enforce=True, commands={"test": 5, "lint": "   ", "typecheck": ["x"], "build": None,
                                               "integration": "run-it"})
        self.assertTrue(self.allowed("run-it"))
        self.assertFalse(self.allowed("5"))
        self.assertFalse(self.allowed(""))
        self.assertFalse(self.allowed("   "))
        reason = self.reason(self.call("x"))
        self.assertIn("(integration)", reason)

    def test_whitespace_around_the_whole_command_is_removed_and_nothing_else(self):
        for wrap in ("{}", " {}", "{} ", "\t{}\t", "{}\n", "\n{}\n", "\r\n{}\r\n", "  {}  \n"):
            with self.subTest(repr(wrap)):
                self.assertTrue(self.allowed(wrap.format(self.TEST_COMMAND)))
        self.set_config(enforce=True, commands={"test": "  run-test \n"})  # blanks in the config are stripped too
        self.assertTrue(self.allowed("run-test"))

    def test_a_chain_a_pipe_a_redirect_a_subshell_or_an_added_argument_is_another_command(self):
        c = self.TEST_COMMAND
        for command in (c + "; echo x", c + " && echo x", c + " || echo x", c + " | tee out", c + " > out.txt",
                        c + " >> out.txt", c + " & ", "(" + c + ")", "$(" + c + ")", "`" + c + "`", c + " -v",
                        c.replace(" ", "  ", 1), c.replace(" ", "\t", 1), c + "\necho x", c + "\n\nrm -rf x", "echo x\n" + c, "cd /tmp && " + c, "sudo " + c,
                        "bash -c '" + c + "'", c.replace("python3", "python"), c.upper(), c + " # comment"):
            with self.subTest(repr(command)):
                self.assertFalse(self.allowed(command))
                self.assertIn("configured check commands", self.reason(self.call(command)))

    def test_no_usable_command_refuses_every_call_with_a_reason_that_says_so(self):
        for commands in ({}, {"test": ""}, {"deploy": "run-deploy"}, "test", None, ["x"]):
            with self.subTest(repr(commands)):
                self.set_config(enforce=True, **({} if commands is None else {"commands": commands}))
                self.assertIn("none is configured", self.reason(self.call()))
                self.assertIn("none is configured", self.reason(self.call("git status")))

    def test_the_reasons_name_at_most_five_commands_and_never_a_command_string(self):
        self.set_config(enforce=True, commands={"test": "run-test", "lint": "run-lint", "typecheck": "run-types",
                                               "build": "run-build", "integration": "run-it"})
        reason = self.reason(self.call("x"))
        self.assertIn("(build, integration, lint, test, typecheck)", reason)
        for secret in ("run-test", "run-lint", "run-types", "run-build", "run-it"):
            self.assertNotIn(secret, reason)

    def test_a_configured_command_that_pushes_gets_the_push_decision(self):
        self.set_config(enforce=True, commands={"test": "git push origin main"})
        self.assertIn("sdlc verify", self.reason(self.call("git push origin main")))  # red: no record
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "config")
        self.set_config(enforce=True, commands={"test": "git push origin main", "lint": "true"})
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "config again")
        code, vout, verr = run("verify", self.d)  # `git push` itself fails in the fixture, so the record is red
        self.assertEqual(code, 1, vout + verr)
        self.assertIn("sdlc verify", self.reason(self.call("git push origin main")))

    def test_a_configured_command_that_pushes_on_a_green_record_is_allowed_explicitly(self):
        self.set_config(enforce=True, commands={"test": "true", "lint": "git push origin main"})
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "config")
        # a record that is green at HEAD: write it the way `sdlc verify` would, with every command passing
        head = subprocess.run(["git", "-C", self.d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        os.makedirs(os.path.join(self.d, ".sdlc", "evidence"), exist_ok=True)
        with open(os.path.join(self.d, ".sdlc", "evidence", "verify.json"), "w") as f:
            json.dump({"version": 1, "revision": head, "dirty": False,
                       "commands": [{"name": "test", "exit": 0, "result": "pass"}]}, f)
        self.assertEqual(self.decision(self.call("git push origin main")).get("permissionDecision"), "allow")

    def test_a_configured_command_with_an_unbalanced_quote_is_refused_for_the_role_only(self):
        self.set_config(enforce=True, commands={"test": 'echo "x'})
        reason = self.reason(self.call('echo "x'))
        self.assertIn("could not tell whether the command pushes", reason)
        self.assertNotIn("allowed", reason)
        out = self.call('echo "x', agent=None)
        self.assertIn("unbalanced quote", json.loads(out)["systemMessage"])  # the main session keeps spec 006's note

    def test_a_fixture_command_that_is_not_configured_is_not_allowed_by_name(self):
        self.write_config({"commands": {"test": "python3 -m unittest"}})
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "other command")
        self.assertIsNotNone(deny_reason(self.call()))


class Parse(unittest.TestCase):
    MATCH = [
        "git push", "git push origin main", "a && git push", "a; git push", "a | git push", "a\ngit push",
        "git -C x push", "git -c k=v push", "sudo git push", "FOO=1 git push", "env X=1 git push", "command git push",
        "sh -c 'git push'", "bash -lc \"build && git push\"", "sh -c 'a; git push'", "gh pr create", "gh -R x pr create",
        "(git push)", "{ git push; }", "if x; then git push; fi", "! git push", "env -i X=1 git push",
        "sudo -u u git push", "time -p git push", "timeout 60 git push", "git --git-dir x push", "git --work-tree=x push",
        "git status # x\ngit push", "echo a#b\ngit push", "a;\ngit push", "a &&\n git push", "a\n\ngit push",
        "(git push);", "a;;b; git push", "git push>out", "git push<in", "git push 2>&1", "git push;", "a&&git push",
        "git add . \\\n&& git push", "echo $(git push)", "echo hi\n  git push origin HEAD",
        "cat <<EOF\nhello\nEOF\ngit push", "cat <<EOF\ngit push\nEOF",
    ]
    NO_MATCH = [
        "git status", "git commit -m \"git push\"", "echo git push", "git push --help", "git push -h", "gh pr view",
        "gh pr create --help", "gh pr create -h", "git pull", "echo \"$(git push)\"", "echo `git push`", "",
        "git log --oneline", "ls; cat push", "git -C x status", "sh -c 'echo hi'", "bash script.sh", "git pushall",
        "sh -c \"sh -c 'sh -c \\\"git push\\\"'\"",
    ]
    UNSURE = ["echo don't\ngit push", "git commit -m 'unbalanced", "echo \"open"]

    def test_matches(self):
        import sdlc_hooks
        for c in self.MATCH:
            with self.subTest(c):
                self.assertIs(sdlc_hooks.pushes(c), True)

    def test_does_not_match(self):
        import sdlc_hooks
        for c in self.NO_MATCH:
            with self.subTest(c):
                self.assertIs(sdlc_hooks.pushes(c), False)

    def test_cannot_tell(self):
        import sdlc_hooks
        for c in self.UNSURE:
            with self.subTest(c):
                self.assertIsNone(sdlc_hooks.pushes(c))

    def test_lexer_is_configured_as_the_contract_says(self):
        import sdlc_hooks
        lex = sdlc_hooks.lexer("a")
        self.assertEqual(lex.commenters, "")
        self.assertTrue(lex.whitespace_split)
        self.assertEqual(lex.whitespace, " \t\r")
        for ch in ";&|()<>\n":
            self.assertIn(ch, sdlc_hooks.PUNCT)


DEMO_SPEC = """# Spec: Demo

Feature: demo
Number: 006
Status: %s <!-- draft | approved | implemented -->
Approved: <!-- filled by gate approve -->
Owner: o
Track: T3

## Requirements

- **FR-001**: The system MUST do a thing.
"""
DEMO_PLAN = "# Plan: Demo\n\nSpec: [spec.md](spec.md) · Status: draft\n\n## Summary\n\nHow.\n"
DEMO_TASKS = ("# Tasks: Demo\n\nInputs: [spec.md](spec.md) · Status: draft\n\n## S1\n\n- [ ] T001 [S1] Do it\n\n"
              "## Progress log\n\n- start\n")


class Feature(Proj):
    """A project on branch feat/006-demo with a draft spec, plan and tasks."""

    branch = "feat/006-demo"

    def setUp(self):
        super().setUp()
        self.spec_dir = os.path.join(self.d, "specs", "006-demo")
        os.makedirs(self.spec_dir)
        self.put("spec.md", DEMO_SPEC % "draft")
        self.put("plan.md", DEMO_PLAN)
        self.put("tasks.md", DEMO_TASKS)

    def put(self, name, text):
        with open(os.path.join(self.spec_dir, name), "w", encoding="utf-8") as f:
            f.write(text)

    def approve(self):
        code, out, err = run("gate", "approve", self.d, "--spec", "006", "--by", "tester")
        self.assertEqual(code, 0, out + err)

    def edit(self, fixture_name="edit-file.json", path=None, cwd=None):
        payload = json.loads(fixture(fixture_name, self.d))
        if path is not None:
            key = "notebook_path" if "notebook_path" in payload["tool_input"] else "file_path"
            payload["tool_input"][key] = path
        if cwd is not None:
            payload["cwd"] = cwd
        return self.fire("edit", json.dumps(payload))


class EditHook(Feature):
    def test_source_edit_is_refused_while_the_spec_is_a_draft(self):
        rc, out, err = self.edit()
        self.assertEqual(rc, 0)
        reason = deny_reason(out)
        self.assertIsNotNone(reason, out)
        self.assertIn("bin/app.py", reason)
        self.assertIn("006", reason)
        self.assertIn("not approved", reason)

    def test_every_editor_tool_is_covered(self):
        for name in ("edit-file.json", "write-file.json", "multiedit.json", "notebook.json"):
            with self.subTest(name):
                self.assertIsNotNone(deny_reason(self.edit(name)[1]))

    def test_source_edit_is_allowed_once_approved(self):
        self.approve()
        rc, out, err = self.edit()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_editing_an_approved_document_refuses_source_edits_again(self):
        self.approve()
        self.put("plan.md", DEMO_PLAN + "\nA new paragraph.\n")
        reason = deny_reason(self.edit()[1])
        self.assertIn("plan changed since approval", reason)

    def test_documents_and_kit_files_are_always_editable(self):
        for rel in ("specs/006-demo/spec.md", "specs/006-demo/plan.md", "README.md", ".claude/settings.json",
                    ".sdlc/config.json", ".github/x.yml", "docs/a.txt", "notes.md"):
            with self.subTest(rel):
                rc, out, err = self.edit(path=os.path.join(self.d, rel))
                self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_no_active_spec_allows(self):
        git(self.d, "checkout", "-q", "-b", "main2")
        rc, out, err = self.edit()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_statuses_without_a_feature_in_flight_allow(self):
        for status in ("implemented", "rejected", "superseded"):
            with self.subTest(status):
                self.put("spec.md", DEMO_SPEC % status)
                rc, out, err = self.edit()
                self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_unknown_or_missing_status_allows_with_a_note(self):
        self.put("spec.md", DEMO_SPEC % "proposed")
        rc, out, err = self.edit()
        self.assertIn("systemMessage", json.loads(out))
        self.put("spec.md", DEMO_SPEC.replace("Status: %s <!-- draft | approved | implemented -->\n", ""))
        rc, out, err = self.edit()
        self.assertEqual(rc, 0)
        self.assertIn("systemMessage", json.loads(out))

    def test_missing_path_allows_with_a_note(self):
        payload = json.loads(fixture("edit-file.json", self.d))
        payload["tool_input"] = {}
        rc, out, err = self.fire("edit", json.dumps(payload))
        self.assertEqual(rc, 0)
        self.assertIn("systemMessage", json.loads(out))

    def test_relative_path_resolves_against_cwd(self):
        sub = os.path.join(self.d, "bin")
        os.makedirs(sub, exist_ok=True)
        self.assertIsNotNone(deny_reason(self.edit(path="app.py", cwd=sub)[1]))
        rc, out, err = self.edit(path="../README.md", cwd=sub)
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_path_outside_the_project_is_allowed(self):
        rc, out, err = self.edit(path=os.path.join(self._tmp.name, "elsewhere.py"))
        self.assertEqual((rc, out.strip()), (0, ""), out + err)


class StopHook(Feature):
    def stop(self, active=False):
        payload = json.loads(fixture("stop.json", self.d))
        payload["stop_hook_active"] = active
        return self.fire("stop", json.dumps(payload))

    def tick(self, with_evidence):
        text = DEMO_TASKS.replace("- [ ] T001", "- [x] T001")
        if with_evidence:
            rev = subprocess.run(["git", "-C", self.d, "rev-parse", "--short", "HEAD"], capture_output=True,
                                 text=True).stdout.strip()
            text += "- 2026-11-05 `%s` — T001 done\n" % rev
        self.put("tasks.md", text)

    def test_a_tick_without_evidence_warns_and_does_not_block(self):
        self.tick(False)
        for active in (False, True):
            with self.subTest(stop_hook_active=active):
                rc, out, err = self.stop(active)
                self.assertEqual(rc, 0)
                msg = json.loads(out)
                self.assertEqual(list(msg), ["systemMessage"])
                self.assertIn("006", msg["systemMessage"])
                self.assertIn("T001", msg["systemMessage"])
                self.assertNotIn("decision", msg)

    def test_complete_evidence_is_silent(self):
        self.tick(True)
        rc, out, err = self.stop()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_no_ticks_is_silent(self):
        rc, out, err = self.stop()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_no_active_spec_is_silent(self):
        self.tick(False)
        git(self.d, "checkout", "-q", "-b", "other")
        rc, out, err = self.stop()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_a_spec_without_tasks_is_silent(self):
        os.remove(os.path.join(self.spec_dir, "tasks.md"))
        rc, out, err = self.stop()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_a_malformed_tasks_file_is_silent(self):
        with open(os.path.join(self.spec_dir, "tasks.md"), "wb") as f:
            f.write(b"\xff\xfe- [x] T001 bad")
        rc, out, err = self.stop()
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def test_it_never_refuses(self):
        self.tick(False)
        out = self.stop()[1]
        self.assertNotIn("permissionDecision", out)


class Fixtures(unittest.TestCase):
    """The host's input formats, pinned. A change here is a change in what the kit assumes of Claude Code."""

    NAMES = {"bash-push.json": ("PreToolUse", "Bash"), "edit-file.json": ("PreToolUse", "Edit"),
             "write-file.json": ("PreToolUse", "Write"), "multiedit.json": ("PreToolUse", "MultiEdit"),
             "notebook.json": ("PreToolUse", "NotebookEdit"), "stop.json": ("Stop", None)}

    def test_fixtures_carry_the_fields_the_hooks_read(self):
        for name, (event, tool) in self.NAMES.items():
            with self.subTest(name):
                d = json.loads(fixture(name, "/proj"))
                self.assertEqual(d["hook_event_name"], event)
                self.assertEqual(d["cwd"], "/proj")
                if tool:
                    self.assertEqual(d["tool_name"], tool)
                    key = {"Bash": "command", "NotebookEdit": "notebook_path"}.get(tool, "file_path")
                    self.assertIsInstance(d["tool_input"][key], str)

    def test_rendered_entries_match_the_host_format(self):
        import sdlc_hooks
        hooks = sdlc_hooks.render_entries("/kit/bin/sdlc")
        self.assertEqual(sorted(hooks), ["PreToolUse", "Stop"])
        pre = {g["matcher"]: g for g in hooks["PreToolUse"]}
        self.assertEqual(sorted(pre), ["Bash", "Edit|Write|MultiEdit|NotebookEdit"])
        self.assertNotIn("matcher", hooks["Stop"][0])
        for g in hooks["PreToolUse"] + hooks["Stop"]:
            self.assertEqual(len(g["hooks"]), 1)
            h = g["hooks"][0]
            self.assertEqual((h["type"], h["timeout"]), ("command", 90))
            self.assertTrue(h["command"].endswith("exit 0 # sdlc-kit:" + h["command"].rsplit(":", 1)[1]))
            self.assertIn("/kit/bin/sdlc", h["command"])


def load_cli():
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("sdlc_cli", CLI)
    spec = importlib.util.spec_from_loader("sdlc_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class Classify(Proj):
    def active(self, branch, cfg=None):
        git(self.d, "checkout", "-q", "-B", branch)
        import sdlc_hooks
        cli = load_cli()
        return sdlc_hooks.active_spec(self.d, cfg or {}, cli.safe_path)

    def spec(self, name, with_spec=True, root="specs"):
        d = os.path.join(self.d, root, name)
        os.makedirs(d, exist_ok=True)
        if with_spec:
            with open(os.path.join(d, "spec.md"), "w") as f:
                f.write("Status: draft\n")

    def test_active_spec_from_the_branch(self):
        self.spec("006-x")
        for b in ("feat/006-x", "006-x", "fix/006-a/b", "team/feat/006-q"):
            with self.subTest(b):
                self.assertEqual(self.active(b), "006-x")

    def test_no_active_spec(self):
        self.spec("006-x")
        self.spec("007-y", with_spec=False)
        self.spec("008-a")
        self.spec("008-b")
        for b in ("main", "feat/007-y", "feat/008-a", "feat/009-none", "feat/6-x", "feat/x-006-y"):
            with self.subTest(b):
                self.assertIsNone(self.active(b))

    def test_detached_head_has_no_active_spec(self):
        self.spec("006-x")
        git(self.d, "checkout", "-q", "--detach")
        import sdlc_hooks
        self.assertIsNone(sdlc_hooks.active_spec(self.d, {}, load_cli().safe_path))

    def test_no_git_has_no_active_spec(self):
        import sdlc_hooks
        d = os.path.join(self._tmp.name, "nogit")
        os.makedirs(os.path.join(d, "specs", "006-x"))
        open(os.path.join(d, "specs", "006-x", "spec.md"), "w").close()
        self.assertIsNone(sdlc_hooks.active_spec(d, {}, load_cli().safe_path))

    def test_unborn_branch_still_resolves(self):
        import sdlc_hooks
        d = os.path.join(self._tmp.name, "unborn")
        os.makedirs(os.path.join(d, "specs", "006-x"))
        open(os.path.join(d, "specs", "006-x", "spec.md"), "w").close()
        git(d, "init", "-q", "-b", "feat/006-x")
        self.assertEqual(sdlc_hooks.active_spec(d, {}, load_cli().safe_path), "006-x")

    def test_custom_spec_dir(self):
        self.spec("006-x", root="design/specs")
        self.assertEqual(self.active("feat/006-x", {"spec_dir": "design/specs"}), "006-x")
        self.assertIsNone(self.active("feat/006-x", {}))

    def test_source_classifier(self):
        import sdlc_hooks
        cfg = {}
        def c(rel, cwd=None):
            return sdlc_hooks.source_path(self.d, cfg, os.path.join(self.d, rel) if not rel.startswith("..") else rel,
                                          cwd or self.d)
        for rel in ("bin/x", "tests/x.py", "README.txt", "src/docs/x.py", "docs.py", "src/x.md.py", "Makefile"):
            with self.subTest(rel):
                self.assertIs(c(rel), True)
        for rel in ("specs/006-x/spec.md", ".sdlc/config.json", ".claude/settings.json", ".github/a.yml", "docs/a.py",
                    "README.md", "src/notes.md"):
            with self.subTest(rel):
                self.assertIs(c(rel), False)
        self.assertIsNone(sdlc_hooks.source_path(self.d, cfg, os.path.join(self._tmp.name, "out.py"), self.d))
        self.assertIsNone(sdlc_hooks.source_path(self.d, cfg, "../out.py", self.d))
        os.symlink(self._tmp.name, os.path.join(self.d, "link"))
        self.assertIsNone(sdlc_hooks.source_path(self.d, cfg, os.path.join(self.d, "link", "x.py"), self.d))
        self.assertIs(sdlc_hooks.source_path(self.d, {"spec_dir": "design/specs"}, os.path.join(self.d, "specs", "a.py"), self.d), True)
        self.assertIs(sdlc_hooks.source_path(self.d, {"spec_dir": "design/specs"}, os.path.join(self.d, "design", "specs", "a.py"), self.d), False)
        self.assertIs(sdlc_hooks.source_path(self.d, cfg, "bin/new.py", self.d), True)  # relative, not yet existing

    def test_spec_dir_is_normalised_like_the_gate_does(self):
        import sdlc_hooks
        for value in ("./specs", "specs/", "specs//", "./specs/", "a/../specs"):
            with self.subTest(value):
                self.assertIs(sdlc_hooks.source_path(
                    self.d, {"spec_dir": value}, os.path.join(self.d, "specs", "001-x", "plan.py"), self.d), False)


class FailOpen(Feature):
    """Whatever goes wrong inside the kit, the entry exits 0 and nothing but a computed gate failure refuses."""

    def stub_kit(self, sdlc_source, gate_source=None):
        kit = os.path.join(self._tmp.name, "stubkit")
        shutil.copytree(os.path.join(ROOT, "bin"), os.path.join(kit, "bin"),
                        ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
        if sdlc_source is not None:
            with open(os.path.join(kit, "bin", "sdlc"), "w") as f:
                f.write(sdlc_source)
        if gate_source is not None:
            with open(os.path.join(kit, "bin", "sdlc_gate.py"), "w") as f:
                f.write(gate_source)
        self.write_settings(os.path.join(kit, "bin", "sdlc"))

    def push(self, **kw):
        return self.fire("bash", fixture("bash-push.json", self.d), **kw)

    def assert_allowed(self, result, note=False):
        rc, out, err = result
        self.assertEqual(rc, 0, out + err)
        self.assertIsNone(deny_reason(out), out)
        if note:
            self.assertIn("systemMessage", json.loads(out))
        else:
            self.assertEqual(out.strip(), "", out)

    def test_kit_folder_missing(self):
        self.write_settings(os.path.join(self._tmp.name, "gone", "bin", "sdlc"))
        rc, out, err = self.push()
        self.assertEqual(rc, 0)
        self.assertIn("kit not found", json.loads(out)["systemMessage"])

    def test_an_older_kit_that_exits_2(self):
        self.stub_kit("import sys\nsys.exit(2)\n")
        self.assert_allowed(self.push())

    def test_a_crashing_kit(self):
        self.stub_kit("raise RuntimeError('boom')\n")
        self.assert_allowed(self.push())

    def test_python_missing_from_path(self):
        empty = os.path.join(self._tmp.name, "empty-bin")
        os.makedirs(empty)
        self.assert_allowed(self.push(env={"PATH": empty}))

    def test_unusable_input(self):
        for payload in ("", "not json", "[1, 2]", "42", "null", '{"tool_name": "Bash"}', '{"tool_input": []}',
                        '{"tool_name": "Bash", "tool_input": {"command": 7}}'):
            with self.subTest(payload):
                rc, out, err = self.fire("bash", payload)
                self.assertEqual(rc, 0)
                self.assertIsNone(deny_reason(out))

    def test_input_over_the_cap_is_skipped_with_a_note(self):
        big = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push " + "x" * (1 << 20)}})
        self.assert_allowed(self.fire("bash", big), note=True)

    def test_no_project_above_the_working_directory(self):
        other = os.path.join(self._tmp.name, "other")
        os.makedirs(other)
        payload = fixture("bash-push.json", other)
        self.assert_allowed(self.fire("bash", payload, env={"CLAUDE_PROJECT_DIR": other}))

    def test_workspace_config_allows_with_a_note(self):
        self.write_config({"repos": {"a": {"path": "a"}}})
        self.assert_allowed(self.push(), note=True)

    def test_a_gate_that_errors_or_raises_allows_with_a_note(self):
        for gate_src in ("class GateError(Exception):\n    pass\ndef run(*a):\n    return 2, ['sdlc: error: x']\n",
                         "class GateError(Exception):\n    pass\ndef run(*a):\n    raise RuntimeError('boom')\n"):
            with self.subTest(gate_src[-30:]):
                self.stub_kit(None, gate_src)
                self.assert_allowed(self.push(), note=True)

    def test_a_malformed_spec_allows_an_edit_with_a_note(self):
        with open(os.path.join(self.spec_dir, "spec.md"), "wb") as f:
            f.write(b"\xff\xfe")
        self.assert_allowed(self.fire("edit", fixture("edit-file.json", self.d)), note=True)

    def test_enforce_off_at_run_time_allows_silently(self):
        for value in (False, "true", 1, None):
            with self.subTest(value):
                self.write_config({"enforce": value})
                self.assert_allowed(self.push())

    def test_project_dir_falls_back_to_the_input_cwd(self):
        e = dict(os.environ)
        e.pop("CLAUDE_PROJECT_DIR", None)
        p = subprocess.run(["/bin/sh", "-c", self.entry("bash")], input=fixture("bash-push.json", self.d),
                           capture_output=True, text=True, env=e, cwd=os.path.dirname(self.d))
        self.assertEqual(p.returncode, 0)
        self.assertIsNotNone(deny_reason(p.stdout))

    def test_a_repos_config_keeps_the_stop_hook_silent(self):
        self.put("tasks.md", DEMO_TASKS.replace("- [ ] T001", "- [x] T001"))
        self.write_config({"repos": {"a": {"path": "a"}}})
        rc, out, err = self.fire("stop", fixture("stop.json", self.d))
        self.assertEqual((rc, out.strip()), (0, ""), out + err)

    def listing(self):
        out = []
        for dp, dn, fn in os.walk(self.d):
            dn[:] = [x for x in dn if x != ".git"]
            for f in fn:
                p = os.path.join(dp, f)
                out.append((os.path.relpath(p, self.d), os.path.getsize(p), os.path.getmtime(p)))
        return sorted(out)

    def test_hooks_write_nothing_and_leave_no_bytecode(self):
        before = self.listing()
        self.push()
        self.fire("edit", fixture("edit-file.json", self.d))
        self.fire("stop", fixture("stop.json", self.d))
        self.assertEqual(self.listing(), before)
        pyc = [dp for dp, dn, fn in os.walk(os.path.join(ROOT, "bin")) if "__pycache__" in dn]
        self.assertEqual(pyc, [])

    def test_an_allowing_call_is_fast(self):
        import time
        payload = json.loads(fixture("bash-push.json", self.d))
        payload["tool_input"]["command"] = "git status"
        start = time.time()
        self.fire("bash", json.dumps(payload))
        self.assertLess(time.time() - start, 1.0)


class RunUnit(unittest.TestCase):
    """`sdlc_hooks.run` called directly, so each safety net is tested without the layer above it."""

    def test_any_exception_becomes_a_note(self):
        import sdlc_hooks
        def broken(root):
            raise RuntimeError("boom")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        os.makedirs(os.path.join(d, ".sdlc"))
        open(os.path.join(d, ".sdlc", "lock.json"), "w").close()
        out = sdlc_hooks.run("bash", json.dumps({"cwd": d}), {}, broken, None)
        self.assertIn("RuntimeError", json.loads(out)["systemMessage"])

    def test_input_over_the_cap_is_skipped_even_when_it_is_valid_json(self):
        import sdlc_hooks
        raw = json.dumps({"tool_name": "Bash", "cwd": "/"}) + " " * sdlc_hooks.INPUT_CAP
        out = sdlc_hooks.run("bash", raw, {}, lambda r: {}, None)
        self.assertIn("too large", json.loads(out)["systemMessage"])


OWN = {"permissions": {"allow": ["Bash(ls)"]},
       "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}],
                 "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "after.sh"}]}]},
       "env": {"A": "1"}}


class Settings(unittest.TestCase):
    KIT = "/kit/bin/sdlc"

    def merge(self, settings, cli=None, lock=None, force=False):
        import sdlc_hooks
        return sdlc_hooks.merge(settings, sdlc_hooks.render_entries(cli or self.KIT), lock, force)

    def test_adds_three_groups_to_an_empty_settings(self):
        import copy
        new, lines, skipped, lock = self.merge({})
        self.assertEqual(sorted(new["hooks"]), ["PreToolUse", "Stop"])
        self.assertEqual(len(new["hooks"]["PreToolUse"]), 2)
        self.assertEqual(len(new["hooks"]["Stop"]), 1)
        self.assertEqual(sorted(lock["hooks"]), ["bash", "edit", "stop"])
        self.assertEqual((skipped, lock["created"]), (0, False))

    def test_keeps_the_projects_own_values_order_and_hooks(self):
        import copy
        before = copy.deepcopy(OWN)
        new, lines, skipped, lock = self.merge(OWN)
        self.assertEqual(OWN, before)  # the input is not modified
        self.assertEqual(list(new), ["permissions", "hooks", "env"])
        self.assertEqual(new["permissions"], before["permissions"])
        self.assertEqual(new["env"], before["env"])
        self.assertEqual(new["hooks"]["PostToolUse"], before["hooks"]["PostToolUse"])
        pre = new["hooks"]["PreToolUse"]
        self.assertEqual(pre[0], before["hooks"]["PreToolUse"][0])  # theirs first, same matcher kept apart
        self.assertEqual(len(pre), 3)

    def test_is_idempotent_to_the_byte(self):
        import sdlc_hooks
        first, _, _, lock = self.merge(OWN)
        second, lines, skipped, lock2 = self.merge(first, lock=lock)
        self.assertEqual((second, lines, skipped, lock2), (first, [], 0, lock))
        self.assertEqual(sdlc_hooks.dump(second, sdlc_hooks.dump(first, "")), sdlc_hooks.dump(first, ""))

    def test_a_moved_kit_replaces_the_entries_in_place(self):
        first, _, _, lock = self.merge(OWN)
        new, lines, skipped, lock2 = self.merge(first, cli="/elsewhere/bin/sdlc", lock=lock)
        self.assertEqual(skipped, 0)
        self.assertEqual(len(new["hooks"]["PreToolUse"]), 3)
        self.assertIn("/elsewhere/bin/sdlc", json.dumps(new))
        self.assertNotIn("/kit/bin/sdlc", json.dumps(new))
        self.assertEqual(new["hooks"]["PreToolUse"][0], OWN["hooks"]["PreToolUse"][0])
        self.assertNotEqual(lock2, lock)

    def test_a_hand_edited_entry_is_skipped_unless_forced(self):
        import copy
        first, _, _, lock = self.merge(OWN)
        edited = copy.deepcopy(first)
        edited["hooks"]["PreToolUse"][1]["hooks"][0]["timeout"] = 5
        new, lines, skipped, lock2 = self.merge(edited, cli="/elsewhere/bin/sdlc", lock=lock)
        self.assertEqual(skipped, 1)
        self.assertTrue(any("bash" in l and "modified locally" in l for l in lines), lines)
        self.assertEqual(new["hooks"]["PreToolUse"][1], edited["hooks"]["PreToolUse"][1])
        self.assertEqual(lock2["hooks"]["bash"], lock["hooks"]["bash"])
        forced, lines, skipped, lock3 = self.merge(edited, cli="/elsewhere/bin/sdlc", lock=lock, force=True)
        self.assertEqual(skipped, 0)
        self.assertEqual(forced["hooks"]["PreToolUse"][1]["hooks"][0]["timeout"], 90)

    def test_an_entry_without_a_lock_record_that_differs_is_modified(self):
        first, _, _, _ = self.merge(OWN)
        new, lines, skipped, lock = self.merge(first, cli="/elsewhere/bin/sdlc", lock=None)
        self.assertEqual(skipped, 3)
        self.assertEqual(new, first)

    def test_a_deleted_entry_is_added_back(self):
        first, _, _, lock = self.merge(OWN)
        del first["hooks"]["Stop"]
        new, lines, skipped, lock2 = self.merge(first, lock=lock)
        self.assertEqual(len(new["hooks"]["Stop"]), 1)
        self.assertEqual(skipped, 0)

    def test_unmergeable_shapes_are_refused_with_a_reason(self):
        import sdlc_hooks
        for bad, word in (([], "object"), ({"hooks": []}, "hooks"), ({"hooks": {"Stop": {}}}, "Stop"),
                          ({"hooks": {"Stop": ["x"]}}, "Stop"), ({"hooks": {"PreToolUse": [3]}}, "PreToolUse")):
            with self.subTest(bad):
                with self.assertRaises(sdlc_hooks.SettingsError) as cm:
                    self.merge(bad)
                self.assertIn(word, str(cm.exception))

    def test_remove_takes_out_only_the_kits_entries(self):
        import sdlc_hooks
        merged, _, _, lock = self.merge(OWN)
        new, lines, rest, empty = sdlc_hooks.remove(merged, lock)
        self.assertEqual(new, OWN)
        self.assertEqual((lines, rest, empty), ([], None, False))

    def test_remove_from_a_file_the_kit_filled_leaves_nothing(self):
        import sdlc_hooks
        merged, _, _, lock = self.merge({})
        new, lines, rest, empty = sdlc_hooks.remove(merged, lock)
        self.assertEqual((new, empty), ({}, True))

    def test_remove_keeps_a_hand_edited_entry_and_says_so(self):
        import copy
        import sdlc_hooks
        merged, _, _, lock = self.merge(OWN)
        merged["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 1
        new, lines, rest, empty = sdlc_hooks.remove(merged, lock)
        self.assertEqual(len(new["hooks"]["Stop"]), 1)
        self.assertTrue(any("KEPT" in l and "stop" in l for l in lines), lines)
        self.assertIsNone(rest)  # the kept entry is no longer managed, so the lock lets go of it
        self.assertEqual(len(new["hooks"]["PreToolUse"]), 1)

    def test_remove_does_not_touch_an_empty_hooks_object_it_did_not_empty(self):
        import sdlc_hooks
        new, lines, rest, empty = sdlc_hooks.remove({"hooks": {}, "a": 1}, {"hooks": {}, "created": False})
        self.assertEqual((new, empty), ({"hooks": {}, "a": 1}, False))

    def test_remove_ignores_marked_entries_the_lock_does_not_know(self):
        import sdlc_hooks
        merged, _, _, lock = self.merge(OWN)
        new, lines, rest, empty = sdlc_hooks.remove(merged, {"hooks": {}, "created": False})
        self.assertEqual(new, merged)

    def test_only_a_single_hook_group_with_the_marker_at_the_end_is_the_kits(self):
        import sdlc_hooks
        g = lambda c, n=1: {"hooks": [{"type": "command", "command": c}] * n}
        self.assertEqual(sdlc_hooks.group_name(g("x # sdlc-kit:bash")), "bash")
        self.assertIsNone(sdlc_hooks.group_name(g("x # sdlc-kit:bash then more")))
        self.assertIsNone(sdlc_hooks.group_name(g("x # sdlc-kit:other")))
        self.assertIsNone(sdlc_hooks.group_name(g("x # sdlc-kit:bash", 2)))
        self.assertIsNone(sdlc_hooks.group_name({"hooks": "x"}))
        self.assertIsNone(sdlc_hooks.group_name("x"))

    def test_indentation_and_final_newline(self):
        import sdlc_hooks
        for indent, text in (("\t", '{\n\t"a": 1\n}'), (4, '{\n    "a": 1\n}'), (2, '{\n  "a": 1\n}'),
                             (2, '{"a": 1}')):
            with self.subTest(repr(text)):
                settings = sdlc_hooks.load(text)
                out = sdlc_hooks.dump(settings, text)
                self.assertTrue(out.endswith("}\n"))
                self.assertEqual(sdlc_hooks.load(out), settings)
                if indent != 2 or "\n  " in text:
                    self.assertEqual(out.splitlines()[1][:len(indent) if indent == "\t" else indent],
                                     "\t" if indent == "\t" else " " * indent)

    def test_load_refuses_what_it_cannot_merge_into(self):
        import sdlc_hooks
        for text in ("", "not json", "[1]", "null", '{"a": '):
            with self.subTest(text):
                with self.assertRaises(sdlc_hooks.SettingsError):
                    sdlc_hooks.load(text)

    def test_non_ascii_values_survive(self):
        import sdlc_hooks
        text = '{"note": "größe — 日本"}'
        self.assertIn("größe — 日本", sdlc_hooks.dump(sdlc_hooks.load(text), text))


KIT_ENTRIES = ("bash", "edit", "stop")


class Bare(unittest.TestCase):
    """An empty folder to install the kit into."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "proj")
        os.mkdir(self.d)

    def path(self, *parts):
        return os.path.join(self.d, *parts)

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as f:
            return f.read()

    def write(self, text, *parts):
        os.makedirs(os.path.dirname(self.path(*parts)), exist_ok=True)
        with open(self.path(*parts), "w", encoding="utf-8") as f:
            f.write(text)

    def config(self, **cfg):
        self.write(json.dumps(cfg), ".sdlc", "config.json")

    def settings(self):
        return json.loads(self.read(".claude", "settings.json"))

    def lock(self):
        return json.loads(self.read(".sdlc", "lock.json"))

    def install(self, *extra, cli=CLI):
        return run("install", self.d, *extra, cli=cli)

    def update(self, *extra, cli=CLI):
        return run("update", self.d, *extra, cli=cli)

    def kit_commands(self, settings=None):
        s = settings or self.settings()
        return [h["command"] for groups in s["hooks"].values() for g in groups for h in g["hooks"]
                if "# sdlc-kit:" in h["command"]]


class Install(Bare):
    def test_a_symlinked_settings_file_is_left_alone_without_enforce(self):
        self.config(commands={"test": "true"})
        self.install("--targets", "claude")
        real = os.path.join(self._tmp.name, "real.json")
        with open(real, "w", encoding="utf-8") as f:
            f.write('{"a": 1}')
        os.symlink(real, self.path(".claude", "settings.json"))
        code, out, err = self.update()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("settings", out)
        self.assertEqual(slurp(real), '{"a": 1}')

    def test_an_unreadable_settings_file_is_left_alone_without_enforce(self):
        self.config(commands={"test": "true"})
        self.install("--targets", "claude")
        with open(self.path(".claude", "settings.json"), "wb") as f:
            f.write(b'{"x":"\xe9"}')
        code, out, err = self.update()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Traceback", err)

    def test_a_settings_file_the_kit_cannot_read_is_a_skip_when_enforce_is_on(self):
        self.config(enforce=True, commands={"test": "true"})
        os.makedirs(self.path(".claude"))
        with open(self.path(".claude", "settings.json"), "wb") as f:
            f.write(b'{"x":"\xe9"}')
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 2, out + err)
        self.assertIn("SKIP .claude/settings.json", out)
        self.assertNotIn("Traceback", err)
        with open(self.path(".claude", "settings.json"), "rb") as f:
            self.assertEqual(f.read(), b'{"x":"\xe9"}')

    def test_a_symlinked_settings_file_is_a_skip_when_enforce_is_on(self):
        self.config(enforce=True, commands={"test": "true"})
        real = os.path.join(self._tmp.name, "real.json")
        with open(real, "w", encoding="utf-8") as f:
            f.write('{"a": 1}')
        os.makedirs(self.path(".claude"))
        os.symlink(real, self.path(".claude", "settings.json"))
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 2, out + err)
        self.assertIn("SKIP .claude/settings.json", out)
        self.assertEqual(slurp(real), '{"a": 1}')

    def test_a_kept_entry_is_not_reported_again_after_enforce_goes_off(self):
        self.config(enforce=True, commands={"test": "true"})
        self.install("--targets", "claude")
        s = self.settings()
        s["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 1
        self.write(json.dumps(s, indent=2) + "\n", ".claude", "settings.json")
        self.config(commands={"test": "true"})
        code, out, err = self.update()
        self.assertIn("KEPT .claude/settings.json (kit hook stop", out)
        self.assertNotIn("settings", self.lock())
        code, out, err = self.update()
        self.assertNotIn("KEPT", out)
        code, out, err = run("check", self.d)
        self.assertEqual((code, out.strip()), (0, "ok"), out + err)

    def test_enforce_absent_renders_nothing(self):
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 0, out + err)
        self.assertFalse(os.path.exists(self.path(".claude", "settings.json")))
        self.assertNotIn("settings", self.lock())

    def test_only_the_json_true_turns_it_on(self):
        for value in ("true", 1, "yes", None, [True]):
            with self.subTest(repr(value)):
                shutil.rmtree(self.d)
                os.mkdir(self.d)
                self.config(enforce=value)
                code, out, err = self.install("--targets", "claude")
                self.assertEqual(code, 0, out + err)
                self.assertFalse(os.path.exists(self.path(".claude", "settings.json")))

    def test_enforce_true_renders_three_entries_from_the_lock(self):
        self.config(enforce=True, commands={"test": "true"})
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 0, out + err)
        cmds = self.kit_commands()
        self.assertEqual(len(cmds), 3)
        cli = os.path.join(self.lock()["kit_path"], "bin", "sdlc")  # FR-007: the entry names the lock's kit path
        for c in cmds:
            self.assertIn(cli, c)
        for groups in self.settings()["hooks"].values():
            for g in groups:
                self.assertEqual(g["hooks"][0]["timeout"], 90)
        self.assertEqual(self.lock()["settings"][".claude/settings.json"]["created"], True)
        self.assertEqual(sorted(self.lock()["settings"][".claude/settings.json"]["hooks"]), list(KIT_ENTRIES))

    def test_install_twice_changes_nothing(self):
        self.config(enforce=True, commands={"test": "true"})
        self.install("--targets", "claude")
        before = (self.read(".claude", "settings.json"), self.read(".sdlc", "lock.json"))
        mtime = os.stat(self.path(".claude", "settings.json")).st_mtime_ns
        code, out, err = self.update()
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.read(".claude", "settings.json"), self.read(".sdlc", "lock.json")), before)
        self.assertEqual(os.stat(self.path(".claude", "settings.json")).st_mtime_ns, mtime)  # not rewritten

    def test_the_projects_own_settings_survive_on_and_off(self):
        own = {"permissions": {"allow": ["Bash(ls)"]}, "env": {"A": "ö"},
               "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}]}}
        self.write(json.dumps(own, indent=4, ensure_ascii=False) + "\n", ".claude", "settings.json")
        self.config(enforce=True, commands={"test": "true"})
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 0, out + err)
        text = self.read(".claude", "settings.json")
        self.assertTrue(text.splitlines()[1].startswith("    \""), text[:40])
        s = self.settings()
        self.assertEqual(s["permissions"], own["permissions"])
        self.assertEqual(s["env"], own["env"])
        self.assertEqual(s["hooks"]["PreToolUse"][0], own["hooks"]["PreToolUse"][0])
        self.assertEqual(len(self.kit_commands(s)), 3)
        self.assertFalse(self.lock()["settings"][".claude/settings.json"]["created"])
        self.config(enforce=False)
        code, out, err = self.update()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.settings(), own)
        self.assertNotIn("settings", self.lock())

    def test_turning_enforce_off_removes_a_file_the_kit_created(self):
        self.config(enforce=True, commands={"test": "true"})
        self.install("--targets", "claude")
        self.config(enforce=False, commands={"test": "true"})
        code, out, err = self.update()
        self.assertEqual(code, 0, out + err)
        self.assertFalse(os.path.exists(self.path(".claude", "settings.json")))
        self.assertNotIn("settings", self.lock())

    def test_an_unmergeable_file_is_left_alone_and_reported(self):
        for text, word in (("not json", "not valid JSON"), ('{"hooks": []}', "hooks")):
            with self.subTest(text):
                shutil.rmtree(self.d)
                os.mkdir(self.d)
                self.write(text, ".claude", "settings.json")
                self.config(enforce=True, commands={"test": "true"})
                code, out, err = self.install("--targets", "claude")
                self.assertEqual(code, 2, out + err)
                self.assertIn("SKIP .claude/settings.json", out)
                self.assertIn(word, out)
                self.assertEqual(self.read(".claude", "settings.json"), text)
                self.assertNotIn("settings", self.lock())

    def test_a_hand_edited_entry_is_skipped_unless_forced(self):
        self.config(enforce=True, commands={"test": "true"})
        self.install("--targets", "claude")
        s = self.settings()
        s["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 5
        self.write(json.dumps(s, indent=2) + "\n", ".claude", "settings.json")
        edited = self.read(".claude", "settings.json")
        code, out, err = self.update()
        self.assertEqual(code, 2, out + err)
        self.assertIn("kit hook stop modified locally", out)
        self.assertEqual(self.read(".claude", "settings.json"), edited)
        code, out, err = self.update("--force")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.settings()["hooks"]["Stop"][0]["hooks"][0]["timeout"], 90)

    def test_a_deleted_entry_comes_back(self):
        self.config(enforce=True, commands={"test": "true"})
        self.install("--targets", "claude")
        s = self.settings()
        del s["hooks"]["Stop"]
        self.write(json.dumps(s, indent=2) + "\n", ".claude", "settings.json")
        code, out, err = self.update()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(self.kit_commands()), 3)

    def test_a_moved_kit_rewrites_the_entries(self):
        self.config(enforce=True, commands={"test": "true"})
        self.install("--targets", "claude")
        moved = os.path.join(self._tmp.name, "kit2")
        shutil.copytree(ROOT, moved, ignore=shutil.ignore_patterns(".git", "__pycache__", "specs", "evals"))
        code, out, err = self.update(cli=os.path.join(moved, "bin", "sdlc"))
        self.assertEqual(code, 0, out + err)
        for c in self.kit_commands():
            self.assertIn(os.path.realpath(moved), c)
            self.assertNotIn(os.path.join(ROOT, "bin", "sdlc"), c)

    def test_copilot_only_gets_a_note_and_no_hook(self):
        self.config(enforce=True, commands={"test": "true"})
        code, out, err = self.install("--targets", "copilot")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Copilot has no hook equivalent", out)
        self.assertFalse(os.path.exists(self.path(".claude", "settings.json")))

    def test_workspace_config_gets_a_note_and_no_hook(self):
        self.config(enforce=True, commands={"test": "true"}, repos={"a": {"path": "a"}})
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 0, out + err)
        self.assertIn("workspaces are not supported yet", out)
        self.assertFalse(os.path.exists(self.path(".claude", "settings.json")))

    def test_empty_commands_get_a_note(self):
        self.config(enforce=True)
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 0, out + err)
        self.assertIn("commands", out)
        self.assertIn("every push will be refused", out)
        self.assertEqual(len(self.kit_commands()), 3)

    def test_an_old_lock_without_the_key_works(self):
        self.install("--targets", "claude")
        self.assertNotIn("settings", self.lock())
        code, out, err = self.update()
        self.assertEqual(code, 0, out + err)

    def test_a_bad_settings_key_in_the_lock_is_refused(self):
        self.install("--targets", "claude")
        for bad in ([], {"../x": {"hooks": {}, "created": False}}, {".claude/settings.json": {"hooks": {"bash": 1}, "created": False}},
                    {".claude/settings.json": {"hooks": {}, "created": "yes"}}):
            with self.subTest(bad):
                lock = self.lock()
                lock["settings"] = bad
                self.write(json.dumps(lock), ".sdlc", "lock.json")
                code, out, err = self.update()
                self.assertNotEqual(code, 0)
                self.assertRegex(err + out, "invalid lock: settings|unsafe path")

    def test_the_kit_folder_gets_no_bytecode(self):
        self.config(enforce=True, commands={"test": "true"})
        self.install("--targets", "claude")
        self.update()
        self.assertEqual([dp for dp, dn, fn in os.walk(os.path.join(ROOT, "bin")) if "__pycache__" in dn], [])


class Lifecycle(Bare):
    """`check` and `uninstall` with the kit's settings entries."""

    def on(self, **extra):
        self.config(enforce=True, commands={"test": "true"}, **extra)
        code, out, err = self.install("--targets", "claude")
        self.assertEqual(code, 0, out + err)

    def check(self):
        return run("check", self.d)

    def edit_settings(self, fn):
        s = self.settings()
        fn(s)
        self.write(json.dumps(s, indent=2) + "\n", ".claude", "settings.json")

    def set_lock(self, fn):
        lock = self.lock()
        fn(lock)
        self.write(json.dumps(lock, indent=2, sort_keys=True) + "\n", ".sdlc", "lock.json")

    def test_check_is_ok_after_install(self):
        self.on()
        code, out, err = self.check()
        self.assertEqual((code, out.strip()), (0, "ok"), out + err)

    def test_check_reports_an_edited_entry(self):
        self.on()

        def tweak(s):
            s["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 5
        self.edit_settings(tweak)
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip().splitlines(), ["DRIFT .claude/settings.json: kit hook bash edited"])

    def test_check_reports_a_missing_entry_and_a_missing_file(self):
        self.on()

        def drop(s):
            s["hooks"]["Stop"] = []
        self.edit_settings(drop)
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip().splitlines(), ["DRIFT .claude/settings.json: kit hook stop missing"])
        os.remove(self.path(".claude", "settings.json"))
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(out.strip().splitlines(),
                         ["DRIFT .claude/settings.json: kit hook %s missing" % n for n in KIT_ENTRIES])

    def test_check_ignores_the_projects_own_entries(self):
        self.on()

        def add(s):
            s["hooks"]["PreToolUse"].append({"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]})
            s["permissions"] = {"allow": []}
        self.edit_settings(add)
        code, out, err = self.check()
        self.assertEqual((code, out.strip()), (0, "ok"), out + err)

    def test_check_reports_a_settings_file_it_cannot_read(self):
        self.on()
        self.write("{not json", ".claude", "settings.json")
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertIn("DRIFT .claude/settings.json:", out)

    def test_a_missing_kit_path_is_drift_when_hooks_are_recorded(self):
        self.on()
        gone = os.path.join(self._tmp.name, "gone")
        self.set_lock(lambda l: l.update(kit_path=gone))
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertIn("KIT-PATH-MISSING %s" % gone, out.splitlines())

    def test_a_missing_kit_path_is_drift_when_enforce_is_on(self):
        self.on()
        gone = os.path.join(self._tmp.name, "gone")
        self.set_lock(lambda l: (l.update(kit_path=gone), l.pop("settings")))
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertIn("KIT-PATH-MISSING %s" % gone, out.splitlines())

    def test_a_missing_kit_path_is_only_a_note_without_hooks(self):
        self.config(commands={"test": "true"})
        self.install("--targets", "claude")
        gone = os.path.join(self._tmp.name, "gone")
        self.set_lock(lambda l: l.update(kit_path=gone))
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertIn("NOTE KIT-PATH-MISSING %s" % gone, out.splitlines())
        self.assertNotIn("\nKIT-PATH-MISSING", "\n" + out)

    def test_a_lock_without_kit_path_is_fine(self):
        self.config(commands={"test": "true"})
        self.install("--targets", "claude")
        self.set_lock(lambda l: l.pop("kit_path"))
        code, out, err = self.check()
        self.assertEqual((code, out.strip()), (0, "ok"), out + err)

    def test_enforce_on_with_no_recorded_hooks_is_a_note(self):
        self.config(commands={"test": "true"})
        self.install("--targets", "claude")
        self.config(enforce=True, commands={"test": "true"})
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertIn("NOTE enforce is true but the lock records no hooks (run update)", out.splitlines())

    def test_uninstall_removes_exactly_the_kit_entries(self):
        own = {"permissions": {"allow": ["Bash(ls)"]},
               "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}]}}
        self.write(json.dumps(own, indent=2) + "\n", ".claude", "settings.json")
        self.on()
        self.assertEqual(len(self.kit_commands()), 3)
        code, out, err = run("uninstall", self.d)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.settings(), own)
        self.assertFalse(os.path.exists(self.path(".sdlc", "lock.json")))

    def test_uninstall_deletes_a_file_the_kit_created(self):
        self.on()
        code, out, err = run("uninstall", self.d)
        self.assertEqual(code, 0, out + err)
        self.assertFalse(os.path.exists(self.path(".claude", "settings.json")))

    def test_uninstall_keeps_a_hand_edited_entry(self):
        self.on()

        def tweak(s):
            s["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 5
        self.edit_settings(tweak)
        code, out, err = run("uninstall", self.d)
        self.assertEqual(code, 0, out + err)
        self.assertIn("KEPT .claude/settings.json (kit hook bash modified locally, no longer managed)",
                      out.splitlines())
        names = [c.rsplit("# sdlc-kit:", 1)[1] for c in self.kit_commands()]
        self.assertEqual(names, ["bash"])
        self.assertFalse(os.path.exists(self.path(".sdlc", "lock.json")))

    def test_uninstall_leaves_a_broken_settings_file_alone(self):
        self.on()
        self.write("{not json", ".claude", "settings.json")
        code, out, err = run("uninstall", self.d)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.read(".claude", "settings.json"), "{not json")
        self.assertIn("SKIP .claude/settings.json", out)

    def test_a_symlinked_settings_file_does_not_stop_check_or_uninstall(self):
        self.on()
        real = os.path.join(self._tmp.name, "real.json")
        shutil.move(self.path(".claude", "settings.json"), real)
        os.symlink(real, self.path(".claude", "settings.json"))
        code, out, err = self.check()
        self.assertEqual(code, 1, out + err)
        self.assertIn("DRIFT .claude/settings.json:", out)
        code, out, err = run("uninstall", self.d)
        self.assertEqual(code, 0, out + err)
        self.assertIn("SKIP .claude/settings.json", out)
        self.assertFalse(os.path.exists(self.path(".sdlc", "lock.json")))
        self.assertIn("sdlc-kit", slurp(real))  # the target of the link is untouched

    def test_uninstall_without_hooks_does_not_touch_settings(self):
        self.write('{"a":1}', ".claude", "settings.json")
        self.config(commands={"test": "true"})
        self.install("--targets", "claude")
        mtime = os.stat(self.path(".claude", "settings.json")).st_mtime_ns
        code, out, err = run("uninstall", self.d)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.read(".claude", "settings.json"), '{"a":1}')
        self.assertEqual(os.stat(self.path(".claude", "settings.json")).st_mtime_ns, mtime)

    def test_the_kit_folder_gets_no_bytecode_across_the_lifecycle(self):
        self.on()
        self.check()
        run("uninstall", self.d)
        self.assertEqual([dp for dp, dn, fn in os.walk(os.path.join(ROOT, "bin")) if "__pycache__" in dn], [])


class AtomicWrite(unittest.TestCase):
    def test_a_failed_replace_leaves_the_file_and_no_temp(self):
        import sdlc_hooks
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        target = os.path.join(d, "settings.json")
        with open(target, "w") as f:
            f.write("old")
        os.chmod(target, 0o640)
        def boom(a, b):
            raise OSError("no")
        with self.assertRaises(OSError):
            sdlc_hooks.write_atomic(target, b"new", replace=boom)
        self.assertEqual(slurp(target), "old")
        self.assertEqual(os.listdir(d), ["settings.json"])
        sdlc_hooks.write_atomic(target, b"new")
        self.assertEqual(slurp(target), "new")
        self.assertEqual(os.stat(target).st_mode & 0o777, 0o640)

    def test_creates_missing_folders(self):
        import sdlc_hooks
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        target = os.path.join(d, "a", "b.json")
        sdlc_hooks.write_atomic(target, b"x")
        self.assertEqual(slurp(target), "x")


class SpacedKitPath(unittest.TestCase):
    def test_the_entry_runs_a_kit_installed_under_a_path_with_a_space(self):
        import sdlc_hooks
        with tempfile.TemporaryDirectory() as d:
            kit = os.path.join(d, "My Projects", "sdlc kit", "bin")
            os.makedirs(kit)
            cli = os.path.join(kit, "sdlc")
            with open(cli, "w") as f:
                f.write("import sys\nprint('ran', sys.argv[1:])\n")
            p = subprocess.run(["sh", "-c", sdlc_hooks.command(cli, "bash")], capture_output=True, text=True)
            self.assertEqual((p.returncode, p.stdout.strip()), (0, "ran ['hook', 'bash']"), p.stdout + p.stderr)


class Imports(unittest.TestCase):
    def test_only_stdlib_and_sibling_modules(self):
        path = os.path.join(ROOT, "bin", "sdlc_hooks.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                names.add(n.module.split(".")[0])
        allowed = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else None
        siblings = {"sdlc_gate", "sdlc_verify"}
        if allowed is None:
            allowed = {"copy", "json", "os", "re", "shlex", "stat", "sys", "tempfile", "types", "hashlib", "subprocess"}
        self.assertEqual(names - allowed - siblings, set())


if __name__ == "__main__":
    unittest.main()
