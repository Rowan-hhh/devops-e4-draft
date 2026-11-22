import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from e14_b2_handoff import file_ref, safe_file


class EvidencePathTests(unittest.TestCase):
    def test_file_ref_binds_size_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "result.json"
            path.write_bytes(b'{"status":"SUCCEEDED"}\n')
            data = path.read_bytes()
            self.assertEqual(
                file_ref(path, root),
                {
                    "path": "result.json",
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                },
            )

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            root.mkdir()
            outside = Path(temp) / "e2e-smoke-result.json"
            outside.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "outside root"):
                safe_file(outside, root)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            root.mkdir()
            target = root / "real.json"
            target.write_text("{}\n", encoding="utf-8")
            link = root / "e2e-smoke-result.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable on this runner")
            with self.assertRaisesRegex(SystemExit, "symlink forbidden"):
                safe_file(link, root)


if __name__ == "__main__":
    unittest.main()
