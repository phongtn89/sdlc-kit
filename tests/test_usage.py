import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USAGE = os.path.join(ROOT, "core", "skills", "sdlc-usage", "usage.py")
SID = "0b8b2d7f-d1c8-4d58-86d4-eb8b0ad184f6"
MODEL = "claude-opus-5-5"
START = "2026-11-03T10:00:00.000Z"
STOP = "2026-11-03T10:23:07.456Z"
TASKS = "# Tasks\n\n## Progress log\n\n- 2026-11-03 `abc` - T001 done\n"


def usage(inp, cr, cc, out):
    return {"input_tokens": inp, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc,
            "output_tokens": out}


def response(mid, ts, u, model=MODEL):
    return {"type": "assistant", "timestamp": ts,
            "message": {"id": mid, "role": "assistant", "model": model, "usage": u}}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.proj = os.path.join(self._tmp.name, "proj")
        self.cfg = os.path.join(self._tmp.name, "claude")
        os.makedirs(os.path.join(self.proj, ".sdlc"))
        os.makedirs(os.path.join(self.proj, "specs", "001-x"))
        self.config({"usage": {"enabled": True}})
        self.write_record(TASKS)

    # -- files
    def config(self, data):
        text = data if isinstance(data, str) else json.dumps(data)
        with open(os.path.join(self.proj, ".sdlc", "config.json"), "w") as f:
            f.write(text)

    def rec_path(self, rel="specs/001-x/tasks.md"):
        return os.path.join(self.proj, rel)

    def write_record(self, text, rel="specs/001-x/tasks.md"):
        with open(self.rec_path(rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def read_record(self, rel="specs/001-x/tasks.md"):
        with open(self.rec_path(rel), encoding="utf-8", newline="") as f:
            return f.read()

    def transcript(self, records, sid=SID, project="-proj"):
        d = os.path.join(self.cfg, "projects", project)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, sid + ".jsonl"), "w", encoding="utf-8") as f:
            for r in records:
                f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")

    def mark(self, unit="T012", ts=START, sid=SID):
        return "<!-- usage-start %s %s session=%s -->\n" % (unit, ts, sid)

    # -- running the script
    def run_usage(self, *args, sid=SID, env_extra=None, cwd=None):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": self._tmp.name, "CLAUDE_CONFIG_DIR": self.cfg}
        if sid:
            env["CLAUDE_CODE_SESSION_ID"] = sid
        env.update(env_extra or {})
        p = subprocess.run([sys.executable, "-B", USAGE] + list(args), capture_output=True, text=True, timeout=20,
                           cwd=cwd or self.proj, env=env, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr

    def start(self, unit="T012", **kw):
        return self.run_usage("start", unit, "--record", "specs/001-x/tasks.md", **kw)

    def stop(self, unit="T012", at=STOP, extra=(), **kw):
        args = ["stop", unit, "--record", "specs/001-x/tasks.md"] + list(extra)
        if at:
            args += ["--at", at]
        return self.run_usage(*args, **kw)

    def lines_for(self, unit="T012"):
        return [l for l in self.read_record().split("\n") if l.startswith("- usage %s:" % unit)]


class Tracer(Base):
    def test_start_writes_a_mark(self):
        code, out, err = self.start()
        self.assertEqual(code, 0, out + err)
        text = self.read_record()
        m = re.search(r"^<!-- usage-start T012 (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z) session=%s -->$" % SID, text, re.M)
        self.assertTrue(m, text)
        self.assertLess(text.index("T001 done"), text.index("usage-start"))  # appended at the end of the section

    def test_stop_writes_the_exact_line(self):
        self.write_record(TASKS + self.mark())
        self.transcript([
            response("m1", "2026-11-03T10:00:05.000Z", usage(3, 1000, 500, 100)),
            response("m2", "2026-11-03T10:10:00.250Z", usage(1, 2000, 0, 250)),
            response("m3", "2026-11-03T10:20:00.000Z", usage(2, 300000, 40000, 1654)),
        ])
        code, out, err = self.stop()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines_for(), ["- usage T012: in 6 · cache-read 303,000 · cache-write 40,500 · out 2,004 "
                                            "· sub-agents 0 · 23 min wall · 3 turns · model %s" % MODEL])
        self.assertIn("<!-- usage-stop T012 %s -->" % STOP, self.read_record())

    def test_section_is_created_when_absent(self):
        self.write_record("# Tasks\n\n- [ ] T001 something\n")
        code, out, err = self.start()
        self.assertEqual(code, 0, out + err)
        text = self.read_record()
        self.assertIn("- [ ] T001 something\n", text)
        self.assertRegex(text, r"\n## Progress log\n\n?<!-- usage-start T012 ")

    def test_off_writes_nothing_and_reads_no_transcript(self):
        for cfg in ({}, {"usage": {"enabled": False}}):
            self.config(cfg)
            self.write_record(TASKS + self.mark())
            before = self.read_record()
            for call in (self.start, self.stop):
                code, out, err = call()
                self.assertEqual(code, 0, out + err)
                self.assertEqual(out.strip(), "usage off")
                self.assertEqual(self.read_record(), before)
        self.assertFalse(os.path.exists(self.cfg))  # nothing was created under the Claude folder

    def test_unit_id_charset(self):
        before = self.read_record()
        for bad in ("T1/../x", "a b", "x;y", "", "-"):
            code, out, err = self.run_usage("start", bad, "--record", "specs/001-x/tasks.md")
            self.assertEqual(code, 2, (bad, out, err))
            self.assertEqual(self.read_record(), before)
        for good in ("T012", "review1-F3", "T012-r2", "fix_bug.1"):
            self.assertEqual(self.start(good)[0], 0, good)

    def test_timestamps_with_z_and_fraction(self):
        self.write_record(TASKS + self.mark())
        self.transcript([
            response("m1", "2026-11-03T10:00:05Z", usage(1, 0, 0, 10)),
            response("m2", "2026-11-03T10:00:06.123Z", usage(1, 0, 0, 20)),
        ])
        code, out, err = self.stop()
        self.assertEqual(code, 0, out + err)
        self.assertRegex(self.lines_for()[0], r"in 2 · cache-read 0 · cache-write 0 · out 30 · .* 2 turns")


if __name__ == "__main__":
    unittest.main()
