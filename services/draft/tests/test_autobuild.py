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
