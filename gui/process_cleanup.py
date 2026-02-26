from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time


def terminate_child_processes_for_current_app(
    parent_pid: int | None = None,
    timeout_seconds: float = 1.5,
) -> dict:
    pid = int(parent_pid or os.getpid())
    errors: list[str] = []
    scanned = 0
    terminated = 0

    children = _list_direct_children(pid, errors)
    scanned = len(children)
    for child in children:
        name = str(child.get("name") or "").lower()
        child_pid = int(child.get("pid") or 0)
        if child_pid <= 0:
            continue
        if not _is_target_child_name(name):
            continue
        if _terminate_process_tree(child_pid, timeout_seconds, errors):
            terminated += 1

    return {
        "parent_pid": pid,
        "scanned": scanned,
        "terminated": terminated,
        "errors": errors,
    }


def _is_target_child_name(name: str) -> bool:
    return (
        "stockfish" in name
        or name in {"python.exe", "pythonw.exe", "python", "python3"}
    )


def _list_direct_children(parent_pid: int, errors: list[str]) -> list[dict]:
    if sys.platform.startswith("win"):
        return _list_direct_children_windows(parent_pid, errors)
    return _list_direct_children_posix(parent_pid, errors)


def _list_direct_children_windows(parent_pid: int, errors: list[str]) -> list[dict]:
    ps_script = (
        "$pidIn = " + str(parent_pid) + "; "
        "Get-CimInstance Win32_Process -Filter \"ParentProcessId=$pidIn\" | "
        "Select-Object ProcessId, Name, ParentProcessId | "
        "ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                ps_script,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        errors.append(f"child-list windows failed: {exc}")
        return []

    payload = (result.stdout or "").strip()
    if not payload:
        return []
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        errors.append(f"child-list parse failed: {exc}")
        return []

    rows = parsed if isinstance(parsed, list) else [parsed]
    children: list[dict] = []
    for row in rows:
        try:
            children.append(
                {
                    "pid": int(row.get("ProcessId") or 0),
                    "ppid": int(row.get("ParentProcessId") or 0),
                    "name": str(row.get("Name") or ""),
                }
            )
        except Exception:
            continue
    return children


def _list_direct_children_posix(parent_pid: int, errors: list[str]) -> list[dict]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,comm="],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        errors.append(f"child-list posix failed: {exc}")
        return []

    children: list[dict] = []
    for line in (result.stdout or "").splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        if ppid != parent_pid:
            continue
        children.append({"pid": pid, "ppid": ppid, "name": parts[2]})
    return children


def _terminate_process_tree(pid: int, timeout_seconds: float, errors: list[str]) -> bool:
    if sys.platform.startswith("win"):
        return _terminate_process_tree_windows(pid, timeout_seconds, errors)
    return _terminate_process_tree_posix(pid, timeout_seconds, errors)


def _terminate_process_tree_windows(
    pid: int,
    timeout_seconds: float,
    errors: list[str],
) -> bool:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        errors.append(f"taskkill soft failed for {pid}: {exc}")

    end = time.time() + max(0.2, timeout_seconds)
    while time.time() < end:
        if not _is_process_running_windows(pid):
            return True
        time.sleep(0.05)

    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid), "/T"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        errors.append(f"taskkill force failed for {pid}: {exc}")
        return False

    return not _is_process_running_windows(pid)


def _is_process_running_windows(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return False
    output = (result.stdout or "").lower()
    return str(pid) in output and "no tasks are running" not in output


def _terminate_process_tree_posix(
    pid: int,
    timeout_seconds: float,
    errors: list[str],
) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except Exception as exc:
        errors.append(f"sigterm failed for {pid}: {exc}")

    end = time.time() + max(0.2, timeout_seconds)
    while time.time() < end:
        try:
            os.kill(pid, 0)
            time.sleep(0.05)
        except ProcessLookupError:
            return True
        except Exception:
            return True

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except Exception as exc:
        errors.append(f"sigkill failed for {pid}: {exc}")
        return False

    return True
