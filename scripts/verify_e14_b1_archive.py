#!/usr/bin/env python3
"""Verify the committed E14 B1 formal evidence archive."""

from pathlib import Path
import hashlib
import json
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
B1 = ROOT / "reports/E14/B1"
EVIDENCE = B1 / "evidence"

CANDIDATE = "ff92071368bbd40083e3014dd09adc40a5c24dbb"
TOOL_COMMIT = "588957ad6373e45fa166ed5a58c546bea018669d"
BASE = "4d6815a591fe87ea7b511c8b3e9f021d413e4415"
TARGET = "eac8fcd24bc182be27f07ee50544fccc9a1e6826"
IMAGE_ID = (
    "sha256:"
    "a9c65eab021262a76f2025a42a9526aa5d793ee4f2224696bbb6419d0daf80e0"
)

STAGES = [
    "draft",
    "full-check",
    "incremental-check",
    "repair",
    "recheck",
]

ROLES = {
    "buildchecker": ("18081", False),
    "echecker": ("18082", False),
    "draft": ("18083", True),
    "mdfixer": ("18084", False),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def checked_relative(root, value, must_exist=True):
    require(isinstance(value, str) and value, "invalid relative path")
    raw = Path(value)
    require(not raw.is_absolute() and ".." not in raw.parts, "unsafe path")

    path = root / raw
    resolved = path.resolve(strict=must_exist)

    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("path outside allowed root") from exc

    current = root
    for part in raw.parts:
        current = current / part
        require(not current.is_symlink(), f"symlink path: {value}")

    if must_exist:
        require(resolved.is_file(), f"not a regular file: {value}")

    return resolved


def checked_ref(info):
    require(isinstance(info, dict), "file reference must be an object")
    require(
        set(info) >= {"path", "bytes", "sha256"},
        "incomplete file reference",
    )

    path = checked_relative(B1, info["path"])
    actual = {
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    expected = {
        "bytes": info["bytes"],
        "sha256": info["sha256"],
    }

    require(actual == expected, f"file reference mismatch: {info['path']}")
    return path


def validate_archive_tree():
    for path in B1.rglob("*"):
        require(not path.is_symlink(), f"symlink in B1 archive: {path}")
        mode = path.lstat().st_mode
        require(
            stat.S_ISREG(mode) or stat.S_ISDIR(mode),
            f"special file in B1 archive: {path}",
        )


def validate_evidence_manifest(identity, handoff):
    manifest_path = checked_ref(identity["evidence_manifest"])
    require(
        identity["evidence_manifest"] == handoff["evidence_manifest"],
        "handoff evidence manifest differs from identity",
    )

    manifest = read_json(manifest_path)
    require(
        manifest.get("schema_version") == "e14-b1-evidence-manifest-1",
        "unexpected evidence manifest schema",
    )

    declared = {}
    for item in manifest.get("files", []):
        require(isinstance(item, dict), "invalid manifest entry")
        relative = item.get("path")
        require(relative not in declared, f"duplicate evidence path: {relative}")

        path = checked_relative(EVIDENCE, relative)
        actual = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        expected = {
            "bytes": item.get("bytes"),
            "sha256": item.get("sha256"),
        }

        require(actual == expected, f"evidence mismatch: {relative}")
        declared[relative] = actual

    actual_paths = {
        path.relative_to(EVIDENCE).as_posix()
        for path in EVIDENCE.rglob("*")
        if path.is_file() and path != manifest_path
    }

    require(set(declared) == actual_paths, "evidence manifest membership mismatch")
    require(manifest.get("file_count") == len(actual_paths), "file count mismatch")
    require(
        manifest.get("total_bytes")
        == sum(item["bytes"] for item in declared.values()),
        "total byte count mismatch",
    )

    return manifest


def validate_fixed_sample(identity, handoff):
    fixed = identity["fixed_sample"]
    require(fixed == handoff["fixed_sample"], "fixed sample handoff mismatch")
    require(fixed.get("status") == "PASS", "fixed sample is not PASS")
    require(fixed.get("base_commit") == BASE, "fixed sample base mismatch")
    require(fixed.get("target_commit") == TARGET, "fixed sample target mismatch")
    require(fixed.get("bundle_verified") is True, "bundle not verified")
    require(fixed.get("restore_verified") is True, "bundle restore not verified")

    request_path = checked_ref(fixed["request"])
    candidate_path = checked_ref(fixed["candidate"])
    fixed_report_path = checked_ref(fixed["fixed_report"])
    checked_ref(fixed["source_bundle"])

    require(
        sha256(request_path)
        == "422f4bdd9d9e1eeded9d03584a3219185c429fee484dbdcd90e0e5bcdad77c1c",
        "fixed request hash mismatch",
    )
    require(
        sha256(candidate_path)
        == "c2f7a9f70caf44bbf4852a1c61e262203de9f28cd6fbe3aa2dec5adf6d34c6da",
        "candidate hash mismatch",
    )
    require(
        sha256(fixed_report_path)
        == "98f33161543830077ca311ddface7f7e2b5d4bb94fc470ed595c8843ba9b305c",
        "fixed report hash mismatch",
    )

    request = read_json(request_path)
    require(request.get("base") == BASE, "request base mismatch")
    require(request.get("target") == TARGET, "request target mismatch")
    require(
        request.get("repo") == "/course/data/integration-sample/repo",
        "request repo path mismatch",
    )
    require(
        request.get("candidate")
        == "/course/data/integration-sample/candidate.Dockerfile",
        "request candidate path mismatch",
    )
    require(
        request.get("fixed_report")
        == "/course/data/integration-sample/fixed-md.json",
        "request fixed report path mismatch",
    )


def validate_single(identity, handoff):
    single = identity["single_container_run"]
    require(
        single == handoff["single_container_run"],
        "single-container handoff mismatch",
    )
    require(single.get("status") == "VERIFIED", "single run not verified")
    require(
        single.get("execution_status") == "RUN_COMPLETED",
        "single execution incomplete",
    )
    require(single.get("source_boundary_unchanged") is True, "source changed")

    result_path = checked_ref(single["result"])
    manifest_path = checked_ref(single["sealed_run_manifest"])
    checked_ref(single["sealed_input_manifest"])

    result = read_json(result_path)
    sealed = read_json(manifest_path)
    execution = read_json(EVIDENCE / "single-container/execution.json")

    require(execution.get("status") == "RUN_COMPLETED", "execution status mismatch")
    require(execution.get("primary_failure") is None, "unexpected primary failure")
    require(result.get("status") == "SUCCEEDED", "single result did not succeed")

    require(
        result.get("job_id") == single.get("job_id"),
        "single job identity mismatch",
    )
    require(
        result.get("trace_id") == single.get("trace_id"),
        "single trace identity mismatch",
    )
    require(
        [item.get("name") for item in result.get("stages", [])] == STAGES,
        "single stage order mismatch",
    )
    require(
        len(sealed.get("artifacts", [])) == single.get("artifact_count") == 156,
        "single artifact count mismatch",
    )

    require(
        re.fullmatch(r"job-[0-9a-f]{32}", single["job_id"]) is not None,
        "invalid single job ID",
    )
    require(
        re.fullmatch(r"trace-[0-9a-f]{32}", single["trace_id"]) is not None,
        "invalid single trace ID",
    )


def validate_four_services(identity, handoff):
    four = identity["four_service_run"]
    require(
        four == handoff["four_service_run"],
        "four-service handoff mismatch",
    )
    require(four.get("status") == "VERIFIED", "four-service run not verified")
    require(four.get("base_commit") == BASE, "four-service base mismatch")
    require(four.get("target_commit") == TARGET, "four-service target mismatch")
    require(four.get("stages") == STAGES, "four-service stage order mismatch")
    require(four.get("artifact_count") == 162, "four-service artifact count mismatch")
    require(four.get("source_boundary_unchanged") is True, "source changed")

    result_path = checked_ref(four["result"])
    summary_path = checked_ref(four["verification_summary"])

    result = read_json(result_path)
    summary = read_json(summary_path)

    require(result.get("status") == "SUCCEEDED", "four-service result failed")
    require(result.get("schema_version") == "e14-compose-1", "result schema mismatch")
    require(result.get("job_id") == four.get("job_id"), "four-service job mismatch")
    require(
        result.get("trace_id") == four.get("trace_id"),
        "four-service trace mismatch",
    )
    require(result.get("base_commit") == BASE, "result base mismatch")
    require(result.get("target_commit") == TARGET, "result target mismatch")
    require(
        [item.get("name") for item in result.get("stages", [])] == STAGES,
        "result stage order mismatch",
    )
    require(len(result.get("artifacts", [])) == 162, "result artifact mismatch")

    require(summary.get("status") == "VERIFIED", "four-service summary failed")
    require(summary.get("job_id") == four.get("job_id"), "summary job mismatch")
    require(summary.get("trace_id") == four.get("trace_id"), "summary trace mismatch")
    require(summary.get("locked_candidate") == CANDIDATE, "candidate mismatch")
    require(summary.get("tool_commit") == TOOL_COMMIT, "tool commit mismatch")

    services = four.get("services")
    require(set(services) == set(ROLES), "service membership mismatch")

    for role, (port, socket_expected) in ROLES.items():
        service = services[role]
        require(service.get("state") == "running", f"{role} was not running")
        require(service.get("health") == "healthy", f"{role} was not healthy")
        require(service.get("image_id") == IMAGE_ID, f"{role} image mismatch")
        require(
            service.get("published") == f"127.0.0.1:{port}->8080/tcp",
            f"{role} port mismatch",
        )
        require(
            service.get("docker_socket") is socket_expected,
            f"{role} Docker socket mismatch",
        )

        log_path = EVIDENCE / f"four-services/logs/{role}.log"
        log = log_path.read_text(encoding="utf-8", errors="replace")
        require(four["job_id"] in log, f"{role} log lacks job ID")
        require(four["trace_id"] in log, f"{role} log lacks trace ID")

    for name in (
        "compose-up-exit-code.txt",
        "orchestrate-exit-code.txt",
        "scan-evidence-exit-code.txt",
        "scan-services-exit-code.txt",
        "compose-down-exit-code.txt",
    ):
        value = (EVIDENCE / "four-services" / name).read_text().strip()
        require(value == "0", f"{name} is not zero")

    require(
        not (EVIDENCE / "four-services/remaining-project-containers.txt")
        .read_text()
        .strip(),
        "Compose project containers remained after shutdown",
    )


def validate_b2(identity, handoff):
    b2 = identity["b2_handoff"]
    require(b2 == handoff["b2_handoff"], "B2 handoff metadata mismatch")
    require(b2.get("status") == "VERIFIED", "B2 handoff not verified")
    require(b2.get("candidate_commit") == CANDIDATE, "B2 candidate mismatch")

    path = ROOT / b2["path"]
    require(path.is_file() and not path.is_symlink(), "B2 handoff missing")
    require(path.stat().st_size == b2["bytes"], "B2 handoff size mismatch")
    require(sha256(path) == b2["sha256"], "B2 handoff hash mismatch")

    source = read_json(path)
    require(source.get("status") == "SUCCEEDED", "B2 source handoff failed")
    require(source.get("candidate_commit") == CANDIDATE, "B2 source candidate mismatch")


def validate_recovery(identity, handoff):
    recovery_path = checked_ref(identity["recovery"])
    require(identity["recovery"] == handoff["recovery"], "recovery ref mismatch")
    recovery = read_json(recovery_path)

    require(
        recovery.get("status") == "RECOVERED_AND_VERIFIED",
        "recovery status mismatch",
    )
    require(recovery.get("input_modified") is False, "recovery modified input")
    require(recovery["failed"]["status"] == "FAILED", "failure record missing")
    require(
        recovery["succeeded"]["status"] == "SUCCEEDED",
        "recovery success missing",
    )
    require(
        recovery["succeeded"]["verification"] == "VERIFIED",
        "recovery verification missing",
    )


def main():
    validate_archive_tree()

    identity = read_json(B1 / "identity.json")
    handoff = read_json(B1 / "handoff.json")

    require(
        identity.get("schema_version") == "e14-b1-identity-1",
        "identity schema mismatch",
    )
    require(
        handoff.get("schema_version") == "e14-b1-handoff-1",
        "handoff schema mismatch",
    )
    require(handoff.get("status") == "PASS", "handoff is not PASS")

    require(
        identity.get("final_candidate_commit") == CANDIDATE,
        "identity candidate mismatch",
    )
    require(
        handoff.get("candidate_commit") == CANDIDATE,
        "handoff candidate mismatch",
    )
    require(identity.get("tool_commit") == TOOL_COMMIT, "identity tool mismatch")
    require(handoff.get("tool_commit") == TOOL_COMMIT, "handoff tool mismatch")

    require(identity["formal_result"]["status"] == "PASS", "formal result failed")
    require(
        identity["formal_result"] == handoff["formal_result"],
        "formal result handoff mismatch",
    )
    require(identity.get("archive_ci") == "NOT_RUN", "invalid archive CI state")
    require(handoff.get("archive_ci") == "NOT_RUN", "invalid handoff CI state")
    require(handoff.get("next_role") == "E14-B4", "next role mismatch")

    manifest = validate_evidence_manifest(identity, handoff)
    validate_fixed_sample(identity, handoff)
    validate_single(identity, handoff)
    validate_four_services(identity, handoff)
    validate_b2(identity, handoff)
    validate_recovery(identity, handoff)

    teaching = identity["teaching_image"]
    require(teaching == handoff["teaching_image"], "image handoff mismatch")
    require(teaching.get("image_id") == IMAGE_ID, "teaching image mismatch")
    checked_ref(teaching["inspect"])

    readme = (B1 / "README.md").read_text(encoding="utf-8")
    for required in (
        "E14 B1：正式固定样例验收",
        CANDIDATE,
        TOOL_COMMIT,
        identity["single_container_run"]["job_id"],
        identity["four_service_run"]["job_id"],
    ):
        require(required in readme, f"README missing identity: {required}")

    output = {
        "status": "E14_B1_ARCHIVE_VERIFIED",
        "candidate_commit": CANDIDATE,
        "tool_commit": TOOL_COMMIT,
        "single_job_id": identity["single_container_run"]["job_id"],
        "four_service_job_id": identity["four_service_run"]["job_id"],
        "evidence_files": manifest["file_count"],
        "evidence_bytes": manifest["total_bytes"],
        "next_role": handoff["next_role"],
        "archive_ci": handoff["archive_ci"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)
