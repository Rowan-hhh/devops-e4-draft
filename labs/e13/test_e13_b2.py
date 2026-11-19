import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from e13_b2 import make_ini_request, run_c3, run_c5


class E13B2Tests(unittest.TestCase):
    def test_c3_rejects_tampered_artifact_with_original_hash(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            artifact = root / "tampered.json"
            original = b'{"kind":"incremental-check","status":"SUCCEEDED"}\n'
            artifact.write_bytes(original + b" ")
            expected = hashlib.sha256(original).hexdigest()

            result = run_c3(artifact, expected, root / "c3")

            self.assertFalse(result["accepted"])
            self.assertEqual(result["code"], "ARTIFACT_HASH_MISMATCH")
            self.assertFalse(result["repair_started"])
            self.assertNotEqual(result["expected_sha256"], result["actual_sha256"])
            self.assertTrue((root / "c3" / "result.json").is_file())

    def test_c5_rejects_invalid_patch_and_preserves_project_state(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            project = root / "project"
            project.mkdir()
            (project / "Makefile").write_text("all:\n\techo ok\n", encoding="utf-8")
            (project / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
            (project / "helper.c").write_text("int helper(void) { return 0; }\n", encoding="utf-8")
            (project / "config.h").write_text("#define VALUE 1\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "241880300"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=project, check=True)
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=project, check=True, capture_output=True)
            bad_patch = root / "bad.patch"
            bad_patch.write_text("not a unified diff\n", encoding="utf-8")

            result = run_c5(project, bad_patch, root / "c5")

            self.assertFalse(result["accepted"])
            self.assertTrue(result["rollback"])
            self.assertTrue(result["source_unchanged"])
            self.assertEqual(result["before"]["head"], result["after"]["head"])
            self.assertEqual(result["before"]["sha256"], result["after"]["sha256"])
            self.assertTrue((root / "c5" / "validation" / "validation.json").is_file())

    def test_ini_request_uses_target_then_base_commits(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            project = root / "repo"
            project.mkdir()
            (project / "Makefile").write_text("all:\n\ttrue\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "241880300"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=project, check=True)
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "C0"], cwd=project, check=True, capture_output=True)
            (project / "config.h").write_text("#define VALUE 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "C1"], cwd=project, check=True, capture_output=True)
            candidate = root / "candidate.Dockerfile"
            candidate.write_text("FROM scratch\n", encoding="utf-8")

            request = make_ini_request(project, candidate, root / "request.json")
            commits = subprocess.check_output(
                ["git", "rev-list", "--max-count=2", "HEAD"], cwd=project, text=True
            ).splitlines()

            self.assertEqual(request["target"], commits[0])
            self.assertEqual(request["base"], commits[1])
            self.assertEqual(request["expected_output"], "1")
            self.assertEqual(request["mode"], "e12")
            self.assertEqual(json.loads((root / "request.json").read_text())["target"], commits[0])


if __name__ == "__main__":
    unittest.main()
