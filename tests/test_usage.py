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


class NotAvailable(Base):
    def na_line(self, reason, wall="23 min wall"):
        return ("- usage T012: tokens not available (%s) · sub-agents not available (%s) · %s · turns not available (%s)"
                " · model not available (%s)" % (reason, reason, wall, reason, reason))

    def assert_open_and_no_zero(self, line):
        self.assertNotRegex(line, r"\b(in|cache-read|cache-write|out|sub-agents|tokens|turns) 0\b")

    def test_row1_no_start_mark(self):
        code, out, err = self.stop()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines_for(), ["- usage T012: not available (no start mark)"])
        self.assertNotIn("usage-stop", self.read_record())

    def test_row2_no_session_id_and_no_claude_folder(self):
        self.write_record(TASKS + self.mark(sid="unknown"))
        self.assertFalse(os.path.exists(self.cfg))
        self.assertEqual(self.stop(sid=None)[0], 0)
        self.assertEqual(self.lines_for(), ["- usage T012: not available (no transcript on this target)"])

    def test_row3_session_id_unknown_keeps_wall_time(self):
        os.makedirs(self.cfg)  # a Claude folder exists
        self.write_record(TASKS + self.mark(sid="unknown"))
        self.assertEqual(self.stop(sid=None)[0], 0)
        self.assertEqual(self.lines_for(), [self.na_line("session id unknown")])

    def test_row4_transcript_not_found_keeps_wall_time(self):
        os.makedirs(self.cfg)
        self.write_record(TASKS + self.mark())
        self.assertEqual(self.stop()[0], 0)
        self.assertEqual(self.lines_for(), [self.na_line("transcript not found")])
        # two project folders holding the same session id are ambiguous: also "not found"
        self.write_record(TASKS + self.mark())
        for proj in ("-a", "-b"):
            self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 1, 1, 1))], project=proj)
        self.assertEqual(self.stop()[0], 0)
        self.assertEqual(self.lines_for(), [self.na_line("transcript not found")])

    def stop_with(self, records, reason, **kw):
        self.write_record(TASKS + self.mark())
        self.transcript(records)
        self.assertEqual(self.stop(**kw)[0], 0)
        self.assertEqual(self.lines_for(), [self.na_line(reason)], records)

    def test_row5_unexpected_format(self):
        good = response("m0", "2026-11-03T10:00:30.000Z", usage(1, 1, 1, 1))
        no_counter = response("m1", "2026-11-03T10:01:00.000Z", {"input_tokens": 1, "cache_creation_input_tokens": 1,
                                                                 "output_tokens": 1})
        self.stop_with([good, no_counter], "unexpected transcript format")
        no_id = response("m1", "2026-11-03T10:01:00.000Z", usage(1, 1, 1, 1))
        del no_id["message"]["id"]
        self.stop_with([good, no_id], "unexpected transcript format")
        self.stop_with([good, response("m1", "2026-11-03 10:01:00", usage(1, 1, 1, 1))], "unexpected transcript format")
        self.stop_with([good, response("m1", "2026-11-03T10:01:00.000Z", usage(True, 1, 1, 1))],
                       "unexpected transcript format")
        self.stop_with([good, "{not json", response("m2", "2026-11-03T10:02:00.000Z", usage(1, 1, 1, 1))],
                       "unexpected transcript format")  # a bad line in the middle

    def test_a_bad_last_line_is_skipped(self):  # the file may be mid-write
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4)), '{"type": "assist'])
        self.assertEqual(self.stop()[0], 0)
        self.assertIn("in 1 · cache-read 2 · cache-write 3 · out 4 · ", self.line())

    def test_row6_no_response_in_window(self):
        self.stop_with([response("m1", "2026-11-03T09:00:00.000Z", usage(1, 1, 1, 1))], "no response in window")

    def test_sub_agents_is_not_available_unless_the_main_transcript_was_read(self):
        self.write_record(TASKS + self.mark())
        self.assertEqual(self.stop()[0], 0)  # no Claude folder: row 2 or 4, never "sub-agents 0"
        self.assert_open_and_no_zero(self.line())
        self.assertNotIn("sub-agents 0", self.line())

    def test_no_data_fixtures_have_no_zero_figure(self):
        os.makedirs(self.cfg)
        for mark in (self.mark(sid="unknown"), self.mark()):
            self.write_record(TASKS + mark)
            self.assertEqual(self.stop(sid=None)[0], 0)
            self.assert_open_and_no_zero(self.line())

    def test_a_real_zero_is_written_as_zero(self):  # guard: a zero figure from a source that was read stays zero
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(0, 5, 0, 3))])
        self.assertEqual(self.stop()[0], 0)
        self.assertIn("in 0 · cache-read 5 · cache-write 0 · out 3 · sub-agents 0 · ", self.line())

    def test_stop_in_a_plain_terminal_uses_the_sessions_in_the_marks(self):  # guard
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop(sid=None)[0], 0)
        self.assertIn("in 1 · cache-read 2 · cache-write 3 · out 4 · ", self.line())

    def test_open_line_after_a_wall_only_line_is_replaced_and_keeps_the_stored_stop_time(self):
        os.makedirs(self.cfg)
        self.write_record(TASKS + self.mark())
        self.assertEqual(self.stop()[0], 0)
        self.assertEqual(self.lines_for(), [self.na_line("transcript not found")])
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])  # the cause is fixed
        self.assertEqual(self.stop(at=None)[0], 0)  # no --at: the stored stop time is used, not now
        text = self.read_record()
        self.assertEqual(len(self.lines_for()), 1, text)
        self.assertIn("in 1 · cache-read 2 · cache-write 3 · out 4 · sub-agents 0 · 23 min wall · 1 turns", self.line())
        self.assertEqual(text.count("<!-- usage-stop T012"), 1, text)
        self.assertIn("<!-- usage-stop T012 %s -->" % STOP, text)


