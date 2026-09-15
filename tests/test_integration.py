"""End-to-end integration tests.

These are skipped unless EV_RUN_INTEGRATION=1 is set, because they hit live
GitHub and require a real .env with EV_GITHUB_TOKEN and EV_DATABASE_URL.
"""

import os

import pytest
from click.testing import CliRunner

from ev.cli.main import cli

pytestmark = pytest.mark.skipif(
    os.environ.get("EV_RUN_INTEGRATION") != "1",
    reason="Set EV_RUN_INTEGRATION=1 to run live integration tests",
)


def test_integration_status():
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "RoboCAD"])
    assert result.exit_code == 0
    assert "RoboCAD" in result.output
