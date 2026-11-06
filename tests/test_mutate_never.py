import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from tests import mutate_never  # noqa: E402

# A stand-in for unittest: flag 1 passes, 0 fails an assertion, anything else errors without a failure.
PROBE = [sys.executable, "-B", "-c", "import sys; f = open('flag.txt').read(); "
         "sys.exit(0) if f == '1' else (print('FAILED (failures=1)') or sys.exit(1)) if f == '0' "
         "else (print('FAILED (errors=1)') or sys.exit(1))"]


class Script(unittest.TestCase):
    """The script on a tiny fake kit whose 'tests' pass only while flag.txt holds 1."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.kit = self._tmp.name
        with open(os.path.join(self.kit, "flag.txt"), "w") as f:
            f.write("1")

    def run_it(self, mutations):
        return mutate_never.run(self.kit, mutations, command=PROBE, say=lambda line: None)

    def test_a_caught_mutation_is_not_a_survivor(self):
        self.assertEqual(self.run_it([("flip", [("flag.txt", "1", "0")])]), [])

    def test_a_no_op_mutation_is_reported_as_a_survivor(self):
        self.assertEqual(self.run_it([("no-op", [("flag.txt", "1", "1")])]), ["no-op"])

    def test_an_error_without_a_failure_is_not_a_catch(self):
        self.assertEqual(self.run_it([("breaks", [("flag.txt", "1", "x")])]), ["breaks"])

    def test_a_timeout_is_not_a_catch(self):
        hang = [sys.executable, "-B", "-c", "import sys, time; time.sleep(5) if open('flag.txt').read() != '1' else 0"]
        old, mutate_never.TIMEOUT = mutate_never.TIMEOUT, 1
        try:
            got = mutate_never.run(self.kit, [("hang", [("flag.txt", "1", "0")])], command=hang, say=lambda line: None)
        finally:
            mutate_never.TIMEOUT = old
        self.assertEqual(got, ["hang"])

    def test_a_text_not_found_exactly_once_is_a_script_error(self):
        with self.assertRaises(mutate_never.MutationError):
            self.run_it([("moved", [("flag.txt", "2", "0")])])

    def test_a_red_baseline_is_a_script_error(self):
        with open(os.path.join(self.kit, "flag.txt"), "w") as f:
            f.write("0")
        with self.assertRaises(mutate_never.MutationError):
            self.run_it([("flip", [("flag.txt", "0", "1")])])

    def test_the_real_kit_is_never_written(self):
        self.run_it([("flip", [("flag.txt", "1", "0")])])
        with open(os.path.join(self.kit, "flag.txt")) as f:
            self.assertEqual(f.read(), "1")

    def test_every_listed_mutation_still_applies_to_the_kit(self):
        root = mutate_never.ROOT
        for label, edits in mutate_never.MUTATIONS:
            for rel, old, _ in edits:
                with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as f:
                    self.assertEqual(f.read().count(old), 1, "%s: %s" % (label, rel))

    def test_the_readme_names_the_script(self):
        with open(os.path.join(mutate_never.ROOT, "README.md"), encoding="utf-8") as f:
            self.assertIn("python3 -B tests/mutate_never.py", f.read())


if __name__ == "__main__":
    unittest.main()
