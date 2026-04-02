#!/usr/bin/env python3
"""Helpers for locating and terminating processes bound to TCP ports."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, Iterable, List, Set


def find_listening_pids(port: int) -> Set[int]:
    if sys.platform == "win32":
        return _find_listening_pids_windows(port)
    return _find_listening_pids_posix(port)


def kill_pid(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
        else:
            result = subprocess.run(
                ["kill", "-9", str(pid)],
                capture_output=True,
                text=True,
            )
        return result.returncode == 0
    except Exception:
        return False


def kill_ports(ports: Iterable[int]) -> Dict[int, Set[int]]:
    killed: Dict[int, Set[int]] = {}
    for port in ports:
        pids = find_listening_pids(port)
        killed_pids = {pid for pid in pids if kill_pid(pid)}
        killed[int(port)] = killed_pids
    return killed


def describe_port_listeners(ports: Iterable[int]) -> Dict[int, List[Dict[str, str | int]]]:
    descriptions: Dict[int, List[Dict[str, str | int]]] = {}
    for port in ports:
        port_num = int(port)
        listeners: List[Dict[str, str | int]] = []
        for pid in sorted(find_listening_pids([port_num][0])):
            listeners.append(
                {
                    "pid": pid,
                    "process_name": _process_name(pid),
                }
            )
        descriptions[port_num] = listeners
    return descriptions


def _find_listening_pids_windows(port: int) -> Set[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()

    pids: Set[int] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0] != "TCP":
            continue
        local_address = parts[1]
        state = parts[3]
        pid_text = parts[4]
        if state != "LISTENING":
            continue
        if _port_from_address(local_address) != port:
            continue
        try:
            pids.add(int(pid_text))
        except ValueError:
            continue
    return pids


def _find_listening_pids_posix(port: int) -> Set[int]:
    commands = [
        ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        ["fuser", "-n", "tcp", str(port)],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True)
        except FileNotFoundError:
            continue
        if result.returncode not in {0, 1}:
            continue
        output = result.stdout.strip() or result.stderr.strip()
        if not output:
            continue
        pids: Set[int] = set()
        for token in output.replace("\n", " ").split():
            try:
                pids.add(int(token))
            except ValueError:
                continue
        if pids:
            return pids
    return set()


def _port_from_address(address: str) -> int | None:
    try:
        return int(address.rsplit(":", 1)[-1])
    except ValueError:
        return None


def _process_name(pid: int) -> str:
    if pid <= 0:
        return "unknown"
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                line = result.stdout.strip().splitlines()[0].strip()
                if line and line != "INFO: No tasks are running which match the specified criteria.":
                    return line.split('","')[0].strip('"')
        except Exception:
            return "unknown"
        return "unknown"
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        return "unknown"
    return "unknown"
