"""Tests for the Hi-EV safe code sandbox."""

from __future__ import annotations

import pytest

from ev.sandbox.policy import SandboxError, SandboxPolicy
from ev.sandbox.runner import CodeRunner
from ev.sandbox.tool import SandboxTool


def test_policy_allows_simple_math():
    policy = SandboxPolicy()
    policy.check("result = 1 + 1")


def test_policy_rejects_import_os():
    policy = SandboxPolicy()
    with pytest.raises(SandboxError, match="Import of 'os' is not allowed"):
        policy.check("import os")


def test_policy_rejects_import_from_os():
    policy = SandboxPolicy()
    with pytest.raises(SandboxError, match="Import from 'os.path' is not allowed"):
        policy.check("from os.path import join")


def test_policy_rejects_open_call():
    policy = SandboxPolicy()
    with pytest.raises(SandboxError, match="Call to builtin 'open' is not allowed"):
        policy.check("open('/etc/passwd')")


def test_runner_computes_result():
    runner = CodeRunner(timeout=5.0)
    result = runner.run("result = 2 + 3 * 4")
    assert "error" not in result
    assert result["result"] == 14
    assert result["stdout"] == ""
    assert result["exception"] is None


def test_runner_captures_stdout():
    runner = CodeRunner(timeout=5.0)
    result = runner.run("print('hello sandbox')\nresult = 42")
    assert result["stdout"] == "hello sandbox\n"
    assert result["result"] == 42


def test_runner_provides_input_data():
    runner = CodeRunner(timeout=5.0)
    result = runner.run("result = input_data['x'] * 2", inputs={"x": 21})
    assert result["result"] == 42


def test_runner_uses_allowed_import():
    runner = CodeRunner(timeout=5.0)
    result = runner.run("import math\nresult = math.factorial(5)")
    assert result["result"] == 120


def test_runner_rejects_disallowed_import():
    runner = CodeRunner(timeout=5.0)
    result = runner.run("import os\nresult = os.getcwd()")
    assert "error" in result
    assert "Import of 'os'" in result["error"]


def test_runner_catches_exception():
    runner = CodeRunner(timeout=5.0)
    result = runner.run("result = 1 / 0")
    assert result["exception"] is not None
    assert "ZeroDivisionError" in result["exception"]


def test_runner_enforces_timeout():
    runner = CodeRunner(timeout=0.5)
    result = runner.run("while True: pass")
    assert "error" in result
    assert "timed out" in result["error"].lower()


@pytest.mark.anyio
async def test_tool_runs_code():
    tool = SandboxTool(timeout=5.0)
    result = await tool.run(code="result = sum(range(10))")
    assert result["result"] == 45


@pytest.mark.anyio
async def test_tool_rejects_non_python():
    tool = SandboxTool()
    result = await tool.run(code="console.log(1)", language="javascript")
    assert "error" in result
