"""E12 B2: consume A's real incremental-check and validate one repair.

The input is an A-group incremental-check envelope, not E11's fixed-md report.
The B1 project bundle is treated as the immutable source; all changes happen
in a fresh working copy under the output directory.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "labs/e8e10"))
from lab import patch, scan, validate  # noqa: E402


EXPECTED_REPORT_SHA256 = "66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83"
EXPECTED_TARGET = "745ecf2621c8221b97bf0a5435ace50150ef57d4"
EXPECTED_BUNDLE_SHA256 = "0a74f580219b55ab97119cdfa81f730f23fd0d5cbfbf2f986e4791110f3ce608"


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
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(argv)}")
    return completed.stdout.strip()


def snapshot(root):
    root = Path(root)
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bundle = args.bundle.resolve()
    report_path = args.report.resolve()
    candidate = args.candidate.resolve()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit("OUTPUT_EXISTS: choose a fresh output directory")
    out.mkdir(parents=True)

    report_sha = sha256(report_path)
    bundle_sha = sha256(bundle)
    if report_sha != EXPECTED_REPORT_SHA256:
        raise SystemExit(f"REPORT_HASH_MISMATCH: {report_sha}")
    if bundle_sha != EXPECTED_BUNDLE_SHA256:
        raise SystemExit(f"BUNDLE_HASH_MISMATCH: {bundle_sha}")

    envelope = json.loads(report_path.read_text(encoding="utf-8"))
    if envelope.get("schema_version") != "e11e12-1":
        raise SystemExit("SCHEMA_MISMATCH")
    if envelope.get("kind") != "incremental-check":
        raise SystemExit("ARTIFACT_TYPE_MISMATCH")
    if envelope.get("status") != "SUCCEEDED":
        raise SystemExit("UPSTREAM_FAILED")
    if envelope.get("commit") != EXPECTED_TARGET:
        raise SystemExit("STALE_REPORT")
    data = envelope.get("data") or {}
    if data.get("commit") != EXPECTED_TARGET:
        raise SystemExit("STALE_REPORT: data commit")

    save(out / "request.json", {
        "bundle": str(bundle),
        "report": str(report_path),
        "candidate": str(candidate),
        "expected_target": EXPECTED_TARGET,
        "report_sha256": report_sha,
        "bundle_sha256": bundle_sha,
    })
    shutil.copy2(report_path, out / "incremental-check.json")
    shutil.copy2(candidate, out / "candidate.Dockerfile")
    run(["git", "clone", "--no-hardlinks", str(bundle), str(out / "project")], ROOT, out / "clone.log")
    project = out / "project"
    run(["git", "checkout", "--detach", EXPECTED_TARGET], project, out / "checkout.log")
    actual_head = run(["git", "rev-parse", "HEAD"], project)
    if actual_head != EXPECTED_TARGET:
        raise SystemExit(f"TARGET_MISMATCH: {actual_head}")
    before = snapshot(project)

    diff, edits = patch(project, data)
    if not diff:
        raise SystemExit("NO_MISSING_DEPENDENCY")
    (out / "candidate.patch").write_text(diff, encoding="utf-8")
    save(out / "repair-plan.json", edits)
    if edits != [{"target": "helper.o", "dependency": "output_format.h", "style": "direct"}]:
        raise SystemExit(f"UNEXPECTED_REPAIR_PLAN: {edits}")

    verdict = validate(project, out / "candidate.patch", out / "validation" / "evidence")
    if not verdict.get("accepted"):
        raise SystemExit(f"REPAIR_REJECTED: {verdict}")
    recheck = scan(project)
    save(out / "recheck.json", recheck)
    after = snapshot(project)
    missing = [item for item in recheck.get("findings", []) if item.get("type") == "MISSING"]
    result = {
        "schema_version": "e12-b2-1",
        "status": "SUCCEEDED" if not missing else "FAILED",
        "job_id": envelope["job_id"],
        "trace_id": envelope["trace_id"],
        "upstream": {
            "kind": envelope["kind"],
            "commit": envelope["commit"],
            "sha256": report_sha,
            "artifact_uris": envelope.get("artifacts", []),
        },
        "target_commit": actual_head,
        "candidate_sha256": sha256(candidate),
        "bundle_sha256": bundle_sha,
        "edits": edits,
        "validation": verdict,
        "recheck": {
            "status": recheck.get("status", "LOCAL_SCAN"),
            "missing_count": len(missing),
            "findings": recheck.get("findings", []),
        },
        "source_bundle_unchanged": bundle_sha == EXPECTED_BUNDLE_SHA256,
        "working_copy_changed": before != after,
    }
    save(out / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

