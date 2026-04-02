#!/usr/bin/env python3
"""ResearchSquid dev starter — cross-platform (Windows/Mac/Linux)."""

import os
import signal
import subprocess
import sys
import time


def main():
    print("🦑 Starting ResearchSquid...")

    procs = []

    def cleanup(sig=None, frame=None):
        print("\nStopping...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    env = os.environ.copy()
    env["SQUID_MOCK_LLM"] = env.get("SQUID_MOCK_LLM", "true")

    # Start backend
    print("Starting coordinator on :8000...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "squid.coordinator.app:app", "--reload", "--port", "8000"],
        env=env,
    )
    procs.append(backend)

    # Wait a bit for backend
    time.sleep(2)

    # Start frontend
    print("Starting frontend on :3000...")
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    frontend = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=os.path.abspath(frontend_dir),
    )
    procs.append(frontend)

    print()
    print("🦑 ResearchSquid running:")
    print("   Frontend: http://localhost:3000")
    print("   Backend:  http://localhost:8000")
    print("   Health:   http://localhost:8000/health")
    print()
    print("Press Ctrl+C to stop")

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