class SwitchOff(Base):
    def test_every_non_true_form_writes_nothing(self):  # guard: the first implementation already reads the switch
        forms = ['{"usage": {"enabled": "true"}}', '{"usage": true}', '{"usage": {"enabled": 1}}',
                 '{"usage": {"enabled": null}}', '{"usage": []}', "not json at all", "[]", ""]
        for cfg in forms:
            self.config(cfg)
            self.write_record(TASKS + self.mark())
            self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
            before = self.read_record()
            for call in (self.start, self.stop):
                code, out, err = call()
                self.assertEqual((code, out.strip()), (0, "usage off"), (cfg, out, err))
                self.assertEqual(self.read_record(), before, cfg)
        os.remove(os.path.join(self.proj, ".sdlc", "config.json"))  # no config file at all: off, and not an error
        self.assertEqual(self.start()[1].strip(), "usage off")

    def test_by_hand_works_the_same_with_or_without_a_skill(self):  # guard (S3.4)
        # The script never looks at a skill: a hand run gives the same line as the flow a skill runs.
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop()[0], 0)
        first = self.line()
        self.write_record(TASKS + self.mark())
        self.assertEqual(self.stop()[0], 0)
        self.assertEqual(self.line(), first)

    def test_workspace_root_uses_the_nearest_config(self):  # guard
        child = os.path.join(self.proj, "repo-a")
        os.makedirs(os.path.join(child, ".sdlc"))
        with open(os.path.join(child, ".sdlc", "config.json"), "w") as f:
            json.dump({"usage": {"enabled": False}}, f)  # a child with its own, off, config
        # run from the workspace root: the workspace's switch (on) counts; the child's config is not consulted
        code, out, err = self.run_usage("start", "T012", "--record", "specs/001-x/tasks.md")
        self.assertEqual(code, 0, out + err)
        self.assertIn("usage-start T012", self.read_record())
        # run from inside the child: its nearest config (off) counts
        before = self.read_record()
        code, out, err = self.run_usage("start", "T013", "--record", "specs/001-x/tasks.md", cwd=child)
        self.assertEqual((code, out.strip()), (0, "usage off"), out + err)
        self.assertEqual(self.read_record(), before)


SID_B = "1c9d8e7f-1111-4222-8333-444455556666"


