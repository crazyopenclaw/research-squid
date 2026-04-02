#!/usr/bin/env python3
"""Force-kill listening processes on one or more TCP ports."""

from __future__ import annotations

import argparse
import sys

from port_utils import find_listening_pids, kill_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Terminate listening processes on the given TCP ports.",
    )
    parser.add_argument(
        "ports",
        nargs="+",
        type=int,
        help="TCP ports to clear, for example: 3000 8000",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_ports = [int(port) for port in args.ports]

    listeners = {port: find_listening_pids(port) for port in requested_ports}
    if not any(listeners.values()):
        print("No listening processes found on the requested ports.")
        return 0

    for port, pids in listeners.items():
        if pids:
            print(f"Port {port}: found PIDs {', '.join(str(pid) for pid in sorted(pids))}")

    killed = kill_ports(requested_ports)
    for port in requested_ports:
        port_kills = killed.get(port, set())
        if port_kills:
            print(f"Port {port}: terminated PIDs {', '.join(str(pid) for pid in sorted(port_kills))}")
        elif listeners.get(port):
            print(f"Port {port}: failed to terminate one or more listeners")

    return 0


if __name__ == "__main__":
    sys.exit(main())
