"""Static AST policy for the Hi-EV code sandbox.

The sandbox is intentionally simple: it is meant for small, generated helper
snippets and quick calculations, not a hardened security boundary. It runs code
in a subprocess with a short timeout, a restricted builtin namespace, and a
whitelist of allowed imports. The tool is marked tier 2 so the user must
confirm before it runs.
"""

from __future__ import annotations

import ast
from typing import Any

# Modules that self-authored snippets may import. Keep it small and safe.
DEFAULT_ALLOWED_IMPORTS: set[str] = {
    "collections",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "hashlib",
    "itertools",
    "json",
    "math",
    "random",
    "re",
    "statistics",
    "string",
}

# Builtins that should not be available inside the sandbox.
BANNED_BUILTINS: set[str] = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "exit",
    "quit",
    "input",
    "help",
}


class SandboxError(Exception):
    """Raised when code violates the sandbox policy."""


class SandboxPolicy:
    """AST visitor that rejects disallowed imports and builtin calls."""

    def __init__(
        self,
        allowed_imports: set[str] | None = None,
        banned_builtins: set[str] | None = None,
    ):
        self.allowed_imports = set(allowed_imports or DEFAULT_ALLOWED_IMPORTS)
        self.banned_builtins = set(banned_builtins or BANNED_BUILTINS)

    def check(self, code: str) -> None:
        """Parse `code` and raise `SandboxError` on policy violations."""
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise SandboxError(f"Syntax error: {exc}") from exc

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in self.allowed_imports:
                        raise SandboxError(f"Import of '{alias.name}' is not allowed.")
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module not in self.allowed_imports:
                    raise SandboxError(f"Import from '{node.module}' is not allowed.")
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in self.banned_builtins:
                    raise SandboxError(f"Call to builtin '{func.id}' is not allowed.")

    def safe_builtins(self) -> dict[str, Any]:
        """Return a copy of builtins with dangerous names removed."""
        import builtins

        safe = {name: value for name, value in builtins.__dict__.items() if name not in self.banned_builtins}
        return safe
