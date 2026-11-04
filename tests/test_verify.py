import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True  # the module under test must not leave bytecode in the kit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "sdlc")
PY = shlex.quote(sys.executable)
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def py(code):
    """A shell command line that runs a python one-liner."""
    return "%s -c %s" % (PY, shlex.quote(code))


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

    def p(self, rel):
        return os.path.join(self.d, *rel.split("/"))

    def config(self, commands=None, **extra):
        cfg = {"commands": commands or {}}
        cfg.update(extra)
        os.makedirs(self.p(".sdlc"), exist_ok=True)
        with open(self.p(".sdlc/config.json"), "w") as f:
            json.dump(cfg, f)

    def record(self):
        with open(self.p(".sdlc/evidence/verify.json")) as f:
            return json.load(f)

    def verify(self, *extra, **kw):
        return run("verify", self.d, *extra, **kw)

    def repo(self):
        git(self.d, "init", "-q")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "init")


class GreenRun(Proj):
    def test_one_passing_command_exits_0_with_a_record_and_a_summary(self):
        self.config({"test": py("pass")})
        code, out, err = self.verify()
        self.assertEqual(code, 0, out + err)
        lines = out.strip().split("\n")
        self.assertRegex(lines[0], r"^verify test: pass \(\d+\.\d s\)$")
        self.assertEqual(lines[-1], "verify: PASSED (no revision, not verified at HEAD)")
        rec = self.record()
        self.assertEqual(rec["version"], 1)
        self.assertRegex(rec["started"], TS_RE)
        self.assertRegex(rec["finished"], TS_RE)
        self.assertIsNone(rec["revision"])
        self.assertIs(rec["dirty"], False)
        c = rec["commands"]
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0]["name"], c[0]["command"], c[0]["exit"], c[0]["result"]), ("test", py("pass"), 0, "pass"))
        self.assertIsInstance(c[0]["seconds"], float)

    def test_commands_run_once_in_fixed_order_and_empty_ones_are_skipped(self):
        log = self.p("order.log")
        def add(n):
            return py("open(%r,'a').write(%r+'\\n')" % (log, n))
        self.config({"integration": add("integration"), "build": add("build"), "test": add("test"),
                     "lint": "", "typecheck": add("typecheck")})
        code, out, err = self.verify()
        self.assertEqual(code, 0, out + err)
        with open(log) as f:
            self.assertEqual(f.read().split(), ["test", "typecheck", "build", "integration"])
        self.assertEqual([c["name"] for c in self.record()["commands"]], ["test", "typecheck", "build", "integration"])

    def test_standard_input_is_closed(self):
        self.config({"test": py("import sys; sys.exit(0 if sys.stdin.read() == '' else 1)")})
        self.assertEqual(self.verify(timeout=10)[0], 0)

    def test_runs_through_a_symlink_to_the_cli(self):
        link = os.path.join(self._tmp.name, "sdlc-link")
        os.symlink(CLI, link)
        self.config({"test": py("pass")})
        code, out, err = run("verify", self.d, cli=link)
        self.assertEqual(code, 0, out + err)


class Isolation(Proj):
    def listing(self, d):
        return sorted(os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs)

    def test_hostile_environment_and_arguments_run_nothing(self):
        marker = self.p("pwned")
        self.config({"test": py("pass")})
        env = {k: py("open(%r,'w')" % marker) for k in ("SDLC_VERIFY_COMMAND", "COMMANDS_TEST", "VERIFY_COMMAND")}
        code, out, err = self.verify(env=env)
        self.assertEqual(code, 0, out + err)
        self.assertFalse(os.path.exists(marker))
        code, out, err = self.verify("--command", "touch " + marker)
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(marker))

    def test_default_config_works_and_nothing_is_left_outside_the_project_or_in_the_kit(self):
        self.config({"test": py("pass")})  # no enforce, no usage
        before = (self.listing(os.path.join(ROOT, "bin")), self.listing(self._tmp.name))
        self.assertEqual(self.verify()[0], 0)
        after = (self.listing(os.path.join(ROOT, "bin")), self.listing(self._tmp.name))
        self.assertEqual(before[0], after[0])  # no __pycache__ in the kit
        new_in_parent = set(after[1]) - set(before[1])
        self.assertEqual({os.path.relpath(f, self._tmp.name) for f in new_in_parent}, {os.path.join("proj", ".sdlc", "evidence", "verify.json")})


