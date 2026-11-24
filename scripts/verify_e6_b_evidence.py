"""Validate an E6 B auto-build evidence directory without rerunning Docker."""

import argparse
import hashlib
import json
from pathlib import Path
import re


IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify(directory: str | Path) -> dict:
    root = Path(directory).resolve()
    report = _read_json(root / "result.json")
    if report.get("status") != "SUCCEEDED":
        raise ValueError("workflow was not successful")

    attempts = report.get("attempts", [])
    if [item.get("iteration") for item in attempts] != ["iter-01", "iter-02"]:
        raise ValueError("expected exactly two ordered build attempts")
    if (
        attempts[0].get("build_exit_code") == 0
        or attempts[0].get("failure_class") != "MISSING_MAKE"
    ):
        raise ValueError("baseline did not reproduce MISSING_MAKE")

    initial_log = (root / "iter-01" / "build.log").read_text(
        encoding="utf-8", errors="replace"
    )
    if "make: not found" not in initial_log.lower():
        raise ValueError("missing-make evidence was not found in the saved log")

    candidate_attempt = attempts[1]
    if candidate_attempt.get("build_exit_code") != 0:
        raise ValueError("candidate build did not succeed")
    candidate = (root / "iter-02" / "Dockerfile").read_bytes()
    candidate_sha256 = hashlib.sha256(candidate).hexdigest()
    if candidate_sha256 != report.get("candidate_sha256"):
        raise ValueError("candidate hash mismatch")

    image_id = candidate_attempt.get("image_id")
    if not isinstance(image_id, str) or not IMAGE_ID_PATTERN.fullmatch(image_id):
        raise ValueError("candidate image ID is missing or invalid")
    inspect = _read_json(root / "iter-02" / "image-inspect.json")
    if inspect.get("exit_code") != 0 or inspect.get("stdout", "").strip() != image_id:
        raise ValueError("saved image inspection does not match the result")

    verification = report.get("verification", {})
    command = verification.get("command", [])
    required_pairs = {
        "--network": "none",
        "--cpus": "1",
        "--memory": "128m",
        "--pids-limit": "64",
    }
    for flag, expected in required_pairs.items():
        try:
            actual = command[command.index(flag) + 1]
        except (ValueError, IndexError) as exc:
            raise ValueError(f"verification command is missing {flag}") from exc
        if actual != expected:
            raise ValueError(f"verification command has unexpected {flag}")
    if not command or command[-1] != image_id:
        raise ValueError("verified image ID differs from the built image ID")

    stdout = (root / "iter-02" / "verify.stdout.log").read_text(encoding="utf-8")
    stderr = (root / "iter-02" / "verify.stderr.log").read_text(encoding="utf-8")
    if (
        verification.get("exit_code") != 0
        or verification.get("output_matches") is not True
        or verification.get("stderr_empty") is not True
        or verification.get("actual_output") != stdout
        or verification.get("stderr") != stderr
        or stdout != "hello E3\n"
        or stderr != ""
    ):
        raise ValueError("program output verification failed")

    return {
        "passed": True,
        "trace_id": report.get("trace_id"),
        "baseline_failure": "MISSING_MAKE",
        "candidate_build_exit_code": 0,
        "verify_exit_code": 0,
        "verified_output": "hello E3",
        "candidate_sha256": candidate_sha256,
        "image_id": image_id,
        "scope": "saved evidence consistency; Docker builds were not rerun",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.run_dir)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
