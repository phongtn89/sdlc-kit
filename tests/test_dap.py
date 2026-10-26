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
                      "xoxb-1234-5678-abcdefgh", "sk-abcdefghijklmnopqrstuvwx"):
            self.assertError(self.validate(self.index(body="[repo admin]\ndesc: %s @a#data" % value)), 4, "secret")

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
        self.assertEqual(out.strip(), "committed %s" % sha12(new))

    def test_commit_into_missing_index(self):
        tmp, dest = self.tmp("[repo admin]\ndesc: First @a#data")
        os.remove(dest)
        self.assertEqual(run("commit", tmp, dest, "--root", self.root)[0], 0)
        self.assertTrue(os.path.exists(dest))


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


if __name__ == "__main__":
    unittest.main()
