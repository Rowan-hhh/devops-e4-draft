import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from labs.e11e12.pipeline import Failure, load_artifact


class FixedReportHashTests(unittest.TestCase):
    def test_exact_bytes_are_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixed-md.json"
            path.write_text(json.dumps({"kind": "fixed-md"}) + "\n", encoding="utf-8")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(load_artifact(path, expected)["kind"], "fixed-md")

    def test_changed_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixed-md.json"
            path.write_text("{}\n", encoding="utf-8")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            path.write_text("{}\n\n", encoding="utf-8")
            with self.assertRaisesRegex(Failure, "content changed"):
                load_artifact(path, expected)


if __name__ == "__main__":
    unittest.main()
