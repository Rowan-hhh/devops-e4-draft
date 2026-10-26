"""Unit tests for the E6 B1 two-round build coordinator."""

import pytest

from draft import autobuild
from draft.autobuild import (
    FIXED_FROM,
    build_initial_dockerfile,
    classify_build,
    validate_candidate,
)


CANDIDATE = f"""FROM {FIXED_FROM}
WORKDIR /work
COPY main.c Makefile ./
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
RUN make
CMD ["./hello"]
"""


BROKEN = f"""FROM {FIXED_FROM}
WORKDIR /work
COPY main.c Makefile ./
RUN make
CMD ["./hello"]
"""


def test_candidate2_shape_is_accepted(tmp_path):
    candidate = tmp_path / "Dockerfile"
    candidate.write_text(CANDIDATE, encoding="utf-8")
    assert validate_candidate(candidate) == []


@pytest.mark.parametrize(
    "replacement",
    [
        ("FROM " + FIXED_FROM, "FROM python:3.13-slim"),
        ("WORKDIR /work", "WORKDIR /tmp"),
        ("COPY main.c Makefile ./", "COPY main.c ./"),
        ('CMD ["./hello"]', 'CMD ["python3"]'),
    ],
)
def test_candidate_constraints_are_rejected(tmp_path, replacement):
    candidate = tmp_path / "Dockerfile"
    candidate.write_text(CANDIDATE.replace(*replacement), encoding="utf-8")
    errors = validate_candidate(candidate)
    assert errors


def test_initial_dockerfile_keeps_fixed_from_and_broken_body(tmp_path):
    candidate = tmp_path / "candidate.Dockerfile"
    candidate.write_text(CANDIDATE, encoding="utf-8")
    initial = build_initial_dockerfile(candidate, BROKEN)
    assert initial.splitlines()[0] == f"FROM {FIXED_FROM}"
    assert "RUN make" in initial
    assert "build-essential" not in initial


def test_build_failure_classification():
    assert classify_build(1, "/bin/sh: 1: make: not found") == "MISSING_MAKE"
    assert classify_build(1, "some compiler error") == "BUILD_FAILED"
    assert classify_build(124, "timed out") == "BUILD_TIMEOUT"
    assert classify_build(0, "success") == "SUCCEEDED"


def test_verification_runs_exact_image_offline_with_limits(tmp_path, monkeypatch):
    """B4 regression: verify the built image ID, never a mutable tag."""
    image_id = "sha256:" + "a" * 64
    observed = {}

    def fake_run(command, *, cwd=None, timeout):
        observed["command"] = command
        observed["timeout"] = timeout
        return 0, "hello E3\n", ""

    monkeypatch.setattr(autobuild, "_run", fake_run)
    result = autobuild._verify_image(tmp_path, image_id, "hello E3", 30)

    command = observed["command"]
    assert command[-1] == image_id
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--cpus") + 1] == "1"
    assert command[command.index("--memory") + 1] == "128m"
    assert command[command.index("--pids-limit") + 1] == "64"
    assert observed["timeout"] == 30
    assert result["exit_code"] == 0
    assert result["output_matches"] is True
    assert result["stderr_empty"] is True


def test_build_proxy_is_explicit_and_does_not_change_dockerfile(tmp_path, monkeypatch):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(CANDIDATE, encoding="utf-8")
    before = dockerfile.read_bytes()
    observed = {}

    def fake_run(command, *, cwd=None, timeout):
        observed["command"] = command
        return 1, "", "/bin/sh: 1: make: not found\n"

    monkeypatch.setenv("DRAFT_BUILD_HTTP_PROXY", "http://172.17.0.1:3142")
    monkeypatch.setattr(autobuild, "_run", fake_run)
    autobuild._build_attempt(
        iteration="iter-01",
        dockerfile=dockerfile,
        project=tmp_path,
        tag="proxy-test:latest",
        trace_id="proxy-test",
        timeout=30,
    )

    command = observed["command"]
    assert "HTTP_PROXY=http://172.17.0.1:3142" in command
    assert "http_proxy=http://172.17.0.1:3142" in command
    assert dockerfile.read_bytes() == before


