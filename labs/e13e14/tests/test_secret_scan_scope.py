import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCANNER = REPO_ROOT / "scripts" / "secret_scan.py"


def run(command, *, cwd, check=True):
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class SecretScanHistoryScopeTests(unittest.TestCase):
    def make_repo(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        root = Path(temporary.name)

        run(["git", "init", "-q"], cwd=root)
        run(["git", "config", "user.name", "Test User"], cwd=root)
        run(
            [
                "git",
                "config",
                "user.email",
                "test@example.invalid",
            ],
            cwd=root,
        )
        run(["git", "switch", "-c", "main"], cwd=root)

        return root

    def commit(self, root, message):
        run(["git", "add", "-A"], cwd=root)
        run(["git", "commit", "-q", "-m", message], cwd=root)

    def credential_line(self, suffix):
        return (
            "API_"
            + "SEC"
            + "RET="
            + "{"
            + "secret_for_"
            + suffix
            + "_123456789"
            + "}\n"
        )

    def scan_history(self, root):
        return run(
            [
                sys.executable,
                str(SCANNER),
                str(root),
                "--history",
            ],
            cwd=REPO_ROOT,
            check=False,
        )

    def test_unrelated_branch_history_is_not_scanned(self):
        root = self.make_repo()

        (root / "clean.txt").write_text(
            "clean\n",
            encoding="utf-8",
        )
        self.commit(root, "clean main")

        run(
            ["git", "switch", "-c", "unrelated"],
            cwd=root,
        )

        (root / "credential.txt").write_text(
            self.credential_line("unrelated_branch"),
            encoding="utf-8",
        )
        self.commit(root, "secret on unrelated branch")

        run(["git", "switch", "main"], cwd=root)

        result = self.scan_history(root)

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stdout + result.stderr,
        )
        self.assertNotIn("FOUND", result.stdout)

    def test_current_head_history_is_still_scanned(self):
        root = self.make_repo()

        (root / "clean.txt").write_text(
            "clean\n",
            encoding="utf-8",
        )
        self.commit(root, "clean base")

        credential = root / "credential.txt"
        credential.write_text(
            self.credential_line("current_history"),
            encoding="utf-8",
        )
        self.commit(root, "add historical credential")

        credential.unlink()
        self.commit(root, "remove historical credential")

        result = self.scan_history(root)

        self.assertEqual(
            result.returncode,
            1,
            msg=result.stdout + result.stderr,
        )
        self.assertIn("git-history", result.stdout)
        self.assertIn("密钥赋值", result.stdout)


if __name__ == "__main__":
    unittest.main()
