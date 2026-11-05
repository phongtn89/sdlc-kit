import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "sdlc")
BUDGET = {"target_lines": 200, "reassess_lines": 300, "target_turns": 15, "max_turns": 25}


def run(*args):
    p = subprocess.run([sys.executable, "-B", CLI, "budget"] + list(args), capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


def git(d, *args):
    return subprocess.run(["git", "-C", d, "-c", "user.email=a@b", "-c", "user.name=x"] + list(args),
                          check=True, capture_output=True, text=True).stdout


def lines(n, tag="x"):
    return "".join("%s %d\n" % (tag, i) for i in range(n))


class Repo(unittest.TestCase):
    """A git project on branch `feat/008-demo` made from `main`, with a budget in its config."""
    budget = BUDGET

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "p")
        os.makedirs(os.path.join(self.d, ".sdlc"))
        git(self.d, "init", "-q", "-b", "main")
        self.config(budget=self.budget)
        self.write("base.txt", lines(10, "base"))
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "base")
        git(self.d, "checkout", "-q", "-b", "feat/008-demo")

    def config(self, **cfg):
        self.write(os.path.join(".sdlc", "config.json"), json.dumps(cfg))

    def write(self, rel, text, mode="w"):
        path = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode) as f:
            f.write(text)

    def commit(self, msg="work"):
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", msg)

    def budget_run(self, *extra):
        return run(self.d, *extra)

    def last(self, out):
        return out.strip().splitlines()[-1]


class Lines(Repo):
    def check(self, n, word, code):
        self.write("work.txt", lines(n))
        self.commit()
        c, out, err = self.budget_run()
        self.assertEqual((c, self.last(out)), (code, "budget: " + word), out + err)

    def test_the_boundaries(self):
        for n, word, code in ((0, "OK", 0), (200, "OK", 0), (201, "ABOVE TARGET", 0), (300, "ABOVE TARGET", 0),
                              (301, "REASSESS", 1)):
            with self.subTest(n):
                self.setUp() if n else None
                self.check(n, word, code)

    def test_the_lines_line_names_the_count_and_both_limits(self):
        self.write("work.txt", lines(120))
        self.commit()
        c, out, err = self.budget_run()
        self.assertIn("budget lines: 120 (target 200, reassess 300): ok", out.splitlines())

    def test_deleting_counts_as_much_as_adding(self):
        git(self.d, "checkout", "-q", "main")
        self.write("big.txt", lines(310))
        self.commit("big file on main")
        git(self.d, "checkout", "-q", "-b", "feat/009-delete")
        git(self.d, "rm", "-q", "big.txt")
        git(self.d, "commit", "-q", "-m", "delete it")
        c, out, err = self.budget_run()
        self.assertEqual((c, self.last(out)), (1, "budget: REASSESS"), out + err)
        self.assertIn("lines: 310 ", out)

    def test_committed_uncommitted_and_untracked_all_count(self):
        self.write("a.txt", lines(100))
        self.commit()
        self.write("a.txt", lines(100) + lines(50, "more"))  # modified, not committed
        self.write("new.txt", lines(60))  # untracked
        c, out, err = self.budget_run()
        self.assertIn("lines: 210 ", out, out)
        self.assertEqual(self.last(out), "budget: ABOVE TARGET")

    def test_a_file_without_a_final_newline_and_a_binary_file(self):
        self.write("a.txt", "one\ntwo")  # two lines, the last one unterminated
        self.write("bin.dat", b"\x00\x01\x02" * 100, mode="wb")
        c, out, err = self.budget_run()
        self.assertIn("lines: 2 ", out, out)

    def test_a_rename_counts_as_a_delete_and_an_add(self):
        git(self.d, "checkout", "-q", "main")
        self.write("a.txt", lines(7))
        self.commit("a on main")
        git(self.d, "checkout", "-q", "-b", "feat/009-rename")
        git(self.d, "mv", "a.txt", "b.txt")
        c, out, err = self.budget_run()
        self.assertIn("lines: 14 ", out, out)

    def test_the_spec_folder_the_kit_folders_are_not_counted(self):
        self.write("specs/008-demo/spec.md", lines(400))
        self.write(".sdlc/evidence/verify.json", lines(400))
        self.write(".claude/skills/x/SKILL.md", lines(400))
        self.write("src.py", lines(5))
        c, out, err = self.budget_run()
        self.assertIn("lines: 5 ", out, out)

    def test_a_configured_spec_dir_is_excluded_instead_of_specs(self):
        self.config(budget=BUDGET, spec_dir="design/specs")
        self.write("design/specs/008-demo/spec.md", lines(400))
        self.write("specs/readme.txt", lines(7))
        c, out, err = self.budget_run()
        self.assertIn("lines: 7 ", out, out)

    def test_only_changes_since_the_merge_base_count(self):
        self.write("work.txt", lines(30))
        self.commit()
        git(self.d, "checkout", "-q", "main")
        self.write("main-only.txt", lines(500))
        self.commit("main moves on")
        git(self.d, "checkout", "-q", "feat/008-demo")
        c, out, err = self.budget_run()
        self.assertIn("lines: 30 ", out, out)