def test_candidate_build_failure_stops_before_verification(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "Dockerfile.broken").write_text(BROKEN, encoding="utf-8")
    (fixture / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (fixture / "Makefile").write_text("all:\n\tcc main.c -o hello\n", encoding="utf-8")
    candidate = tmp_path / "candidate.Dockerfile"
    candidate.write_text(CANDIDATE, encoding="utf-8")
    attempts = iter(
        [
            {
                "iteration": "iter-01",
                "build_exit_code": 1,
                "status": "EXPECTED_FAILURE",
                "failure_class": "MISSING_MAKE",
            },
            {
                "iteration": "iter-02",
                "build_exit_code": 1,
                "status": "FAILED",
                "failure_class": "BUILD_FAILED",
            },
        ]
    )

    monkeypatch.setattr(autobuild, "_build_attempt", lambda **kwargs: next(attempts))
    monkeypatch.setattr(
        autobuild,
        "_inspect_image",
        lambda *args, **kwargs: pytest.fail("image inspection must be skipped"),
    )
    monkeypatch.setattr(
        autobuild,
        "_verify_image",
        lambda *args, **kwargs: pytest.fail("program verification must be skipped"),
    )

    output = tmp_path / "evidence"
    assert autobuild.auto_build(fixture, candidate, output) == 1
    result = __import__("json").loads((output / "result.json").read_text())
    assert result["status"] == "FAILED"
    assert result["failure_class"] == "BUILD_FAILED"
    assert len(result["attempts"]) == 2
    assert "image_id" not in result
    assert "verification" not in result


def test_invalid_candidate_is_rejected_before_any_build_attempt(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "Dockerfile.broken").write_text(BROKEN, encoding="utf-8")
    (fixture / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (fixture / "Makefile").write_text("all:\n\tcc main.c -o hello\n", encoding="utf-8")
    candidate = tmp_path / "candidate.Dockerfile"
    candidate.write_text(CANDIDATE.replace('CMD ["./hello"]', 'CMD ["./not-a-real-program"]'), encoding="utf-8")

    monkeypatch.setattr(
        autobuild,
        "_build_attempt",
        lambda **kwargs: pytest.fail("invalid candidate must be rejected before build"),
    )

    output = tmp_path / "evidence"
    assert autobuild.auto_build(fixture, candidate, output) == 1
    result = __import__("json").loads((output / "result.json").read_text())
    assert result["status"] == "FAILED"
    assert result["failure_class"] == "INVALID_CANDIDATE"
    assert result["attempts"] == []
    assert "image_id" not in result
    assert "verification" not in result


def test_wrong_output_is_recorded_as_runtime_verification_failure(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "Dockerfile.broken").write_text(BROKEN, encoding="utf-8")
    (fixture / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (fixture / "Makefile").write_text("all:\n\tcc main.c -o hello\n", encoding="utf-8")
    candidate = tmp_path / "candidate.Dockerfile"
    candidate.write_text(CANDIDATE, encoding="utf-8")
    image_id = "sha256:" + "b" * 64
    attempts = iter(
        [
            {
                "iteration": "iter-01",
                "build_exit_code": 1,
                "status": "EXPECTED_FAILURE",
                "failure_class": "MISSING_MAKE",
            },
            {
                "iteration": "iter-02",
                "build_exit_code": 0,
                "status": "SUCCEEDED",
                "failure_class": "SUCCEEDED",
                "image_id": image_id,
            },
        ]
    )
    monkeypatch.setattr(autobuild, "_build_attempt", lambda **kwargs: next(attempts))
    monkeypatch.setattr(autobuild, "_inspect_image", lambda *args, **kwargs: image_id)
    monkeypatch.setattr(
        autobuild,
        "_verify_image",
        lambda *args, **kwargs: {
            "image_id": image_id,
            "exit_code": 0,
            "expected_output": "wrong E3\n",
            "actual_output": "hello E3\n",
            "stderr": "",
            "output_matches": False,
            "stderr_empty": True,
        },
    )

    output = tmp_path / "evidence"
    assert autobuild.auto_build(fixture, candidate, output, expected_output="wrong E3") == 1
    result = __import__("json").loads((output / "result.json").read_text())
    assert result["status"] == "FAILED"
    assert result["failure_class"] == "RUNTIME_VERIFICATION_FAILED"
    assert result["attempts"][1]["image_id"] == image_id
    assert result["verification"]["output_matches"] is False
