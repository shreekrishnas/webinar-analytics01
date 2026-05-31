"""
Sets up a Windows Task Scheduler task to run the Job Agent every day at 4:30 PM.
Run this script ONCE (as Administrator) after setting up the .env file.

Usage:
    python setup_scheduler.py           # create / update task
    python setup_scheduler.py --remove  # delete the task
    python setup_scheduler.py --run-now # trigger it immediately for a test
"""
import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME   = "JobAgentDailyRun"
RUN_TIME    = "16:30"   # 4:30 PM (24-hour format)

AGENT_DIR   = Path(__file__).parent.resolve()
PYTHON_EXE  = Path(sys.executable).resolve()
MAIN_SCRIPT = AGENT_DIR / "main.py"
LOG_FILE    = AGENT_DIR / "logs" / "scheduler.log"
BAT_FILE    = AGENT_DIR / "run_job_agent.bat"


def _write_bat():
    """Create the .bat launcher that Task Scheduler will invoke."""
    content = (
        f'@echo off\r\n'
        f'cd /d "{AGENT_DIR}"\r\n'
        f'"{PYTHON_EXE}" "{MAIN_SCRIPT}" >> "{LOG_FILE}" 2>&1\r\n'
    )
    BAT_FILE.write_text(content, encoding="utf-8")
    print(f"  Created launcher : {BAT_FILE}")


def create_task():
    _write_bat()

    # Remove stale task silently
    subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True,
    )

    result = subprocess.run(
        [
            "schtasks", "/create",
            "/tn",  TASK_NAME,
            "/tr",  str(BAT_FILE),
            "/sc",  "DAILY",
            "/st",  RUN_TIME,
            "/rl",  "HIGHEST",
            "/f",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print()
        print("  Task Scheduler configured successfully!")
        print(f"  Task name : {TASK_NAME}")
        print(f"  Runs      : every day at {RUN_TIME} (4:30 PM)")
        print(f"  Script    : {MAIN_SCRIPT}")
        print(f"  Logs      : {AGENT_DIR / 'logs'}")
        print(f"  Excel out : {AGENT_DIR / 'output'}")
        print()
        print("  To check status  : schtasks /query /tn JobAgentDailyRun /fo LIST")
        print("  To trigger now   : python setup_scheduler.py --run-now")
    else:
        print()
        print("  ERROR: Could not create scheduled task.")
        print(result.stderr)
        print()
        print("  Make sure you are running this script as Administrator.")
        print("  Right-click 'Command Prompt' or 'PowerShell' -> 'Run as administrator'")
        print("  Then re-run:  python setup_scheduler.py")


def remove_task():
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  Removed task: {TASK_NAME}")
    else:
        print(f"  Task not found or could not be removed: {result.stderr.strip()}")


def run_now():
    result = subprocess.run(
        ["schtasks", "/run", "/tn", TASK_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  Task triggered. Check {AGENT_DIR / 'output'} and {LOG_FILE} for results.")
    else:
        print(f"  Could not trigger task: {result.stderr.strip()}")
        print("  Run manually: python main.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove",  action="store_true", help="Delete the scheduled task")
    parser.add_argument("--run-now", action="store_true", help="Trigger the task immediately")
    args = parser.parse_args()

    print()
    if args.remove:
        remove_task()
    elif args.run_now:
        run_now()
    else:
        create_task()
    print()
