#!/bin/bash
# ResearchSquid — start backend + frontend together
set -e

echo "🦑 Starting ResearchSquid..."

# Kill background processes on exit
trap 'kill $(jobs -p) 2>/dev/null; echo "Stopped."' EXIT INT TERM

# Start backend
echo "Starting coordinator on :8000..."
SQUID_MOCK_LLM=${SQUID_MOCK_LLM:-true} \
uvicorn squid.coordinator.app:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend
sleep 2

# Start frontend
echo "Starting frontend on :3000..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "🦑 ResearchSquid running:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Health:   http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop"

# Wait for either process
wait