class RedRun(Proj):
    def test_failing_command_exits_1_and_later_commands_still_run(self):
        log = self.p("later.log")
        self.config({"test": py("print('boom'); import sys; sys.exit(3)"), "lint": py("open(%r,'w').write('ran')" % log)})
        code, out, err = self.verify()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(open(log).read(), "ran")
        self.assertIn("verify test: FAIL exit 3 (", out)
        self.assertIn("boom", out)
        self.assertIn("verify lint: pass (", out)
        self.assertEqual(out.strip().split("\n")[-1], "verify: FAILED (no revision, not verified at HEAD)")
        rec = self.record()
        self.assertEqual([(c["exit"], c["result"]) for c in rec["commands"]], [(3, "fail"), (0, "pass")])

    def test_tail_is_the_last_20_lines_cut_to_400_chars_and_2000_in_all(self):
        self.config({"test": py("import sys\nfor i in range(100): print('L%03d' % i + 'x' * 500)\nsys.exit(1)")})
        out = self.verify()[1]
        self.assertNotIn("L079", out)
        self.assertIn("L099", out)
        body = [l for l in out.split("\n") if l.startswith("L0")]
        self.assertTrue(all(len(l) <= 400 for l in body))
        self.assertLessEqual(len("\n".join(body)), 2000)

    def test_a_command_killing_itself_with_signal_9_records_exit_minus_9(self):
        self.config({"test": py("import os, signal; os.kill(os.getpid(), signal.SIGKILL)")})
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assertEqual(self.record()["commands"][0]["exit"], -9)
        self.assertIn("FAIL exit -9", out)


class NothingToRun(Proj):
    def test_no_command_is_exit_2_and_no_record(self):
        for cmds in ({}, {"test": ""}, {"test": "   ", "lint": None}):
            self.config(cmds)
            code, out, _ = self.verify()
            self.assertEqual(code, 2)
            self.assertEqual(out.strip().split("\n")[-1], "verify: NOTHING VERIFIED (no command configured)")
            self.assertFalse(os.path.exists(self.p(".sdlc/evidence/verify.json")))

    def test_existing_record_is_left_untouched(self):
        self.config({"test": py("pass")})
        self.verify()
        before = open(self.p(".sdlc/evidence/verify.json")).read()
        self.config({})
        self.assertEqual(self.verify()[0], 2)
        self.assertEqual(open(self.p(".sdlc/evidence/verify.json")).read(), before)

    def test_no_config_file_at_all_is_nothing_verified(self):
        code, out, _ = self.verify()
        self.assertEqual(code, 2)
        self.assertIn("NOTHING VERIFIED", out)


