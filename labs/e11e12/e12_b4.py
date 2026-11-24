"""E12 B4 final acceptance over the real B-group five-stage evidence."""
import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_STAGES = ["draft", "full-check", "incremental-check", "repair", "recheck"]
EXPECTED_TARGET = "745ecf2621c8221b97bf0a5435ace50150ef57d4"
EXPECTED_A_REPORT_SHA256 = "66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83"
EXPECTED_BUNDLE_SHA256 = "0a74f580219b55ab97119cdfa81f730f23fd0d5cbfbf2f986e4791110f3ce608"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(evidence, b1_path, b2_path, b3_path, a_report_path):
    evidence = Path(evidence)
    b1, b2, b3 = load(b1_path), load(b2_path), load(b3_path)
    a_report = load(a_report_path)
    result = load(evidence / "result.json")

    require(b1.get("status") == "SUCCEEDED", "B1_NOT_SUCCEEDED")
    require(b1.get("target") == EXPECTED_TARGET, "B1_TARGET_MISMATCH")
    require(b1.get("bundle", {}).get("sha256") == EXPECTED_BUNDLE_SHA256,
            "B1_BUNDLE_MISMATCH")
    require(b1.get("draft", {}).get("verification", {}).get("output_matches") is True,
            "B1_DRAFT_NOT_VERIFIED")

    require(sha256(a_report_path) == EXPECTED_A_REPORT_SHA256, "A_REPORT_HASH_MISMATCH")
    require(a_report.get("kind") == "incremental-check", "A_REPORT_KIND_MISMATCH")
    require(a_report.get("status") == "SUCCEEDED", "A_REPORT_NOT_SUCCEEDED")
    require(a_report.get("commit") == EXPECTED_TARGET, "A_REPORT_TARGET_MISMATCH")
    require((a_report.get("data") or {}).get("commit") == EXPECTED_TARGET,
            "A_REPORT_DATA_TARGET_MISMATCH")

    require(b2.get("status") == "SUCCEEDED", "B2_NOT_SUCCEEDED")
    require(b2.get("target_commit") == EXPECTED_TARGET, "B2_TARGET_MISMATCH")
    require(b2.get("upstream", {}).get("sha256") == EXPECTED_A_REPORT_SHA256,
            "B2_DID_NOT_CONSUME_A_REPORT")
    require(b2.get("validation", {}).get("accepted") is True, "B2_REPAIR_NOT_ACCEPTED")
    require(b2.get("recheck", {}).get("missing_count") == 0, "B2_MISSING_REMAINS")

    require(b3.get("status") == "SUCCEEDED", "B3_NOT_SUCCEEDED")
    require(b3.get("final_status") == "SUCCEEDED", "B3_JOB_NOT_SUCCEEDED")
    require(all((b3.get("contracts") or {}).values()), "B3_CONTRACT_FAILED")
    require(b3.get("artifact_count", 0) > 0, "B3_NO_ARTIFACTS")

    require(result.get("status") == "SUCCEEDED", "PIPELINE_NOT_SUCCEEDED")
    require(result.get("target_commit") == EXPECTED_TARGET, "PIPELINE_TARGET_MISMATCH")
    require(result.get("job_id") == b3.get("job_id"), "JOB_ID_MISMATCH")
    require(result.get("trace_id") == b3.get("trace_id"), "TRACE_ID_MISMATCH")
    stages = [item.get("name") for item in result.get("stages", [])]
    require(stages == EXPECTED_STAGES, f"STAGE_ORDER_MISMATCH: {stages}")

    for item in result["stages"]:
        artifact = item["artifact"]
        relative = artifact["uri"].split(f"artifact://{result['job_id']}/", 1)[-1]
        path = evidence / relative
        require(path.is_file(), f"STAGE_ARTIFACT_MISSING: {relative}")
        require(sha256(path) == artifact["sha256"], f"STAGE_ARTIFACT_HASH_MISMATCH: {relative}")

    draft = load(evidence / "draft-build" / "result.json")
    require(draft.get("status") == "SUCCEEDED", "DRAFT_NOT_SUCCEEDED")
    require(draft.get("attempts", [{}])[0].get("failure_class") == "MISSING_MAKE",
            "DRAFT_BASELINE_CLASS_MISMATCH")
    require(draft.get("verification", {}).get("output_matches") is True,
            "DRAFT_OUTPUT_MISMATCH")

    plan = load(evidence / "repair-plan.json")
    require(plan == [{"target": "helper.o", "dependency": "output_format.h", "style": "direct"}],
            f"REPAIR_PLAN_MISMATCH: {plan}")
    validation = load(evidence / "validation" / "validation.json")
    require(validation.get("accepted") is True, "FINAL_REPAIR_NOT_ACCEPTED")
    require(all((validation.get("checks") or {}).values()), "FINAL_VALIDATION_CHECK_FAILED")
    findings = load(evidence / "final-full" / "findings.json").get("findings", [])
    require(not any(item.get("type") == "MISSING" for item in findings),
            "FINAL_MISSING_REMAINS")

    return {
        "schema_version": "e12-b4-1",
        "student_id": "241880179",
        "role": "E12-B4",
        "status": "SUCCEEDED",
        "job_id": result["job_id"],
        "trace_id": result["trace_id"],
        "base_commit": result["base_commit"],
        "target_commit": result["target_commit"],
        "stages": stages,
        "artifact_count": len(result.get("artifacts", [])),
        "a_group_report": {
            "job_id": a_report["job_id"],
            "trace_id": a_report["trace_id"],
            "sha256": EXPECTED_A_REPORT_SHA256,
        },
        "validation": validation,
        "final_missing_count": 0,
        "contributors": {
            "B1": {"student_id": b1["student_id"], "status": b1["status"]},
            "B2": {"student_id": "241880610", "status": b2["status"]},
            "B3": {"student_id": b3["student_id"], "status": b3["status"]},
            "B4": {"student_id": "241880179", "status": "SUCCEEDED"},
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--b1", type=Path, required=True)
    parser.add_argument("--b2", type=Path, required=True)
    parser.add_argument("--b3", type=Path, required=True)
    parser.add_argument("--a-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("OUTPUT_EXISTS: choose a fresh output directory")
    try:
        result = audit(args.evidence, args.b1, args.b2, args.b3, args.a_report)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, str(exc) + "\n")
    args.out.mkdir(parents=True)
    (args.out / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
