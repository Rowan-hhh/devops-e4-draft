"""E6 B1 two-round Docker build coordinator.

The coordinator intentionally keeps the baseline failure as a first-class
record: the broken fixture must fail with MISSING_MAKE before the candidate
Dockerfile is built and verified.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit


FIXED_FROM = (
    "python:3.13-slim@sha256:"
    "70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f"
)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int,
) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return completed.returncode, _text(completed.stdout), _text(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        return (
            124,
            _text(exc.stdout),
            _text(exc.stderr) + "\ncommand timed out after "
            f"{timeout} seconds\n",
        )
    except OSError as exc:
        return 127, "", f"{type(exc).__name__}: {exc}\n"


def validate_candidate(path: Path) -> list[str]:
    """Return all E6 B2 constraint violations in a candidate Dockerfile."""
    text = path.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    errors: list[str] = []
    from_lines = [line for line in lines if line.upper().startswith("FROM ")]
    expected_from = f"FROM {FIXED_FROM}"
    if from_lines != [expected_from]:
        errors.append(f"FROM must be exactly: {expected_from}")
    if "WORKDIR /work" not in lines:
        errors.append("WORKDIR /work is required")
    if "COPY main.c Makefile ./" not in lines:
        errors.append("COPY main.c Makefile ./ is required")
    if not any(line == "RUN make" for line in lines):
        errors.append("RUN make is required")
    if 'CMD ["./hello"]' not in lines:
        errors.append('CMD ["./hello"] is required')
    return errors


def build_initial_dockerfile(candidate: Path, broken_text: str) -> str:
    """Combine the candidate's fixed FROM with the broken fixture body."""
    candidate_lines = [
        line.strip()
        for line in candidate.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    from_line = next(
        (line for line in candidate_lines if line.upper().startswith("FROM ")),
        None,
    )
    if from_line is None:
        raise ValueError("candidate has no FROM line")
    broken_lines = broken_text.splitlines()
    from_index = next(
        (
            index
            for index, line in enumerate(broken_lines)
            if line.strip().upper().startswith("FROM ")
        ),
        None,
    )
    if from_index is None:
        raise ValueError("broken fixture has no FROM line")
    body = broken_lines[from_index + 1 :]
    return from_line + "\n" + "\n".join(body) + "\n"


def classify_build(exit_code: int, combined_log: str) -> str:
    if exit_code == 0:
        return "SUCCEEDED"
    if exit_code == 124:
        return "BUILD_TIMEOUT"
    lower = combined_log.lower()
    if "make: not found" in lower or "make: command not found" in lower:
        return "MISSING_MAKE"
    return "BUILD_FAILED"


def _build_proxy_args() -> list[str]:
    """Return an auditable Docker build proxy argument when explicitly set."""
    proxy = os.environ.get("DRAFT_BUILD_HTTP_PROXY", "")
    if not proxy:
        return []
    parsed = urlsplit(proxy)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "DRAFT_BUILD_HTTP_PROXY must be an http(s) URL without credentials"
        )
    return [
        "--build-arg",
        f"HTTP_PROXY={proxy}",
        "--build-arg",
        f"http_proxy={proxy}",
    ]


def _save_build_logs(
    folder: Path,
    command: Sequence[str],
    exit_code: int,
    stdout: str,
    stderr: str,
    *,
    trace_id: str,
    iteration: str,
    failure_class: str,
    status: str,
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    _write_json(folder / "command.json", list(command))
    (folder / "build-stdout.log").write_text(stdout, encoding="utf-8")
    (folder / "build-stderr.log").write_text(stderr, encoding="utf-8")
    combined = stdout
    if stdout and stderr:
        combined += "\n"
    combined += stderr
    (folder / "build.log").write_text(combined, encoding="utf-8")
    _write_json(folder / "build-exit-code.json", {"exit_code": exit_code})
    _write_json(folder / "exit-code.json", {"exit_code": exit_code})
    (folder / "trace_id.txt").write_text(trace_id + "\n", encoding="utf-8")
    _write_json(
        folder / "status.json",
        {
            "iteration": iteration,
            "status": status,
            "trace_id": trace_id,
            "build_exit_code": exit_code,
            "failure_class": failure_class,
        },
    )


def _build_attempt(
    *,
    iteration: str,
    dockerfile: Path,
    project: Path,
    tag: str,
    trace_id: str,
    timeout: int,
) -> dict[str, Any]:
    folder = dockerfile.parent
    command = [
        "docker",
        "build",
        "--progress=plain",
        *_build_proxy_args(),
        "-f",
        str(dockerfile),
        "-t",
        tag,
        str(project),
    ]
    exit_code, stdout, stderr = _run(command, timeout=timeout)
    combined = stdout + ("\n" if stdout and stderr else "") + stderr
    failure_class = classify_build(exit_code, combined)
    status = "SUCCEEDED"
    if exit_code != 0:
        status = "EXPECTED_FAILURE" if failure_class == "MISSING_MAKE" else "FAILED"
    _save_build_logs(
        folder,
        command,
        exit_code,
        stdout,
        stderr,
        trace_id=trace_id,
        iteration=iteration,
        failure_class=failure_class,
        status=status,
    )
    return {
        "iteration": iteration,
        "tag": tag,
        "trace_id": trace_id,
        "command": command,
        "build_exit_code": exit_code,
        "status": status,
        "failure_class": failure_class,
    }


def _inspect_image(folder: Path, tag: str) -> str | None:
    command = [
        "docker",
        "image",
        "inspect",
        "--format",
        "{{.Id}}",
        tag,
    ]
    exit_code, stdout, stderr = _run(command, timeout=30)
    (folder / "image-inspect.stdout.log").write_text(stdout, encoding="utf-8")
    (folder / "image-inspect.stderr.log").write_text(stderr, encoding="utf-8")
    _write_json(
        folder / "image-inspect.json",
        {
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        },
    )
    image_id = stdout.strip().splitlines()[-1] if stdout.strip() else ""
    if exit_code != 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        return None
    (folder / "image_id.txt").write_text(image_id + "\n", encoding="utf-8")
    return image_id


def _verify_image(
    folder: Path,
    image_id: str,
    expected_output: str,
    timeout: int,
) -> dict[str, Any]:
    cidfile = folder / "verify-container-id.txt"
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        "1",
        "--memory",
        "128m",
        "--pids-limit",
        "64",
        "--cidfile",
        str(cidfile),
        image_id,
    ]
    exit_code, stdout, stderr = _run(command, timeout=timeout)
    (folder / "verify.stdout.log").write_text(stdout, encoding="utf-8")
    (folder / "verify.stderr.log").write_text(stderr, encoding="utf-8")
    _write_json(folder / "verify-exit-code.json", {"exit_code": exit_code})
    (folder / "verify.log").write_text(stdout + stderr, encoding="utf-8")
    expected = expected_output + "\n"
    verification = {
        "command": command,
        "image_id": image_id,
        "exit_code": exit_code,
        "expected_output": expected,
        "actual_output": stdout,
        "stderr": stderr,
        "output_matches": stdout == expected,
        "stderr_empty": stderr == "",
    }
    _write_json(folder / "verification.json", verification)
    return verification


