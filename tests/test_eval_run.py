import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "evals", "run.py")
PROMPT = "Review this diff for correctness. Give exactly one verdict."

EVENTS = [
    {"type": "system", "subtype": "init", "session_id": "sess-1", "model": "claude-test"},
    {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "sdlc-review"}}]}},
    {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "git diff"}}]}},
    {"type": "result", "subtype": "success", "num_turns": 3, "total_cost_usd": 0.1,
     "result": "VERDICT: REJECTED\n\nF1 ..."},
]


class Runner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = self._tmp.name
        self.target = os.path.join(self.base, "target")
        os.mkdir(self.target)
        with open(os.path.join(self.target, "app.js"), "w") as f:
            f.write("export const x = 1;\n")
        subprocess.run(["git", "init", "-q", self.target], check=True)
        self.prompt = self.file(os.path.join(self.base, "prompt.txt"), PROMPT + "\n")
        self.out = os.path.join(self.base, "out", "run.jsonl")

    def file(self, path, text):
        with open(path, "w") as f:
            f.write(text)
        return path

    def fake_claude(self, events, touch=None, after="", commit=False):
        lines = "".join(json.dumps(e) + "\n" for e in events)
        data = self.file(os.path.join(self.base, "events.jsonl"), lines)
        script = "#!/bin/sh\n%s%scat %s\n%s" % (
            "echo changed > %s\n" % touch if touch else "",
            "git -c user.name=t -c user.email=t@t commit -q --allow-empty -m x\n" if commit else "",
            data, after)
        path = self.file(os.path.join(self.base, "claude"), script)
        os.chmod(path, 0o755)
        return path

    def run_it(self, prompt=None, claude=None, out=None, extra=()):
        cmd = [sys.executable, RUNNER, prompt or self.prompt, self.target, "--out", out or self.out,
               "--claude", claude or self.fake_claude(EVENTS)] + list(extra)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return p.returncode, p.stdout + p.stderr

    def test_refuses_prompt_file_inside_target(self):
        inside = self.file(os.path.join(self.target, "task.txt"), PROMPT)
        code, out = self.run_it(prompt=inside)
        self.assertEqual(code, 2, out)
        self.assertIn("LEAK", out)
        self.assertFalse(os.path.exists(self.out))

    def test_refuses_when_prompt_text_is_in_target(self):
        self.file(os.path.join(self.target, "notes.md"), "Expect for: " + PROMPT + "\n")
        code, out = self.run_it()
        self.assertEqual(code, 2, out)
        self.assertIn("LEAK notes.md", out)
        self.assertFalse(os.path.exists(self.out))

    def test_summary_of_a_complete_run(self):
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        for needle in ["session: sess-1", "model: claude-test", "tool: Skill sdlc-review",
                       "tool: Bash git diff", "first line: VERDICT: REJECTED", "turns: 3",
                       "target unchanged"]:
            self.assertIn(needle, out)
        with open(self.out) as f:
            self.assertEqual(len(f.read().strip().split("\n")), len(EVENTS))

    def test_reports_a_changed_target(self):
        code, out = self.run_it(claude=self.fake_claude(EVENTS, touch=os.path.join(self.target, "app.js")))
        self.assertEqual(code, 0, out)
        self.assertIn("TARGET CHANGED", out)
        self.assertIn("app.js", out)

    def test_no_result_event_is_not_a_finished_run(self):
        code, out = self.run_it(claude=self.fake_claude(EVENTS[:-1]))
        self.assertEqual(code, 3, out)
        self.assertIn("NO RESULT", out)

    def test_timeout_keeps_transcript_and_reports_changes(self):
        claude = self.fake_claude(EVENTS[:2], touch=os.path.join(self.target, "app.js"), after="sleep 5\n")
        code, out = self.run_it(claude=claude, extra=["--timeout", "1"])
        self.assertEqual(code, 3, out)
        self.assertIn("NO RESULT: timed out after 1 s", out)
        self.assertIn("tool: Skill sdlc-review", out)
        self.assertIn("TARGET CHANGED", out)
        self.assertTrue(os.path.exists(self.out))

    def test_refuses_out_inside_target(self):
        code, out = self.run_it(out=os.path.join(self.target, "run.jsonl"))
        self.assertEqual(code, 2, out)
        self.assertIn("--out", out)

    def test_refuses_empty_prompt(self):
        code, out = self.run_it(prompt=self.file(os.path.join(self.base, "empty.txt"), "  \n"))
        self.assertEqual(code, 2, out)
        self.assertIn("empty prompt", out)

    def test_reports_a_commit(self):
        subprocess.run(["git", "-C", self.target, "-c", "user.name=t", "-c", "user.email=t@t",
                        "commit", "-q", "--allow-empty", "-m", "base"], check=True)
        code, out = self.run_it(claude=self.fake_claude(EVENTS, commit=True))
        self.assertEqual(code, 0, out)
        self.assertIn("HEAD MOVED", out)

    def test_cli_gets_no_stdin(self):
        claude = self.fake_claude(EVENTS)
        with open(claude) as f:
            script = f.read().replace("#!/bin/sh\n", "#!/bin/sh\nread line\n", 1)
        self.file(claude, script)
        cmd = [sys.executable, RUNNER, self.prompt, self.target, "--out", self.out,
               "--claude", claude, "--timeout", "3"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        p.wait(timeout=30)  # stdin stays open: a CLI that inherits it blocks on `read`
        out = p.stdout.read()
        p.stdin.close()
        self.assertEqual(p.returncode, 0, out)
