"""Tests for the Hi-EV auto-updater."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from ev.updater.checker import UpdateChecker, UpdateCheckError, _normalize_version


@pytest.mark.anyio
async def test_update_available_when_latest_greater():
    checker = UpdateChecker(repo="owner/repo")
    release = {"tag_name": "v0.2.0"}

    with (
        patch.object(UpdateChecker, "current_version", return_value="0.1.0"),
        patch.object(UpdateChecker, "latest_release", return_value=release),
    ):
        result = await checker.check()

    assert result["update_available"] is True
    assert result["current"] == "0.1.0"
    assert result["latest"] == "v0.2.0"
    assert result["error"] is None
    assert result["url"].endswith("/v0.2.0/scripts/install_windows.ps1")


@pytest.mark.anyio
async def test_up_to_date_when_latest_equals_current():
    checker = UpdateChecker(repo="owner/repo")
    release = {"tag_name": "v1.0.0"}

    with (
        patch.object(UpdateChecker, "current_version", return_value="1.0.0"),
        patch.object(UpdateChecker, "latest_release", return_value=release),
    ):
        result = await checker.check()

    assert result["update_available"] is False
    assert result["current"] == "1.0.0"
    assert result["latest"] == "v1.0.0"
    assert result["error"] is None


@pytest.mark.anyio
async def test_no_update_when_latest_lower():
    checker = UpdateChecker(repo="owner/repo")
    release = {"tag_name": "v0.9.0"}

    with (
        patch.object(UpdateChecker, "current_version", return_value="1.0.0"),
        patch.object(UpdateChecker, "latest_release", return_value=release),
    ):
        result = await checker.check()

    assert result["update_available"] is False


@pytest.mark.anyio
async def test_check_reports_error_on_network_failure():
    checker = UpdateChecker(repo="owner/repo")

    with (
        patch.object(UpdateChecker, "current_version", return_value="0.1.0"),
        patch.object(
            UpdateChecker,
            "latest_release",
            side_effect=UpdateCheckError("network down"),
        ),
    ):
        result = await checker.check()

    assert result["update_available"] is False
    assert result["current"] == "0.1.0"
    assert result["latest"] is None
    assert result["error"] == "Could not check for updates"


@pytest.mark.anyio
async def test_check_strips_leading_v_for_comparison():
    checker = UpdateChecker(repo="owner/repo")
    release = {"tag_name": "1.2.3"}

    with (
        patch.object(UpdateChecker, "current_version", return_value="v1.2.3"),
        patch.object(UpdateChecker, "latest_release", return_value=release),
    ):
        result = await checker.check()

    assert result["update_available"] is False


@pytest.mark.anyio
async def test_latest_release_queries_github():
    checker = UpdateChecker(repo="owner/repo")
    payload = {"tag_name": "v2.0.0"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = payload
            response.raise_for_status.return_value = None
            return response

    with patch("httpx.AsyncClient", side_effect=FakeClient):
        release = await checker.latest_release()

    assert release["tag_name"] == "v2.0.0"


@pytest.mark.anyio
async def test_latest_release_raises_on_network_error():
    checker = UpdateChecker(repo="owner/repo")

    with (
        patch("httpx.AsyncClient.get", side_effect=Exception("api rate limited")),
        pytest.raises(UpdateCheckError),
    ):
        await checker.latest_release()


def test_normalize_version_handles_v_prefix_and_prerelease():
    assert _normalize_version("v1.2.3") == (1, 2, 3)
    assert _normalize_version("1.2.3-beta") == (1, 2, 3)
    assert _normalize_version("1.2.3-beta.4") == (1, 2, 3)
    assert _normalize_version("") == ()


def test_current_version_reads_pyproject():
    version = UpdateChecker.current_version()
    assert re.match(r"^\d+\.\d+\.\d+", version)
