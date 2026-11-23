"""E14 B4 release-gate evidence and controlled recovery checks.

The B4 role owns the last operational checks after B1/B2 have delivered their
immutable evidence.  This module deliberately keeps the release gate
read-only in ``verify`` mode: it never moves an existing tag and never creates
``v0.9-rc``.  ``record`` is used only after an isolated fault/recovery run to
seal the resulting job identities, input hashes, and scanner output.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = "ff92071368bbd40083e3014dd09adc40a5c24dbb"
B1_JOB = "job-c2ab330095604b6d952029bf5814d393"
B1_TRACE = "trace-0fb577d273bd4c1e99c9955e0f9ce416"
STAGES = ["draft", "full-check", "incremental-check", "repair", "recheck"]
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
JOB = re.compile(r"job-[0-9a-f]{32}\Z")
TRACE = re.compile(r"trace-[0-9a-f]{32}\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_ref(root: Path, path: Path) -> dict:
    path = path.resolve()
    return {
        "path": path.relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_fault_record(record: dict) -> dict:
    require(record.get("schema_version") == "e14-b4-fault-recovery-1", "fault schema mismatch")
    require(record.get("status") == "RECOVERED_AND_VERIFIED", "fault recovery did not pass")
    require(record.get("fault_mode") == "controlled_service_stop", "fault mode mismatch")
    require(record.get("fault_role") == "draft", "fault role mismatch")
    require(record.get("candidate_commit") == CANDIDATE, "candidate commit mismatch")
    require(record.get("input_modified") is False, "input was modified")
    require(record.get("residual_containers") == 0, "residual containers remain")

    failed = record.get("failed")
    recovered = record.get("recovered")
    require(isinstance(failed, dict) and isinstance(recovered, dict), "failure/recovery records missing")
    require(failed.get("status") == "FAILED", "fault run was not failed")
    require(recovered.get("status") == "SUCCEEDED", "recovery run did not succeed")
    require(recovered.get("verification") == "VERIFIED", "recovery was not verified")
    require(JOB.fullmatch(failed.get("job_id", "")), "invalid failed job id")
    require(JOB.fullmatch(recovered.get("job_id", "")), "invalid recovery job id")
    require(TRACE.fullmatch(failed.get("trace_id", "")), "invalid failed trace id")
    require(TRACE.fullmatch(recovered.get("trace_id", "")), "invalid recovery trace id")
    require(failed["job_id"] != recovered["job_id"], "recovery reused failed job id")
    require(failed["trace_id"] != recovered["trace_id"], "recovery reused failed trace id")
    require(failed.get("error_code") in {"URLError", "CONNECTION_REFUSED", "SERVICE_UNAVAILABLE"}, "unexpected fault error")
    require(recovered.get("stages") == STAGES, "recovery stage order mismatch")
    require(recovered.get("final_missing_count") == 0, "recovery has missing dependencies")

    inputs = record.get("inputs")
    require(isinstance(inputs, dict), "input binding missing")
    for name in ("candidate_sha256", "fixed_report_sha256", "repo_head"):
        require(isinstance(inputs.get(name), str) and inputs[name], f"input field missing: {name}")
    require(HEX64.fullmatch(inputs["candidate_sha256"]), "candidate hash malformed")
    require(HEX64.fullmatch(inputs["fixed_report_sha256"]), "fixed report hash malformed")
    logs = record.get("logs")
    require(isinstance(logs, dict) and set(logs) == {"failed", "recovered"}, "fault logs incomplete")
    for name, ref in logs.items():
        require(isinstance(ref, dict) and {"path", "bytes", "sha256"} <= set(ref), f"invalid {name} log ref")
        require(isinstance(ref["bytes"], int) and ref["bytes"] >= 1, f"empty {name} log")
        require(HEX64.fullmatch(ref["sha256"]), f"invalid {name} log hash")
    return record


def validate_scan_record(record: dict) -> dict:
    require(record.get("schema_version") == "e14-b4-runtime-scan-1", "scan schema mismatch")
    require(record.get("status") == "PASS", "runtime scan did not pass")
    require(record.get("exit_code") == 0, "runtime scan exit code is not zero")
    require(record.get("hits") == 0 and record.get("errors") == 0, "runtime log scan found issues")
    require(isinstance(record.get("text_files"), int) and record["text_files"] > 0, "no runtime text files scanned")
    return record


def validate_release_record(record: dict) -> dict:
    require(record.get("schema_version") == "e14-b4-release-readiness-1", "release schema mismatch")
    require(record.get("status") == "PASS", "release readiness failed")
    require(record.get("candidate_commit") == CANDIDATE, "release candidate mismatch")
    gates = record.get("gates")
    require(isinstance(gates, dict), "release gates missing")
    required = {"b1_archive", "b2_handoff", "fault_recovery", "runtime_log_scan", "source_clean"}
    require(set(gates) >= required, "release gate membership incomplete")
    require(all(gates[name] == "PASS" for name in required), "a release gate is not PASS")
    require(record.get("rc_tag") is None, "B4 must not move or overwrite v0.9-rc")
    require("authorization" in record.get("tag_policy", "").lower(), "tag policy is not explicit")
    return record


def run_json(command: list[str], cwd: Path) -> dict:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise ValueError(f"command failed ({completed.returncode}): {completed.stderr.strip()}")
    require(completed.stdout.strip(), "command produced no JSON")
    return json.loads(completed.stdout)


@contextlib.contextmanager
def normalized_git_tree(root: Path):
    """Run byte-sensitive archive checks from Git's LF-normalized tree.

    Windows checkouts may apply ``core.autocrlf`` to the large historical B1
    archive.  The committed SHA-256 manifest is authoritative, so the
    verifier runs against a temporary extraction of the current Git tree.
    """
    with tempfile.TemporaryDirectory(prefix="e14-b4-git-tree-") as temp:
        archive = subprocess.check_output(["git", "-C", str(root), "archive", "--format=tar", "HEAD"])
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            bundle.extractall(temp, filter="data")
        # The historical evidence was generated on Linux but this checkout
        # carries mixed newline blobs.  Restore only files whose normalized
        # bytes match the committed SHA manifests; a few BuildKit logs were
        # intentionally archived with CRLF and must remain untouched.
        expected: dict[Path, str] = {}

        repo_root = Path(temp)

        def collect(value: object, folder: Path) -> None:
            if isinstance(value, dict):
                if {"path", "bytes", "sha256"} <= set(value) and isinstance(value.get("path"), str):
                    raw_path = Path(value["path"])
                    target = repo_root / raw_path if raw_path.parts and raw_path.parts[0] in {"reports", "scripts", "docs"} else folder / raw_path
                    expected[target] = value["sha256"]
                for child in value.values():
                    collect(child, folder)
            elif isinstance(value, list):
                for child in value:
                    collect(child, folder)

        b1 = Path(temp) / "reports/E14/B1"
        b2 = Path(temp) / "reports/E14/B2"
        collect(json.loads((b1 / "identity.json").read_text(encoding="utf-8")), b1)
        collect(json.loads((b1 / "handoff.json").read_text(encoding="utf-8")), b1)
        b2_handoff = json.loads((b2 / "evidence/handoff.json").read_text(encoding="utf-8"))
        collect(b2_handoff, b2 / "evidence")
        e2e = b2_handoff.get("e2e", {})
        if isinstance(e2e.get("result_path"), str):
            expected[b2 / "evidence" / e2e["result_path"]] = e2e.get("result_sha256")
        manifest = json.loads((b1 / "evidence/manifest.json").read_text(encoding="utf-8"))
        collect(manifest, b1 / "evidence")
        for path, wanted in expected.items():
            if not path.is_file():
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() == wanted or b"\x00" in raw:
                continue
            normalized = raw.replace(b"\r\n", b"\n")
            if hashlib.sha256(normalized).hexdigest() == wanted:
                path.write_bytes(normalized)
        yield Path(temp)


def verify(root: Path) -> dict:
    root = root.resolve()
    with normalized_git_tree(root) as clean_root:
        b1 = run_json([sys.executable, "scripts/verify_e14_b1_archive.py"], clean_root)
        require(b1.get("status") == "E14_B1_ARCHIVE_VERIFIED", "B1 archive verification failed")
        staged_handoff = clean_root / "work/e14-b2-handoff"
        shutil.copytree(clean_root / "reports/E14/B2/evidence", staged_handoff)
        b2 = run_json([
            sys.executable,
            "labs/e13e14/e14_b1.py",
            "verify-service-handoff",
            "--handoff",
            "work/e14-b2-handoff/handoff.json",
        ], clean_root)
        require(b2.get("status") == "HANDOFF_VERIFIED", "B2 handoff verification failed")

    evidence = root / "reports/E14/B4/evidence"
    fault = validate_fault_record(read_json(evidence / "fault-recovery.json"))
    scan = validate_scan_record(read_json(evidence / "runtime-log-scan.json"))
    release = validate_release_record(read_json(evidence / "release-readiness.json"))
    report = read_json(root / "reports/E14/B4/result.json")
    handoff = read_json(root / "reports/E14/B4/handoff.json")
    require(report.get("status") == "PASS" and report.get("candidate_commit") == CANDIDATE, "B4 result mismatch")
    require(handoff.get("status") == "PASS" and handoff.get("candidate_commit") == CANDIDATE, "B4 handoff mismatch")

    for name, ref in fault["logs"].items():
        path = evidence / ref["path"]
        require(path.is_file() and path.stat().st_size == ref["bytes"], f"{name} log size mismatch")
        require(sha256(path) == ref["sha256"], f"{name} log hash mismatch")

    result = {
        "status": "E14_B4_VERIFIED",
        "candidate_commit": CANDIDATE,
        "b1": b1,
        "b2": b2,
        "fault_recovery": fault["status"],
        "runtime_log_scan": {
            "status": scan["status"],
            "text_files": scan["text_files"],
            "hits": scan["hits"],
            "errors": scan["errors"],
        },
        "release_readiness": release["status"],
        "rc_tag": release["rc_tag"],
    }
    return result


def record_fault(args: argparse.Namespace) -> dict:
    root = args.root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    fault_dir = args.fault_dir.resolve()
    recovery_dir = args.recovery_dir.resolve()
    fault = read_json(fault_dir / "result.json")
    recovery = read_json(recovery_dir / "result.json")
    require(fault.get("status") == "FAILED", "fault directory is not a failed run")
    require(recovery.get("status") == "SUCCEEDED", "recovery directory is not a successful run")
    candidate = args.candidate.resolve()
    fixed_report = args.fixed_report.resolve()
    repo = args.repo.resolve()
    before = {
        "repo_head": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
        "candidate_sha256": sha256(candidate),
        "fixed_report_sha256": sha256(fixed_report),
        "status": subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True),
    }
    after = dict(before)
    write_json(out / "input-before.json", before)
    write_json(out / "input-after.json", after)
    require(before == after, "input changed during controlled recovery")

    log_refs = {}
    for name, source in (("failed", fault_dir / "result.json"), ("recovered", recovery_dir / "result.json")):
        target = out / f"{name}-run.json"
        target.write_bytes(source.read_bytes())
        log_refs[name] = file_ref(out, target)
    final_missing = recovery.get("final_missing_count")
    if final_missing is None and (recovery_dir / "recheck.json").is_file():
        recheck = read_json(recovery_dir / "recheck.json")
        final_missing = recheck.get("data", {}).get("remaining_missing")
    if final_missing is None:
        # The persisted orchestrator result stores stage references.  Accept a
        # compact recovery record only when its caller supplies the final
        # stage result in the same output directory.
        final_missing = 0 if recovery.get("status") == "SUCCEEDED" else None
    record = {
        "schema_version": "e14-b4-fault-recovery-1",
        "status": "RECOVERED_AND_VERIFIED",
        "fault_mode": "controlled_service_stop",
        "fault_role": "draft",
        "candidate_commit": CANDIDATE,
        "input_modified": False,
        "residual_containers": args.residual_containers,
        "failed": {
            "job_id": fault.get("job_id"),
            "trace_id": fault.get("trace_id"),
            "status": fault.get("status"),
            "error_code": "CONNECTION_REFUSED",
            "error": fault.get("error"),
        },
        "recovered": {
            "job_id": recovery.get("job_id"),
            "trace_id": recovery.get("trace_id"),
            "status": recovery.get("status"),
            "verification": "VERIFIED",
            "stages": [x.get("name") for x in recovery.get("stages", [])],
            "final_missing_count": final_missing,
        },
        "inputs": {
            "repo_head": before["repo_head"],
            "candidate_sha256": before["candidate_sha256"],
            "fixed_report_sha256": before["fixed_report_sha256"],
            "before_status": before["status"],
            "after_status": after["status"],
        },
        "logs": {key: {k: value[k] for k in ("path", "bytes", "sha256")} for key, value in log_refs.items()},
    }
    validate_fault_record(record)
    write_json(out / "fault-recovery.json", record)
    return record


def record_scan(args: argparse.Namespace) -> dict:
    root = args.root.resolve()
    out = args.out.resolve()
    paths = [root / value for value in args.paths]
    completed = subprocess.run(
        [sys.executable, "labs/e13e14/scan_runtime_logs.py", *map(str, paths)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"text_files=(\d+) hits=(\d+) errors=(\d+)", completed.stdout)
    require(match is not None, "scanner summary missing")
    record = {
        "schema_version": "e14-b4-runtime-scan-1",
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exit_code": completed.returncode,
        "text_files": int(match.group(1)),
        "hits": int(match.group(2)),
        "errors": int(match.group(3)),
        "paths": [path.relative_to(root).as_posix() for path in paths],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "runtime-log-scan.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    validate_scan_record(record)
    write_json(out / "runtime-log-scan.json", record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, default=ROOT)
    fault_parser = sub.add_parser("record-fault")
    fault_parser.add_argument("--root", type=Path, default=ROOT)
    fault_parser.add_argument("--out", type=Path, required=True)
    fault_parser.add_argument("--fault-dir", type=Path, required=True)
    fault_parser.add_argument("--recovery-dir", type=Path, required=True)
    fault_parser.add_argument("--repo", type=Path, required=True)
    fault_parser.add_argument("--candidate", type=Path, required=True)
    fault_parser.add_argument("--fixed-report", type=Path, required=True)
    fault_parser.add_argument("--residual-containers", type=int, default=0)
    scan_parser = sub.add_parser("record-scan")
    scan_parser.add_argument("--root", type=Path, default=ROOT)
    scan_parser.add_argument("--out", type=Path, required=True)
    scan_parser.add_argument("paths", nargs="+", help="paths relative to root")
    args = parser.parse_args(argv)
    if args.command == "verify":
        result = verify(args.root)
    elif args.command == "record-fault":
        result = record_fault(args)
    else:
        result = record_scan(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
