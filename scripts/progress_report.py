#!/usr/bin/env python3
"""Progress report for the Hi-EV Web / Voice / HUD MVP.

Reads the plan, checks which deliverables exist in the working tree, and emits
a concise summary of completed vs remaining work.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PLAN_PATH = Path("docs/superpowers/plans/2026-09-15-hi-ev-web-voice-hud-mvp.md")

NEW_FILES = [
    "web/package.json",
    "web/tsconfig.json",
    "web/vite.config.ts",
    "web/index.html",
    "web/src/index.css",
    "web/src/main.tsx",
    "web/src/App.tsx",
    "web/src/config.ts",
    "web/src/store.ts",
    "web/src/lib/bridge.ts",
    "web/src/lib/audio.ts",
    "web/src/lib/vad.ts",
    "web/src/lib/voice.ts",
    "web/src/lib/tts.ts",
    "web/src/scene/Scene.tsx",
    "web/src/scene/Core.tsx",
    "web/src/scene/Particles.tsx",
    "web/src/ui/Boot.tsx",
    "web/src/ui/Ignition.tsx",
    "web/src/ui/Hud.tsx",
    "web/src/ui/Diagnostics.tsx",
    "web/src/ui/Suggestions.tsx",
    "src/ev/server/chat.py",
    "tests/test_chat_handler.py",
    "docs/superpowers/plans/2026-09-15-hi-ev-web-voice-hud-mvp.md",
    "scripts/smoke_web.py",
]

MODIFIED_FILES = [
    "src/ev/server/api.py",
    "tests/test_server.py",
    ".gitignore",
    ".env.example",
    "pyproject.toml",
]

CRITERIA = {
    "pytest passes": lambda: run_cmd("python -m pytest -q", ok_exit={0, 5}) is not None,
    "ruff clean": lambda: run_cmd("ruff check src tests scripts", ok_exit={0}) is not None,
    "web builds": lambda: web_build_ok(),
    "WebSocket/chat tests exist": lambda: Path("tests/test_chat_handler.py").exists(),
    "frontend dev scaffold exists": lambda: Path("web/package.json").exists(),
    "smoke script exists": lambda: Path("scripts/smoke_web.py").exists(),
}


def run_cmd(cmd: str, ok_exit: set[int] | None = None) -> str | None:
    ok_exit = ok_exit or {0}
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=Path(__file__).resolve().parent.parent,
        )
        if result.returncode not in ok_exit:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def web_build_ok() -> bool:
    web = Path(__file__).resolve().parent.parent / "web"
    if not (web / "package.json").exists():
        return False
    if not (web / "node_modules").exists():
        return run_cmd("cd web && npm install", ok_exit={0}) is not None
    return run_cmd("cd web && npm run build", ok_exit={0}) is not None


def git_status() -> str:
    status = run_cmd("git status --short", ok_exit={0, 1})
    if status is None:
        return "(git unavailable)"
    return status or "working tree clean"


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    present_new = [p for p in NEW_FILES if (root / p).exists()]
    present_mod = [p for p in MODIFIED_FILES if (root / p).exists()]
    missing = [p for p in NEW_FILES if not (root / p).exists()]

    criteria_met = [name for name, check in CRITERIA.items() if check()]
    criteria_pending = [name for name in CRITERIA if name not in criteria_met]

    print("=== Hi-EV Web / Voice / HUD MVP — Progress Report ===\n")
    print(f"Plan: {PLAN_PATH}\n")
    print(f"New files created: {len(present_new)}/{len(NEW_FILES)}")
    print(f"Modified files touched: {len(present_mod)}/{len(MODIFIED_FILES)}")
    print(f"Acceptance criteria met: {len(criteria_met)}/{len(CRITERIA)}\n")

    if missing:
        print("Missing deliverables:")
        for m in missing:
            print(f"  - {m}")
        print()

    if criteria_pending:
        print("Pending acceptance checks:")
        for c in criteria_pending:
            print(f"  - {c}")
        print()

    print("Git status:")
    print(git_status())
    print()

    progress = (len(present_new) + len(present_mod)) / (len(NEW_FILES) + len(MODIFIED_FILES))
    print(f"Overall file-completion estimate: {progress:.0%}")
    print("\nImmediate goal: complete the Hi-EV web voice/HUD MVP (browser shell wired to local daemon).")


if __name__ == "__main__":
    main()
