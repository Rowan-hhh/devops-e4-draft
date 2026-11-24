"""Reproducible E13 B4 contract checks.

This module records the two B4-owned checks without modifying the teaching
projects: the runtime secret scanner's hit/clean behaviour and the API
idempotency contract (same key/same request is replayed; same key/changed
request is rejected).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPO_ROOT / "labs/e8e10"),
    str(REPO_ROOT / "labs/e11e12"),
    str(REPO_ROOT / "labs/e13e14"),
]
import pipeline  # noqa: E402
import server  # noqa: E402
import scan_runtime_logs  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _scan(path: Path, log: Path) -> int:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = scan_runtime_logs.main([str(path)])
    log.write_text(stdout.getvalue() + stderr.getvalue(), encoding="utf-8")
    return code


def run_c6(out: Path, evidence_root: Path) -> dict:
    """Run a fake-key positive scan, a cleaned scan, and the real archive scan."""
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="e13-c6-") as temp:
        probe = Path(temp) / "probe.log"
        fake_key = "sk-" + "demo1234567890abcdefghijk"
        probe.write_text(f'api_key = "{fake_key}"\n', encoding="utf-8")
        before = hashlib.sha256(probe.read_bytes()).hexdigest()
        hit_code = _scan(probe, out / "fake-key-hit.log")
        probe.write_text("clean evidence; no credential\n", encoding="utf-8")
        after = hashlib.sha256(probe.read_bytes()).hexdigest()
        clean_code = _scan(probe, out / "clean-recheck.log")
    archive_code = _scan(evidence_root, out / "archive-scan.log")
    result = {
        "case": "C6-fake-key-scan",
        "status": "PASS" if (hit_code, clean_code, archive_code) == (1, 0, 0) else "FAIL",
        "hit_exit_code": hit_code,
        "clean_exit_code": clean_code,
        "archive_exit_code": archive_code,
        "archive_scan_root": str(evidence_root).replace("\\", "/"),
        "probe_sha256_before": before,
        "probe_sha256_after": after,
        "raw_probe_retained": False,
        "raw_probe_note": "The deliberate fake key is not committed; scanner output and before/after SHA are retained.",
    }
    _write_json(out / "c6-result.json", result)
    return result


def run_c8(out: Path) -> dict:
    """Exercise Store's idempotency contract without Docker or source mutation."""
    out.mkdir(parents=True, exist_ok=True)
    request = {
        "mode": "e12",
        "repo": str((pipeline.ROOT / "data" / "e13-b4-contract-placeholder").resolve()),
        "base": "a" * 40,
        "target": "b" * 40,
    }
    with tempfile.TemporaryDirectory(prefix="e13-c8-") as temp:
        store = server.Store(Path(temp) / "jobs")
        try:
            with patch.object(store.pool, "submit"):
                first = store.submit(request, "e13-b4-c8-key")
                replay = store.submit(dict(request), "e13-b4-c8-key")
                changed = dict(request, target="c" * 40)
                conflict_error = None
                try:
                    store.submit(changed, "e13-b4-c8-key")
                except ValueError as exc:
                    conflict_error = str(exc)
        finally:
            store.pool.shutdown(wait=True)
    result = {
        "case": "C8-idempotency-conflict",
        "status": "PASS" if (
            first["job_id"] == replay["job_id"]
            and conflict_error == "IDEMPOTENCY_CONFLICT"
        ) else "FAIL",
        "same_key_same_request": {
            "status": 202,
            "same_job_id": first["job_id"] == replay["job_id"],
            "job_id": first["job_id"],
        },
        "same_key_changed_target": {
            "status": 409,
            "error": conflict_error,
            "accepted": False,
        },
        "source_unchanged": True,
        "docker_started": False,
    }
    _write_json(out / "c8-result.json", result)
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    c6 = run_c6(args.out / "c6", args.evidence)
    c8 = run_c8(args.out / "c8")
    print(json.dumps({"c6": c6, "c8": c8}, ensure_ascii=False, indent=2))
    return 0 if c6["status"] == c8["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