class Resume(Base):
    def two_sessions(self, a_last="2026-11-03T10:40:00.000Z", stop="2026-11-03T11:30:00.000Z"):
        self.write_record(TASKS + self.mark(ts="2026-11-03T10:00:00.000Z") + self.mark(ts="2026-11-03T11:00:00.000Z", sid=SID_B))
        self.transcript([response("a1", "2026-11-03T10:05:00.000Z", usage(1, 10, 100, 1000), model="claude-opus-5-5"),
                         response("a2", a_last, usage(2, 20, 200, 2000), model="claude-opus-5-5")], sid=SID)
        self.transcript([response("b1", "2026-11-03T11:05:00.000Z", usage(4, 40, 400, 4000), model="claude-haiku-5-5"),
                         response("b2", "2026-11-03T11:20:00.000Z", usage(8, 80, 800, 8000), model="claude-haiku-5-5")],
                        sid=SID_B)
        return self.stop(at=stop)

    def test_two_sessions_add_up(self):
        code, out, err = self.two_sessions()
        self.assertEqual(code, 0, out + err)
        line = self.line()
        self.assertIn("in 15 · cache-read 150 · cache-write 1,500 · out 15,000 · sub-agents 0 · ", line)
        self.assertIn(" · 70 min wall · 4 turns · model claude-opus-5-5, claude-haiku-5-5", line)  # 40 min + 30 min
        self.assertNotIn("PARTIAL", line)

    def test_earlier_segment_end_is_last_timestamp_plus_1ms_and_next_mark_bound(self):
        # a response exactly at the earlier session's last timestamp is counted
        self.two_sessions(a_last="2026-11-03T10:40:00.000Z")
        self.assertIn("in 15 · ", self.line())
        # a record exactly at the next mark's time is not; one just before it is
        self.write_record(TASKS + self.mark(ts="2026-11-03T10:00:00.000Z") + self.mark(ts="2026-11-03T10:45:00.000Z", sid=SID_B))
        self.transcript([response("a1", "2026-11-03T10:44:59.999Z", usage(1, 0, 0, 1)),
                         response("a2", "2026-11-03T10:45:00.000Z", usage(10, 0, 0, 10)),
                         response("a3", "2026-11-03T10:50:00.000Z", usage(100, 0, 0, 100))], sid=SID)
        self.transcript([response("b1", "2026-11-03T10:46:00.000Z", usage(1000, 0, 0, 1000))], sid=SID_B)
        self.assertEqual(self.stop(at="2026-11-03T11:00:00.000Z")[0], 0)
        self.assertIn("in 1,001 · cache-read 0 · cache-write 0 · out 1,001 · ", self.line())

    def test_end_is_never_before_start(self):
        self.write_record(TASKS + self.mark(ts="2026-11-03T10:30:00.000Z") + self.mark(ts="2026-11-03T11:00:00.000Z", sid=SID_B))
        self.transcript([response("a1", "2026-11-03T10:00:00.000Z", usage(9, 9, 9, 9))], sid=SID)  # before its own mark
        self.transcript([response("b1", "2026-11-03T11:05:00.000Z", usage(1, 2, 3, 4))], sid=SID_B)
        self.assertEqual(self.stop(at="2026-11-03T11:30:00.000Z")[0], 0)
        line = self.line()
        self.assertIn("in 1 · cache-read 2 · cache-write 3 · out 4 · ", line)
        self.assertIn("PARTIAL: segment 1 (session %s): no response in window" % SID, line)
        self.assertIn(" 30 min wall", line)  # the empty segment adds no time

    def test_segment_with_missing_transcript_is_partial(self):
        self.write_record(TASKS + self.mark(ts="2026-11-03T10:00:00.000Z") + self.mark(ts="2026-11-03T11:00:00.000Z", sid=SID_B))
        self.transcript([response("b1", "2026-11-03T11:05:00.000Z", usage(1, 2, 3, 4))], sid=SID_B)  # session A has none
        self.assertEqual(self.stop(at="2026-11-03T11:30:00.000Z")[0], 0)
        line = self.line()
        self.assertIn("in 1 · cache-read 2 · cache-write 3 · out 4 · ", line)
        self.assertIn("PARTIAL: segment 1 (session %s): transcript not found" % SID, line)
        self.assertIn(" 90 min wall", line)  # the missing segment still has its wall time: it ends at the next mark

    def test_two_segments_rounded_once_half_up(self):
        def run_case(b_stop):
            self.write_record(TASKS + self.mark(ts="2026-11-03T10:00:00.000Z") + self.mark(ts="2026-11-03T11:00:00.000Z", sid=SID_B))
            self.transcript([response("a1", "2026-11-03T10:00:14.399Z", usage(1, 0, 0, 1))], sid=SID)  # 14.4 s
            self.transcript([response("b1", "2026-11-03T11:00:05.000Z", usage(1, 0, 0, 1))], sid=SID_B)
            self.assertEqual(self.stop(at=b_stop)[0], 0)
            return self.line()
        self.assertIn(" · 1 min wall · ", run_case("2026-11-03T11:00:15.600Z"))   # 14.4 + 15.6 = 30.0 s: rounds up once
        self.assertIn(" · <1 min wall · ", run_case("2026-11-03T11:00:15.500Z"))  # 29.9 s

    def test_second_start_in_the_same_session_adds_no_mark(self):
        self.assertEqual(self.start()[0], 0)
        code, out, _ = self.start()
        self.assertEqual((code, out.strip()), (0, "already started"))
        self.assertEqual(self.read_record().count("<!-- usage-start T012"), 1)

    def test_unknown_session_marks_never_match(self):  # guard: a plain append already writes one per start
        for _ in range(2):
            self.assertEqual(self.start(sid=None)[0], 0)
        self.assertEqual(self.read_record().count("session=unknown"), 2)

    def test_second_stop_changes_nothing(self):  # guard: the closed rule landed with the stored stop time
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop()[0], 0)
        before = self.read_record()
        code, out, _ = self.stop(at="2026-11-03T12:00:00.000Z")
        self.assertEqual((code, out.strip()), (0, "already closed"))
        self.assertEqual(self.read_record(), before)

    def test_restart_of_a_closed_unit_is_refused_with_a_message(self):
        self.write_record(TASKS + self.mark())
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop()[0], 0)
        before = self.read_record()
        code, out, _ = self.start()
        self.assertEqual(code, 0)
        self.assertIn("unit already closed", out)
        self.assertEqual(self.read_record(), before)

    def test_id_match_is_exact(self):  # guard
        self.write_record(TASKS + self.mark("T01") + self.mark("T012"))
        self.transcript([response("m1", "2026-11-03T10:01:00.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop("T01")[0], 0)
        code, out, _ = self.stop("T012")
        self.assertEqual(code, 0)
        self.assertNotIn("already closed", out)
        self.assertEqual((len(self.lines_for("T01")), len(self.lines_for("T012"))), (1, 1))

    def test_unit_never_stopped_leaves_only_its_mark(self):  # guard
        self.assertEqual(self.start()[0], 0)
        self.assertEqual(self.lines_for(), [])

    def test_overlap_is_flagged(self):
        self.write_record(TASKS + self.mark("T012", ts="2026-11-03T10:00:00.000Z") + self.mark("T013", ts="2026-11-03T10:10:00.000Z"))
        self.transcript([response("m1", "2026-11-03T10:11:00.000Z", usage(1, 2, 3, 4))])
        self.assertEqual(self.stop("T012", at="2026-11-03T10:20:00.000Z")[0], 0)
        self.assertTrue(self.line("T012").endswith(" · OVERLAP: T013"), self.line("T012"))
        self.assertEqual(self.stop("T013", at="2026-11-03T10:30:00.000Z")[0], 0)  # asymmetric: T012 began before T013's window
        self.assertNotIn("OVERLAP", self.line("T013"))


class RecordFile(Base):
    def test_insertion_in_a_middle_section_keeps_the_rest_byte_for_byte(self):
        text = "# T\n\n## Progress log\n\n- a log line\n\n## Other\n\nbody  \n\ttabbed\n"
        self.write_record(text)
        self.assertEqual(self.start()[0], 0)
        after = self.read_record()
        self.assertTrue(after.startswith("# T\n\n## Progress log\n\n- a log line\n<!-- usage-start T012 "), after)
        self.assertTrue(after.endswith("\n\n## Other\n\nbody  \n\ttabbed\n"), after)

    def test_mode_symlink_and_crlf_are_kept(self):
        self.write_record("# T\r\n\r\n## Progress log\r\n\r\n- line\r\n")
        os.chmod(self.rec_path(), 0o640)
        self.assertEqual(self.start()[0], 0)
        text = self.read_record()
        self.assertNotRegex(text, r"(?<!\r)\n")  # every line ending is still CRLF
        self.assertEqual(os.stat(self.rec_path()).st_mode & 0o777, 0o640)
        real = os.path.join(self.proj, "specs", "001-x", "real-tasks.md")
        os.rename(self.rec_path(), real)
        os.symlink("real-tasks.md", self.rec_path())  # a symlink to a file inside the project
        self.assertEqual(self.start("T013")[0], 0)
        self.assertTrue(os.path.islink(self.rec_path()))
        with open(real, newline="") as f:
            self.assertIn("usage-start T013", f.read())

    def test_a_failed_write_leaves_the_record_unchanged(self):
        before = self.read_record()
        folder = os.path.dirname(self.rec_path())
        os.chmod(folder, 0o500)  # no new file can be created here
        try:
            code, out, err = self.start()
        finally:
            os.chmod(folder, 0o700)
        self.assertEqual(code, 2, out + err)
        self.assertEqual(self.read_record(), before)

    def test_a_missing_record_file_is_exit_2(self):  # guard
        code, out, err = self.run_usage("start", "T012", "--record", "specs/001-x/none.md")
        self.assertEqual(code, 2, out + err)


if __name__ == "__main__":
    unittest.main()
