#!/usr/bin/env bash
set -euo pipefail

# scripts/dev-session.sh
# Helper to start/stop/list per-session gateway containers for local development.
# Assumes: docker and docker compose available. Uses infra/docker-compose.dev.yml to start infra services (redis, dynamodb-local).

COMPOSE_FILE="infra/docker-compose.dev.yml"
GATEWAY_DIR="./gateway"
IMAGE_NAME="gateway:dev"

usage() {
  cat <<EOF
Usage: $0 <command> [session-id]

Commands:
  start <session-id>   Start a gateway container for the given session id
  stop <session-id>    Stop and remove a gateway container for the given session id
  status <session-id>  Show container status and published ports for the given session id
  list                 List all running gateway session containers

Examples:
  $0 start session-1
  $0 status session-1
  $0 stop session-1
EOF
}

ensure_infra() {
  if [[ -f "$COMPOSE_FILE" ]]; then
    echo "Bringing up infra services from $COMPOSE_FILE (redis, dynamodb-local)..."
    docker compose -f "$COMPOSE_FILE" up -d || true
  else
    echo "Warning: $COMPOSE_FILE not found. Please ensure Redis is running on localhost:6379."
  fi
}

build_image_if_missing() {
  if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    if [[ -d "$GATEWAY_DIR" ]]; then
      echo "Building $IMAGE_NAME from $GATEWAY_DIR..."
      docker build -t "$IMAGE_NAME" "$GATEWAY_DIR"
    else
      echo "Gateway directory $GATEWAY_DIR not found. Please build an image named $IMAGE_NAME manually."
    fi
  fi
}

start_session() {
  local SID="$1"
  if docker ps -a --format '{{.Names}}' | grep -q "^gateway-$SID$"; then
    echo "Container gateway-$SID already exists. Starting it..."
    docker start "gateway-$SID"
    docker ps --filter "name=gateway-$SID" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    return
  fi

    # Always build the local gateway image from source so code changes are included
    build_image_if_missing
    if [[ -d "$GATEWAY_DIR" ]]; then
      echo "Building (or rebuilding) $IMAGE_NAME from $GATEWAY_DIR..."
      docker build -t "$IMAGE_NAME" "$GATEWAY_DIR"
    fi

    echo "Starting gateway container gateway-$SID..."
  # Expose container ports to random host ports (-P). Use host.docker.internal for host services.
  docker run -d --name "gateway-$SID" \
    --label gateway.session="$SID" \
    -e SESSION_ID="$SID" \
    -e REDIS_URL="redis://host.docker.internal:6379" \
    -e VALKEY_HOST="host.docker.internal" \
    -e VALKEY_PORT="6379" \
    -e TN3270_HOST="host.docker.internal" \
    -e TN3270_PORT="3270" \
    -e DYNAMODB_ENDPOINT="http://host.docker.internal:8042" \
    -e METADATA_STORE="local" \
    -e IDLE_TIMEOUT_SECS="300" \
    -P "$IMAGE_NAME"

  echo "Started. Mapping of published ports:"
  docker port "gateway-$SID" || true
}

stop_session() {
  local SID="$1"
  if docker ps -a --format '{{.Names}}' | grep -q "^gateway-$SID$"; then
    echo "Stopping and removing gateway-$SID..."
    docker rm -f "gateway-$SID" || true
    echo "Removed gateway-$SID"
  else
    echo "No container named gateway-$SID found."
  fi
}

status_session() {
  local SID="$1"
  if docker ps -a --filter "name=gateway-$SID" --format '{{.Names}}' | grep -q .; then
    docker ps --filter "name=gateway-$SID" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
  else
    echo "No container named gateway-$SID found."
  fi
}

list_sessions() {
  docker ps --filter "label=gateway.session" --format 'table {{.Names}}\t{{.Status}}\t{{.Labels}}\t{{.Ports}}'
}

# Main
if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

COMMAND="$1"
SESSION_ID=""
if [[ $# -ge 2 ]]; then
  SESSION_ID="$2"
fi

case "$COMMAND" in
  start)
    if [[ -z "$SESSION_ID" ]]; then
      echo "start requires a session id"
      usage
      exit 1
    fi
    ensure_infra
    start_session "$SESSION_ID"
    ;;
  stop)
    if [[ -z "$SESSION_ID" ]]; then
      echo "stop requires a session id"
      usage
      exit 1
    fi
    stop_session "$SESSION_ID"
    ;;
  status)
    if [[ -z "$SESSION_ID" ]]; then
      echo "status requires a session id"
      usage
      exit 1
    fi
    status_session "$SESSION_ID"
    ;;
  list)
    list_sessions
    ;;
  *)
    usage
    exit 2
    ;;
esac
