import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "sdlc")
FIXKIT = os.path.join(ROOT, "tests", "fixtures", "kit")
BEGIN = "<!-- BEGIN sdlc-kit (managed; edit .sdlc/config.json or the kit instead) -->"
END = "<!-- END sdlc-kit -->"


def run(*args, kit=FIXKIT):
    cmd = [sys.executable, CLI] + (["--kit", kit] if kit else []) + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return p.returncode, p.stdout, p.stderr


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = os.path.join(self._tmp.name, "proj")
        os.mkdir(self.d)

    def p(self, rel):
        return os.path.join(self.d, *rel.split("/"))

    def read(self, rel):
        with open(self.p(rel), encoding="utf-8") as f:
            return f.read()

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.p(rel)), exist_ok=True)
        with open(self.p(rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def exists(self, rel):
        return os.path.exists(self.p(rel))

    def lock(self):
        return json.loads(self.read(".sdlc/lock.json"))

    def install(self, *a):
        return run("install", self.d, *a)


class InstallTests(Base):
    def test_both_targets_paths(self):
        code, out, _ = self.install()
        self.assertEqual(code, 0, out)
        for rel in [".claude/skills/sdlc/SKILL.md", ".claude/skills/sdlc/references/ref.md",
                    ".claude/skills/debug/SKILL.md", ".claude/agents/sdlc-explorer.md",
                    ".claude/agents/sdlc-implementer.md", ".github/agents/sdlc-explorer.agent.md",
                    ".github/agents/sdlc-implementer.agent.md", ".github/copilot-instructions.md",
                    "AGENTS.md", "CLAUDE.md", ".sdlc/constitution.md", ".sdlc/principles/alpha.md",
                    ".sdlc/checklists/done.md", ".sdlc/templates/spec.md", ".sdlc/config.json",
                    ".sdlc/lock.json"]:
            self.assertTrue(self.exists(rel), rel)
        self.assertFalse(self.exists(".github/skills"))
        self.assertFalse(self.exists(".claude/skills/qa-plan"))
        self.assertIn("written", out)

    def test_skill_copied_verbatim(self):
        self.install()
        src = os.path.join(FIXKIT, "core", "skills", "sdlc", "SKILL.md")
        with open(src, "rb") as a, open(self.p(".claude/skills/sdlc/SKILL.md"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_copilot_only(self):
        code, _, _ = self.install("--targets", "copilot")
        self.assertEqual(code, 0)
        self.assertTrue(self.exists(".github/skills/sdlc/SKILL.md"))
        self.assertFalse(self.exists(".claude"))
        self.assertFalse(self.exists("AGENTS.md"))
        self.assertFalse(self.exists("CLAUDE.md"))
        agent = self.read(".github/agents/sdlc-explorer.agent.md")
        self.assertNotIn("target:", agent)
        self.assertIn("tools: ['read', 'search']\n", agent)
        self.assertNotIn("model:", agent)
        full = self.read(".github/agents/sdlc-implementer.agent.md")
        self.assertIn("tools: ['read', 'search', 'edit', 'execute', 'todo']\n", full)
        self.assertEqual(self.lock()["targets"], ["copilot"])

    def test_role_frontmatter_claude_and_target_line(self):
        self.install()
        ro = self.read(".claude/agents/sdlc-explorer.md")
        self.assertTrue(ro.startswith("---\nname: sdlc-explorer\ndescription: Read-only repository explorer.\n"
                                      "tools: Read, Grep, Glob\nmodel: haiku\n---\n"))
        self.assertIn("You explore.", ro)
        full = self.read(".claude/agents/sdlc-implementer.md")
        self.assertNotIn("tools:", full)
        self.assertIn("model: sonnet\n", full)
        self.assertIn('description: "Implements approved tasks: carefully."', full)
        gh = self.read(".github/agents/sdlc-explorer.agent.md")
        self.assertIn("target: github-copilot\n", gh)

    def test_model_override_from_config(self):
        self.write(".sdlc/config.json", json.dumps({"models": {"claude": {"explorer": "sonnet"},
                                                                "copilot": {"explorer": "gpt-x"}}}))
        self.install()
        self.assertIn("model: sonnet\n", self.read(".claude/agents/sdlc-explorer.md"))
        self.assertIn("model: gpt-x\n", self.read(".github/agents/sdlc-explorer.agent.md"))

    def test_claude_md_created_and_existing_without_import(self):
        self.install()
        self.assertEqual(self.read("CLAUDE.md"), "@AGENTS.md\n")
        d2 = os.path.join(self._tmp.name, "p2")
        os.mkdir(d2)
        with open(os.path.join(d2, "CLAUDE.md"), "w") as f:
            f.write("# Mine\n")
        self.assertEqual(run("install", d2)[0], 0)
        with open(os.path.join(d2, "CLAUDE.md")) as f:
            text = f.read()
        self.assertTrue(text.startswith("# Mine\n\n" + BEGIN + "\n@AGENTS.md\n" + END))
        d3 = os.path.join(self._tmp.name, "p3")
        os.mkdir(d3)
        with open(os.path.join(d3, "CLAUDE.md"), "w") as f:
            f.write("# Mine\n@AGENTS.md\n")
        run("install", d3)
        with open(os.path.join(d3, "CLAUDE.md")) as f:
            self.assertEqual(f.read(), "# Mine\n@AGENTS.md\n")

    def test_managed_block_content_and_outside_preserved(self):
        self.write("AGENTS.md", "# My rules\nkeep me\n")
        self.write(".sdlc/config.json", json.dumps({"extra_instructions": ["Use tabs", "No emojis"]}))
        self.install()
        text = self.read("AGENTS.md")
        self.assertTrue(text.startswith("# My rules\nkeep me\n\n" + BEGIN + "\n"))
        self.assertTrue(text.endswith(END + "\n"))
        self.assertIn("Intro line.", text)
        self.assertNotIn("# fake constitution", text)
        self.assertIn("## Index", text)
        self.assertIn("T3 Feature", text)
        self.assertIn("- **sdlc** — Pick the track", text)
        self.assertNotIn("Then route", text)
        self.assertIn("- **sdlc-explorer** — Read-only repository explorer.", text)
        self.assertIn("## Project rules\n\n- Use tabs\n- No emojis", text)
        # update preserves outside text and is idempotent
        self.write("AGENTS.md", text.replace("keep me", "keep me too"))
        code, _, _ = run("update", self.d)
        self.assertEqual(code, 0)
        self.assertIn("keep me too", self.read("AGENTS.md"))
        self.assertEqual(run("check", self.d)[0], 0)

    def test_no_project_rules_section_when_empty(self):
        self.install()
        self.assertNotIn("## Project rules", self.read("AGENTS.md"))

    def test_config_created_once_and_preserved(self):
        self.install()
        self.assertEqual(json.loads(self.read(".sdlc/config.json"))["spec_dir"], "specs")
        self.write(".sdlc/config.json", '{"spec_dir": "docs/specs"}')
        self.install()
        run("update", self.d)
        self.assertEqual(self.read(".sdlc/config.json"), '{"spec_dir": "docs/specs"}')
        self.assertNotIn(".sdlc/config.json", self.lock()["files"])

    def test_lock_contents(self):
        self.install("--modules", "qa")
        lock = self.lock()
        self.assertEqual(lock["kit_version"], "0.1.0")
        self.assertEqual(lock["targets"], ["claude", "copilot"])
        self.assertEqual(lock["modules"], ["qa"])
        self.assertEqual(lock["kit_path"], os.path.realpath(FIXKIT))
        rel = ".claude/agents/sdlc-explorer.md"
        with open(self.p(rel), "rb") as f:
            self.assertEqual(lock["files"][rel], hashlib.sha256(f.read()).hexdigest())
        self.assertIn(".sdlc/constitution.md", lock["files"])
        self.assertIn("CLAUDE.md", lock["files"])
        self.assertEqual(sorted(lock["blocks"]), [".github/copilot-instructions.md", "AGENTS.md"])
        text = self.read("AGENTS.md")
        inner = text[text.index(BEGIN) + len(BEGIN) + 1:text.index("\n" + END)]
        self.assertEqual(lock["blocks"]["AGENTS.md"], hashlib.sha256(inner.encode()).hexdigest())

    def test_modules_flag(self):
        self.install("--modules", "qa")
        self.assertTrue(self.exists(".claude/skills/qa-plan/SKILL.md"))
        self.assertTrue(self.exists(".sdlc/templates/qa.md"))
        self.assertIn("**qa-plan**", self.read("AGENTS.md"))

    def test_conflict_on_first_install_writes_nothing(self):
        self.write(".claude/agents/sdlc-explorer.md", "mine\n")
        code, out, _ = self.install()
        self.assertEqual(code, 2)
        self.assertIn("CONFLICT .claude/agents/sdlc-explorer.md", out)
        self.assertFalse(self.exists(".sdlc"))
        self.assertFalse(self.exists("AGENTS.md"))
        self.assertEqual(self.read(".claude/agents/sdlc-explorer.md"), "mine\n")
        code, _, _ = self.install("--force")
        self.assertEqual(code, 0)
        self.assertIn("Read-only", self.read(".claude/agents/sdlc-explorer.md"))

    def test_target_must_be_existing_dir(self):
        code, _, err = run("install", os.path.join(self._tmp.name, "nope"))
        self.assertEqual(code, 1)
        self.assertIn("not an existing directory", err)
        f = os.path.join(self._tmp.name, "file")
        open(f, "w").close()
        self.assertEqual(run("install", f)[0], 1)

    def test_git_repo_ok(self):
        os.mkdir(self.p(".git"))
        self.assertEqual(self.install()[0], 0)

    def test_malicious_lock_path_refused(self):
        self.install()
        lock = self.lock()
        lock["files"]["../evil"] = "0" * 64
        self.write(".sdlc/lock.json", json.dumps(lock))
        code, _, err = run("uninstall", self.d)
        self.assertEqual(code, 1)
        self.assertIn("unsafe path", err)


def managed_block(text):
    return text[text.index(BEGIN):text.index(END) + len(END)]


class ModuleRules(Base):
    RULES = "## Module rules\n\n### rul\n\n- Fixture module rule one.\n- Read `.sdlc/templates/rul.md` first."

    def test_rules_rendered_in_both_blocks_between_roles_and_project_rules(self):
        self.write(".sdlc/config.json", json.dumps({"extra_instructions": ["Use tabs"]}))
        code, out, _ = self.install("--modules", "rul")
        self.assertEqual(code, 0, out)
        agents = managed_block(self.read("AGENTS.md"))
        self.assertIn(self.RULES, agents)
        self.assertLess(agents.index("### Roles"), agents.index("## Module rules"))
        self.assertLess(agents.index("## Module rules"), agents.index("## Project rules"))
        self.assertEqual(agents, managed_block(self.read(".github/copilot-instructions.md")))
        self.assertEqual(run("check", self.d)[0], 0)

    def test_no_module_rules_section_without_rules(self):
        self.install("--modules", "qa")
        self.assertNotIn("## Module rules", self.read("AGENTS.md"))
        self.assertNotIn("## Module rules", self.read(".github/copilot-instructions.md"))

    def test_add_then_remove_restores_module_free_install(self):
        self.install()
        before = {r: self.read(r) for r in ("AGENTS.md", ".github/copilot-instructions.md")}
        lock_before = self.lock()
        self.install("--modules", "rul")
        self.assertNotEqual(self.read("AGENTS.md"), before["AGENTS.md"])
        code, out, _ = self.install("--modules", "")
        self.assertEqual(code, 0, out)
        self.assertEqual({r: self.read(r) for r in before}, before)
        self.assertEqual(self.lock(), lock_before)
        self.assertFalse(self.exists(".sdlc/templates/rul.md"))

    def test_bytecode_in_skill_folder_not_installed(self):
        kit = os.path.join(self._tmp.name, "kit2")
        shutil.copytree(FIXKIT, kit)
        cache = os.path.join(kit, "core", "skills", "debug", "__pycache__")
        os.makedirs(cache)
        with open(os.path.join(cache, "x.cpython-39.pyc"), "wb") as f:
            f.write(b"\0")
        with open(os.path.join(kit, "core", "skills", "debug", "stray.pyc"), "wb") as f:
            f.write(b"\0")
        code, out, _ = run("install", self.d, kit=kit)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.exists(".claude/skills/debug/SKILL.md"))
        self.assertFalse(self.exists(".claude/skills/debug/__pycache__"))
        self.assertFalse(self.exists(".claude/skills/debug/stray.pyc"))
        self.assertFalse(any("pyc" in r for r in self.lock()["files"]))



class RealKitRules(Base):
    def test_review_rule_names_skill_and_verdict_line(self):
        code, out, _ = run("install", self.d, kit=ROOT)
        self.assertEqual(code, 0, out)
        rule = [l for l in managed_block(self.read("AGENTS.md")).split("\n") if "Review" in l and "verdict" in l]
        self.assertEqual(len(rule), 1, rule)
        for needle in ["`sdlc-review`", "`VERDICT: APPROVED`", "`VERDICT: REJECTED`", "not under `.sdlc/`"]:
            self.assertIn(needle, rule[0])

    def test_spec_002_evaluation_has_a_recorded_status_and_readme_matches(self):
        with open(os.path.join(ROOT, "specs", "002-dense-find-command", "tasks.md"), encoding="utf-8") as f:
            self.assertRegex(f.read().split("\n")[2], r"Status: parked \(.+, \d{4}-\d{2}-\d{2}\)")
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        self.assertIn("parked", readme)
        self.assertNotIn("hasn't run. Don't enable", readme)

    def test_license_is_mit_and_readme_support_table_names_each_host(self):
        with open(os.path.join(ROOT, "LICENSE"), encoding="utf-8") as f:
            lic = f.read()
        self.assertTrue(lic.startswith("MIT License"))
        self.assertRegex(lic, r"Copyright \(c\) 2026 \S+")
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        for needle in ("| Claude Code | first-class", "| GitHub Copilot | rendered, not evaluated",
                       "internal to Claude Code", "`--resume` keeps the session id", "no concurrency lock"):
            self.assertIn(needle, readme)
        self.assertNotIn("no `LICENSE` file", readme)

    def test_adr_0003_fixes_the_enforcement_model(self):
        with open(os.path.join(ROOT, "docs", "adr", "0003-enforcement-model.md"), encoding="utf-8") as f:
            adr = f.read()
        self.assertIn("Status: accepted", adr)
        for needle in ("| Push while tests are red |", "| Source edit on a T3 feature without approval |",
                       "| Task ticked without evidence |", "| Reviewer able to write |",
                       "`enforce`", "off by default", "| Claude Code |", "| GitHub Copilot |", "Level 6"):
            self.assertIn(needle, adr)

    def test_real_kit_lints_clean(self):
        code, out, _ = run("lint", kit=ROOT)
        self.assertEqual(code, 0, out)

    def test_value_gate_in_plan_template_and_analyze(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        plan = self.read(".sdlc/templates/plan.md")
        rollout = plan[plan.index("## Rollout & rollback"):plan.index("## Complexity justifications")]
        self.assertIn("Value gate", rollout)
        analyze = self.read(".claude/skills/sdlc-analyze/SKILL.md")
        line = [l for l in analyze.split("\n") if "Value gate" in l]
        self.assertEqual(len(line), 1, line)
        self.assertIn("threshold", line[0])


class DenseModule(Base):
    """The real modules/dense, rendered with the real kit."""
    KIT = os.environ.get("SDLC_TEST_KIT", ROOT)  # override only to check that this class catches breakage
    SKILL = "skills/sdlc-dense-index"

    def dap(self, script, *args):
        p = subprocess.run([sys.executable, self.p(script)] + list(args), capture_output=True, text=True,
                           timeout=20, cwd=self.d)
        return p.returncode, p.stdout

    def test_real_kit_lints(self):
        code, out, _ = run("lint", kit=self.KIT)
        self.assertEqual(code, 0, out)

    def test_install_renders_rules_skill_and_script(self):
        code, out, _ = run("install", self.d, "--modules", "dense", kit=self.KIT)
        self.assertEqual(code, 0, out)
        agents = managed_block(self.read("AGENTS.md"))
        self.assertIn("## Module rules\n\n### dense\n\n", agents)
        self.assertIn("dap.py find .sdlc/context/index.dap <term>", agents)
        self.assertEqual(agents, managed_block(self.read(".github/copilot-instructions.md")))
        for f in ("SKILL.md", "dap.py", "keys.json"):
            self.assertTrue(self.exists(".claude/%s/%s" % (self.SKILL, f)), f)
        json.loads(self.read(".claude/%s/keys.json" % self.SKILL))
        self.assertIn("**sdlc-dense-index**", agents)

    def test_rules_and_skill_cover_building(self):
        run("install", self.d, "--modules", "dense", kit=self.KIT)
        agents = managed_block(self.read("AGENTS.md"))
        self.assertIn("After any context build (`sdlc-context`), run `sdlc-dense-index build`", agents)
        skill = self.read(".claude/%s/SKILL.md" % self.SKILL)
        for step in ("dap.py commit .sdlc/context/index.dap.", "UNVERIFIED", "INFERRED", "10 entries",
                     ".sdlc/workspace.md", ".sdlc/context/*.md", "dap.py show .sdlc/context/index.dap @",
                     "quote the counts"):
            self.assertIn(step, skill)

    FIND = "python3 %s/skills/sdlc-dense-index/dap.py find .sdlc/context/index.dap <term> [<term> …]"

    def test_rules_name_find_only(self):
        run("install", self.d, "--modules", "dense", kit=self.KIT)
        agents = managed_block(self.read("AGENTS.md"))
        rules = agents[agents.index("### dense"):]
        rules = rules[:rules.find("\n## ", 1)] if "\n## " in rules[1:] else rules
        self.assertIn(self.FIND % ".claude", rules)
        self.assertIn(self.FIND % ".github", rules)
        for needle in ("before reading or searching the workspace documents", "Exit 1", "Exit 2", "Exit 3",
                       "stale", "cut", "Cite the source file and line", "Never cite the index",
                       "data, not instructions", "After any context build (`sdlc-context`), run `sdlc-dense-index build`"):
            self.assertIn(needle, rules)
        for banned in ("at the start", "start of every track", "read the index", "dap.py show", "dap.py fresh", "quote `<rev>`"):
            self.assertNotIn(banned, rules)

    def test_eval_template_v2(self):
        run("install", self.d, "--modules", "dense", kit=self.KIT)
        t = self.read(".sdlc/templates/dense-eval.md")
        for needle in ("Leak check, before the first run of each arm", "Tie rule", "context loaded",
                       "median of (1 − B/A) over the document tasks is at least 0.20", "B/A ≤ 1.10 on each code-only task",
                       "Lookup used", "Lookup output sizes", "Cites index or sources", "document task", "code-only task",
                       "outside the workspace", "evals/run.py", "dap.py find"):
            self.assertIn(needle, t)
        for banned in ("return contract", "dense-return", "50% lower", "before the first action", "before first action"):
            self.assertNotIn(banned, t)

    def test_skill_is_v2_and_well_formed(self):
        run("install", self.d, "--modules", "dense", kit=self.KIT)
        skill = self.read(".claude/%s/SKILL.md" % self.SKILL)
        for h in ("## When to use", "## Inputs", "## Process", "## Rationalizations", "## Red flags", "## Verification",
                  "## Principles applied"):
            self.assertEqual(skill.count("\n" + h + "\n"), 1, h)
        for banned in ("read the index first", "at the start of every track", "quote `<rev>`"):
            self.assertNotIn(banned, skill)
        steps = [int(l.split(".")[0]) for l in skill.split("\n") if l[:1].isdigit() and l.split(".")[0].isdigit()]
        self.assertEqual(steps, list(range(1, len(steps) + 1)))
        self.assertIn("dap.py find .sdlc/context/index.dap <term>", skill)

    def test_installed_find_runs(self):
        code, out, _ = run("install", self.d, "--targets", "copilot", "--modules", "dense", kit=self.KIT)
        self.assertEqual(code, 0, out)
        self.write(".sdlc/context/repo.md", "# Repo\n\n## Purpose\n\nA routing thing.\n")
        with open(self.p(".sdlc/context/repo.md"), "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()[:12]
        self.write(".sdlc/context/index.dap", "#dap 1 built 2026-10-26\nsrc r context/repo.md %s\n"
                                             "[repo thing]\ndesc: A thing. @r#purpose\n" % h)
        code, out = self.dap(".github/%s/dap.py" % self.SKILL, "find", ".sdlc/context/index.dap", "routing", "thing")
        self.assertEqual(code, 0, out)
        self.assertIn(".sdlc/context/repo.md:3-5", out)
        self.assertIn("A routing thing.", out)

    def snapshot(self):
        out = {}
        for dp, _, fn in os.walk(self.d):
            for f in fn:
                full = os.path.join(dp, f)
                with open(full, "rb") as fh:
                    out[os.path.relpath(full, self.d).replace(os.sep, "/")] = hashlib.sha256(fh.read()).hexdigest()
        return out

    def test_add_and_remove_restores_install(self):
        self.write(".sdlc/context/index.dap", "#dap 1 built 2026-10-26\n")  # project-owned, never touched
        code, out, _ = run("install", self.d, kit=self.KIT)
        self.assertEqual(code, 0, out)
        before = self.snapshot()
        block_before = managed_block(self.read("AGENTS.md"))
        run("install", self.d, "--modules", "dense", kit=self.KIT)
        during = self.snapshot()
        self.assertEqual([r for r in before if r not in during], [])
        changed = sorted(r for r in before if during[r] != before[r])
        self.assertEqual(changed, [".github/copilot-instructions.md", ".sdlc/lock.json", "AGENTS.md"])
        added = [r for r in during if r not in before]
        self.assertTrue(added)
        for r in added:
            self.assertTrue(r.startswith((".claude/skills/sdlc-dense-index/", ".sdlc/templates/dense-")), r)
        # Allowed: the Module rules section and the module's own Skills index line (module skills are indexed).
        block = managed_block(self.read("AGENTS.md"))
        start = block.index("\n\n## Module rules")
        end = block.find("\n\n## Project rules", start)
        block = block[:start] + (block[end:] if end >= 0 else block[-len("\n" + END):])
        block = "\n".join(l for l in block.split("\n") if not l.startswith("- **sdlc-dense-index** — "))
        self.assertEqual(block, block_before)
        code, out, _ = run("install", self.d, "--modules", "", kit=self.KIT)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.snapshot(), before)

    def test_installed_script_runs(self):
        run("install", self.d, "--modules", "dense", kit=self.KIT)
        self.write(".sdlc/context/repo.md", "# Repo\n\n## Purpose\n\nA thing.\n")
        with open(self.p(".sdlc/context/repo.md"), "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()[:12]
        self.write(".sdlc/context/index.dap", "#dap 1 built 2026-10-26\nsrc r context/repo.md %s\n"
                                             "[repo thing]\ndesc: A thing. @r#purpose\n" % h)
        script = ".claude/%s/dap.py" % self.SKILL
        self.assertEqual(self.dap(script, "validate", ".sdlc/context/index.dap"), (0, "valid\n"))
        code, out = self.dap(script, "fresh", ".sdlc/context/index.dap")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("fresh "), out)

    def test_copilot_only_install_uses_github_skills(self):
        code, out, _ = run("install", self.d, "--targets", "copilot", "--modules", "dense", kit=self.KIT)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.exists(".github/%s/dap.py" % self.SKILL))
        self.assertIn(".github/skills/sdlc-dense-index/dap.py", self.read(".github/copilot-instructions.md"))


class UsageSkill(Base):
    """Spec 003: the sdlc-usage skill and the skills that call it, rendered from the real kit."""
    SKILL = "skills/sdlc-usage"
    SID = "0b8b2d7f-d1c8-4d58-86d4-eb8b0ad184f6"
    # The files an install of the kit at `main` fc77daa (before spec 003) wrote, except .sdlc/lock.json.
    MAIN_PATHS = {
        ".claude/agents/sdlc-explorer.md",
        ".claude/agents/sdlc-implementer.md",
        ".claude/agents/sdlc-planner.md",
        ".claude/agents/sdlc-reviewer.md",
        ".claude/agents/sdlc-security-reviewer.md",
        ".claude/skills/sdlc-analyze/SKILL.md",
        ".claude/skills/sdlc-clarify/SKILL.md",
        ".claude/skills/sdlc-context/SKILL.md",
        ".claude/skills/sdlc-converge/SKILL.md",
        ".claude/skills/sdlc-debug/SKILL.md",
        ".claude/skills/sdlc-grill/SKILL.md",
        ".claude/skills/sdlc-handoff/SKILL.md",
        ".claude/skills/sdlc-implement/SKILL.md",
        ".claude/skills/sdlc-plan/SKILL.md",
        ".claude/skills/sdlc-retro/SKILL.md",
        ".claude/skills/sdlc-review/SKILL.md",
        ".claude/skills/sdlc-review/references/review-method.md",
        ".claude/skills/sdlc-setup/SKILL.md",
        ".claude/skills/sdlc-ship/SKILL.md",
        ".claude/skills/sdlc-specify/SKILL.md",
        ".claude/skills/sdlc-tasks/SKILL.md",
        ".claude/skills/sdlc-tdd/SKILL.md",
        ".claude/skills/sdlc/SKILL.md",
        ".github/agents/sdlc-explorer.agent.md",
        ".github/agents/sdlc-implementer.agent.md",
        ".github/agents/sdlc-planner.agent.md",
        ".github/agents/sdlc-reviewer.agent.md",
        ".github/agents/sdlc-security-reviewer.agent.md",
        ".github/copilot-instructions.md",
        ".sdlc/checklists/accessibility.md",
        ".sdlc/checklists/compatibility-migration.md",
        ".sdlc/checklists/definition-of-done.md",
        ".sdlc/checklists/observability.md",
        ".sdlc/checklists/performance.md",
        ".sdlc/checklists/requirements-quality.md",
        ".sdlc/checklists/security.md",
        ".sdlc/config.json",
        ".sdlc/constitution.md",
        ".sdlc/principles/agree-before-building.md",
        ".sdlc/principles/depth-follows-risk.md",
        ".sdlc/principles/encode-lessons.md",
        ".sdlc/principles/evidence-over-claims.md",
        ".sdlc/principles/fail-safe-keep-work.md",
        ".sdlc/principles/guard-context.md",
        ".sdlc/principles/prove-it-works.md",
        ".sdlc/principles/root-causes.md",
        ".sdlc/principles/subtract-before-adding.md",
        ".sdlc/principles/thin-vertical-slices.md",
        ".sdlc/templates/adr.md",
        ".sdlc/templates/bug.md",
        ".sdlc/templates/context.md",
        ".sdlc/templates/handoff.md",
        ".sdlc/templates/mini-spec.md",
        ".sdlc/templates/plan.md",
        ".sdlc/templates/pr.md",
        ".sdlc/templates/prd.md",
        ".sdlc/templates/review-report.md",
        ".sdlc/templates/spec.md",
        ".sdlc/templates/tasks.md",
        ".sdlc/templates/workspace.md",
        "AGENTS.md",
        "CLAUDE.md",
    }

    def enable(self):
        self.write(".sdlc/config.json", json.dumps({"usage": {"enabled": True}}))

    def run_script(self, script, *args):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": self.d, "CLAUDE_CONFIG_DIR": self.p("claude-cfg"),
               "CLAUDE_CODE_SESSION_ID": self.SID}
        p = subprocess.run([sys.executable, "-B", self.p(script)] + list(args), capture_output=True, text=True,
                           timeout=20, cwd=self.d, env=env, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout + p.stderr

    def flow(self, script):
        """start, a tiny transcript, stop: the line must carry the transcript's figures."""
        self.write("specs/001-x/tasks.md", "# Tasks\n\n## Progress log\n\n")
        code, out = self.run_script(script, "start", "T001", "--record", "specs/001-x/tasks.md")
        self.assertEqual(code, 0, out)
        mark = re.search(r"usage-start T001 (\S+) session=", self.read("specs/001-x/tasks.md")).group(1)
        year = int(mark[:4]) + 1  # a response one year after the mark, and a stop two years after it
        rec = {"type": "assistant", "timestamp": "%d%s" % (year, mark[4:]),
               "message": {"id": "m1", "model": "claude-opus-5-5",
                           "usage": {"input_tokens": 5, "cache_read_input_tokens": 7, "cache_creation_input_tokens": 11,
                                     "output_tokens": 13}}}
        self.write("claude-cfg/projects/-p/%s.jsonl" % self.SID, json.dumps(rec) + "\n")
        code, out = self.run_script(script, "stop", "T001", "--record", "specs/001-x/tasks.md",
                                    "--at", "%d%s" % (year + 1, mark[4:]))
        self.assertEqual(code, 0, out)
        self.assertRegex(self.read("specs/001-x/tasks.md"),
                         r"- usage T001: in 5 · cache-read 7 · cache-write 11 · out 13 · sub-agents 0 · .* wall · 1 turns")

    def installed_paths(self):
        out = set()
        for dp, _, files in os.walk(self.d):
            for f in files:
                out.add(os.path.relpath(os.path.join(dp, f), self.d).replace(os.sep, "/"))
        return out - {".sdlc/lock.json"}

    def test_install_adds_only_the_expected_paths(self):
        code, out, _ = run("install", self.d, kit=ROOT)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.installed_paths(), UsageSkill.MAIN_PATHS | {".claude/skills/sdlc-usage/SKILL.md",
                                                                          ".claude/skills/sdlc-usage/usage.py"})
        default = json.loads(open(os.path.join(ROOT, "adapters", "config.default.json")).read())
        self.assertEqual(json.loads(self.read(".sdlc/config.json")), default)
        self.assertNotIn("usage", default)
        self.assertEqual(run("check", self.d, kit=ROOT)[1].strip(), "ok")
        self.enable()  # FR-018: lint and drift stay green with the switch on
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        self.assertEqual(run("check", self.d, kit=ROOT)[1].strip(), "ok")
        self.assertEqual(run("lint", kit=ROOT)[0], 0)

    def test_reinstall_is_idempotent_and_check_is_ok(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        before = {p: open(self.p(p), "rb").read() for p in self.installed_paths()}
        code, out, _ = run("install", self.d, kit=ROOT)
        self.assertEqual(code, 0, out)
        self.assertEqual({p: open(self.p(p), "rb").read() for p in self.installed_paths()}, before)
        self.assertEqual(run("check", self.d, kit=ROOT)[1].strip(), "ok")

    def test_install_ships_the_skill_and_script(self):
        code, out, _ = run("install", self.d, kit=ROOT)
        self.assertEqual(code, 0, out)
        for f in ("SKILL.md", "usage.py"):
            self.assertTrue(self.exists(".claude/%s/%s" % (self.SKILL, f)), f)
        self.assertIn("**sdlc-usage**", managed_block(self.read("AGENTS.md")))
        self.assertFalse(self.exists(".claude/%s/__pycache__" % self.SKILL))
        self.assertEqual(run("check", self.d, kit=ROOT)[1].strip(), "ok")
        copilot = os.path.join(self._tmp.name, "copilot-only")
        os.makedirs(copilot)
        self.assertEqual(run("install", copilot, "--targets", "copilot", kit=ROOT)[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(copilot, ".github", self.SKILL, "usage.py")))

    def test_installed_script_runs(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        self.enable()
        self.flow(".claude/%s/usage.py" % self.SKILL)

    def test_installed_script_runs_for_a_copilot_only_install(self):
        self.assertEqual(run("install", self.d, "--targets", "copilot", kit=ROOT)[0], 0)
        self.enable()
        self.flow(".github/%s/usage.py" % self.SKILL)

    def test_bug_template_has_a_usage_section(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        self.assertEqual(self.read(".sdlc/templates/bug.md").count("\n## Usage\n"), 1)

    def test_debug_names_the_exact_commands_and_the_bug_record(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        text = self.read(".claude/skills/sdlc-debug/SKILL.md")
        for needle in ("usage.py start <slug> --record", "usage.py stop <slug> --record", '--section "Usage"',
                       "usage.enabled", "bugs/<slug>.md", "create the bug record"):
            self.assertIn(needle, text)

    def test_debug_starts_usage_in_step_one_before_any_run(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        text = self.read(".claude/skills/sdlc-debug/SKILL.md")
        steps = text[text.index("\n## Process\n"):]
        one = steps[steps.index("\n1. "):steps.index("\n2. ")]
        two = steps[steps.index("\n2. "):steps.index("\n3. ")]
        self.assertIn("usage.py start <slug> --record", one)
        self.assertIn("before you run the failing test", one)
        self.assertNotIn("usage.py start", two)

    def test_implement_names_the_exact_commands_for_a_finding(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        text = self.read(".claude/skills/sdlc-implement/SKILL.md")
        for needle in ("review finding", "<pass>-<finding id>", "review1-F3", "one-line text", "Progress log"):
            self.assertIn(needle, text)

    def test_every_skill_that_asks_names_the_command(self):  # guard for sdlc-implement, already covered by the task step
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        for name in ("sdlc-implement", "sdlc-debug"):
            for line in self.read(".claude/skills/%s/SKILL.md" % name).split("\n"):
                if "usage.py" in line:
                    self.assertRegex(line, r"usage\.py (start|stop) ", (name, line))
                    self.assertIn("--record", line, (name, line))

    def test_implement_runs_start_and_stop_for_a_task(self):
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)
        text = self.read(".claude/skills/sdlc-implement/SKILL.md")
        for needle in ("usage.py start", "usage.py stop", "--record", "usage.enabled", "one after another"):
            self.assertIn(needle, text)


class VerifySkills(Base):
    def skill(self, name):
        return self.read(".claude/skills/%s/SKILL.md" % name)

    def setUp(self):
        super().setUp()
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)

    def check_writer(self, name):
        text = self.skill(name)
        line = [l for l in text.split("\n") if "bin/sdlc verify" in l]
        self.assertEqual(len(line), 1, (name, line))
        for needle in ("<kit_path>/bin/sdlc verify .", "--repo <repo>", "final line", "(clean tree)", "tool timeout"):
            self.assertIn(needle, line[0], (name, needle))

    def test_implement_debug_and_ship_run_verify_and_quote_the_final_line(self):
        for name in ("sdlc-implement", "sdlc-debug", "sdlc-ship"):
            self.check_writer(name)

    def test_ship_runs_it_after_the_commit_and_before_any_push(self):
        line = [l for l in self.skill("sdlc-ship").split("\n") if "bin/sdlc verify" in l][0]
        self.assertIn("after the commit", line)
        self.assertIn("before any push or PR", line)

    def test_review_reads_the_record_and_never_runs_the_command(self):
        text = self.skill("sdlc-review")
        line = [l for l in text.split("\n") if ".sdlc/evidence/verify.json" in l]
        self.assertEqual(len(line), 1, line)
        for needle in ("revision", "stale", "absent"):
            self.assertIn(needle, line[0])
        self.assertNotIn("bin/sdlc verify", text)
        role = self.read(".claude/agents/sdlc-reviewer.md")
        self.assertIn("tools: Read, Grep, Glob", role)

    def test_ship_gate_runs_the_suite_once_and_review_gets_the_head_from_the_caller(self):
        ship = self.skill("sdlc-ship").split("\n")
        step2 = [l for l in ship if l.startswith("2. ")][0]
        self.assertIn("step 4", step2)
        self.assertNotIn("each run once", step2)
        review = [l for l in self.skill("sdlc-review").split("\n") if ".sdlc/evidence/verify.json" in l][0]
        self.assertIn("the caller", review)
        self.assertIn("head", review)

    def test_readme_says_uninstall_keeps_the_evidence_folder(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        self.assertIn("uninstall` keeps `.sdlc/evidence/`", readme)

    def test_constitution_carries_one_matching_rule(self):
        rule = [l for l in managed_block(self.read("AGENTS.md")).split("\n") if "sdlc verify" in l]
        self.assertEqual(len(rule), 1, rule)
        for needle in ("final line", "(clean tree)"):
            self.assertIn(needle, rule[0])


class GateSkills(Base):
    def skill(self, name):
        return self.read(".claude/skills/%s/SKILL.md" % name)

    def setUp(self):
        super().setUp()
        self.assertEqual(run("install", self.d, kit=ROOT)[0], 0)

    def line(self, text, needle):
        found = [l for l in text.split("\n") if needle in l]
        self.assertEqual(len(found), 1, (needle, found))
        return found[0]

    def test_analyze_records_approval_through_the_command_after_explicit_approval(self):
        step = self.line(self.skill("sdlc-analyze"), "bin/sdlc gate approve")
        self.assertIn("one exception", self.line(self.skill("sdlc-analyze"), "Read-only."))
        for needle in ("<kit_path>/bin/sdlc gate approve", "--by", "explicit approval", "--repo <repo>", "again"):
            self.assertIn(needle, step)
        self.assertNotIn("add `Approved: <name>, YYYY-MM-DD` beneath it", self.skill("sdlc-analyze"))

    def test_implement_readiness_runs_approved_with_a_legacy_fallback(self):
        text = self.skill("sdlc-implement")
        step = self.line(text, "gate approved")
        for needle in ("<kit_path>/bin/sdlc gate approved", "--spec", "no approval digest", "ask the human", "changed"):
            self.assertIn(needle, step)
        self.assertNotIn("or the user approved it in this session", text)

    def test_implement_finish_runs_evidence_for_ticks_and_not_green_at_head(self):
        text = self.skill("sdlc-implement")
        self.assertIn("quote its last line", self.line(text, "bin/sdlc gate evidence-for-ticks"))
        self.assertNotIn("green-at-head", text)

    def test_implement_says_a_task_line_edit_needs_a_new_approval_and_logs_the_hash(self):
        text = self.skill("sdlc-implement")
        self.assertIn("gate approve", self.line(text, "update the task line"))
        self.assertIn("short hash", self.line(text, "Never tick work that is blocked"))

    def test_ship_runs_evidence_and_green_after_the_verify(self):
        text = self.skill("sdlc-ship")
        step = self.line(text, "gate green-at-head")
        for needle in ("gate evidence-for-ticks", "after", "verify"):
            self.assertIn(needle, step)

    def test_constitution_has_one_gate_rule(self):
        rule = [l for l in managed_block(self.read("AGENTS.md")).split("\n") if "gate approved" in l]
        self.assertEqual(len(rule), 1, rule)
        for needle in ("gate evidence-for-ticks", "gate green-at-head", "last line"):
            self.assertIn(needle, rule[0])

    def test_templates_state_the_evidence_format_and_the_approved_grammar(self):
        tasks = self.read(".sdlc/templates/tasks.md")
        log = tasks[tasks.index("## Progress log"):]
        for needle in ("short commit hash", "## Convergence", "re-approval", "baseline"):
            self.assertIn(needle, log + tasks)
        spec = self.read(".sdlc/templates/spec.md")
        self.assertIn("gate approve", self.line(spec, "Approved:"))

    def test_readme_rendering_and_design_document_the_gate(self):
        for rel in ("README.md", os.path.join("adapters", "RENDERING.md"), "DESIGN.md"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                self.assertIn("gate", f.read(), rel)
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        for needle in ("sdlc gate approved", "evidence-for-ticks", "green-at-head"):
            self.assertIn(needle, readme)


class EvalRows(unittest.TestCase):
    def rows(self):
        with open(os.path.join(ROOT, "evals", "scenarios.md"), encoding="utf-8") as f:
            return {l.split("|")[1].strip(): l for l in f.read().split("\n") if l.startswith("| ") and l.count("|") >= 4}

    def test_u1_u2_u3_and_ur1_exist_and_name_neither_skill_nor_script(self):
        rows = self.rows()
        for key in ("U1", "U2", "U3", "UR1"):
            self.assertIn(key, rows)
        for key in ("U1", "U2", "U3"):
            prompt = rows[key].split("|")[2]
            self.assertNotIn("sdlc-usage", prompt, key)
            self.assertNotIn("usage.py", prompt, key)
            self.assertNotIn("usage", prompt.lower().replace("usage metrics", ""), key)

    def test_v1_exists_names_no_skill_or_command_and_expects_the_final_line(self):
        row = self.rows()["V1"]
        prompt, expect = re.findall(r'"([^"]+)"', row.split("|")[2])[-1], row.split("|")[-2]
        for word in ("sdlc", "verify", "skill"):
            self.assertNotIn(word, prompt.lower(), word)
        self.assertIn("verify:", expect)
        self.assertIn("(clean tree)", expect)

    def test_readme_and_rendering_document_the_verify_command(self):
        for rel in ("README.md", os.path.join("adapters", "RENDERING.md")):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("verify", text, rel)
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        self.assertIn("POSIX", readme)
        self.assertIn(".sdlc/evidence/verify.json", readme)


class CheckUpdateTests(Base):
    def setUp(self):
        super().setUp()
        self.install()

    def test_check_clean(self):
        code, out, _ = run("check", self.d)
        self.assertEqual(code, 0, out)

    def test_modified_and_missing(self):
        self.write(".claude/skills/debug/SKILL.md", "changed\n")
        os.remove(self.p(".sdlc/constitution.md"))
        code, out, _ = run("check", self.d)
        self.assertEqual(code, 1)
        self.assertIn("MODIFIED .claude/skills/debug/SKILL.md", out)
        self.assertIn("MISSING .sdlc/constitution.md", out)

    def test_block_drift(self):
        self.write("AGENTS.md", self.read("AGENTS.md").replace("Intro line.", "Hacked."))
        code, out, _ = run("check", self.d)
        self.assertEqual(code, 1)
        self.assertIn("DRIFT AGENTS.md", out)

    def test_outside_block_edit_is_not_drift(self):
        self.write("AGENTS.md", "# top\n\n" + self.read("AGENTS.md"))
        self.assertEqual(run("check", self.d)[0], 0)

    def test_claude_md_user_edits_ok_while_import_present(self):
        self.write("CLAUDE.md", "@AGENTS.md\nmore\n")
        self.assertEqual(run("check", self.d)[0], 0)

    def test_duplicate_spec_warning(self):
        for n in ("001-a", "001-b", "002-c", "notes"):
            os.makedirs(self.p("specs/" + n))
        self.write("specs/003-file.md", "x")
        code, out, _ = run("check", self.d)
        self.assertEqual(code, 0)
        self.assertIn("DUPLICATE-SPEC 001: 001-a, 001-b", out)
        self.assertNotIn("002", out)

    def test_outdated_warning(self):
        lock = self.lock()
        lock["kit_version"] = "0.0.9"
        self.write(".sdlc/lock.json", json.dumps(lock))
        code, out, _ = run("check", self.d)
        self.assertEqual(code, 0)
        self.assertIn("OUTDATED", out)

    def test_update_skips_modified_then_force(self):
        rel = ".claude/agents/sdlc-explorer.md"
        self.write(rel, "local edit\n")
        code, out, _ = run("update", self.d)
        self.assertEqual(code, 2)
        self.assertIn("SKIP " + rel, out)
        self.assertEqual(self.read(rel), "local edit\n")
        self.assertEqual(run("check", self.d)[0], 1)
        code, _, _ = run("update", self.d, "--force")
        self.assertEqual(code, 0)
        self.assertIn("Read-only", self.read(rel))
        self.assertEqual(run("check", self.d)[0], 0)

    def test_update_restores_missing(self):
        os.remove(self.p(".sdlc/templates/spec.md"))
        self.assertEqual(run("update", self.d)[0], 0)
        self.assertTrue(self.exists(".sdlc/templates/spec.md"))

    def test_update_skips_edited_block(self):
        text = self.read("AGENTS.md").replace("Intro line.", "Hacked.")
        self.write("AGENTS.md", text)
        code, out, _ = run("update", self.d)
        self.assertEqual(code, 2)
        self.assertIn("SKIP AGENTS.md", out)
        self.assertEqual(self.read("AGENTS.md"), text)
        self.assertEqual(run("update", self.d, "--force")[0], 0)
        self.assertIn("Intro line.", self.read("AGENTS.md"))

    def test_update_removes_files_no_longer_rendered(self):
        kit = os.path.join(self._tmp.name, "kit2")
        shutil.copytree(FIXKIT, kit)
        shutil.rmtree(os.path.join(kit, "core", "skills", "debug"))
        os.remove(os.path.join(kit, "core", "roles", "explorer.md"))
        self.write(".claude/agents/sdlc-implementer.md", "x")  # keep modified; also still rendered
        code, out, _ = run("update", self.d, kit=kit)
        self.assertEqual(code, 2)
        self.assertFalse(self.exists(".claude/skills/debug"))
        self.assertFalse(self.exists(".claude/agents/sdlc-explorer.md"))
        self.assertFalse(self.exists(".github/agents/sdlc-explorer.agent.md"))
        self.assertNotIn("sdlc-explorer", self.read("AGENTS.md"))

    def test_update_updates_changed_kit_content(self):
        kit = os.path.join(self._tmp.name, "kit2")
        shutil.copytree(FIXKIT, kit)
        with open(os.path.join(kit, "core", "principles", "alpha.md"), "w") as f:
            f.write("# alpha v2\n")
        with open(os.path.join(kit, "VERSION"), "w") as f:
            f.write("0.2.0\n")
        self.assertEqual(run("update", self.d, kit=kit)[0], 0)
        self.assertEqual(self.read(".sdlc/principles/alpha.md"), "# alpha v2\n")
        self.assertEqual(self.lock()["kit_version"], "0.2.0")

    def test_reinstall_acts_as_update_and_keeps_lock_targets(self):
        run("uninstall", self.d)
        self.install("--targets", "copilot")
        code, _, _ = self.install()
        self.assertEqual(code, 0)
        self.assertEqual(self.lock()["targets"], ["copilot"])

    def test_update_without_install_fails(self):
        d2 = os.path.join(self._tmp.name, "empty")
        os.mkdir(d2)
        self.assertEqual(run("update", d2)[0], 1)


class UninstallTests(Base):
    def test_uninstall(self):
        self.write("AGENTS.md", "# mine\n")
        self.install()
        self.write(".claude/skills/debug/SKILL.md", "changed\n")
        code, out, _ = run("uninstall", self.d)
        self.assertEqual(code, 0)
        self.assertIn("KEPT .claude/skills/debug/SKILL.md", out)
        self.assertTrue(self.exists(".claude/skills/debug/SKILL.md"))
        self.assertFalse(self.exists(".claude/agents"))
        self.assertFalse(self.exists(".claude/skills/sdlc"))
        self.assertFalse(self.exists(".github"))
        self.assertFalse(self.exists("CLAUDE.md"))
        self.assertFalse(self.exists(".sdlc/lock.json"))
        self.assertFalse(self.exists(".sdlc/constitution.md"))
        self.assertTrue(self.exists(".sdlc/config.json"))
        self.assertEqual(self.read("AGENTS.md"), "# mine\n")

    def test_uninstall_created_agents_md_removed(self):
        self.install()
        run("uninstall", self.d)
        self.assertFalse(self.exists("AGENTS.md"))

    def test_uninstall_claude_md_block(self):
        self.write("CLAUDE.md", "# Mine\n")
        self.install()
        run("uninstall", self.d)
        self.assertEqual(self.read("CLAUDE.md"), "# Mine\n")


class NextSpecTests(Base):
    def test_empty_and_max(self):
        code, out, _ = run("next-spec", self.d)
        self.assertEqual((code, out.strip()), (0, "001"))
        for n in ("001-a", "007-b", "007-c", "abc", "12-x"):
            os.makedirs(self.p("specs/" + n))
        self.assertEqual(run("next-spec", self.d)[1].strip(), "008")

    def test_custom_spec_dir(self):
        self.write(".sdlc/config.json", '{"spec_dir": "docs/specs"}')
        os.makedirs(self.p("docs/specs/041-x"))
        os.makedirs(self.p("docs/specs/041-x/099-nested"))
        self.assertEqual(run("next-spec", self.d)[1].strip(), "042")


class LintTests(Base):
    def kit(self):
        k = os.path.join(self._tmp.name, "k")
        shutil.copytree(FIXKIT, k)
        return k

    def sk(self, k, name="debug"):
        return os.path.join(k, "core", "skills", name, "SKILL.md")

    def lint(self, k):
        code, out, _ = run("lint", kit=k)
        return code, out

    def sub(self, path, old, new):
        with open(path) as f:
            t = f.read()
        self.assertIn(old, t)
        with open(path, "w") as f:
            f.write(t.replace(old, new))

    def test_fixture_passes(self):
        code, out = self.lint(FIXKIT)
        self.assertEqual(code, 0, out)

    def rules(self, k):
        return os.path.join(k, "modules", "rul", "rules.md")

    def test_module_rules_too_long(self):
        k = self.kit()
        with open(self.rules(k), "a") as f:
            f.write("".join("- rule %d\n" % i for i in range(30)))
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("modules/rul/rules.md: 32 lines (max 30)", out)

    def test_module_rules_missing_reference(self):
        k = self.kit()
        self.sub(self.rules(k), "`.sdlc/templates/rul.md`", "`.sdlc/templates/ghost.md`")
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("modules/rul/rules.md: references missing .sdlc/templates/ghost.md", out)

    def test_evals_reference_is_project_owned(self):
        k = self.kit()
        with open(self.rules(k), "a") as f:
            f.write("- Record results in `.sdlc/evals/sample/results.md`.\n")
        code, out = self.lint(k)
        self.assertEqual(code, 0, out)

    def test_runtime_evidence_folder_may_be_referenced(self):
        k = self.kit()
        with open(self.rules(k), "a") as f:
            f.write("- Read `.sdlc/evidence/verify.json` for the last verify result.\n")
        code, out = self.lint(k)
        self.assertEqual(code, 0, out)

    def trigger_kit(self, row=None):
        k = self.kit()
        with open(os.path.join(k, "core", "constitution.md"), "a") as f:
            f.write("\n- A failing behaviour goes through the `debug` skill.\n")
        if row is not None:
            os.makedirs(os.path.join(k, "evals"))
            with open(os.path.join(k, "evals", "scenarios.md"), "w") as f:
                f.write("| # | Prompt | Expect |\n|---|---|---|\n" + row + "\n")
        return k

    def test_constitution_skill_without_unnamed_eval_row(self):
        code, out = self.lint(self.trigger_kit())
        self.assertEqual(code, 1, out)
        self.assertIn("core/constitution.md: `debug` has no eval row", out)

    def test_eval_row_that_names_the_skill_does_not_count(self):
        code, out = self.lint(self.trigger_kit("| X1 | `/debug` the login 500 | Loads `debug` first |"))
        self.assertEqual(code, 1, out)
        self.assertIn("`debug` has no eval row", out)

    def test_unnamed_eval_row_satisfies_the_rule(self):
        code, out = self.lint(self.trigger_kit("| X1 | Login returns 500, fix it | Loads `debug` with the skill tool first |"))
        self.assertEqual(code, 0, out)

    def test_constitution_skill_the_model_may_not_invoke_is_an_error(self):
        k = self.trigger_kit("| X1 | Login returns 500, fix it | Loads `debug` with the skill tool first |")
        self.sub(self.sk(k), "description:", "disable-model-invocation: true\ndescription:")
        code, out = self.lint(k)
        self.assertEqual(code, 1, out)
        self.assertIn("core/skills/debug/SKILL.md: named in core/constitution.md but disable-model-invocation is true", out)

    def test_skill_the_constitution_does_not_name_may_block_the_model(self):
        k = self.kit()
        self.sub(self.sk(k), "description:", "disable-model-invocation: true\ndescription:")
        code, out = self.lint(k)
        self.assertEqual(code, 0, out)

    def test_router_is_told_to_load_first_in_description_and_constitution(self):
        with open(os.path.join(ROOT, "core", "skills", "sdlc", "SKILL.md"), encoding="utf-8") as f:
            desc = [l for l in f.read().split("\n") if l.startswith("description:")][0]
        self.assertIn("Load this first, before any other sdlc- skill", desc)
        with open(os.path.join(ROOT, "core", "constitution.md"), encoding="utf-8") as f:
            line = [l for l in f.read().split("\n") if "`sdlc` skill" in l][0]
        for needle in ("before any other skill", "bug, change or feature", "skill tool", "typo"):
            self.assertIn(needle, line)

    def test_real_router_is_model_invocable_and_user_invocable(self):
        with open(os.path.join(ROOT, "core", "skills", "sdlc", "SKILL.md"), encoding="utf-8") as f:
            head = f.read().split("---")[1]
        self.assertNotIn("disable-model-invocation: true", head)
        self.assertIn("user-invocable: true", head)

    def test_hyphenated_skill_name_does_not_name_its_prefix(self):
        k = self.trigger_kit("| X1 | Run debug-extra on the login 500 | Loads `debug` first |")
        code, out = self.lint(k)
        self.assertEqual(code, 0, out)

    def test_missing_section(self):
        k = self.kit()
        self.sub(self.sk(k), "## Red flags", "## Flags")
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("missing section '## Red flags'", out)

    def test_name_mismatch(self):
        k = self.kit()
        self.sub(self.sk(k), "name: debug", "name: other")
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("must equal folder", out)

    def test_role_name_mismatch_and_bad_access(self):
        k = self.kit()
        r = os.path.join(k, "core", "roles", "explorer.md")
        self.sub(r, "name: explorer", "name: scout")
        self.sub(r, "access: read-only", "access: sometimes")
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("must equal file stem", out)
        self.assertIn("access must be", out)

    def test_missing_sdlc_reference(self):
        k = self.kit()
        self.sub(self.sk(k), "`.sdlc/config.json`", "`.sdlc/templates/nope.md`")
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("missing .sdlc/templates/nope.md", out)

    def test_missing_reference_in_role_and_reference_file(self):
        k = self.kit()
        with open(os.path.join(k, "core", "roles", "explorer.md"), "a") as f:
            f.write("See .sdlc/principles/ghost.md\n")
        with open(os.path.join(k, "core", "skills", "sdlc", "references", "ref.md"), "a") as f:
            f.write("See .sdlc/checklists/ghost.md.\n")
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("principles/ghost.md", out)
        self.assertIn("checklists/ghost.md", out)

    def test_module_template_reference_ok(self):
        k = self.kit()
        with open(self.sk(k), "a") as f:
            f.write("See .sdlc/templates/qa.md\n")
        self.assertEqual(self.lint(k)[0], 0)

    def test_too_long(self):
        k = self.kit()
        with open(self.sk(k), "a") as f:
            f.write("filler\n" * 200)
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("max 200", out)

    def test_bad_frontmatter(self):
        k = self.kit()
        self.sub(self.sk(k), "description: Debug a bug.", "description: x\nfoo: bar\ntags: [a, b]")
        code, out = self.lint(k)
        self.assertEqual(code, 1)
        self.assertIn("unknown frontmatter key foo", out)
        self.assertIn("tags must be a bare word", out)

    def test_description_too_long(self):
        k = self.kit()
        self.sub(self.sk(k), "Debug a bug.", "x" * 1025)
        self.assertIn("1024", self.lint(k)[1])



def git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True, capture_output=True, timeout=20)


def snapshot(root):
    out = {}
    for d, dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            st = os.lstat(p)
            out[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns)
    return out


class DiscoverTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = os.path.join(self._tmp.name, "ws")
        os.mkdir(self.ws)

    def make_repo(self, name, files):
        repo = os.path.join(self.ws, name)
        os.mkdir(repo)
        for rel, text in files.items():
            p = os.path.join(repo, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
        return repo

    def build(self):
        api = self.make_repo("api", {
            "package.json": json.dumps({"packageManager": "pnpm@11.5.1", "scripts": {
                "test": "vitest run", "lint": "eslint .", "dev": "tsx watch", "test:integration": "vitest run -c i",
                "validate": "./scripts/validate.sh"}}),
            "pnpm-lock.yaml": "", "package-lock.json": "{}",
            ".github/workflows/ci.yml": "on: push\n",
            "specs/001-a/spec.md": "x", "specs/001-b/spec.md": "x", "specs/002-c/spec.md": "x",
            ".specify/init-options.json": json.dumps({"speckit_version": "0.12.4"}),
            ".claude/skills/speckit-plan/SKILL.md": "x",
            "AGENTS.md": "a\nb\nc\n",
        })
        git(api, "remote", "add", "origin", "https://user:s3cret@example.com/org/api.git")
        with open(os.path.join(api, "dirty.txt"), "w") as f:
            f.write("x")
        self.make_repo("lib", {"Makefile": "test:\n\ttrue\n"})
        os.mkdir(os.path.join(self.ws, "notes"))  # plain folder, not a repo
        os.symlink(api, os.path.join(self.ws, "link-to-api"))

    def discover(self, *a):
        return run("discover", self.ws, *a)

    def test_json_shape_and_facts(self):
        self.build()
        code, out, err = self.discover("--json")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(data["workspace"], os.path.realpath(self.ws))
        names = [r["name"] for r in data["repos"]]
        self.assertEqual(names, ["api", "lib"])  # no plain folder, no symlink
        api = data["repos"][0]
        self.assertEqual(api["branch"], "main")
        self.assertEqual(api["dirty"], 1)
        self.assertEqual(api["remote"], "https://example.com/org/api.git")
        self.assertNotIn("s3cret", out)
        self.assertEqual(api["package_manager"], "pnpm@11.5.1")
        self.assertEqual(api["lockfiles"], ["package-lock.json", "pnpm-lock.yaml"])
        self.assertEqual(api["scripts"], {"lint": "eslint .", "test": "vitest run",
                                          "test:integration": "vitest run -c i", "validate": "./scripts/validate.sh"})
        self.assertEqual(api["ci_workflows"], 1)
        self.assertEqual(api["specs"], {"dir": "specs", "count": 3, "duplicates": {"001": ["001-a", "001-b"]}})
        self.assertEqual(api["speckit_version"], "0.12.4")
        self.assertIn(".specify", api["surfaces"])
        self.assertIn(".claude/skills", api["surfaces"])
        self.assertEqual(api["agents_md_lines"], 3)
        self.assertIsNone(api["sdlc_version"])
        lib = data["repos"][1]
        self.assertEqual(lib["manifests"], ["Makefile"])
        self.assertIsNone(lib["package_manager"])
        self.assertEqual(lib["specs"]["count"], 0)

    def test_context_freshness(self):
        self.build()
        api = os.path.join(self.ws, "api")
        head = subprocess.run(["git", "-C", api, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        ctx = os.path.join(self.ws, ".sdlc", "context")
        os.makedirs(ctx)
        with open(os.path.join(ctx, "api.md"), "w") as f:
            f.write("# Context: api\n\nBuilt from: `%s` (main) on 2026-10-22\n" % head[:12])
        data = json.loads(self.discover("--json")[1])
        api_r, lib_r = data["repos"]
        self.assertEqual(api_r["context"], {"path": ".sdlc/context/api.md", "built_from": head[:12],
                                            "stale": False, "commits_behind": 0})
        self.assertIsNone(lib_r["context"])
        git(api, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "next")
        api_r = json.loads(self.discover("--json")[1])["repos"][0]
        self.assertTrue(api_r["context"]["stale"])
        self.assertEqual(api_r["context"]["commits_behind"], 1)
        self.assertIn("STALE", self.discover()[1])

    def test_markdown_table(self):
        self.build()
        code, out, _ = self.discover()
        self.assertEqual(code, 0)
        self.assertIn("| api |", out)
        self.assertIn("| lib |", out)
        self.assertIn("001", out)

    def test_read_only(self):
        self.build()
        before = snapshot(self.ws)
        self.assertEqual(self.discover("--json")[0], 0)
        self.assertEqual(self.discover()[0], 0)
        self.assertEqual(snapshot(self.ws), before)

    def test_empty_workspace(self):
        code, out, _ = self.discover()
        self.assertEqual(code, 0)
        self.assertIn("no repos found", out)

    def test_not_a_directory(self):
        code, _, err = run("discover", os.path.join(self.ws, "missing"))
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
