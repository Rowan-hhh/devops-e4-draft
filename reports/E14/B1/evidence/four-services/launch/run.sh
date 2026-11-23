#!/usr/bin/env bash
set -uo pipefail

cd /root/devops-students/241880360/draft

EVIDENCE_DIR=$1
PROJECT=$2
LAUNCH_DIR=$3

IMAGE="course-e11e12:241880360"
EXPECTED_IMAGE_ID="sha256:a9c65eab021262a76f2025a42a9526aa5d793ee4f2224696bbb6419d0daf80e0"
REQUEST="data/integration-sample/e12.json"
COMPOSE_FILE="labs/e13e14/compose.yaml"

export E14_ROOT="$PWD"
export E14_IMAGE="$IMAGE"

COMPOSE=(
  docker compose
  -f "$COMPOSE_FILE"
  -p "$PROJECT"
)

mkdir -p "$EVIDENCE_DIR/logs"

{
  printf 'started_at_utc='
  date -u +%Y-%m-%dT%H:%M:%SZ
  printf 'branch='
  git branch --show-current
  printf 'tool_commit='
  git rev-parse HEAD
  printf 'locked_candidate=ff92071368bbd40083e3014dd09adc40a5c24dbb\n'
  printf 'compose_project=%s\n' "$PROJECT"
  printf 'image=%s\n' "$IMAGE"
  printf 'expected_image_id=%s\n' "$EXPECTED_IMAGE_ID"
  printf 'request=%s\n' "$REQUEST"
} > "$EVIDENCE_DIR/context.txt"

cp "$COMPOSE_FILE" "$EVIDENCE_DIR/compose.yaml"

"${COMPOSE[@]}" config --format json \
  > "$EVIDENCE_DIR/compose-config.json" \
  2> "$EVIDENCE_DIR/compose-config.stderr"

docker image inspect "$IMAGE" \
  > "$EVIDENCE_DIR/image-inspect.json"

ACTUAL_IMAGE_ID=$(
  docker image inspect "$IMAGE" --format '{{.Id}}'
)

printf '%s\n' "$ACTUAL_IMAGE_ID" \
  > "$EVIDENCE_DIR/image-id.txt"

START_EXIT=0
ORCHESTRATE_EXIT=99
SCAN_EVIDENCE_EXIT=99
SCAN_LOG_EXIT=99
DOWN_EXIT=99

if test "$ACTUAL_IMAGE_ID" != "$EXPECTED_IMAGE_ID"; then
  echo "FAIL: teaching image identity changed" \
    > "$EVIDENCE_DIR/failure.txt"
  START_EXIT=10
else
  "${COMPOSE[@]}" up -d --wait \
    > "$EVIDENCE_DIR/compose-up.log" 2>&1 ||
    START_EXIT=$?
fi

printf '%s\n' "$START_EXIT" \
  > "$EVIDENCE_DIR/compose-up-exit-code.txt"

"${COMPOSE[@]}" ps --format json \
  > "$EVIDENCE_DIR/health.json" 2>&1 || true

for role in buildchecker echecker draft mdfixer
do
  CID=$("${COMPOSE[@]}" ps -q "$role" 2>/dev/null || true)

  if test -n "$CID"; then
    docker inspect "$CID" \
      > "$EVIDENCE_DIR/mounts-${role}.json"
  fi
done

if test "$START_EXIT" -eq 0; then
  python3 labs/e13e14/orchestrate.py \
    --request "$REQUEST" \
    --out "$EVIDENCE_DIR/run" \
    > "$EVIDENCE_DIR/orchestrate-stdout.json" \
    2> "$EVIDENCE_DIR/orchestrate-stderr.log"

  ORCHESTRATE_EXIT=$?
fi

printf '%s\n' "$ORCHESTRATE_EXIT" \
  > "$EVIDENCE_DIR/orchestrate-exit-code.txt"

"${COMPOSE[@]}" logs --no-color \
  > "$EVIDENCE_DIR/four-services.log" 2>&1 || true

for role in buildchecker echecker draft mdfixer
do
  "${COMPOSE[@]}" logs --no-color "$role" \
    > "$EVIDENCE_DIR/logs/${role}.log" 2>&1 || true
done

if test -d "$EVIDENCE_DIR/run"; then
  python3 labs/e13e14/scan_runtime_logs.py \
    "$EVIDENCE_DIR/run" \
    > "$EVIDENCE_DIR/scan-evidence.log" 2>&1
  SCAN_EVIDENCE_EXIT=$?
fi

python3 labs/e13e14/scan_runtime_logs.py \
  "$EVIDENCE_DIR/four-services.log" \
  > "$EVIDENCE_DIR/scan-services.log" 2>&1
SCAN_LOG_EXIT=$?

printf '%s\n' "$SCAN_EVIDENCE_EXIT" \
  > "$EVIDENCE_DIR/scan-evidence-exit-code.txt"

printf '%s\n' "$SCAN_LOG_EXIT" \
  > "$EVIDENCE_DIR/scan-services-exit-code.txt"

"${COMPOSE[@]}" down \
  > "$EVIDENCE_DIR/compose-down.log" 2>&1
DOWN_EXIT=$?

printf '%s\n' "$DOWN_EXIT" \
  > "$EVIDENCE_DIR/compose-down-exit-code.txt"

"${COMPOSE[@]}" ps -q \
  > "$EVIDENCE_DIR/remaining-project-containers.txt" 2>&1 || true

docker ps --format \
  '{{.ID}}	{{.Image}}	{{.Names}}	{{.Status}}' \
  > "$EVIDENCE_DIR/docker-after.txt"

{
  printf 'finished_at_utc='
  date -u +%Y-%m-%dT%H:%M:%SZ
  printf 'compose_up_exit=%s\n' "$START_EXIT"
  printf 'orchestrate_exit=%s\n' "$ORCHESTRATE_EXIT"
  printf 'scan_evidence_exit=%s\n' "$SCAN_EVIDENCE_EXIT"
  printf 'scan_services_exit=%s\n' "$SCAN_LOG_EXIT"
  printf 'compose_down_exit=%s\n' "$DOWN_EXIT"
} > "$EVIDENCE_DIR/execution-summary.txt"

if test "$START_EXIT" -ne 0; then
  exit "$START_EXIT"
fi

if test "$ORCHESTRATE_EXIT" -ne 0; then
  exit "$ORCHESTRATE_EXIT"
fi

if test "$SCAN_EVIDENCE_EXIT" -ne 0; then
  exit "$SCAN_EVIDENCE_EXIT"
fi

if test "$SCAN_LOG_EXIT" -ne 0; then
  exit "$SCAN_LOG_EXIT"
fi

if test "$DOWN_EXIT" -ne 0; then
  exit "$DOWN_EXIT"
fi

test ! -s "$EVIDENCE_DIR/remaining-project-containers.txt"
