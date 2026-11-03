import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAP = os.path.join(ROOT, "modules", "dense", "skills", "sdlc-dense-index", "dap.py")

SOURCE = "# Admin\n\n## Purpose and boundaries\n\nShop Manager.\n\n## Data\n\nshop_admin.\n"


def sha12(data):
    return hashlib.sha256(data).hexdigest()[:12]


def run(*args, cwd=None):
    # Always a subprocess: importing dap.py would leave __pycache__ in the module folder.
    p = subprocess.run([sys.executable, DAP] + list(args), capture_output=True, text=True, timeout=20, cwd=cwd)
    return p.returncode, p.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.write("context/a.md", SOURCE)

    def path(self, rel):
        return os.path.join(self.root, ".sdlc", *rel.split("/"))

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def src_hash(self, rel):
        with open(self.path(rel), "rb") as f:
            return sha12(f.read())

    def index(self, body=None, header="#dap 1 built 2026-10-26", src=None):
        if src is None:
            src = "src a context/a.md %s" % self.src_hash("context/a.md")
        if body is None:
            body = "[repo admin]\ndesc: Shop Manager @a#purpose-and-boundaries\ndb: shop_admin @a#data"
        self.write("context/index.dap", "\n".join(x for x in (header, src, body) if x) + "\n")
        return self.path("context/index.dap")

    def validate(self, idx):
        return run("validate", idx, "--root", self.root)

    def fresh(self, idx):
        return run("fresh", idx, "--root", self.root)


