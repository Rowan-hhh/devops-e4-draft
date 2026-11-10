import tempfile
import unittest
from pathlib import Path

from lab import commit, fixture, patch, run, scan


class StudentE11B2(unittest.TestCase):
    def test_two_missing_headers_share_one_safe_direct_patch(self):
        """E11-B must repair both MD findings without changing recipes or input."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            fixture(project)
            main = project / "main.c"
            main.write_text('#include "extra.h"\n' + main.read_text())
            target = commit(project, "E11 B2: add second local header")

            before = (project / "Makefile").read_bytes()
            report = scan(project)
            diff, plan = patch(project, report)

            self.assertEqual(report["commit"], target)
            self.assertEqual(
                plan,
                [
                    {"target": "main.o", "dependency": "config.h", "style": "direct"},
                    {"target": "main.o", "dependency": "extra.h", "style": "direct"},
                ],
            )
            self.assertIn(
                "+main.o: main.c unused.h config.h extra.h",
                diff,
            )
            self.assertEqual((project / "Makefile").read_bytes(), before)
            self.assertEqual(run(["git", "status", "--porcelain"], project), "")
            recipes = lambda data: [
                line for line in data.splitlines(keepends=True)
                if line.startswith(b"\t")
            ]
            patched = before.replace(
                b"main.o: main.c unused.h",
                b"main.o: main.c unused.h config.h extra.h",
            )
            self.assertEqual(recipes(before), recipes(patched))


if __name__ == "__main__":
    unittest.main()
