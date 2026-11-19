"""E13 B2: C3 artifact tamper rejection, C5 patch rollback, and H2-inih.

The teacher project archive is an execution input only.  This module keeps
the submitted evidence small and auditable: negative tests retain hashes,
validation decisions, source state, and logs, while H2 evidence excludes the
copied project source and its Git metadata.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "labs/e11e12"), str(ROOT / "labs/e8e10")]
from lab import validate  # noqa: E402
from pipeline import Failure, load_artifact  # noqa: E402


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


def command(argv, cwd, timeout=120):
    completed = subprocess.run(
        [str(item) for item in argv],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(map(str, argv))}\n"
            f"{completed.stdout}{completed.stderr}"
        )
    return completed.stdout.strip()


def source_state(project):
    """Return Git identity, clean status, and hashes of tracked source bytes."""
    project = Path(project).resolve()
    head = command(["git", "rev-parse", "--verify", "HEAD"], project)
    status = command(["git", "status", "--porcelain", "--untracked-files=all"], project)
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=project)
    names = [os.fsdecode(item) for item in raw.split(b"\0") if item]
    return {
        "head": head,
        "status": status,
        "sha256": {name: sha256(project / name) for name in names},
    }


def run_c3(artifact_path, expected_sha256, out_dir):
    """Consume an artifact with its old digest and record the rejection."""
    artifact_path = Path(artifact_path).resolve()
    out_dir = Path(out_dir).resolve()
    if out_dir.exists():
        raise ValueError("OUTPUT_EXISTS: choose a fresh C3 output directory")
    out_dir.mkdir(parents=True)
    actual_sha256 = sha256(artifact_path)
    accepted = False
    code = "UNEXPECTED_ACCEPT"
    message = "artifact unexpectedly accepted"
    try:
        load_artifact(artifact_path, expected_sha256)
        accepted = True
    except Failure as exc:
        code = exc.code
        message = str(exc)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        code = "ARTIFACT_INVALID"
        message = str(exc)
    result = {
        "schema_version": "e13-b2-c3-1",
        "case": "C3-artifact-hash-tamper",
        "artifact": artifact_path.name,
        "accepted": accepted,
        "code": code,
        "message": message,
        "repair_started": False,
        "expected_sha256": expected_sha256,
        "actual_sha256": actual_sha256,
    }
    save(out_dir / "result.json", result)
    (out_dir / "expected-sha256.txt").write_text(expected_sha256 + "\n", encoding="utf-8")
    (out_dir / "actual-sha256.txt").write_text(actual_sha256 + "\n", encoding="utf-8")
    return result


def run_c5(project_path, patch_path, out_dir):
    """Apply an intentionally invalid patch in a validation sandbox."""
    project_path = Path(project_path).resolve()
    patch_path = Path(patch_path).resolve()
    out_dir = Path(out_dir).resolve()
    if out_dir.exists():
        raise ValueError("OUTPUT_EXISTS: choose a fresh C5 output directory")
    out_dir.mkdir(parents=True)
    before = source_state(project_path)
    validation_dir = out_dir / "validation"
    verdict = validate(project_path, patch_path, validation_dir)
    after = source_state(project_path)
    source_unchanged = before == after
    result = {
        "schema_version": "e13-b2-c5-1",
        "case": "C5-invalid-patch",
        "accepted": bool(verdict.get("accepted")),
        "rollback": bool(verdict.get("rollback")) and source_unchanged,
        "source_unchanged": source_unchanged,
        "patch": patch_path.name,
        "before": before,
        "after": after,
        "validation": verdict,
    }
    save(out_dir / "result.json", result)
    return result


def course_path(path):
    path = Path(path).resolve()
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return path.as_posix()
    return "/course/" + relative.as_posix()


def make_ini_request(project_path, candidate_path, out_path):
    """Generate the H2 request from the independent repo's two real commits."""
    project_path = Path(project_path).resolve()
    candidate_path = Path(candidate_path).resolve()
    out_path = Path(out_path).resolve()
    commits = command(["git", "rev-list", "--max-count=2", "HEAD"], project_path).splitlines()
    if len(commits) != 2:
        raise ValueError(f"H2_REQUIRES_TWO_COMMITS: {commits}")
    target, base = commits
    request = {
        "mode": "e12",
        "repo": course_path(project_path),
        "base": base,
        "target": target,
        "candidate": course_path(candidate_path),
        "expected_output": "1",
        "build_timeout": 600,
    }
    save(out_path, request)
    return request


def archive_h2_evidence(work_dir, evidence_dir):
    """Copy audit-relevant H2 output while excluding copied source trees."""
    work_dir = Path(work_dir).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    excluded = {".git", "base-project", "target-project", "project", "sandbox"}
    for path in work_dir.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        if path.suffix not in {".json", ".log", ".txt", ".patch"}:
            continue
        relative = path.relative_to(work_dir)
        destination = evidence_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def run_h2(project_path, candidate_path, request_path, evidence_dir):
    """Run H2 through the existing Linux/Docker entry point and archive evidence."""
    request_path = Path(request_path).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    request = make_ini_request(project_path, candidate_path, request_path)
    work_dir = ROOT / "work" / ("e13-b2-H2-inih-" + uuid.uuid4().hex[:12])
    command_args = [
        sys.executable,
        str(ROOT / "run_e11e12.py"),
        "run",
        "--request",
        str(request_path.relative_to(ROOT)),
        "--out",
        str(work_dir.relative_to(ROOT)),
    ]
    completed = subprocess.run(
        command_args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "console.log").write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    (evidence_dir / "exit-code.txt").write_text(str(completed.returncode) + "\n", encoding="utf-8")
    if work_dir.exists():
        archive_h2_evidence(work_dir, evidence_dir / "run")
    result_path = work_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
    return {
        "request": request,
        "work_dir": str(work_dir),
        "exit_code": completed.returncode,
        "result": result,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--c5-project", type=Path, required=True)
    parser.add_argument("--c5-patch", type=Path, required=True)
    parser.add_argument("--inih-project", type=Path, required=True)
    parser.add_argument("--inih-candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit("OUTPUT_EXISTS: choose a fresh B2 output directory")
    out.mkdir(parents=True)

    original_sha256 = sha256(args.artifact)
    tampered = out / "C3-artifact-hash-tamper" / "tampered-artifact.json"
    tampered.parent.mkdir(parents=True)
    tampered.write_bytes(Path(args.artifact).read_bytes() + b"\n")
    c3 = run_c3(tampered, original_sha256, tampered.parent / "decision")
    c3["original_artifact_sha256"] = original_sha256
    save(tampered.parent / "result.json", c3)

    c5 = run_c5(args.c5_project, args.c5_patch, out / "C5-invalid-patch")
    inih = run_h2(
        args.inih_project,
        args.inih_candidate,
        out / "H2-inih" / "request-e12.json",
        out / "H2-inih",
    )

    h2_result = inih.get("result") or {}
    passed = (
        c3["accepted"] is False
        and c3["code"] == "ARTIFACT_HASH_MISMATCH"
        and c5["accepted"] is False
        and c5["rollback"] is True
        and h2_result.get("status") == "SUCCEEDED"
    )
    summary = {
        "schema_version": "e13-b2-1",
        "status": "SUCCEEDED" if passed else "FAILED",
        "student_id": "241880300",
        "branch": "e13-zyh-b2",
        "cases": {"C3": c3, "C5": c5, "H2-inih": inih},
        "passed": passed,
    }
    save(out / "result.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
