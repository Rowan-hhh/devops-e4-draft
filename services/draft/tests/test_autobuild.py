"""Unit tests for the E6 B1 two-round build coordinator."""

import pytest

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