class Validate(Base):
    def assertError(self, result, line, fragment):
        code, out = result
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR %d:" % line, out)
        self.assertIn(fragment, out)

    def test_valid_index(self):
        code, out = self.validate(self.index())
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "valid")

    def test_value_may_contain_at_sign(self):
        idx = self.index(body="[repo components]\ndesc: @jtl/shop-component @a#data\nowns: see @a#data docs @a#purpose-and-boundaries")
        code, out = self.validate(idx)
        self.assertEqual(code, 0, out)

    def test_comments_and_blank_lines_ignored(self):
        idx = self.index(body="; comment\n\n[repo admin]\ndesc: x @a#data")
        self.assertEqual(self.validate(idx)[0], 0)

    def test_missing_header(self):
        self.assertError(self.validate(self.index(header="")), 1, "header")

    def test_unknown_version(self):
        self.assertError(self.validate(self.index(header="#dap 2 built 2026-10-26")), 1, "version")

    def test_src_file_missing(self):
        self.assertError(self.validate(self.index(src="src a context/nope.md 000000000000")), 2, "context/nope.md")

    def test_src_duplicate_alias(self):
        h = self.src_hash("context/a.md")
        idx = self.index(src="src a context/a.md %s\nsrc a context/a.md %s" % (h, h))
        self.assertError(self.validate(idx), 3, "duplicate")

    def test_src_outside_sdlc_rejected(self):
        for bad in ("../secret.md", "/etc/passwd"):
            self.assertError(self.validate(self.index(src="src a %s 000000000000" % bad)), 2, "outside .sdlc")

    def test_src_malformed(self):
        self.assertError(self.validate(self.index(src="src a context/a.md")), 2, "src")

    def test_entry_without_ref(self):
        self.assertError(self.validate(self.index(body="[repo admin]\ndesc: Shop Manager")), 4, "@ref")

    def test_entry_undeclared_alias(self):
        self.assertError(self.validate(self.index(body="[repo admin]\ndesc: x @b#data")), 4, "alias b")

    def test_entry_unresolvable_slug(self):
        self.assertError(self.validate(self.index(body="[repo admin]\ndesc: x @a#no-such-heading")), 4, "no-such-heading")

    def test_entry_outside_section(self):
        self.assertError(self.validate(self.index(body="desc: x @a#data")), 3, "section")

    def test_missing_index_file(self):
        code, out = self.validate(self.path("context/index.dap"))
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR", out)

    def test_unknown_section_type(self):
        self.assertError(self.validate(self.index(body="[service admin]\ndesc: x @a#data")), 3, "section type service")

    def test_duplicate_section(self):
        idx = self.index(body="[repo admin]\ndesc: x @a#data\n[repo admin]\ndb: y @a#data")
        self.assertError(self.validate(idx), 5, "duplicate section [repo admin]")

    def test_key_not_allowed_for_type(self):
        self.assertError(self.validate(self.index(body="[risk r1]\ndesc: x @a#data")), 4, "key desc")

    def test_key_repeated_in_section(self):
        idx = self.index(body="[repo admin]\ndesc: x @a#data\ndesc: y @a#data")
        self.assertError(self.validate(idx), 5, "repeated key desc")

    def test_secrets_rejected(self):
        for value in ("https://bob:hunter2@db.example.com/x", "-----BEGIN RSA PRIVATE KEY-----",
                      "token ghp_abcdefghijklmnopqrstuvwxyz0123456789", "AKIAABCDEFGHIJKLMNOP",
                      "xoxb-1234-5678-abcdefgh", "sk-abcdefghijklmnopqrstuvwx",
                      "sk-proj-abcdefghijklmnopqrstuvwxyz0123", "sk-ant-api03-abcdefghijklmnopqrstuv",
                      "sk_live_abcdefghijklmnop1234", "rk_test_abcdefghijklmnop1234",
                      "redis://:s3cret@cache:6379", "HTTPS://bob:pw@host/x"):
            self.assertError(self.validate(self.index(body="[repo admin]\ndesc: %s @a#data" % value)), 4, "secret")

    def test_header_only_invalid(self):
        self.assertError(self.validate(self.index(src="", body="")), 1, "no src lines")

    def test_no_sections_invalid(self):
        self.assertError(self.validate(self.index(body="")), 2, "no sections")

    def test_empty_section_invalid(self):
        self.assertError(self.validate(self.index(body="[repo admin]\n[repo b]\ndesc: x @a#data")), 3, "no entries")
        self.assertError(self.validate(self.index(body="[repo admin]\ndesc: x @a#data\n[repo b]")), 5, "no entries")

    def test_email_addresses_rejected(self):
        for value in ("owner bob.smith@example.com", "Phong <p.ngo@jtl-software.com>", "x@y.de, done"):
            self.assertError(self.validate(self.index(body="[repo admin]\nowner: %s @a#data" % value)), 4, "e-mail")

    def test_at_signs_that_are_not_email_accepted(self):
        for value in ("git@github.com:jtl-software/x.git", "@jtl/shop-component", "pkg@1.2.3", "user @ host"):
            idx = self.index(body="[repo admin]\ndesc: %s @a#data" % value)
            code, out = self.validate(idx)
            self.assertEqual(code, 0, (value, out))

    def test_plain_url_is_not_a_secret(self):
        idx = self.index(body="[repo admin]\ndesc: https://github.com/jtl-software/x.git @a#data")
        self.assertEqual(self.validate(idx)[0], 0)

    def test_size_warning_is_not_an_error(self):
        self.write("context/a.md", SOURCE + "words " * 5000)  # ~30 KB, above the 20 KB floor
        body = "[repo admin]\n" + "desc: %s @a#data" % ("x" * 2000)
        code, out = self.validate(self.index(body=body))
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: index is", out)
        self.assertIn("of its sources (max 5%)", out)
        self.assertTrue(out.strip().endswith("valid"), out)

    def test_no_size_warning_for_small_sources(self):
        code, out = self.validate(self.index(body="[repo admin]\ndesc: %s @a#data" % ("x" * 2000)))
        self.assertEqual((code, out.strip()), (0, "valid"))

    def test_root_defaults_to_nearest_folder_with_sdlc(self):
        self.index()
        sub = os.path.join(self.root, "deep", "er")
        os.makedirs(sub)
        code, out = run("validate", os.path.join("..", "..", ".sdlc", "context", "index.dap"), cwd=sub)
        self.assertEqual(code, 0, out)


class Fresh(Base):
    def idx12(self):
        with open(self.path("context/index.dap"), "rb") as f:
            return sha12(f.read())

    def test_fresh_prints_index_revision(self):
        code, out = self.fresh(self.index())
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "fresh %s" % self.idx12())

    def test_edited_source_is_stale(self):
        idx = self.index()
        self.write("context/a.md", SOURCE + "\nmore.\n")
        code, out = self.fresh(idx)
        self.assertEqual(code, 1, out)
        lines = out.strip().splitlines()
        self.assertEqual(lines[0], "stale %s" % self.idx12())
        self.assertIn("STALE a context/a.md", lines[1:])

    def test_renamed_or_deleted_source_is_stale(self):
        idx = self.index()
        os.rename(self.path("context/a.md"), self.path("context/b.md"))
        code, out = self.fresh(idx)
        self.assertEqual(code, 1, out)
        self.assertIn("STALE a context/a.md", out)
        os.remove(self.path("context/b.md"))
        self.assertEqual(self.fresh(idx)[0], 1)

    def test_missing_index_is_invalid(self):
        code, out = self.fresh(self.path("context/index.dap"))
        self.assertEqual(code, 2, out)
        self.assertTrue(out.startswith("INVALID"), out)

    def test_invalid_index_is_invalid_with_errors(self):
        code, out = self.fresh(self.index(body="[repo admin]\ndesc: no ref"))
        self.assertEqual(code, 2, out)
        self.assertTrue(out.startswith("INVALID"), out)
        self.assertIn("ERROR 4:", out)