class Base(Repo):
    def test_origin_head_is_the_default_base(self):
        git(self.d, "update-ref", "refs/remotes/origin/develop", "main")  # develop stays at the base commit
        self.write("work.txt", lines(40))
        self.commit()
        git(self.d, "checkout", "-q", "main")
        self.write("dev.txt", lines(100))
        self.commit("main moves on")
        git(self.d, "checkout", "-q", "feat/008-demo")
        git(self.d, "merge", "-q", "main", "-m", "merge")
        c, out, err = self.budget_run()
        self.assertIn("lines: 40 ", out, out)  # no origin/HEAD yet: main is the base
        git(self.d, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
        c, out, err = self.budget_run()
        self.assertIn("lines: 140 ", out, out)

    def test_a_dangling_origin_head_falls_back_to_main(self):
        git(self.d, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone")
        self.write("work.txt", lines(9))
        self.commit()
        c, out, err = self.budget_run()
        self.assertEqual(c, 0, out + err)
        self.assertIn("lines: 9 ", out)

    def test_master_is_found_when_there_is_no_main(self):
        git(self.d, "branch", "-m", "main", "master")
        self.write("work.txt", lines(9))
        self.commit()
        c, out, err = self.budget_run()
        self.assertEqual(c, 0, out + err)
        self.assertIn("lines: 9 ", out)

    def test_no_default_branch_is_a_usage_error_and_base_fixes_it(self):
        git(self.d, "branch", "-m", "main", "trunk")
        self.write("work.txt", lines(9))
        self.commit()
        c, out, err = self.budget_run()
        self.assertEqual(c, 2, out + err)
        self.assertIn("--base", out + err)
        c, out, err = self.budget_run("--base", "trunk")
        self.assertEqual(c, 0, out + err)
        self.assertIn("lines: 9 ", out)

    def test_an_unknown_base_is_a_usage_error(self):
        c, out, err = self.budget_run("--base", "nope")
        self.assertEqual(c, 2, out + err)
        self.assertIn("nope", out + err)

    def test_a_base_that_looks_like_an_option_is_refused(self):
        c, out, err = self.budget_run("--base=--output=/tmp/x")
        self.assertEqual(c, 2, out + err)
        self.assertIn("not an option", out + err)

    def test_a_folder_that_is_not_a_git_repository_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".sdlc"))
            with open(os.path.join(d, ".sdlc", "config.json"), "w") as f:
                json.dump({"budget": BUDGET}, f)
            c, out, err = run(d)
        self.assertEqual(c, 2, out + err)


class Config(Repo):
    def test_a_bad_budget_value_is_a_usage_error_naming_the_key(self):
        for bad in ("200", -1, True, 1.5, None, [1]):
            with self.subTest(repr(bad)):
                self.config(budget=dict(BUDGET, target_lines=bad))
                c, out, err = self.budget_run()
                self.assertEqual(c, 2, out + err)
                self.assertIn("budget.target_lines", out + err)

    def test_a_missing_budget_or_key_is_a_usage_error(self):
        self.config()
        c, out, err = self.budget_run()
        self.assertEqual(c, 2, out + err)
        self.config(budget={"target_lines": 200})
        c, out, err = self.budget_run()
        self.assertEqual(c, 2, out + err)
        self.assertIn("budget.reassess_lines", out + err)

    def test_target_above_reassess_is_a_usage_error(self):
        self.config(budget=dict(BUDGET, target_lines=400))
        c, out, err = self.budget_run()
        self.assertEqual(c, 2, out + err)

    def test_the_turn_keys_are_only_needed_with_a_unit(self):
        self.config(budget={"target_lines": 200, "reassess_lines": 300})
        c, out, err = self.budget_run()
        self.assertEqual(c, 0, out + err)


