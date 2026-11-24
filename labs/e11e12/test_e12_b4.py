import json
import unittest
from pathlib import Path

import e12_b4


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


class E12B4Contracts(unittest.TestCase):
    def test_expected_five_stage_order_is_strict(self):
        self.assertEqual(
            e12_b4.EXPECTED_STAGES,
            ["draft", "full-check", "incremental-check", "repair", "recheck"],
        )

    def test_stage_artifact_hash_changes_when_bytes_change(self):
        self.assertNotEqual(
            e12_b4.hashlib.sha256(b"one\n").hexdigest(),
            e12_b4.hashlib.sha256(b"two\n").hexdigest(),
        )

    def test_a_report_fixture_is_the_handed_off_bytes(self):
        report = Path(__file__).resolve().parents[2] / "reports/E12/B2/incremental-check.json"
        self.assertTrue(report.is_file())
        envelope = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(envelope["kind"], "incremental-check")
        self.assertEqual(envelope["status"], "SUCCEEDED")
        self.assertEqual(envelope["commit"], e12_b4.EXPECTED_TARGET)
        self.assertEqual(envelope["data"]["commit"], e12_b4.EXPECTED_TARGET)


if __name__ == "__main__":
    unittest.main()