class KeyList(unittest.TestCase):
    KEYS = os.path.join(os.path.dirname(DAP), "keys.json")
    CONTRACT = os.path.join(ROOT, "specs", "001-dense-agent-protocol", "contracts", "index-format.md")
    # Every key the shop6 prototype (.sdlc/manifest.yaml, 2026-10-26) needs, by DAP section type.
    # Merged on purpose: ops/op/msgs → msg, fail → note, planned → status, blocked_by → blocked,
    # adr_conflicts → conflicts; prototype list ids (id) become section ids.
    PROTOTYPE = {
        "meta": ["prod", "kind", "erp", "prd", "gate", "mvp", "ga"],
        "ux": ["personas", "a11y", "figma", "tokens", "themes", "sf_pages", "adm_screens", "builder"],
        "repo": ["desc", "stack", "run", "db", "specs", "owns", "scope", "runtime", "consumers", "envs", "owner"],
        "link": ["from", "to", "via", "auth", "msg", "mode", "hdr", "note", "status", "topic", "payload", "local",
                 "pattern", "normative", "consumer", "blocked", "pkg", "skew", "spec"],
        "infra": ["bus", "cache", "blob", "secrets", "edge", "obs"],
        "entity": ["parts", "owner", "states", "scope", "note"],
        "decision": ["what", "state", "owner", "conflicts", "rejected"],
        "risk": ["what", "sev"],
    }

    def types(self):
        with open(self.KEYS, encoding="utf-8") as f:
            return json.load(f)["types"]

    def test_covers_prototype(self):
        types = self.types()
        missing = ["%s.%s" % (t, k) for t, ks in self.PROTOTYPE.items() for k in ks if k not in types.get(t, {})]
        self.assertEqual(missing, [])

    def test_every_key_has_meaning_and_value_form(self):
        for t, keys in self.types().items():
            for k, spec in keys.items():
                self.assertRegex(k, r"^[a-z][a-z0-9_.-]*$", "%s.%s" % (t, k))
                self.assertTrue(spec.get("meaning"), "%s.%s has no meaning" % (t, k))
                v = spec.get("value", "")
                self.assertTrue(v in ("text", "list", "integer", "date") or v.startswith("one of: "),
                                "%s.%s has value form %r" % (t, k, v))

    def test_contract_example_keys_exist(self):
        with open(self.CONTRACT, encoding="utf-8") as f:
            text = f.read()
        example = text.split("Example (abridged from the shop6 prototype):")[1].split("```")[1]
        types, current = self.types(), None
        for line in example.splitlines():
            if line.startswith("["):
                current = line[1:].split()[0]
            elif current and ": " in line:
                self.assertIn(line.split(": ")[0], types[current], line)


