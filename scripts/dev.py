#!/usr/bin/env python3
"""ResearchSquid dev starter - cross-platform (Windows/Mac/Linux)."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv

from port_utils import describe_port_listeners, kill_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local ResearchSquid dev stack.")
    parser.add_argument(
        "--kill-ports",
        nargs="*",
        type=int,
        default=None,
        help="Force-kill listeners on these ports before startup. Defaults to 3000 and 8000 when the flag is present without values.",
    )
    return parser.parse_args()


def run_cmd(cmd, check=True, capture=False):
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        if result.stderr:
            print(result.stderr)
        return None
    return result


def docker_services_running():
    result = run_cmd(
        "docker compose ps --services --filter status=running",
        check=False,
        capture=True,
    )
    if result and result.stdout:
        services = result.stdout.strip().split("\n")
        return "neo4j" in services and "postgres" in services
    return False


def start_docker_services():
    print("Starting Docker services (neo4j, postgres)...")
    root_dir = os.path.dirname(os.path.dirname(__file__))
    result = run_cmd(
        f'docker compose -f "{root_dir}/docker-compose.yml" -f "{root_dir}/docker-compose.dev.yml" up -d --remove-orphans neo4j postgres',
        check=False,
        capture=True,
    )
    if result is None or result.returncode != 0:
        print("WARNING: Could not start Docker services. Ensure Docker is running.")
        if result is not None:
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip())
        return False
    print("Waiting for services to be healthy...")
    for _ in range(30):
        time.sleep(2)
        if docker_services_running():
            print("Docker containers are running.")
            return True
    print("WARNING: Docker services may not be fully ready.")
    return True


def ensure_sandbox_image():
    print("Ensuring sandbox image is available...")
    root_dir = os.path.dirname(os.path.dirname(__file__))
    inspect = run_cmd(
        "docker image inspect squid-sandbox:latest",
        check=False,
        capture=True,
    )
    if inspect is not None and inspect.returncode == 0:
        print("Sandbox image is ready.")
        return True

    result = run_cmd(
        f'docker build -t squid-sandbox:latest -f "{root_dir}/backend/Dockerfile.sandbox" "{root_dir}/backend"',
        check=False,
        capture=True,
    )
    if result is None or result.returncode != 0:
        print("WARNING: Could not build sandbox image. Experiments may fail.")
        if result is not None:
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip())
        return False

    print("Sandbox image built.")
    return True


def stop_docker_services():
    print("Stopping Docker services...")
    root_dir = os.path.dirname(os.path.dirname(__file__))
    run_cmd(
        f'docker compose -f "{root_dir}/docker-compose.yml" -f "{root_dir}/docker-compose.dev.yml" stop neo4j postgres',
        check=False,
    )


def maybe_kill_requested_ports(ports):
    if ports is None:
        return
    target_ports = ports or [3000, 8000]
    print(f"Force-clearing listening processes on ports: {', '.join(str(port) for port in target_ports)}")
    results = kill_ports(target_ports)
    for port in target_ports:
        killed = results.get(port, set())
        if killed:
            print(f"  Port {port}: terminated PIDs {', '.join(str(pid) for pid in sorted(killed))}")
        else:
            print(f"  Port {port}: no listeners terminated")


def ensure_python_modules(venv_python):
    checks = [
        ("openai", "Real LLM calls"),
        ("neo4j", "Neo4j connectivity"),
        ("fastapi", "Backend server"),
    ]
    missing = []
    for module_name, label in checks:
        result = subprocess.run(
            [venv_python, "-c", f"import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('{module_name}') else 1)"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            missing.append((module_name, label))
    if not missing:
        return
    print("ERROR: The virtual environment is missing required Python packages:")
    for module_name, label in missing:
        print(f"  - {module_name} ({label})")
    print()
    print("Run this once to sync the environment:")
    print("  python scripts\\setup.py" if sys.platform == "win32" else "  python scripts/setup.py")
    print()
    sys.exit(1)


def neo4j_ready(venv_python, env):
    probe = [
        venv_python,
        "-c",
        (
            "import os; "
            "from neo4j import GraphDatabase; "
            "driver = GraphDatabase.driver("
            "os.getenv('NEO4J_URI', 'bolt://localhost:7687'), "
            "auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', 'researchsquid'))"
            "); "
            "driver.verify_connectivity(); "
            "driver.close()"
        ),
    ]
    result = subprocess.run(probe, env=env, capture_output=True, text=True)
    return result.returncode == 0


def _local_docker_env_mismatches(env):
    mismatches = []
    neo4j_uri = env.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = env.get("NEO4J_USER", "neo4j")
    neo4j_password = env.get("NEO4J_PASSWORD", "researchsquid")
    database_url = env.get("DATABASE_URL", "postgresql+asyncpg://squid:researchsquid@localhost:5432/squid")

    if neo4j_uri in {"bolt://localhost:7687", "bolt://127.0.0.1:7687"}:
        if neo4j_user != "neo4j" or neo4j_password != "researchsquid":
            mismatches.append(
                "NEO4J_* in .env does not match the local Docker Neo4j credentials "
                "(expected neo4j / researchsquid for bolt://localhost:7687)."
            )

    normalized_db = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    expected_db = "postgresql+asyncpg://squid:researchsquid@localhost:5432/squid"
    expected_db_loopback = "postgresql+asyncpg://squid:researchsquid@127.0.0.1:5432/squid"
    if "@localhost:5432/" in normalized_db or "@127.0.0.1:5432/" in normalized_db:
        if normalized_db not in {expected_db, expected_db_loopback}:
            mismatches.append(
                "DATABASE_URL in .env does not match the local Docker Postgres credentials "
                "(expected squid / researchsquid on localhost:5432, database squid)."
            )

    return mismatches


def wait_for_neo4j(venv_python, env):
    print("Waiting for Neo4j Bolt readiness...")
    for _ in range(45):
        if neo4j_ready(venv_python, env):
            print("Neo4j Bolt is ready.")
            return True
        time.sleep(2)
    print("WARNING: Neo4j Bolt did not become ready in time.")
    return False


def backend_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def wait_for_backend(url: str, timeout_seconds: int = 90) -> bool:
    print(f"Waiting for backend readiness at {url}...")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if backend_ready(url):
            print("Backend is ready.")
            return True
        time.sleep(1)
    print("WARNING: Backend did not become ready before frontend startup.")
    return False


def ensure_neo4j_available(venv_python, env, *, attempted_docker_start: bool) -> None:
    if neo4j_ready(venv_python, env):
        print("Using existing Neo4j instance.")
        return
    print("ERROR: Neo4j is not reachable at the configured NEO4J_URI.")
    conflict_ports = _detect_institute_port_conflicts(env)
    if conflict_ports:
        print("Conflicting local listeners detected:")
        for port, listeners in conflict_ports.items():
            for listener in listeners:
                print(f"  Port {port}: PID {listener['pid']} ({listener['process_name']})")
        print("If those are stale listeners, clear them with:")
        print("  python scripts\\kill_ports.py 7687 5432 3000 8000" if sys.platform == "win32" else "  python scripts/kill_ports.py 7687 5432 3000 8000")
    if attempted_docker_start:
        print("Docker startup also failed, so the coordinator cannot boot.")
        print("Start Docker Desktop or run a local Neo4j instance, then retry.")
    else:
        print("Start Docker services or point NEO4J_URI to a running local Neo4j instance, then retry.")
    print(f"Current NEO4J_URI: {env.get('NEO4J_URI', 'bolt://localhost:7687')}")
    sys.exit(1)


def _detect_institute_port_conflicts(env):
    ports = {3000, 8000}
    neo4j_uri = env.get("NEO4J_URI", "bolt://localhost:7687")
    database_url = env.get("DATABASE_URL", "postgresql://squid:researchsquid@localhost:5432/squid")
    if "localhost:" in neo4j_uri or "127.0.0.1:" in neo4j_uri:
        try:
            ports.add(int(neo4j_uri.rsplit(":", 1)[-1]))
        except ValueError:
            pass
    if "@localhost:" in database_url or "@127.0.0.1:" in database_url:
        try:
            ports.add(int(database_url.rsplit(":", 1)[-1].split("/", 1)[0]))
        except ValueError:
            pass
    conflicts = describe_port_listeners(sorted(ports))
    return {port: listeners for port, listeners in conflicts.items() if listeners}


def main():
    args = parse_args()
    print("Starting ResearchSquid...")

    # Determine venv python path
    venv_dir = os.path.join(os.path.dirname(__file__), "..", ".venv")
    root_dir = os.path.dirname(venv_dir)
    load_dotenv(os.path.join(root_dir, ".env"))
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        npm_cmd = "npm.cmd"
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        npm_cmd = "npm"

    ensure_python_modules(venv_python)

    maybe_kill_requested_ports(args.kill_ports)

    env = os.environ.copy()

    # Start Docker services if not running
    docker_available = run_cmd("docker --version", check=False) is not None
    attempted_docker_start = False
    services_running = docker_services_running() if docker_available else False
    if docker_available and not services_running:
        attempted_docker_start = True
        started = start_docker_services()
        services_running = docker_services_running() if started else False
    if docker_available and services_running:
        mismatches = _local_docker_env_mismatches(env)
        if mismatches:
            print("ERROR: Local Docker services are running, but your root .env uses different local DB credentials.")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
            print("Update the repo-root .env or use external service URLs instead of localhost defaults.")
            sys.exit(1)
        wait_for_neo4j(venv_python, env)
        ensure_sandbox_image()
    else:
        ensure_neo4j_available(venv_python, env, attempted_docker_start=attempted_docker_start)

    procs = []

    def cleanup(sig=None, frame=None):
        print("\nStopping...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        stop_docker_services()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Start backend
    print("Starting backend on :8000...")
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    backend = subprocess.Popen(
        [
            venv_python,
            "run_server.py",
        ],
        env=env,
        cwd=backend_dir,
    )
    procs.append(backend)

    wait_for_backend("http://127.0.0.1:8000/health")

    # Start frontend
    print("Starting frontend on :3000...")
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    frontend = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=os.path.abspath(frontend_dir),
    )
    procs.append(frontend)

    print()
    print("ResearchSquid running:")
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
