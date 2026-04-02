"""Quick-start CLI runner for the Research Institute.

This is the convenience entrypoint for local CLI use:

    python run_cli.py "What mechanisms drive antibiotic resistance?"
    python run_cli.py "Your question" --sources paper.pdf another.pdf
    python run_cli.py "Your question" --agents 3 --budget 200 --iterations 3

The canonical implementation still lives in ``backend/src``. This wrapper keeps
the old one-command UX while using the repo-root virtual environment and env
file.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def _ensure_venv() -> None:
    """Re-launch under the repo virtualenv when needed."""
    venv_dir = ROOT / ".venv"
    if not venv_dir.exists():
        print("Error: .venv not found. Run 'python scripts/setup.py' first.")
        raise SystemExit(1)

    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    current_exe = Path(sys.executable).resolve()
    if current_exe == venv_python.resolve():
        return

    result = subprocess.run([str(venv_python), __file__, *sys.argv[1:]], cwd=str(ROOT))
    raise SystemExit(result.returncode)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Research Institute of Squids - quick research runner",
    )
    parser.add_argument("question", help="The research question to investigate.")
    parser.add_argument(
        "--sources",
        "-s",
        nargs="*",
        default=[],
        help="Source files (PDF, text) or URLs to ingest.",
    )
    parser.add_argument(
        "--agents",
        "-a",
        type=int,
        default=3,
        help="Number of squid agents (default: 3).",
    )
    parser.add_argument(
        "--budget",
        "-b",
        type=int,
        default=100,
        help="Max LLM calls allowed (default: 100).",
    )
    parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=3,
        help="Max research iterations (default: 3).",
    )
    return parser.parse_args()


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _service_targets():
    from src.config import settings

    neo4j = urlparse(settings.neo4j_uri)
    neo4j_host = neo4j.hostname or "localhost"
    neo4j_port = neo4j.port or 7687

    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    postgres = urlparse(db_url)
    pg_host = postgres.hostname or "localhost"
    pg_port = postgres.port or 5432

    return {
        "neo4j": (neo4j_host, neo4j_port),
        "postgres": (pg_host, pg_port),
    }


def _print_service_help() -> None:
    print()
    print("Local research services are not reachable.")
    print("Start the local databases first:")
    print("  python scripts\\dev.py" if sys.platform == "win32" else "  python scripts/dev.py")
    print()
    print("Or start only the databases:")
    print(
        "  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d neo4j postgres"
    )
    print()


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "--version"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except OSError:
        return False


def _neo4j_ready() -> bool:
    from neo4j import GraphDatabase
    from src.config import settings

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
        return True
    except Exception:
        return False
    finally:
        driver.close()


def _start_local_services() -> bool:
    print("Starting local Neo4j/Postgres services for CLI...")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            str(ROOT / "docker-compose.dev.yml"),
            "up",
            "-d",
            "neo4j",
            "postgres",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        return False

    deadline = time.time() + 90
    postgres_host, postgres_port = _service_targets()["postgres"]
    while time.time() < deadline:
        if _neo4j_ready() and _port_open(postgres_host, postgres_port):
            return True
        time.sleep(2)
    return False


def _ensure_sandbox_image() -> None:
    inspect = subprocess.run(
        ["docker", "image", "inspect", "squid-sandbox:latest"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if inspect.returncode == 0:
        return

    print("Building sandbox image for experiments...")
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "squid-sandbox:latest",
            "-f",
            str(BACKEND_ROOT / "Dockerfile.sandbox"),
            str(BACKEND_ROOT),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Warning: could not build sandbox image. Experiments may fail.")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        return
    print("Sandbox image ready.")


def _preflight_local_services() -> None:
    targets = _service_targets()
    missing = []
    for name, (host, port) in targets.items():
        if host in {"localhost", "127.0.0.1", "::1"} and not _port_open(host, port):
            missing.append((name, host, port))
    if not missing:
        if _docker_available():
            _ensure_sandbox_image()
        return

    if _docker_available():
        if _start_local_services():
            _ensure_sandbox_image()
            return

    print("Error: required local services are not running:")
    for name, host, port in missing:
        print(f"  - {name}: {host}:{port}")
    _print_service_help()
    raise SystemExit(1)


async def _async_main() -> None:
    args = parse_args()

    from src.api.service import ResearchService
    from src.cli.display import console, display_event, display_report
    from neo4j.exceptions import AuthError, ServiceUnavailable
    from sqlalchemy.exc import OperationalError

    service = ResearchService()
    service.event_bus.subscribe("*", display_event)

    try:
        console.print("\n[bold]Research Institute of Squids[/bold]")
        console.print(f"[dim]Question: {args.question}[/dim]")
        console.print(
            f"[dim]Agents: {args.agents} | Budget: {args.budget} | Iterations: {args.iterations}[/dim]"
        )
        if args.sources:
            console.print(f"[dim]Sources: {', '.join(args.sources)}[/dim]")
        console.print()

        _preflight_local_services()
        await service.initialize()
        result = await service.start_research(
            question=args.question,
            sources=args.sources,
            num_agents=args.agents,
            budget=args.budget,
            max_iterations=args.iterations,
        )

        for event in result.get("events", []):
            if event.get("type") == "final_report":
                display_report(event.get("content", "No report generated."))
    except AuthError:
        console.print("\n[red]Neo4j authentication failed.[/]")
        console.print("[dim]Check NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in the repo-root .env.[/]")
        raise SystemExit(1)
    except ServiceUnavailable:
        console.print("\n[red]Neo4j is not reachable.[/]")
        _print_service_help()
        raise SystemExit(1)
    except OperationalError:
        console.print("\n[red]Postgres is not reachable.[/]")
        _print_service_help()
        raise SystemExit(1)
    finally:
        await service.shutdown()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    _ensure_venv()
    main()
