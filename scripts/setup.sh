#!/bin/bash
# ResearchSquid — one-command local dev setup
set -e

echo "=== ResearchSquid Dev Setup ==="

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3.12+ required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 18+ required"; exit 1; }

# Create virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install
source .venv/bin/activate
pip install -e backend
npm install --prefix frontend

# Copy .env if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env — fill in your API keys"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Start everything:"
echo "  python scripts/dev.py"
echo ""
echo "Or individually:"
echo "  Backend:  cd backend && python run_server.py"
echo "  Frontend: cd frontend && npm run dev"
