#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

# Load .env
source "$ROOT_DIR/.env"

docker_services_running() {
    docker compose ps --services --filter status=running 2>/dev/null | grep -q neo4j
}

start_docker_services() {
    echo "Starting Docker services (neo4j, postgres)..."
    docker compose -f "$ROOT_DIR/docker-compose.yml" -f "$ROOT_DIR/docker-compose.dev.yml" up neo4j postgres -d
    echo "Waiting for services to be healthy..."
    for i in {1..30}; do
        sleep 2
        if docker_services_running; then
            echo "Docker services ready."
            return 0
        fi
    done
    echo "WARNING: Docker services may not be fully ready."
}

stop_docker_services() {
    echo "Stopping Docker services..."
    docker compose -f "$ROOT_DIR/docker-compose.yml" -f "$ROOT_DIR/docker-compose.dev.yml" stop neo4j postgres
}

cleanup() {
    echo ""
    echo "Stopping..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    stop_docker_services
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting ResearchSquid..."

# Start Docker services if not running and docker is available
if command -v docker &> /dev/null && ! docker_services_running; then
    start_docker_services
fi

# Start backend
echo "Starting backend on :8000..."
cd "$ROOT_DIR/backend"
"$VENV_PYTHON" run_server.py &
BACKEND_PID=$!

sleep 2

# Start frontend
echo "Starting frontend on :3000..."
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "ResearchSquid running:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Health:   http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop"

wait
