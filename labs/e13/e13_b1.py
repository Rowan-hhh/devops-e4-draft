"""E13 B1 gates: verify the real A->B handoff and exercise C1/C2.

The immutable E12 inputs are never edited.  C1 delegates the real repair to
the E12 B2 runner in a fresh directory; C2 only consumes isolated report
copies and must reject them before repair starts.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_A_COMMIT = "d9e3cccadcfc94c46b1bf9dd54d92dd47c75cce5"
EXPECTED_REPORT_SHA256 = "66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83"
EXPECTED_BUNDLE_SHA256 = "0a74f580219b55ab97119cdfa81f730f23fd0d5cbfbf2f986e4791110f3ce608"
EXPECTED_BASE = "0b62c79a6adb4cd913a814068074575afdbbd18b"
EXPECTED_TARGET = "745ecf2621c8221b97bf0a5435ace50150ef57d4"
EXPECTED_JOB = "job-701e024edd564902a625716aa9547cf7"
EXPECTED_TRACE = "trace-be8e398fc0564ebcb177991840937797"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(argv, cwd, log=None):
    completed = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    if log:
        Path(log).write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(map(str, argv))}")
    return completed.stdout.strip()


def validate_report(envelope, requested_target=EXPECTED_TARGET):
    """Return a deterministic pre-repair decision for one report envelope."""
    if requested_target != EXPECTED_TARGET:
        return False, "WRONG_TARGET"
    if envelope.get("schema_version") != "e11e12-1":
        return False, "SCHEMA_MISMATCH"
    if envelope.get("kind") != "incremental-check":
        return False, "ARTIFACT_TYPE_MISMATCH"
    if envelope.get("status") != "SUCCEEDED":
        return False, "UPSTREAM_FAILED"
    if envelope.get("commit") != requested_target:
        return False, "STALE_REPORT"
    if (envelope.get("data") or {}).get("commit") != requested_target:
        return False, "STALE_REPORT"
    return True, "ACCEPTED"


def verify_a_checkout(a_repo):
    head = run(["git", "rev-parse", "HEAD"], a_repo)
    if head != EXPECTED_A_COMMIT:
        raise SystemExit(f"A_COMMIT_MISMATCH: {head}")
    doc = a_repo / "docs/e11-e12/A05-AB交接与组级验收.md"
    if not doc.is_file():
        raise SystemExit("A_HANDOFF_DOCUMENT_MISSING")
    content = doc.read_text(encoding="utf-8")
    required = [EXPECTED_JOB, EXPECTED_TRACE, EXPECTED_BASE, EXPECTED_TARGET, EXPECTED_REPORT_SHA256]
    missing = [item for item in required if item not in content]
    if missing:
        raise SystemExit(f"A_HANDOFF_FIELDS_MISSING: {missing}")
    return {"repository_head": head, "document": doc.relative_to(a_repo).as_posix()}


def rejection_case(name, envelope, requested_target, out, source_hashes):
    case_dir = out / name
    case_dir.mkdir(parents=True)
    save(case_dir / "isolated-input.json", envelope)
    accepted, code = validate_report(envelope, requested_target)
    result = {
        "schema_version": "e13-b1-rejection-1",
        "case": name,
        "accepted": accepted,
        "code": code,
        "repair_started": False,
        "requested_target": requested_target,
        "isolated_input_sha256": sha256(case_dir / "isolated-input.json"),
        "source_hashes_before": source_hashes,
    }
    save(case_dir / "result.json", result)
    if accepted:
        raise SystemExit(f"{name}: INVALID_REPORT_ACCEPTED")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--a-repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paths = {key: value.resolve() for key, value in {
        "bundle": args.bundle, "report": args.report, "candidate": args.candidate
    }.items()}
    a_repo = args.a_repo.resolve()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit("OUTPUT_EXISTS: choose a fresh output directory")
    out.mkdir(parents=True)

    source_hashes = {key: sha256(path) for key, path in paths.items()}
    if source_hashes["report"] != EXPECTED_REPORT_SHA256:
        raise SystemExit(f"REPORT_HASH_MISMATCH: {source_hashes['report']}")
    if source_hashes["bundle"] != EXPECTED_BUNDLE_SHA256:
        raise SystemExit(f"BUNDLE_HASH_MISMATCH: {source_hashes['bundle']}")

    a_evidence = verify_a_checkout(a_repo)
    envelope = json.loads(paths["report"].read_text(encoding="utf-8"))
    accepted, code = validate_report(envelope)
    if not accepted:
        raise SystemExit(f"C1_REJECTED: {code}")
    for field, expected in (("job_id", EXPECTED_JOB), ("trace_id", EXPECTED_TRACE)):
        if envelope.get(field) != expected:
            raise SystemExit(f"A_REPORT_{field.upper()}_MISMATCH")

    c1 = out / "C1-normal"
    command = [
        sys.executable, str(ROOT / "labs/e11e12/e12_b2.py"),
        "--bundle", str(paths["bundle"]), "--report", str(paths["report"]),
        "--candidate", str(paths["candidate"]), "--out", str(c1),
    ]
    run(command, ROOT, out / "C1-normal.log")
    c1_result = json.loads((c1 / "result.json").read_text(encoding="utf-8"))
    if c1_result.get("status") != "SUCCEEDED" or c1_result["recheck"].get("missing_count") != 0:
        raise SystemExit("C1_NORMAL_CHAIN_FAILED")

    stale = json.loads(json.dumps(envelope))
    stale["commit"] = EXPECTED_BASE
    stale.setdefault("data", {})["commit"] = EXPECTED_BASE
    c2_stale = rejection_case("C2-stale-report", stale, EXPECTED_TARGET, out, source_hashes)
    c2_wrong = rejection_case("C2-wrong-target", envelope, EXPECTED_BASE, out, source_hashes)
    after_hashes = {key: sha256(path) for key, path in paths.items()}
    if source_hashes != after_hashes:
        raise SystemExit("IMMUTABLE_SOURCE_CHANGED")

    result = {
        "schema_version": "e13-b1-1",
        "status": "SUCCEEDED",
        "student_id": "241880179",
        "a_to_b": {
            **a_evidence,
            "job_id": EXPECTED_JOB,
            "trace_id": EXPECTED_TRACE,
            "base": EXPECTED_BASE,
            "target": EXPECTED_TARGET,
            "report_sha256": EXPECTED_REPORT_SHA256,
        },
        "C1": {"status": c1_result["status"], "missing_count": 0, "result": "C1-normal/result.json"},
        "C2": {
            "stale_report": c2_stale["code"],
            "wrong_target": c2_wrong["code"],
            "repair_started": False,
        },
        "immutable_inputs": source_hashes,
    }
    save(out / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
