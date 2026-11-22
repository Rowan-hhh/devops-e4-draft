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
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--image-tag", required=True)
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
    for item in health:
        name = item.get("Service") or item.get("Name", "")
        for service in SERVICES:
            if service in name:
                health_by_service[service] = {
                    "name": name,
                    "state": item.get("State"),
                    "health": item.get("Health"),
                }
    if set(health_by_service) != set(SERVICES):
        raise SystemExit(f"missing health records: {sorted(set(SERVICES) - set(health_by_service))}")
    if any(item.get("health") not in ("healthy", "healthy (healthy)")
           for item in health_by_service.values()):
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
            "repo_digests": digests,
            "inspect": file_ref(root / "image-inspect.json", root),
            "tag_present": args.image_tag in tags,
            "repo_digest_present": bool(digests),
        },
        "health": health_by_service,
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
    (root / "handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(handoff, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