class Timeout(Proj):
    def pid_alive(self, pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def test_timeout_kills_the_group_including_a_child_and_exits_1(self):
        pidfile = self.p("child.pid")
        code_ = ("import subprocess,sys,time\n"
                 "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                 "open(%r,'w').write(str(c.pid))\ntime.sleep(60)" % pidfile)
        self.config({"test": py(code_)}, verify={"timeout_seconds": 3})
        code, out, _ = self.verify(timeout=20)
        self.assertEqual(code, 1)
        self.assertIn("verify test: TIMEOUT after 3 s", out)
        rec = self.record()["commands"][0]
        self.assertEqual((rec["exit"], rec["result"]), ("timeout", "timeout"))
        pid = int(open(pidfile).read())
        for _ in range(20):
            if not self.pid_alive(pid):
                break
            import time; time.sleep(0.1)
        self.assertFalse(self.pid_alive(pid))

    def test_a_child_in_a_new_session_holding_the_output_does_not_hang_verify(self):
        pidfile = self.p("daemon.pid")
        code_ = ("import subprocess,sys\n"
                 "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)\n"
                 "open(%r,'w').write(str(c.pid))" % pidfile)
        self.config({"test": py(code_)})
        try:
            code, out, _ = self.verify(timeout=15)
            self.assertEqual(code, 0, out)
        finally:
            try:
                os.kill(int(open(pidfile).read()), 9)
            except (OSError, ValueError, FileNotFoundError):
                pass

    def test_a_background_child_in_the_group_is_killed_after_a_normal_exit(self):
        pidfile = self.p("bg.pid")
        code_ = ("import subprocess,sys\n"
                 "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                 "open(%r,'w').write(str(c.pid))" % pidfile)
        self.config({"test": py(code_)})
        self.assertEqual(self.verify()[0], 0)
        pid = int(open(pidfile).read())
        import time
        for _ in range(20):
            if not self.pid_alive(pid):
                break
            time.sleep(0.1)
        self.assertFalse(self.pid_alive(pid))

    def test_sigterm_kills_the_running_group_writes_no_record_and_exits_1(self):
        import signal, time
        pidfile = self.p("run.pid")
        code_ = ("import os,time\nopen(%r,'w').write(str(os.getpid()))\ntime.sleep(60)" % pidfile)
        self.config({"test": py(code_)})
        p = subprocess.Popen([sys.executable, "-B", CLI, "verify", self.d], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(100):
            if os.path.exists(pidfile) and open(pidfile).read():
                break
            time.sleep(0.1)
        child = int(open(pidfile).read())
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=15)
        self.assertEqual(p.returncode, 1)
        self.assertIn("verify: interrupted, no record written", err)
        self.assertFalse(os.path.exists(self.p(".sdlc/evidence/verify.json")))
        for _ in range(20):
            if not self.pid_alive(child):
                break
            time.sleep(0.1)
        self.assertFalse(self.pid_alive(child))


class CannotRun(Proj):
    def test_exit_127_is_a_failure_with_that_code(self):
        self.config({"test": "definitely-not-a-real-command-xyz"})
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assertEqual(self.record()["commands"][0]["exit"], 127)
        self.assertEqual(self.record()["commands"][0]["result"], "fail")

    def test_launch_error_is_recorded_not_started_with_the_error_text(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import sdlc_verify
        from unittest import mock
        with mock.patch.object(sdlc_verify.subprocess, "Popen", side_effect=OSError("cannot fork")):
            entry, tail = sdlc_verify.run_command("test", "x", self.d, 5)
        self.assertEqual((entry["exit"], entry["result"], entry["error"]), ("not started", "fail", "cannot fork"))
        self.assertIn("NOT STARTED (cannot fork)", sdlc_verify.summary_line(entry, 5))

    def test_nul_and_non_string_commands_are_config_errors(self):
        for bad in ("a\u0000b", 5, ["x"]):
            self.config({"test": bad})
            code, out, _ = self.verify()
            self.assertEqual(code, 2, bad)
            self.assertIn("commands.test", out)


class ConfigErrors(Proj):
    def test_each_bad_config_is_exit_2_before_anything_runs(self):
        marker = self.p("ran")
        ok = {"test": py("open(%r,'w')" % marker)}
        cases = [
            ("{not json", None),
            ("[1]", None),
            (json.dumps({"commands": [1]}), None),
            (json.dumps({"commands": ok, "verify": []}), None),
            (json.dumps({"commands": ok, "repos": []}), None),
            (json.dumps({"commands": ok, "verify": {"timeout_seconds": 0}}), None),
            (json.dumps({"commands": ok, "verify": {"timeout_seconds": True}}), None),
            (json.dumps({"commands": ok, "verify": {"timeout_seconds": "5"}}), None),
        ]
        for text, _ in cases:
            os.makedirs(self.p(".sdlc"), exist_ok=True)
            with open(self.p(".sdlc/config.json"), "w") as f:
                f.write(text)
            code, out, err = self.verify()
            self.assertEqual(code, 2, (text, out, err))
            self.assertFalse(os.path.exists(marker), text)

    def test_missing_folder_and_unknown_option_are_exit_2(self):
        self.assertEqual(run("verify", os.path.join(self._tmp.name, "nope"))[0], 2)
        self.config({"test": py("pass")})
        self.assertEqual(self.verify("--bogus")[0], 2)


class Revision(Proj):
    def head(self):
        return subprocess.run(["git", "-C", self.d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    def test_clean_repo_records_full_head_and_clean_final_line(self):
        self.config({"test": py("pass")})
        self.repo()
        code, out, _ = self.verify()
        self.assertEqual(code, 0, out)
        rec = self.record()
        self.assertEqual(rec["revision"], self.head())
        self.assertIs(rec["dirty"], False)
        self.assertEqual(out.strip().split("\n")[-1], "verify: PASSED at %s (clean tree)" % self.head()[:7])

    def test_two_runs_in_a_row_are_both_clean(self):
        self.config({"test": py("pass")})
        self.repo()
        self.verify()
        code, out, _ = self.verify()
        self.assertIs(self.record()["dirty"], False, out)

    def test_uncommitted_change_is_dirty_and_not_verified_at_head(self):
        self.config({"test": py("pass")})
        self.repo()
        with open(self.p("new.txt"), "w") as f:
            f.write("x")
        code, out, _ = self.verify()
        self.assertEqual(code, 0)
        self.assertIs(self.record()["dirty"], True)
        self.assertEqual(out.strip().split("\n")[-1], "verify: PASSED at %s (dirty tree, not verified at HEAD)" % self.head()[:7])
        self.assertNotIn("green", out)

    def test_a_command_that_edits_a_file_makes_the_run_dirty(self):
        self.config({"test": py("open('made.txt','w').write('x')")})
        self.repo()
        self.verify()
        self.assertIs(self.record()["dirty"], True)

    def test_a_command_that_commits_and_leaves_a_change_has_no_revision_and_stays_dirty(self):
        script = ("import subprocess\n"
                  "g = ['git', '-c', 'user.email=a@b', '-c', 'user.name=x']\n"
                  "open('a.txt','w').write('1')\nsubprocess.run(g+['add','a.txt'], check=True)\n"
                  "subprocess.run(g+['commit','-qm','c'], check=True)\nopen('b.txt','w').write('2')")
        self.config({"test": py(script)})
        self.repo()
        self.verify()
        rec = self.record()
        self.assertIsNone(rec["revision"])
        self.assertIs(rec["dirty"], True)

    def test_no_repository_and_no_commit_both_mean_no_revision(self):
        self.config({"test": py("pass")})
        self.assertIsNone((self.verify(), self.record())[1]["revision"])
        git(self.d, "init", "-q")
        out = self.verify()[1]
        rec = self.record()
        self.assertIsNone(rec["revision"])
        self.assertIs(rec["dirty"], False)
        self.assertIn("no revision, not verified at HEAD", out)

    def test_after_a_new_commit_the_old_record_is_not_green_at_the_new_head(self):
        self.config({"test": py("pass")})
        self.repo()
        self.verify()
        old = self.record()["revision"]
        with open(self.p("n.txt"), "w") as f:
            f.write("n")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "n")
        self.assertNotEqual(old, self.head())
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import sdlc_verify
        self.assertIs(sdlc_verify.green_at_head(self.record(), self.head()), False)


class FakeGit(Proj):
    """A fake `git` first on PATH that logs each call and can fail on `status`."""
    def fake(self, fail_status=False, answer_head="a" * 40):
        bindir = os.path.join(self._tmp.name, "bin")
        os.makedirs(bindir, exist_ok=True)
        log = os.path.join(self._tmp.name, "git.log")
        script = ("#!/bin/sh\necho \"$*\" >> %s\n"
                  "case \"$*\" in\n*rev-parse*) echo %s; exit 0;;\n*status*) %s;;\nesac\nexit 0\n"
                  % (log, answer_head, "exit 1" if fail_status else "exit 0"))
        path = os.path.join(bindir, "git")
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        return {"PATH": bindir + os.pathsep + os.environ["PATH"]}, log


class GitCalls(FakeGit):
    def test_a_failed_status_reads_as_dirty(self):
        self.config({"test": py("pass")})
        env, _ = self.fake(fail_status=True)
        code, out, _ = self.verify(env=env)
        self.assertEqual(code, 0, out)
        self.assertIs(self.record()["dirty"], True)
        self.assertIn("dirty tree", out)

    def test_at_most_four_git_calls_in_a_repository(self):
        self.config({"test": py("pass")})
        env, log = self.fake()
        self.assertEqual(self.verify(env=env)[0], 0)
        calls = open(log).read().strip().split("\n")
        self.assertEqual(len(calls), 4, calls)
        self.assertTrue(all("--untracked-files=normal" in c for c in calls if "status" in c))

    def test_one_git_call_without_a_commit_and_none_without_git(self):
        self.config({"test": py("pass")})
        bindir = os.path.join(self._tmp.name, "bin")
        os.makedirs(bindir)
        log = os.path.join(self._tmp.name, "git.log")
        with open(os.path.join(bindir, "git"), "w") as f:
            f.write("#!/bin/sh\necho \"$*\" >> %s\nexit 128\n" % log)
        os.chmod(os.path.join(bindir, "git"), 0o755)
        self.verify(env={"PATH": bindir + os.pathsep + os.environ["PATH"]})
        self.assertEqual(len(open(log).read().strip().split("\n")), 1)
        # no git on PATH at all (python is called by absolute path)
        empty = os.path.join(self._tmp.name, "empty")
        os.makedirs(empty)
        code, out, _ = self.verify(env={"PATH": empty})
        self.assertEqual(code, 0, out)
        self.assertIsNone(self.record()["revision"])


class GreenAtHead(unittest.TestCase):
    H = "a" * 40

    def rec(self, **kw):
        r = {"version": 1, "started": "t", "finished": "t", "revision": self.H, "dirty": False,
             "commands": [{"name": "test", "command": "x", "exit": 0, "seconds": 0.1, "result": "pass"}]}
        r.update(kw)
        return r

    def green(self, rec, head=H):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import sdlc_verify
        return sdlc_verify.green_at_head(rec, head)

    def test_true_only_for_a_clean_current_all_pass_record(self):
        self.assertIs(self.green(self.rec()), True)

    def test_false_cases(self):
        bad = [self.rec(revision="b" * 40), self.rec(dirty=True), self.rec(revision=None), self.rec(commands=[]),
               self.rec(commands=[{"name": "t", "command": "x", "exit": 1, "seconds": 0, "result": "fail"}]),
               self.rec(commands=[{"name": "t", "command": "x", "exit": "timeout", "seconds": 0, "result": "timeout"}])]
        for r in bad:
            self.assertIs(self.green(r), False, r)
        self.assertIs(self.green(self.rec(), head=None), False)

    def test_malformed_records_are_false_and_never_raise(self):
        bad = [None, [], "x", {}, self.rec(version=2), self.rec(commands="x"), self.rec(commands=[1]),
               self.rec(commands=[{"result": "pass"}]), {k: v for k, v in self.rec().items() if k != "dirty"},
               self.rec(dirty="no"), self.rec(revision=5)]
        for r in bad:
            self.assertIs(self.green(r), False, r)


class GitRun(Proj):
    def mod(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import sdlc_verify
        return sdlc_verify

    def fake(self, body):
        bindir = os.path.join(self._tmp.name, "gbin")
        os.makedirs(bindir, exist_ok=True)
        with open(os.path.join(bindir, "git"), "w") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(os.path.join(bindir, "git"), 0o755)
        return bindir

    def with_path(self, bindir):
        from unittest import mock
        return mock.patch.dict(os.environ, {"PATH": bindir + os.pathsep + os.environ["PATH"]})

    def test_ok_fail_timeout_and_nogit_statuses(self):
        v = self.mod()
        with self.with_path(self.fake("echo hi")):
            self.assertEqual(v.git_run(self.d, "x"), ("ok", "hi\n"))
        with self.with_path(self.fake("exit 3")):
            self.assertEqual(v.git_run(self.d, "x")[0], "fail")
        from unittest import mock
        with self.with_path(self.fake("sleep 5")), mock.patch.object(v, "GIT_TIMEOUT", 0.2):
            self.assertEqual(v.git_run(self.d, "x")[0], "timeout")
        from unittest import mock
        with mock.patch.dict(os.environ, {"PATH": os.path.join(self._tmp.name, "nowhere")}):
            self.assertEqual(v.git_run(self.d, "x"), ("nogit", ""))

    def test_input_reaches_standard_input(self):
        v = self.mod()
        with self.with_path(self.fake("cat")):
            self.assertEqual(v.git_run(self.d, "x", input="abc\n"), ("ok", "abc\n"))

    def test_git_call_keeps_its_old_answers(self):
        v = self.mod()
        with self.with_path(self.fake("echo hi")):
            self.assertEqual(v.git_call(self.d, "x"), (True, "hi\n"))
        with self.with_path(self.fake("exit 3")):
            self.assertEqual(v.git_call(self.d, "x"), (False, ""))
        from unittest import mock
        with mock.patch.dict(os.environ, {"PATH": os.path.join(self._tmp.name, "nowhere")}):
            self.assertEqual(v.git_call(self.d, "x"), (None, ""))


class GreenReason(unittest.TestCase):
    H = "a" * 40

    def rec(self, **kw):
        r = {"version": 1, "started": "t", "finished": "t", "revision": self.H, "dirty": False,
             "commands": [{"name": "test", "command": "x", "exit": 0, "seconds": 0.1, "result": "pass"}]}
        r.update(kw)
        return r

    def reason(self, rec, head=H):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import sdlc_verify
        return sdlc_verify.green_reason(rec, head)

    def test_none_when_green_and_each_reason_in_order(self):
        self.assertIsNone(self.reason(self.rec()))
        cases = [
            (None, "record shape or version wrong"), ([], "record shape or version wrong"),
            (self.rec(version=2), "record shape or version wrong"),
            (self.rec(dirty="no"), "record shape or version wrong"),
            (self.rec(dirty=None), "record shape or version wrong"),
            (self.rec(commands="x"), "record shape or version wrong"),
            (self.rec(commands=[1]), "record shape or version wrong"),
            (self.rec(revision=5), "record shape or version wrong"),
            (self.rec(revision=None), "record has no revision"),
            (self.rec(revision="b" * 40), "record is for another revision"),
            (self.rec(dirty=True), "record was dirty"),
            (self.rec(commands=[]), "no commands in the record"),
            (self.rec(commands=[{"name": "t", "command": "x", "exit": 1, "seconds": 0, "result": "fail"}]), "a command did not pass"),
        ]
        for rec, want in cases:
            self.assertEqual(self.reason(rec), want, rec)
        self.assertEqual(self.reason(self.rec(), head=None), "record is for another revision")

    def test_green_at_head_is_exactly_reason_is_none(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import sdlc_verify
        for rec in (self.rec(), self.rec(dirty=True), None, self.rec(revision=None)):
            self.assertIs(sdlc_verify.green_at_head(rec, self.H), sdlc_verify.green_reason(rec, self.H) is None)


class Record(Proj):
    def test_record_holds_no_command_output(self):
        marker = "SECRET-MARKER-12345"
        self.config({"test": py("print('SECRET-' + 'MARKER-' + '12345'); import sys; sys.exit(1)")})  # not in the command text
        code, out, _ = self.verify()
        self.assertIn(marker, out)  # printed for the human ...
        with open(self.p(".sdlc/evidence/verify.json")) as f:
            self.assertNotIn(marker, f.read())  # ... never stored

    def test_no_temp_files_are_left_beside_the_record(self):
        self.config({"test": py("pass")})
        self.verify()
        self.assertEqual(os.listdir(self.p(".sdlc/evidence")), ["verify.json"])

    def test_unwritable_record_still_prints_results_and_exits_by_command_outcome(self):
        os.makedirs(self.p(".sdlc/evidence/verify.json"))  # a directory where the record should go
        self.config({"test": py("pass")})
        code, out, _ = self.verify()
        self.assertEqual(code, 2)
        self.assertIn("verify test: pass", out)
        self.assertRegex(out.strip().split("\n")[-1], r"^verify: record NOT written \(.+\); not verified$")
        self.config({"test": py("import sys; sys.exit(1)")})
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assertIn("record NOT written", out.strip().split("\n")[-1])


class WriteFailure(Proj):
    def test_failed_replace_keeps_the_old_record_and_removes_the_temp_file(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import sdlc_verify
        path = self.p(".sdlc/evidence/verify.json")
        sdlc_verify.write_record(path, {"old": True})
        def boom(a, b):
            raise OSError("disk full")
        with self.assertRaises(OSError):
            sdlc_verify.write_record(path, {"new": True}, replace=boom)
        with open(path) as f:
            self.assertEqual(json.load(f), {"old": True})
        self.assertEqual(os.listdir(os.path.dirname(path)), ["verify.json"])


class Workspace(Proj):
    def setUp(self):
        super().setUp()
        self.child = os.path.join(self.d, "api")
        os.makedirs(self.child)
        with open(os.path.join(self.child, "marker.txt"), "w") as f:
            f.write("api")
        self.config({"test": py("open('top.txt','w')")},
                    repos={"api": {"path": "api", "commands": {"test": py("import os; open('here.txt','w').write(os.getcwd())")}}})

    def test_repo_flag_uses_the_repos_commands_and_folder_and_writes_the_record_there(self):
        code, out, err = self.verify("--repo", "api")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.exists(os.path.join(self.child, "here.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.child, ".sdlc", "evidence", "verify.json")))
        self.assertFalse(os.path.exists(self.p(".sdlc/evidence/verify.json")))
        self.assertFalse(os.path.exists(self.p("top.txt")))

    def test_unknown_repo_and_escaping_path_are_exit_2(self):
        self.assertEqual(self.verify("--repo", "nope")[0], 2)
        self.config({}, repos={"x": {"path": "../outside", "commands": {"test": py("pass")}}})
        code, out, _ = self.verify("--repo", "x")
        self.assertEqual(code, 2, out)
        self.config({}, repos={"y": {"path": "/tmp", "commands": {"test": py("pass")}}})
        self.assertEqual(self.verify("--repo", "y")[0], 2)
        self.config({}, repos={"z": ["not", "an", "object"]})
        self.assertEqual(self.verify("--repo", "z")[0], 2)

    def test_two_runs_on_a_child_repo_with_no_other_sdlc_content_both_read_clean(self):
        self.config({}, repos={"api": {"path": "api", "commands": {"test": py("pass")}}})
        git(self.child, "init", "-q")
        git(self.child, "add", "-A")
        git(self.child, "commit", "-q", "-m", "i")
        self.assertEqual(self.verify("--repo", "api")[0], 0)
        self.assertEqual(self.verify("--repo", "api")[0], 0)
        with open(os.path.join(self.child, ".sdlc", "evidence", "verify.json")) as f:
            rec = json.load(f)
        self.assertIsNotNone(rec["revision"])
        self.assertIs(rec["dirty"], False)


if __name__ == "__main__":
    unittest.main()
