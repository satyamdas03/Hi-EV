"""Subprocess runner for the Hi-EV code sandbox."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from ev.sandbox.policy import SandboxError, SandboxPolicy

logger = logging.getLogger(__name__)


class CodeRunner:
    """Run a restricted Python snippet in a subprocess and return the result."""

    def __init__(self, timeout: float = 10.0, allowed_imports: set[str] | None = None):
        self.timeout = timeout
        self.policy = SandboxPolicy(allowed_imports=allowed_imports)

    def run(self, code: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validate and execute `code` in an isolated subprocess.

        Returns a dict with `result`, `stdout`, `stderr`, and optionally
        `error` if the sandbox could not complete.
        """
        try:
            self.policy.check(code)
        except SandboxError as exc:
            return {"error": str(exc), "result": None, "stdout": "", "stderr": ""}

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["SANDBOX"] = "1"

        # Make sure the subprocess can import the `ev` package in dev builds.
        try:
            import ev

            ev_root = str(Path(ev.__file__).resolve().parent.parent)
            env["PYTHONPATH"] = ev_root + os.pathsep + env.get("PYTHONPATH", "")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not add ev package to sandbox PYTHONPATH: %s", exc)

        inputs_path: str | None = None
        output_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
                json.dump(inputs or {}, f)
                inputs_path = f.name

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
                output_path = f.name

            cmd = [
                sys.executable,
                "-m",
                "ev.sandbox.isolated",
                "--inputs-file",
                inputs_path,
                "--output-file",
                output_path,
            ]
            proc = subprocess.run(
                cmd,
                input=code,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                env=env,
                check=False,
            )

            if proc.returncode != 0:
                return {
                    "error": f"Sandbox process failed (exit {proc.returncode}): {proc.stderr}",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "result": None,
                }

            marker = "__HIEV_SANDBOX_DONE__:"
            done_line: str | None = None
            for line in proc.stdout.splitlines():
                if line.startswith(marker):
                    done_line = line
                    break

            if done_line is None:
                return {
                    "error": "Sandbox did not emit result marker",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "result": None,
                }

            reported_output = done_line[len(marker):]
            if reported_output != output_path:
                return {
                    "error": f"Sandbox output path mismatch: {reported_output}",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "result": None,
                }

            with open(output_path, encoding="utf-8") as f:
                return json.load(f)

        except subprocess.TimeoutExpired as exc:
            return {
                "error": f"Sandbox timed out after {self.timeout}s",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "result": None,
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Sandbox runner error: {exc}", "stdout": "", "stderr": "", "result": None}
        finally:
            for path in (inputs_path, output_path):
                if path:
                    try:
                        os.unlink(path)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Could not remove sandbox temp file %s: %s", path, exc)
