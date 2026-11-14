import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/E12/B2/incremental-check.json"


class E12B2Contract(unittest.TestCase):
    def test_consumes_real_a_incremental_report(self):
        self.assertTrue(REPORT.is_file())
        self.assertEqual(
            hashlib.sha256(REPORT.read_bytes()).hexdigest(),
            "66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83",
        )
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], "e11e12-1")
        self.assertEqual(report["kind"], "incremental-check")
        self.assertEqual(report["status"], "SUCCEEDED")
        self.assertEqual(report["commit"], "745ecf2621c8221b97bf0a5435ace50150ef57d4")
        self.assertEqual(
            report["data"]["findings"],
            [{"type": "MISSING", "target": "helper.o", "dependency": "output_format.h"}],
        )

