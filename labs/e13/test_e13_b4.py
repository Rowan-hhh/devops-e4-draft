import tempfile
import unittest
from pathlib import Path

try:
    from e13_b4 import run_c8
except ModuleNotFoundError:
    from labs.e13.e13_b4 import run_c8


class B4Contracts(unittest.TestCase):
    def test_idempotency_replay_and_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_c8(Path(temp))
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["same_key_same_request"]["same_job_id"])
        self.assertEqual(result["same_key_changed_target"]["error"], "IDEMPOTENCY_CONFLICT")


if __name__ == "__main__":
    unittest.main()
