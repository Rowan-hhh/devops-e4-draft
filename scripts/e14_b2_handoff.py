"""Validate and summarize the E14 B2 Compose deployment evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SERVICES = ("buildchecker", "echecker", "draft", "mdfixer")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_ref(path: Path, root: Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def read_json(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # `docker compose ps --format json` emits one JSON object per line
        # on some Compose versions and a JSON array on others.
        rows = [line for line in text.splitlines() if line.strip()]
        if not rows:
            raise
        return [json.loads(line) for line in rows]


def safe_file(path: Path, root: Path) -> Path:
    """Return an evidence file only when it is inside root and not a symlink."""
    root = root.resolve()
    candidate = path if path.is_absolute() else Path.cwd() / path
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"evidence file outside root: {path}") from exc
    current = candidate
    while current != root:
        if current.is_symlink():
            raise SystemExit(f"evidence symlink forbidden: {path}")
        current = current.parent
    if not resolved.is_file():
        raise SystemExit(f"evidence file missing: {path}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--workflow-run-url")
    parser.add_argument("--four-services-job-url")
    parser.add_argument("--e2e-result", type=Path)
    parser.add_argument("--artifact-id")
    args = parser.parse_args()
    root = args.root.resolve()
    image = read_json(root / "image-inspect.json")
    if not isinstance(image, list) or not image:
        raise SystemExit("image-inspect.json must contain a non-empty inspect list")
    image = image[0]
    tags = image.get("RepoTags", [])
    image_id = image.get("Id")
    digests = image.get("RepoDigests", [])
    health = read_json(root / "health.json")
    if isinstance(health, dict):
        health = [health]
    health_by_service = {}
    health_details = {}
    for item in health:
        name = item.get("Service") or item.get("Name", "")
        for service in SERVICES:
            if service in name:
                health_details[service] = {
                    "name": name,
                    "state": item.get("State"),
                    "health": item.get("Health"),
                }
                health_by_service[service] = item.get("Health")
    if set(health_by_service) != set(SERVICES):
        raise SystemExit(f"missing health records: {sorted(set(SERVICES) - set(health_by_service))}")
    if any(value not in ("healthy", "healthy (healthy)")
           for value in health_by_service.values()):
        raise SystemExit(f"not all services healthy: {health_by_service}")

    mounts = {}
    for service in SERVICES:
        data = read_json(root / f"mounts-{service}.json")
        mounts[service] = data[0].get("Mounts", []) if isinstance(data, list) else data.get("Mounts", [])
    socket_mounts = {
        service: [m for m in entries if "docker.sock" in (m.get("Source", "") + m.get("Destination", ""))]
        for service, entries in mounts.items()
    }
    if socket_mounts["draft"] == [] or any(socket_mounts[s] for s in SERVICES if s != "draft"):
        raise SystemExit(f"Docker socket boundary failed: {socket_mounts}")

    logs = {service: file_ref(root / "logs" / f"{service}.log", root) for service in SERVICES}
    handoff = {
        "schema_version": "e14-b2-handoff-1",
        "stage": "E14",
        "role": "B2",
        "status": "SUCCEEDED",
        "candidate_commit": args.candidate_commit,
        "compose": file_ref(root / "compose.yaml", root),
        "rendered_config": file_ref(root / "compose-config.json", root),
        "image": {
            "tag": args.image_tag,
            "image_id": image_id,
            "repo_digest": digests[0] if digests else None,
            "repo_digests": digests,
            "repo_digest_absent_reason": (
                "CI builds the teaching image locally and does not push it to a registry; "
                "the immutable image ID and inspect evidence are authoritative."
                if not digests else None
            ),
            "inspect": file_ref(root / "image-inspect.json", root),
            "tag_present": args.image_tag in tags,
            "repo_digest_present": bool(digests),
        },
        "health": health_by_service,
        "health_details": health_details,
        "ports": {
            "buildchecker": "127.0.0.1:18081->8080/tcp",
            "echecker": "127.0.0.1:18082->8080/tcp",
            "draft": "127.0.0.1:18083->8080/tcp",
            "mdfixer": "127.0.0.1:18084->8080/tcp",
        },
        "docker_socket": {
            "draft_only": True,
            "mounted_services": [s for s, entries in socket_mounts.items() if entries],
        },
        "logs": logs,
        "source": "GitHub Actions four-services job; image and Compose evidence captured after health checks",
    }
    if args.source_commit:
        handoff["image_source_commit"] = args.source_commit
    if args.workflow_run_url:
        handoff["workflow_run"] = {"url": args.workflow_run_url}
    if args.four_services_job_url:
        handoff["four_services_job"] = {"url": args.four_services_job_url}
    if args.artifact_id:
        handoff["evidence_artifact"] = {"id": int(args.artifact_id)}
    if args.e2e_result:
        e2e_path = safe_file(args.e2e_result, root)
        e2e = read_json(e2e_path)
        handoff["e2e"] = {
            "result_path": e2e_path.relative_to(root).as_posix(),
            "result_sha256": sha256(e2e_path),
            "job_id": e2e.get("job_id"),
            "trace_id": e2e.get("trace_id"),
            "status": e2e.get("status"),
            "exit_code": 0 if e2e.get("status") == "SUCCEEDED" else 1,
            "stages": [stage.get("name") for stage in e2e.get("stages", [])],
            "base_commit": e2e.get("base_commit"),
            "target_commit": e2e.get("target_commit"),
        }
    (root / "handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(handoff, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
