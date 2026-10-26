import hashlib
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
        idx = self.index(body="[repo components]\npkg: @jtl/shop-component @a#data\nnote: see @a#data docs @a#purpose-and-boundaries")
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


if __name__ == "__main__":
    unittest.main()
