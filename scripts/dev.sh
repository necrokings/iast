#!/bin/bash
# ============================================================================
# Terminal Development Runner
# Starts all services: Valkey, API, Web, Gateway
# ============================================================================

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Check if running in app-only mode (no gateway)
APP_ONLY=false
if [ "$1" = "app" ]; then
    APP_ONLY=true
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[dev]${NC} $1"; }
success() { echo -e "${GREEN}[dev]${NC} $1"; }
warn() { echo -e "${YELLOW}[dev]${NC} $1"; }
error() { echo -e "${RED}[dev]${NC} $1"; }

cleanup() {
    log "Shutting down services..."

    # Kill background processes
    if [ -n "$API_PID" ]; then
        kill $API_PID 2>/dev/null || true
    fi
    if [ -n "$WEB_PID" ]; then
        kill $WEB_PID 2>/dev/null || true
    fi
    if [ -n "$GATEWAY_PID" ] && [ "$APP_ONLY" = false ]; then
        kill $GATEWAY_PID 2>/dev/null || true
    fi

    # Stop docker
    docker compose -f infra/docker-compose.dev.yml down 2>/dev/null || true

    success "All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ----------------------------------------------------------------------------
# Start Valkey
# ----------------------------------------------------------------------------
log "Starting Valkey..."
docker compose -f infra/docker-compose.dev.yml up -d

# Wait for Valkey to be ready
log "Waiting for Valkey to be ready..."
until docker exec terminal-valkey valkey-cli ping 2>/dev/null | grep -q PONG; do
    sleep 0.5
done
success "Valkey is ready"

# ----------------------------------------------------------------------------
# Setup DynamoDB
# ----------------------------------------------------------------------------
log "Setting up DynamoDB..."
./scripts/setup-dynamodb.sh
success "DynamoDB setup complete"

# ----------------------------------------------------------------------------
# Start API
# ----------------------------------------------------------------------------
log "Starting API server..."
pnpm --filter @terminal/api dev &
API_PID=$!
sleep 2
success "API server started (PID: $API_PID)"

# ----------------------------------------------------------------------------
# Start Web
# ----------------------------------------------------------------------------
log "Starting Web frontend..."
pnpm --filter @terminal/web dev &
WEB_PID=$!
sleep 2
success "Web frontend started (PID: $WEB_PID)"

# ----------------------------------------------------------------------------
# Start Gateway (unless app-only mode)
# ----------------------------------------------------------------------------
if [ "$APP_ONLY" = false ]; then
    log "Starting Python gateway..."
    cd gateway
    uv run gateway &
    GATEWAY_PID=$!
    cd "$ROOT_DIR"
    success "Gateway started (PID: $GATEWAY_PID)"
fi

# ----------------------------------------------------------------------------
# Ready
# ----------------------------------------------------------------------------
echo ""
success "=========================================="
if [ "$APP_ONLY" = true ]; then
    success "  App services running (no gateway)!"
else
    success "  All services running!"
fi
success "=========================================="
echo ""
log "  Web:     http://localhost:5173"
log "  API:     http://localhost:3000"
log "  Valkey:  localhost:6379"
echo ""
log "Press Ctrl+C to stop all services"
echo ""

# Wait for all background processes
wait
