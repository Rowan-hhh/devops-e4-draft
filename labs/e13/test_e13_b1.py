import copy
import unittest

from e13_b1 import EXPECTED_BASE, EXPECTED_TARGET, validate_report


REPORT = {
    "schema_version": "e11e12-1",
    "kind": "incremental-check",
    "status": "SUCCEEDED",
    "commit": EXPECTED_TARGET,
    "data": {"commit": EXPECTED_TARGET},
}


class E13B1GateTests(unittest.TestCase):
    def test_c1_accepts_exact_target(self):
        self.assertEqual(validate_report(REPORT), (True, "ACCEPTED"))

    def test_c2_rejects_stale_envelope_commit(self):
        value = copy.deepcopy(REPORT)
        value["commit"] = EXPECTED_BASE
        self.assertEqual(validate_report(value), (False, "STALE_REPORT"))

    def test_c2_rejects_stale_data_commit(self):
        value = copy.deepcopy(REPORT)
        value["data"]["commit"] = EXPECTED_BASE
        self.assertEqual(validate_report(value), (False, "STALE_REPORT"))

    def test_c2_rejects_wrong_requested_target_first(self):
        self.assertEqual(validate_report(REPORT, EXPECTED_BASE), (False, "WRONG_TARGET"))

    def test_rejects_wrong_artifact_kind(self):
        value = copy.deepcopy(REPORT)
        value["kind"] = "fixed-md"
        self.assertEqual(validate_report(value), (False, "ARTIFACT_TYPE_MISMATCH"))


if __name__ == "__main__":
    unittest.main()
