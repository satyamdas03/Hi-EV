"""One-command demo of Hi-EV Phase 2 capabilities.

Usage:
    EV_RUN_INTEGRATION=1 python scripts/seed_demo.py
    python scripts/demo_phase2.py
"""

import os
import subprocess
import sys
from pathlib import Path


def run_ev(args: list[str], description: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"DEMO: {description}")
    print(f"Command: ev {' '.join(args)}")
    print("=" * 60)
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "ev.cli.main", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"(exit code {result.returncode})", file=sys.stderr)


def main() -> None:
    run_ev(["status", "RoboCAD"], "Rich project status")
    run_ev(["brief"], "Cross-project morning brief")
    run_ev(
        ["research", "what is model predictive control for humanoid robots"],
        "Web research with citations",
    )
    run_ev(
        ["work", "on", "refactor gait controller into a separate module", "--project", "RoboCAD"],
        "Spawn Claude Code with context (Tier 1)",
    )
    run_ev(["draft", "commit", "--project", "RoboCAD"], "Draft commit message (Tier 1)")
    run_ev(["calendar", "prep", "09:00"], "Pre-meeting/deadline prep packet")


if __name__ == "__main__":
    main()