def auto_build(
    fixture: str | Path,
    candidate: str | Path,
    out: str | Path,
    *,
    expected_output: str = "hello E3",
    timeout: int = 600,
) -> int:
    """Run the E6 B1 baseline/candidate build flow and write result.json."""
    fixture_path = Path(fixture).resolve()
    candidate_path = Path(candidate).resolve()
    out_path = Path(out).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    trace_id = "e6-b-" + uuid.uuid4().hex
    candidate_sha256 = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "RUNNING",
        "detector": "DRAFT_TEACHING_AUTO_BUILD",
        "trace_id": trace_id,
        "candidate_source": "student supplied; see student provenance record",
        "candidate_sha256": candidate_sha256,
        "expected_output": expected_output,
        "attempts": [],
    }

    def save() -> None:
        _write_json(out_path / "result.json", result)

    _write_json(
        out_path / "provenance.json",
        {
            "candidate": str(candidate_path),
            "candidate_sha256": candidate_sha256,
            "fixture": str(fixture_path),
            "trace_id": trace_id,
        },
    )
    (out_path / "trace_id.txt").write_text(trace_id + "\n", encoding="utf-8")
    (out_path / "candidate.Dockerfile").write_text(
        candidate_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    errors = validate_candidate(candidate_path)
    if errors:
        result.update(
            {
                "status": "FAILED",
                "failure_class": "INVALID_CANDIDATE",
                "candidate_errors": errors,
            }
        )
        save()
        return 1

    project = out_path / "project"
    shutil.copytree(fixture_path, project)
    broken_text = (project / "Dockerfile.broken").read_text(encoding="utf-8")
    initial_dir = out_path / "iter-01"
    initial_dir.mkdir(parents=True, exist_ok=True)
    initial_dockerfile = build_initial_dockerfile(candidate_path, broken_text)
    (initial_dir / "Dockerfile").write_text(initial_dockerfile, encoding="utf-8")
    initial_trace = trace_id + "-iter-01"
    initial_tag = trace_id + ":iter-01"
    first = _build_attempt(
        iteration="iter-01",
        dockerfile=initial_dir / "Dockerfile",
        project=project,
        tag=initial_tag,
        trace_id=initial_trace,
        timeout=timeout,
    )
    result["attempts"].append(first)
    save()
    if first["failure_class"] != "MISSING_MAKE":
        result.update(
            {
                "status": "FAILED",
                "failure_class": "BASELINE_NOT_MISSING_MAKE",
                "message": "Initial build did not produce MISSING_MAKE",
            }
        )
        save()
        return 1

    candidate_dir = out_path / "iter-02"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_path, candidate_dir / "Dockerfile")
    candidate_trace = trace_id + "-iter-02"
    candidate_tag = trace_id + ":iter-02"
    second = _build_attempt(
        iteration="iter-02",
        dockerfile=candidate_dir / "Dockerfile",
        project=project,
        tag=candidate_tag,
        trace_id=candidate_trace,
        timeout=timeout,
    )
    result["attempts"].append(second)
    image_id = None
    if second["build_exit_code"] == 0:
        image_id = _inspect_image(candidate_dir, candidate_tag)
        second["image_id"] = image_id
        _write_json(candidate_dir / "status.json", second)
    if second["build_exit_code"] != 0:
        result.update(
            {
                "status": "FAILED",
                "failure_class": second["failure_class"],
                "message": "Candidate build failed",
            }
        )
        save()
        return 1
    if image_id is None:
        result.update(
            {
                "status": "FAILED",
                "failure_class": "IMAGE_ID_MISSING",
                "message": "Candidate build succeeded but image ID was unavailable",
            }
        )
        save()
        return 1

    verification = _verify_image(
        candidate_dir,
        image_id,
        expected_output,
        timeout,
    )
    result["image_id"] = image_id
    result["verification"] = verification
    if (
        verification["exit_code"] == 0
        and verification["output_matches"]
        and verification["stderr_empty"]
    ):
        result["status"] = "SUCCEEDED"
        result["failure_class"] = None
        save()
        return 0
    result["status"] = "FAILED"
    result["failure_class"] = "RUNTIME_VERIFICATION_FAILED"
    save()
    return 1
