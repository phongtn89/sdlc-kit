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

    def subagent(self, records, name="agent-a1", sid=SID, project="-proj"):
        d = os.path.join(self.cfg, "projects", project, sid, "subagents")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name + ".jsonl"), "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def line(self, unit="T012"):
        lines = self.lines_for(unit)
        self.assertEqual(len(lines), 1, self.read_record())
        return lines[0]

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


class Dedupe(Base):
    def test_one_response_written_five_times_counts_once(self):
        self.write_record(TASKS + self.mark())
        recs = [response("m1", "2026-11-03T10:01:0%d.000Z" % k, usage(2, 100, 50, 10 * (k + 1))) for k in range(5)]
        recs.append(response("m2", "2026-11-03T10:05:00.000Z", usage(1, 10, 5, 7)))
        self.transcript(recs)
        self.assertEqual(self.stop()[0], 0)
        # the last record of m1 (out 50) and m2: 2 responses, not 6 records
        self.assertIn("in 3 · cache-read 110 · cache-write 55 · out 57 · ", self.line())
        self.assertIn(" 2 turns", self.line())

    def test_the_last_record_wins_even_if_it_has_fewer_tokens(self):
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(9, 9, 9, 99)),
                         response("m1", "2026-11-03T10:01:01.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop()[0], 0)
        self.assertIn("in 1 · cache-read 2 · cache-write 3 · out 4 · ", self.line())


class SubAgents(Base):
    def test_separate_and_not_added_to_main(self):
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
        self.subagent([response("s1", "2026-11-03T10:02:00.000Z", usage(1, 20, 30, 40))], "agent-a1")
        self.subagent([response("s2", "2026-11-03T09:00:00.000Z", usage(500, 500, 500, 500))], "agent-a2")  # before the mark
        self.assertEqual(self.stop()[0], 0)
        line = self.line()
        self.assertIn("in 1 · cache-read 2 · cache-write 3 · out 4 · sub-agents 91 · ", line)  # 1+20+30+40
        self.assertIn(" 1 turns", line)

    def test_no_subagents_folder_means_zero(self):  # guard: the first implementation already writes 0
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop()[0], 0)
        self.assertIn("sub-agents 0 · ", self.line())


class Models(Base):
    def test_each_distinct_model_listed_synthetic_and_invalid_ignored(self):
        self.write_record(TASKS + self.mark())
        self.transcript([
            response("m1", "2026-11-03T10:01:00.000Z", usage(1, 0, 0, 1), model="claude-opus-5-5"),
            response("m2", "2026-11-03T10:02:00.000Z", usage(1, 0, 0, 1), model="claude-haiku-5-5"),
            response("m3", "2026-11-03T10:03:00.000Z", usage(1, 0, 0, 1), model="claude-opus-5-5"),
            response("m4", "2026-11-03T10:04:00.000Z", usage(900, 0, 0, 900), model="<synthetic>"),
            response("m5", "2026-11-03T10:05:00.000Z", usage(1, 0, 0, 1), model="bad model!"),
        ])
        self.assertEqual(self.stop()[0], 0)
        line = self.line()
        self.assertTrue(line.endswith(" · model claude-opus-5-5, claude-haiku-5-5"), line)
        self.assertIn("in 4 · ", line)  # the synthetic response counts for nothing
        self.assertIn(" 4 turns", line)

    def test_turns_count_main_responses_only(self):  # guard: sub-agent files are not read yet, so this already holds
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 0, 0, 1)),
                         response("m2", "2026-11-03T10:02:00.000Z", usage(1, 0, 0, 1))])
        self.subagent([response("s1", "2026-11-03T10:02:30.000Z", usage(1, 0, 0, 1))])
        self.assertEqual(self.stop()[0], 0)
        self.assertIn(" 2 turns", self.line())


class Windows(Base):
    def test_half_open_and_straddling_response_counted_once(self):
        self.write_record(TASKS + self.mark())
        self.transcript([
            response("before", "2026-11-03T09:59:59.999Z", usage(100, 0, 0, 100)),                    # before the mark
            response("at-start", START, usage(1, 0, 0, 1)),                                           # exactly at the mark: in
            response("straddle-start", "2026-11-03T09:59:59.000Z", usage(50, 0, 0, 50)),             # first record before ...
            response("straddle-start", "2026-11-03T10:00:01.000Z", usage(2, 0, 0, 2)),               # ... last record inside: in, once
            response("inside", "2026-11-03T10:10:00.000Z", usage(4, 0, 0, 4)),
            response("at-stop", STOP, usage(1000, 0, 0, 1000)),                                       # exactly at the stop: out
            response("straddle-stop", "2026-11-03T10:23:07.000Z", usage(300, 0, 0, 300)),            # first inside ...
            response("straddle-stop", "2026-11-03T10:23:08.000Z", usage(300, 0, 0, 300)),            # ... last after: out
        ])
        self.assertEqual(self.stop()[0], 0)
        line = self.line()
        self.assertIn("in 7 · cache-read 0 · cache-write 0 · out 7 · ", line)  # 1 + 2 + 4
        self.assertIn(" 3 turns", line)

    def test_non_assistant_records_without_timestamps_are_ignored(self):  # guard
        self.write_record(TASKS + self.mark())
        self.transcript([{"type": "api-request", "message": "x"}, {"type": "last-prompt"},
                         {"type": "user", "timestamp": "2026-11-03T10:01:00.000Z", "message": {"role": "user"}},
                         response("m1", "2026-11-03T10:02:00.000Z", usage(1, 0, 0, 1))])
        self.assertEqual(self.stop()[0], 0)
        self.assertIn(" 1 turns", self.line())


class RealFixture(Base):
    """SC-009: a recorded real run (reduced to ids, timestamps, models and usage) against the CLI's own result."""
    DIR = os.path.join(ROOT, "tests", "fixtures", "usage", "real-run")

    def test_matches_the_cli_result(self):
        with open(os.path.join(self.DIR, "expected.json")) as f:
            exp = json.load(f)
        sid = exp["session"]
        d = os.path.join(self.cfg, "projects", "-proj")
        os.makedirs(os.path.join(d, sid, "subagents"))
        for src, dst in (("main.jsonl", os.path.join(d, sid + ".jsonl")),
                         ("agent-afa034c1c95177076.jsonl", os.path.join(d, sid, "subagents", "agent-afa034c1c95177076.jsonl"))):
            with open(os.path.join(self.DIR, src), "rb") as f, open(dst, "wb") as o:
                o.write(f.read())
        self.write_record(TASKS + self.mark(ts=exp["window"]["start"], sid=sid))
        code, out, err = self.stop(at=exp["window"]["stop"])
        self.assertEqual(code, 0, out + err)
        r, m = exp["result_usage"], exp["model_usage"]
        line = self.line()
        main_part = "in %s · cache-read %s · cache-write %s · out %s · " % (
            "{:,}".format(r["input_tokens"]), "{:,}".format(r["cache_read_input_tokens"]),
            "{:,}".format(r["cache_creation_input_tokens"]), "{:,}".format(r["output_tokens"]))
        self.assertIn(main_part, line)  # the four main fields equal result.usage exactly
        everything = m["inputTokens"] + m["cacheReadInputTokens"] + m["cacheCreationInputTokens"] + m["outputTokens"]
        main_total = sum(r.values())
        self.assertIn("sub-agents {:,} · ".format(everything - main_total), line)  # main + sub-agents = modelUsage
        self.assertIn(" 3 turns", line)


if __name__ == "__main__":
    unittest.main()