class Turns(Repo):
    def tasks(self, *log):
        self.write("specs/008-demo/spec.md", "# Spec\n")
        self.write("specs/008-demo/tasks.md", "# Tasks\n\n## Progress log\n\n" + "".join(l + "\n" for l in log))

    def usage(self, unit, turns):
        return "- usage %s: in 1,502 · cache-read 2,103,441 · cache-write 40,118 · out 18,004 · sub-agents 0 · 23 min wall · %s turns · model m" % (unit, turns)

    def test_the_turn_limits(self):
        for turns, word, code in ((14, "OK", 0), (15, "OK", 0), (16, "ABOVE TARGET", 0), (24, "ABOVE TARGET", 0),
                                  (25, "REASSESS", 1), (41, "REASSESS", 1)):
            with self.subTest(turns):
                self.tasks(self.usage("T001", turns))
                c, out, err = self.budget_run("--unit", "T001", "--spec", "008")
                self.assertEqual((c, self.last(out)), (code, "budget: " + word), out + err)
                self.assertIn("budget turns T001: %d (target 15, max 25)" % turns, out)

    def test_thousands_separator_and_the_last_line_for_a_unit_win(self):
        self.tasks(self.usage("T001", "30"), self.usage("T001", "1,200"), self.usage("T0011", "2"))
        c, out, err = self.budget_run("--unit", "T001", "--spec", "008")
        self.assertIn("budget turns T001: 1200 ", out, out)

    def test_no_line_or_turns_not_available_is_unknown_and_changes_nothing(self):
        self.tasks(self.usage("T002", 3))
        c, out, err = self.budget_run("--unit", "T001", "--spec", "008")
        self.assertEqual((c, self.last(out)), (0, "budget: OK"), out + err)
        self.assertIn("budget turns T001: unknown (no usage line for T001)", out)
        self.tasks("- usage T001: tokens not available (x) · sub-agents not available (x) · 3 min wall · turns not available (x)")
        c, out, err = self.budget_run("--unit", "T001", "--spec", "008")
        self.assertIn("budget turns T001: unknown", out)
        self.assertEqual(c, 0)

    def test_the_worse_of_lines_and_turns_decides(self):
        self.tasks(self.usage("T001", 30))
        self.write("work.txt", lines(10))
        c, out, err = self.budget_run("--unit", "T001", "--spec", "008")
        self.assertEqual((c, self.last(out)), (1, "budget: REASSESS"), out + err)
        self.tasks(self.usage("T001", 10))
        self.write("work.txt", lines(250))
        c, out, err = self.budget_run("--unit", "T001", "--spec", "008")
        self.assertEqual((c, self.last(out)), (0, "budget: ABOVE TARGET"), out + err)

    def test_unit_and_spec_go_together_and_must_be_valid(self):
        self.tasks()
        for args in (("--unit", "T001"), ("--spec", "008"), ("--unit", "T 1", "--spec", "008"),
                     ("--unit", "T001", "--spec", "099"), ("--unit", "../x", "--spec", "008")):
            with self.subTest(args):
                c, out, err = self.budget_run(*args)
                self.assertEqual(c, 2, out + err)

    def test_a_spec_without_tasks_is_a_usage_error(self):
        self.write("specs/008-demo/spec.md", "# Spec\n")
        c, out, err = self.budget_run("--unit", "T001", "--spec", "008")
        self.assertEqual(c, 2, out + err)


class Workspace(unittest.TestCase):
    def test_repo_measures_that_repos_own_git_diff_and_spec_dir(self):
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "api")
            os.makedirs(sub)
            os.makedirs(os.path.join(d, ".sdlc"))
            git(sub, "init", "-q", "-b", "main")
            with open(os.path.join(sub, "a.txt"), "w") as f:
                f.write(lines(3))
            git(sub, "add", "-A")
            git(sub, "commit", "-q", "-m", "base")
            git(sub, "checkout", "-q", "-b", "feat/001-x")
            os.makedirs(os.path.join(sub, "docs", "specs"))
            with open(os.path.join(sub, "docs", "specs", "s.md"), "w") as f:
                f.write(lines(90))
            with open(os.path.join(sub, "code.py"), "w") as f:
                f.write(lines(11))
            with open(os.path.join(d, ".sdlc", "config.json"), "w") as f:
                json.dump({"budget": BUDGET, "repos": {"api": {"path": "api", "spec_dir": "docs/specs"}}}, f)
            c, out, err = run(d, "--repo", "api")
            self.assertEqual(c, 0, out + err)
            self.assertIn("lines: 11 ", out)
            c, out, err = run(d, "--repo", "nope")
            self.assertEqual(c, 2, out + err)


class ReadOnly(Repo):
    def test_it_writes_nothing_and_leaves_no_bytecode_in_the_kit(self):
        self.write("work.txt", lines(20))
        before = git(self.d, "status", "--porcelain", "--ignored")
        self.budget_run()
        self.assertEqual(git(self.d, "status", "--porcelain", "--ignored"), before)
        self.assertEqual([dp for dp, dn, fn in os.walk(os.path.join(ROOT, "bin")) if "__pycache__" in dn], [])


class Docs(unittest.TestCase):
    def text(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
            return f.read()

    def test_implement_runs_the_command_and_quotes_its_last_line(self):
        step = [l for l in self.text("core", "skills", "sdlc-implement", "SKILL.md").split("\n") if l.startswith("6. **Watch the budget")]
        self.assertEqual(len(step), 1)
        for needle in ("sdlc budget", "kit_path", "last line", "REASSESS"):
            self.assertIn(needle, step[0])

    def test_readme_documents_the_command(self):
        readme = self.text("README.md")
        self.assertRegex(readme, r"\| `sdlc budget <dir>")
        for needle in ("budget: OK", "REASSESS", "merge-base", "--unit"):
            self.assertIn(needle, readme)


if __name__ == "__main__":
    unittest.main()
