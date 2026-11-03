import hashlib
import json
import os
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
