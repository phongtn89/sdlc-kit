import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from tests import mutate_never  # noqa: E402

PROBE = [sys.executable, "-B", "-c", "import sys; sys.exit(0 if open('flag.txt').read() == '1' else 1)"]


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


if __name__ == "__main__":
    unittest.main()
