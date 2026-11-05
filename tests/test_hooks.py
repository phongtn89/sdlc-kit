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


def run(*args, env=None, timeout=30, cwd=None):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, "-B", CLI] + list(args), capture_output=True, text=True,
                       timeout=timeout, env=e, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def git(d, *args):
    subprocess.run(["git", "-C", d, "-c", "user.email=a@b", "-c", "user.name=x"] + list(args),
                   check=True, capture_output=True, text=True)


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
        p = subprocess.run(["sh", "-c", self.entry(name)], input=payload, capture_output=True, text=True,
                           timeout=60, env=e, cwd=self.d)
        return p.returncode, p.stdout, p.stderr


def deny_reason(out):
    """The deny reason of a PreToolUse hook's stdout, or None when it is not a deny."""
    if not out.strip():
        return None
    d = json.loads(out)["hookSpecificOutput"]
    return d["permissionDecisionReason"] if d.get("permissionDecision") == "deny" else None


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
            allowed = {"json", "os", "re", "shlex", "sys", "types", "hashlib", "subprocess"}
        self.assertEqual(names - allowed - siblings, set())


if __name__ == "__main__":
    unittest.main()
