import unittest

try:
    from e14_b4 import validate_fault_record, validate_release_record, validate_scan_record
except ModuleNotFoundError:
    from labs.e13e14.e14_b4 import validate_fault_record, validate_release_record, validate_scan_record


def fault_record():
    return {
        "schema_version": "e14-b4-fault-recovery-1",
        "status": "RECOVERED_AND_VERIFIED",
        "fault_mode": "controlled_service_stop",
        "fault_role": "draft",
        "candidate_commit": "ff92071368bbd40083e3014dd09adc40a5c24dbb",
        "input_modified": False,
        "residual_containers": 0,
        "failed": {"job_id": "job-" + "a" * 32, "trace_id": "trace-" + "b" * 32,
                    "status": "FAILED", "error_code": "CONNECTION_REFUSED"},
        "recovered": {"job_id": "job-" + "c" * 32, "trace_id": "trace-" + "d" * 32,
                       "status": "SUCCEEDED", "verification": "VERIFIED",
                       "stages": ["draft", "full-check", "incremental-check", "repair", "recheck"],
                       "final_missing_count": 0},
        "inputs": {"repo_head": "eac8fcd24bc182be27f07ee50544fccc9a1e6826",
                   "candidate_sha256": "a" * 64, "fixed_report_sha256": "b" * 64},
        "logs": {"failed": {"path": "failed-run.json", "bytes": 1, "sha256": "a" * 64},
                 "recovered": {"path": "recovered-run.json", "bytes": 1, "sha256": "b" * 64}},
    }


class E14B4Contracts(unittest.TestCase):
    def test_fault_requires_new_job_and_trace(self):
        record = fault_record()
        self.assertEqual(validate_fault_record(record)["status"], "RECOVERED_AND_VERIFIED")
        record["recovered"]["job_id"] = record["failed"]["job_id"]
        with self.assertRaises(ValueError):
            validate_fault_record(record)

    def test_scan_requires_clean_exit(self):
        record = {"schema_version": "e14-b4-runtime-scan-1", "status": "PASS", "exit_code": 0,
                  "text_files": 3, "hits": 0, "errors": 0}
        self.assertEqual(validate_scan_record(record)["status"], "PASS")
        record["hits"] = 1
        with self.assertRaises(ValueError):
            validate_scan_record(record)

    def test_release_does_not_create_rc_tag(self):
        record = {"schema_version": "e14-b4-release-readiness-1", "status": "PASS",
                  "candidate_commit": "ff92071368bbd40083e3014dd09adc40a5c24dbb",
                  "gates": {name: "PASS" for name in ("b1_archive", "b2_handoff", "fault_recovery", "runtime_log_scan", "source_clean")},
                  "rc_tag": None, "tag_policy": "tag creation requires maintainer authorization"}
        self.assertEqual(validate_release_record(record)["status"], "PASS")
        record["rc_tag"] = "v0.9-rc"
        with self.assertRaises(ValueError):
            validate_release_record(record)


if __name__ == "__main__":
    unittest.main()