class Commit(Base):
    def digest(self, rel):
        with open(self.path(rel), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def tmp(self, body):
        good = self.index()
        with open(good, encoding="utf-8") as f:
            text = f.read()
        self.write("context/index.dap.123.tmp", text.split("[repo")[0] + body + "\n")
        return self.path("context/index.dap.123.tmp"), good

    def test_invalid_tmp_keeps_last_valid_index(self):
        tmp, dest = self.tmp("[repo admin]\ndesc: no ref")
        before = self.digest("context/index.dap")
        code, out = run("commit", tmp, dest, "--root", self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR", out)
        self.assertIn("not committed", out)
        self.assertEqual(self.digest("context/index.dap"), before)

    def test_valid_tmp_replaces_index(self):
        tmp, dest = self.tmp("[repo admin]\ndesc: Replaced @a#data")
        with open(tmp, "rb") as f:
            new = f.read()
        code, out = run("commit", tmp, dest, "--root", self.root)
        self.assertEqual(code, 0, out)
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), new)
        self.assertFalse(os.path.exists(tmp))
        self.assertEqual(out.strip(), "committed %s (1 sources, 1 sections, 1 entries)" % sha12(new))

    def test_commit_reports_counts(self):
        tmp, dest = self.tmp("[repo admin]\ndesc: x @a#data\ndb: y @a#data\n; note\n[risk r1]\nwhat: z @a#data")
        code, out = run("commit", tmp, dest, "--root", self.root)
        self.assertEqual(code, 0, out)
        self.assertTrue(out.strip().endswith("(1 sources, 2 sections, 3 entries)"), out)

    def assertRefused(self, tmp, dest):
        code, out = run("commit", tmp, dest, "--root", self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("commit only writes .sdlc/context/index.dap", out)
        self.assertIn("not committed", out)

    def test_dest_outside_context_refused(self):
        tmp, _ = self.tmp("[repo admin]\ndesc: x @a#data")
        for dest in (os.path.join(self.root, "elsewhere.dap"), self.path("other.dap"), self.path("context/a.md")):
            self.assertRefused(tmp, dest)
            self.assertTrue(os.path.exists(tmp))
        self.assertFalse(os.path.exists(os.path.join(self.root, "elsewhere.dap")))
        with open(self.path("context/a.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), SOURCE)

    def test_tmp_outside_context_refused(self):
        self.tmp("[repo admin]\ndesc: x @a#data")
        stray = os.path.join(self.root, "stray.tmp")
        with open(self.path("context/index.dap.123.tmp"), encoding="utf-8") as f, open(stray, "w") as g:
            g.write(f.read())
        self.assertRefused(stray, self.path("context/index.dap"))
        self.assertTrue(os.path.exists(stray))

    def test_dest_symlink_out_of_context_refused(self):
        tmp, dest = self.tmp("[repo admin]\ndesc: x @a#data")
        target = os.path.join(self.root, "outside.dap")
        with open(target, "w") as f:
            f.write("keep\n")
        os.remove(dest)
        os.symlink(target, dest)
        self.assertRefused(tmp, dest)
        with open(target) as f:
            self.assertEqual(f.read(), "keep\n")

    def test_truncated_tmp_keeps_last_valid_index(self):
        tmp, dest = self.tmp("")  # header and src lines only: a build cut off before its sections
        before = self.digest("context/index.dap")
        code, out = run("commit", tmp, dest, "--root", self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("no sections", out)
        self.assertEqual(self.digest("context/index.dap"), before)

    def test_commit_into_missing_index(self):
        tmp, dest = self.tmp("[repo admin]\ndesc: First @a#data")
        os.remove(dest)
        self.assertEqual(run("commit", tmp, dest, "--root", self.root)[0], 0)
        self.assertTrue(os.path.exists(dest))


SECTIONED = ("# B\n\n## Data\n\ndb: x.\n\n### Tables\n\n- orders\n```text\n## not a heading\n```\n\n"
             "## Key flows\n\nflow.\n")  # Data = lines 3-13, Tables = 7-13, Key flows = 14-16


class Show(Base):
    def setUp(self):
        super().setUp()
        self.write("context/b.md", SECTIONED)
        src = "src a context/a.md %s\nsrc b context/b.md %s" % (self.src_hash("context/a.md"), self.src_hash("context/b.md"))
        self.idx = self.index(src=src, body="[repo admin]\ndesc: x @b#data\ndb: y @a#data")

    def show(self, ref):
        return run("show", self.idx, ref, "--root", self.root)

    def test_prints_one_section_with_line_numbers(self):
        code, out = self.show("@b#data")
        self.assertEqual(code, 0, out)
        lines = out.split("\n")
        self.assertEqual(lines[0], ".sdlc/context/b.md:3-13")
        self.assertEqual(lines[1], "3\t## Data")
        self.assertIn("7\t### Tables", out)
        self.assertIn("11\t## not a heading", out)  # fenced, so it doesn't end the section
        self.assertNotIn("Key flows", out)

    def test_subsection_and_last_section(self):
        code, out = self.show("b#tables")  # the leading @ is optional
        self.assertEqual((code, out.split("\n")[0]), (0, ".sdlc/context/b.md:7-13"))
        code, out = self.show("@b#key-flows")
        self.assertEqual((code, out.split("\n")[0]), (0, ".sdlc/context/b.md:14-16"))
        self.assertIn("16\tflow.", out)

    def test_unknown_alias_or_slug(self):
        code, out = self.show("@z#data")
        self.assertEqual(code, 1, out)
        self.assertIn("unknown alias z", out)
        code, out = self.show("@b#nope")
        self.assertEqual(code, 1, out)
        self.assertIn("no heading nope", out)

    def test_missing_or_invalid_index(self):
        self.assertEqual(run("show", self.path("context/none.dap"), "@b#data", "--root", self.root)[0], 2)
        self.write("context/index.dap", "#dap 1 built 2026-10-26\n")
        code, out = self.show("@b#data")
        self.assertEqual(code, 2, out)
        self.assertTrue(out.startswith("INVALID"), out)

    def test_changed_source_warns_but_shows(self):
        self.write("context/b.md", SECTIONED + "\nmore.\n")
        code, out = self.show("@b#data")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("WARNING: context/b.md changed since this index was built"), out)
        self.assertIn("3\t## Data", out)


class Perf(Base):
    def test_shop6_sized_workspace_under_10s(self):
        import time
        headings = "".join("\n## Section %d\n\n%s\n" % (i, "word " * 600) for i in range(10))
        srcs = []
        for i in range(10):
            self.write("context/r%d.md" % i, "# Repo %d\n%s" % (i, headings))  # 10 × ~30 KB = ~300 KB
            srcs.append("src r%d context/r%d.md %s" % (i, i, self.src_hash("context/r%d.md" % i)))
        body = "\n".join("[repo r%d-%d]\ndesc: entry %d @r%d#section-%d\nowns: a, b @r%d#section-%d"
                         % (i, j, j, i, j % 10, i, (j + 1) % 10) for i in range(10) for j in range(20))
        idx = self.index(body=body, src="\n".join(srcs))
        start = time.monotonic()
        self.assertEqual(self.validate(idx)[0], 0)
        self.assertEqual(self.fresh(idx)[0], 0)
        self.assertLess(time.monotonic() - start, 10)


FINDSRC = ("# Admin\n\n## Routing\n\nRequests are routed per tenant.\nThe edge proxy forwards them.\n\n"
           "## Billing\n\nInvoices per tenant come from the erp connector.\n\n"
           "## Sessions\n\nSession routing uses a cookie.\n\n"
           "## Search\n\nSearch routing is its own service.\n")


class Find(Base):
    def setUp(self):
        super().setUp()
        self.write("context/f.md", FINDSRC)

    def build(self, body, **extra):
        for rel, text in extra.items():
            self.write("context/%s.md" % rel, text)
        names = ["f"] + sorted(extra)
        src = "\n".join("src %s context/%s.md %s" % (n[0], n, self.src_hash("context/%s.md" % n)) for n in names)
        return self.index(body=body, src=src)

    def find(self, idx, *terms):
        return run("find", idx, *(list(terms) + ["--root", self.root]))

    def test_returns_best_three(self):
        idx = self.build("[repo admin]\ndesc: tenant routing rules @f#routing\nowns: routing table @f#routing\n"
                         "[repo billing]\ndesc: invoices per tenant @f#billing\n"
                         "[repo sessions]\ndesc: cookie routing @f#sessions\n"
                         "[repo search]\ndesc: routing for search @f#search")
        code, out = self.find(idx, "routing", "tenant")
        self.assertEqual(code, 0, out)
        results = [l for l in out.split("\n") if l.startswith("[")]
        self.assertEqual([r.split("]")[0] for r in results], ["[1", "[2", "[3"], out)
        self.assertIn("REPO admin / desc: tenant routing rules @f#routing", results[0])
        self.assertIn("REPO billing", results[1])
        self.assertIn("REPO sessions", results[2])
        self.assertNotIn("REPO search", out)  # a fourth match is not returned
        # siblings that point to one source section share one result and one excerpt
        self.assertIn("owns: routing table @f#routing", out)
        self.assertEqual(out.count("## Routing"), 1, out)
        self.assertIn(".sdlc/context/f.md:3-7", out)
        self.assertRegex(out, r"\n\s+3\s+## Routing")
        self.assertRegex(out, r"\n\s+5\s+Requests are routed per tenant\.")

    def test_budget_and_cut_marker(self):
        big = "# Big\n" + "".join("\n## S%d\n\n%s" % (i, "needle filler text here\n" * 1100) for i in range(5))
        self.assertGreater(len(big), 26000)
        body = "".join("[repo r%d]\ndesc: needle number %d @g#s%d\n" % (i, i, i) for i in range(5))
        idx = self.build(body.rstrip("\n"), g=big)
        code, out = self.find(idx, "needle")
        self.assertEqual(code, 0, out)
        self.assertLessEqual(len(out), 2000)
        cuts = [l for l in out.split("\n") if "… cut: read .sdlc/context/g.md:" in l]
        self.assertEqual(len(cuts), 3, out)
        self.assertIn("… cut: read", out.rstrip("\n").split("\n")[-1])


if __name__ == "__main__":
    unittest.main()
