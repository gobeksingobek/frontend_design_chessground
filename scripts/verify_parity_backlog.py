#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / ".github" / "backlog-status.json"
CONTRACT_PATTERN = re.compile(r"web/scripts/check-[a-z0-9-]+-contract\.mjs$")
TASK_ID_PATTERN = re.compile(r"\b[A-Z]{3}-\d{2}\b")


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def run(command: str) -> None:
    print(f"\n$ {command}")
    env = os.environ.copy()
    pythonpath_entries = [str(ROOT)]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    completed = subprocess.run(command, shell=True, cwd=ROOT, env=env)
    if completed.returncode != 0:
        fail(f"Command failed: {command}")


def extract_task_ids(checklist_path: Path) -> set[str]:
    text = checklist_path.read_text(encoding="utf-8")
    ids = set(TASK_ID_PATTERN.findall(text))
    return ids


def main() -> None:
    if not STATUS_FILE.exists():
        fail(f"Missing status file: {STATUS_FILE}")

    payload = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        fail("status file must contain a non-empty 'tasks' list")

    checklist_path = ROOT / payload.get("source_checklist", "docs/web_desktop_parity_checklist.md")
    if not checklist_path.exists():
        fail(f"Checklist file not found: {checklist_path}")

    checklist_task_ids = extract_task_ids(checklist_path)
    status_task_ids: set[str] = set()

    for task in tasks:
        task_id = task.get("id")
        status = task.get("status")
        if not task_id or not isinstance(task_id, str):
            fail("Every task must include string id")
        if task_id in status_task_ids:
            fail(f"Duplicate task id in status file: {task_id}")
        status_task_ids.add(task_id)

        if status not in {"Open", "In progress", "Done"}:
            fail(f"{task_id}: invalid status {status!r}")

        endpoint_files = task.get("endpoint_contract_files") or []
        api_test_commands = task.get("api_test_commands") or []
        ui_test_commands = task.get("ui_test_commands") or []
        contract_check_commands = task.get("contract_check_commands") or []

        if not endpoint_files:
            fail(f"{task_id}: missing endpoint_contract_files evidence")
        if not api_test_commands:
            fail(f"{task_id}: missing api_test_commands evidence")
        if not ui_test_commands:
            fail(f"{task_id}: missing ui_test_commands evidence")
        if not contract_check_commands:
            fail(f"{task_id}: missing contract_check_commands evidence")

        for rel_path in endpoint_files:
            if not (ROOT / rel_path).exists():
                fail(f"{task_id}: endpoint contract file does not exist: {rel_path}")

        for command in api_test_commands + ui_test_commands + contract_check_commands:
            if not isinstance(command, str) or not command.strip():
                fail(f"{task_id}: invalid command in evidence list")

        for command in contract_check_commands:
            script_match = re.search(r"web/scripts/check-[a-z0-9-]+-contract\.mjs", command)
            if not script_match:
                fail(f"{task_id}: contract check command must reference web/scripts/check-*-contract.mjs")
            script_rel = script_match.group(0)
            if not CONTRACT_PATTERN.match(script_rel):
                fail(f"{task_id}: invalid contract script path {script_rel}")
            if not (ROOT / script_rel).exists():
                fail(f"{task_id}: contract script does not exist: {script_rel}")

    missing = checklist_task_ids - status_task_ids
    extra = status_task_ids - checklist_task_ids
    if missing:
        fail(f"Status file missing checklist tasks: {', '.join(sorted(missing))}")
    if extra:
        fail(f"Status file has unknown tasks not in checklist: {', '.join(sorted(extra))}")

    all_contract_commands = sorted({cmd for t in tasks for cmd in t["contract_check_commands"]})
    print("\nRunning all mapped contract checks...")
    for command in all_contract_commands:
        run(command)

    done_tasks = [t for t in tasks if t["status"] == "Done"]
    if done_tasks:
        print("\nDone tasks detected; running evidence gates and UI regression cutover prerequisite...")
        for task in done_tasks:
            for command in task["api_test_commands"] + task["ui_test_commands"]:
                run(command)
        run("npm --prefix web run test:ui-regression")
    else:
        print("\nNo Done tasks detected; skipping heavy API/UI evidence execution.")

    print("\nBacklog evidence verification passed.")


if __name__ == "__main__":
    main()
