"""E7 B gate runner for real success and candidate-build-failure workflows."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


CASES = ("success", "build-failed")


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_logged(command, folder: Path, *, timeout: int) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    _write_json(folder / "command.json", command)
    with (folder / "stdout.log").open("w", encoding="utf-8") as stdout, (
        folder / "stderr.log"
    ).open("w", encoding="utf-8") as stderr:
        try:
            code = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            cidfile = folder / "service-container-id.txt"
            if cidfile.is_file():
                cid = cidfile.read_text(encoding="utf-8").strip()
                if re.fullmatch(r"[0-9a-f]{64}", cid):
                    subprocess.run(
                        ["docker", "rm", "-f", cid],
                        stdout=stderr,
                        stderr=stderr,
                        timeout=30,
                        check=False,
                    )
            code = 124
            stderr.write(f"outer command timed out after {timeout} seconds\n")
    _write_json(folder / "exit-code.json", {"exit_code": code})
    return code


def _attempts(report: dict) -> list[dict]:
    attempts = report.get("attempts", [])
    if [item.get("iteration") for item in attempts] != ["iter-01", "iter-02"]:
        raise ValueError("expected exactly two ordered build attempts")
    first = attempts[0]
    if first.get("build_exit_code") == 0 or first.get("failure_class") != "MISSING_MAKE":
        raise ValueError("baseline did not reproduce MISSING_MAKE")
    return attempts


def evaluate(case_name: str, exit_code: int, report: dict, evidence: Path) -> None:
    attempts = _attempts(report)
    baseline_log = (evidence / "iter-01" / "build.log").read_text(
        encoding="utf-8", errors="replace"
    )
    if "make: not found" not in baseline_log.lower():
        raise ValueError("saved baseline log does not contain make: not found")

    if case_name == "success":
        verification = report.get("verification", {})
        image_id = attempts[1].get("image_id")
        if (
            exit_code != 0
            or report.get("status") != "SUCCEEDED"
            or attempts[1].get("build_exit_code") != 0
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id or "")
            or verification.get("command", [None])[-1] != image_id
            or verification.get("exit_code") != 0
            or verification.get("actual_output") != "hello E3\n"
            or verification.get("stderr") != ""
            or verification.get("output_matches") is not True
        ):
            raise ValueError("normal candidate workflow did not pass")
        return

    if case_name == "build-failed":
        build_log = (evidence / "iter-02" / "build.log").read_text(
            encoding="utf-8", errors="replace"
        )
        if (
            exit_code != 1
            or report.get("status") != "FAILED"
            or attempts[1].get("build_exit_code") != 1
            or attempts[1].get("failure_class") != "BUILD_FAILED"
            or "verification" in report
            or "image_id" in report
            or "exit code: 23" not in build_log.lower()
            or (evidence / "iter-02" / "verify.stdout.log").exists()
        ):
            raise ValueError("candidate build failure did not stop verification")
        return

    raise ValueError(f"unsupported case: {case_name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="course1020-draft:e7-b1")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--build-timeout", type=int, default=600)
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args(argv)
    if os.name != "posix":
        parser.error("run this gate on the Linux Docker host")
    if args.build_timeout <= 0:
        parser.error("build timeout must be positive")

    root = Path(__file__).resolve().parents[1]
    fixture = root / "fixtures" / "draft"
    candidate = Path(args.candidate).resolve()
    output = Path(args.out).resolve()
    cases = list(dict.fromkeys(args.case or CASES))
    if not fixture.is_dir() or not candidate.is_file():
        parser.error("fixture or candidate is missing")
    if output.exists() and any(output.iterdir()):
        parser.error("output must be a fresh directory")
    output.mkdir(parents=True, exist_ok=True)

    candidate_bytes = candidate.read_bytes()
    candidate_text = candidate_bytes.decode("utf-8")
    candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()
    rows = []
    try:
        if run_logged(
            ["docker", "image", "inspect", args.image],
            output / "image",
            timeout=30,
        ):
            raise ValueError("service image is unavailable")
        unit_code = run_logged(
            ["docker", "run", "--rm", "--network", "none", args.image, "pytest"],
            output / "unit-tests",
            timeout=180,
        )
        rows.append(
            {"case": "unit-tests", "passed": unit_code == 0, "exit_code": unit_code}
        )
        if unit_code:
            raise ValueError("service unit tests failed")

        for case_name in cases:
            case_dir = output / case_name
            source = case_dir / "fixture"
            evidence = case_dir / "evidence"
            shutil.copytree(fixture, source)
            reference = source / "Dockerfile.reference"
            if reference.exists():
                reference.unlink()
            evidence.mkdir()

            text = candidate_text
            injection = None
            if case_name == "build-failed":
                if "RUN make" not in text:
                    raise ValueError("candidate RUN make differs; review injection")
                text = text.replace("RUN make", "RUN exit 23\nRUN make", 1)
                injection = {
                    "type": "CANDIDATE_BUILD_EXIT_23",
                    "changed_file": "candidate.Dockerfile",
                    "source_candidate_sha256": candidate_sha256,
                    "expected": "iter-02 build fails and verification is absent",
                }
                _write_json(case_dir / "fault-injection.json", injection)

            case_candidate = case_dir / "candidate.Dockerfile"
            case_candidate.write_text(text, encoding="utf-8", newline="\n")
            _write_json(
                case_dir / "candidate-identity.json",
                {
                    "source": str(candidate),
                    "source_sha256": candidate_sha256,
                    "case_sha256": hashlib.sha256(case_candidate.read_bytes()).hexdigest(),
                    "fault_injection": injection,
                },
            )

            cidfile = case_dir / "service-container-id.txt"
            command = [
                "docker",
                "run",
                "--rm",
                "--network",
                "bridge",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-e",
                "HOME=/tmp",
            ]
            build_proxy = os.environ.get("DRAFT_BUILD_HTTP_PROXY")
            if build_proxy:
                command += ["-e", f"DRAFT_BUILD_HTTP_PROXY={build_proxy}"]
            command += [
                "--group-add",
                str(Path("/var/run/docker.sock").stat().st_gid),
                "-v",
                "/var/run/docker.sock:/var/run/docker.sock",
                "--cidfile",
                str(cidfile),
                "--mount",
                f"type=bind,src={source},dst=/fixture,readonly",
                "--mount",
                f"type=bind,src={case_candidate},dst=/candidate.Dockerfile,readonly",
                "--mount",
                f"type=bind,src={evidence},dst=/evidence",
                args.image,
                "python3",
                "-m",
                "draft",
                "auto-build",
                "--fixture",
                "/fixture",
                "--candidate",
                "/candidate.Dockerfile",
                "--out",
                "/evidence",
                "--expected-output",
                "hello E3",
                "--timeout",
                str(args.build_timeout),
            ]
            exit_code = run_logged(
                command,
                case_dir,
                timeout=2 * args.build_timeout + 180,
            )
            row = {"case": case_name, "passed": False, "exit_code": exit_code}
            try:
                report = json.loads(
                    (evidence / "result.json").read_text(encoding="utf-8")
                )
                evaluate(case_name, exit_code, report, evidence)
                row.update(
                    passed=True,
                    workflow_status=report["status"],
                    trace_id=report.get("trace_id", ""),
                )
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
                row["error"] = str(exc)
            rows.append(row)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        rows.append({"case": "runner", "passed": False, "error": str(exc)})

    passed = len(rows) == len(cases) + 1 and all(row["passed"] for row in rows)
    result = {
        "schema_version": 1,
        "stage": "E7",
        "role": "B1",
        "passed": passed,
        "image": args.image,
        "candidate_sha256": candidate_sha256,
        "selected_cases": cases,
        "cases": rows,
        "build_timeout_seconds": args.build_timeout,
    }
    _write_json(output / "gate-result.json", result)
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "case",
                "passed",
                "exit_code",
                "workflow_status",
                "trace_id",
                "error",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
