"""Isolated runner invoked as a subprocess by `ev.sandbox.runner.CodeRunner`.

Reads user code from stdin, validates it against the static policy, executes it
in a restricted globals namespace, and writes a JSON result file. The parent
process is told where the result lives via a stdout marker line.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import traceback
from pathlib import Path
from typing import Any

# We only import from the local sandbox package; the parent process ensures
# PYTHONPATH points at the project so this works in dev and installed builds.
from ev.sandbox.policy import BANNED_BUILTINS, DEFAULT_ALLOWED_IMPORTS, SandboxError, SandboxPolicy


def _restricted_import(name: str, globals_=None, locals_=None, fromlist=(), level: int = 0):
    top = name.split(".")[0]
    if top not in DEFAULT_ALLOWED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed in the sandbox.")
    return __import__(name, globals_, locals_, fromlist, level)


def _build_safe_builtins(policy: SandboxPolicy) -> dict:
    safe = policy.safe_builtins()
    safe["__import__"] = _restricted_import
    return safe


def run(code: str, inputs: dict | None = None) -> dict[str, Any]:
    """Run `code` under the sandbox policy and return a result dict.

    The result dict contains:
    - result: the value of the `result` variable after execution (if any)
    - stdout: captured standard output
    - stderr: captured standard error
    - exception: formatted traceback if the code raised
    """
    policy = SandboxPolicy()
    policy.check(code)

    safe_globals: dict[str, Any] = {
        "__builtins__": _build_safe_builtins(policy),
        "input_data": inputs or {},
        "result": None,
    }

    out = io.StringIO()
    err = io.StringIO()
    exc_info: str | None = None
    try:
        compiled = compile(code, "<sandbox>", "exec")
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exec(compiled, safe_globals)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        exc_info = traceback.format_exc()

    return {
        "result": safe_globals.get("result"),
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        "exception": exc_info,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Hi-EV sandbox isolated runner")
    parser.add_argument("--inputs-file", help="JSON file containing input_data")
    parser.add_argument("--output-file", required=True, help="Path to write the JSON result")
    args = parser.parse_args()

    inputs: dict = {}
    if args.inputs_file:
        path = Path(args.inputs_file)
        if path.exists():
            with path.open(encoding="utf-8") as f:
                inputs = json.load(f)

    code = sys.stdin.read()
    result = run(code, inputs)

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, default=str)

    sys.stdout.write(f"__HIEV_SANDBOX_DONE__:{args.output_file}\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
