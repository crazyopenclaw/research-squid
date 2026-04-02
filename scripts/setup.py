#!/usr/bin/env python3
"""ResearchSquid setup — cross-platform (Windows/Mac/Linux)."""

import os
import shutil
import subprocess
import sys


def main():
    print("=== ResearchSquid Dev Setup ===\n")

    # Check Python
    if sys.version_info < (3, 11):
        print("ERROR: Python 3.11+ required")
        sys.exit(1)

    # Create venv if missing
    venv_dir = os.path.join(os.path.dirname(__file__), "..", ".venv")
    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)

    # Determine pip path
    if sys.platform == "win32":
        pip = os.path.join(venv_dir, "Scripts", "pip.exe")
        python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        pip = os.path.join(venv_dir, "bin", "pip")
        python = os.path.join(venv_dir, "bin", "python")

    # Install Python deps
    print("Installing Python dependencies...")
    subprocess.run([pip, "install", "-e", "."], check=True)

    # Install frontend deps
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    print("Installing frontend dependencies...")
    subprocess.run([npm_cmd, "install"], cwd=frontend_dir, check=True)

    # Copy .env if missing
    root_dir = os.path.join(os.path.dirname(__file__), "..")
    env_file = os.path.join(root_dir, ".env")
    env_example = os.path.join(root_dir, ".env.example")
    if not os.path.exists(env_file) and os.path.exists(env_example):
        shutil.copy(env_example, env_file)
        print("Created .env — fill in your API keys")

    print("\n=== Setup Complete ===\n")
    print("Start everything:")
    if sys.platform == "win32":
        print("  python scripts\\dev.py")
    else:
        print("  python scripts/dev.py")
    print()
    print("Or individually:")
    print("  Backend:  python -m uvicorn squid.coordinator.app:app --reload --port 8000")
    print("  Frontend: cd frontend && npm run dev")


if __name__ == "__main__":
    main()
