#!/usr/bin/env python3
"""ResearchSquid setup — cross-platform (Windows/Mac/Linux)."""

import os
import shutil
import subprocess
import sys


def main():
    print("=== ResearchSquid Dev Setup ===\n")

    # Check Python
    if sys.version_info < (3, 12):
        print("ERROR: Python 3.12+ required")
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

    # Install Python deps from the backend package
    root_dir = os.path.join(os.path.dirname(__file__), "..")
    backend_dir = os.path.join(root_dir, "backend")
    print("Installing Python dependencies...")
    subprocess.run([pip, "install", "-e", backend_dir], check=True)

    # Install frontend deps
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    print("Installing frontend dependencies...")
    subprocess.run([npm_cmd, "install"], cwd=frontend_dir, check=True)

    # Install OpenCode (agent workspace AI coding assistant)
    if not shutil.which("opencode"):
        print("Installing OpenCode...")
        try:
            subprocess.run(
                [npm_cmd, "install", "-g", "opencode-ai@latest"],
                check=True,
            )
            print("OpenCode installed successfully.")
        except Exception as e:
            print(f"WARNING: Could not install OpenCode automatically: {e}")
            print("Install manually: npm install -g opencode-ai@latest")
            print("(OpenCode is required for the agent workspace layer)")
    else:
        print("OpenCode already installed.")

    # Build sandbox image when Docker is available so experiments work on first run
    docker_available = False
    try:
        docker_available = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
        ).returncode == 0
    except OSError:
        docker_available = False

    if docker_available:
        print("Ensuring sandbox image exists...")
        subprocess.run(
            [
                "docker",
                "build",
                "-t",
                "squid-sandbox:latest",
                "-f",
                os.path.join(backend_dir, "Dockerfile.sandbox"),
                backend_dir,
            ],
            check=False,
        )

    # Copy .env if missing
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
    print("  Backend:  cd backend && python run_server.py")
    print("  Frontend: cd frontend && npm run dev")


if __name__ == "__main__":
    main()
