from __future__ import annotations

from typing import Any

import click
from click.testing import CliRunner

import agent_freddy.cli as cli_module
from agent_freddy.fred_client import FredApiError, FredClient


class _FakeClient:
    def __init__(self) -> None:
        self.api_key = "fake-key"

    def search_series(self, query: str, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        if query == "none":
            return []
        return [
            {
                "id": "UNRATE",
                "title": "Unemployment Rate",
                "frequency": "Monthly",
                "units": "Percent",
                "observation_start": "1948-01-01",
                "observation_end": "2026-01-01",
                "notes": "Headline unemployment rate",
            }
        ]

    def get_series(self, series_id: str) -> dict[str, Any]:
        return {
            "id": series_id,
            "title": "Unemployment Rate",
            "frequency": "Monthly",
            "units": "Percent",
            "seasonal_adjustment": "Seasonally Adjusted",
            "observation_start": "1948-01-01",
            "observation_end": "2026-01-01",
            "last_updated": "2026-02-01",
            "popularity": "98",
            "notes": "Headline unemployment rate",
        }

    def get_series_observations(
        self,
        series_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        sort_order: str = "desc",
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> list[dict[str, str]]:
        return [{"date": "2026-01-01", "value": "4.0"}, {"date": "2025-12-01", "value": "4.1"}]


def _patch_client(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "_client_or_exit", lambda api_key: _FakeClient())


def test_client_or_exit_requires_key() -> None:
    try:
        cli_module._client_or_exit(None)
    except click.ClickException as exc:
        assert "FRED API key is required" in str(exc)
    else:
        raise AssertionError("Expected ClickException for missing API key")


def test_client_or_exit_returns_client() -> None:
    client = cli_module._client_or_exit("abc123")

    assert isinstance(client, FredClient)
    assert client.api_key == "abc123"


def test_truncate_adds_ellipsis() -> None:
    assert cli_module._truncate("abcdefghij", 8) == "abcde..."


def test_search_command_prints_results(monkeypatch) -> None:
    _patch_client(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(cli_module.cli, ["--api-key", "x", "search", "jobs"])

    assert result.exit_code == 0
    assert "Found 1 series for query: 'jobs'" in result.output
    assert "UNRATE" in result.output


def test_search_command_prints_no_match_message(monkeypatch) -> None:
    _patch_client(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(cli_module.cli, ["--api-key", "x", "search", "none"])

    assert result.exit_code == 0
    assert "No matching series found." in result.output


def test_search_command_wraps_api_error(monkeypatch) -> None:
    _patch_client(monkeypatch)
    runner = CliRunner()

    def raising_search(*args, **kwargs):
        raise FredApiError("Search unavailable")

    monkeypatch.setattr(_FakeClient, "search_series", raising_search)
    result = runner.invoke(cli_module.cli, ["--api-key", "x", "search", "jobs"])

    assert result.exit_code != 0
    assert "Search unavailable" in result.output


def test_describe_command_prints_metadata(monkeypatch) -> None:
    _patch_client(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(cli_module.cli, ["--api-key", "x", "describe", "UNRATE"])

    assert result.exit_code == 0
    assert "Series ID:            UNRATE" in result.output
    assert "Description:" in result.output


def test_pull_command_prints_csv_rows(monkeypatch) -> None:
    _patch_client(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(cli_module.cli, ["--api-key", "x", "pull", "UNRATE", "--limit", "2"])

    assert result.exit_code == 0
    assert "date,value" in result.output
    assert "2026-01-01,4.0" in result.output
    assert "2025-12-01,4.1" in result.output


def test_pull_command_wraps_api_error(monkeypatch) -> None:
    _patch_client(monkeypatch)
    runner = CliRunner()

    def raising_get_series(*args, **kwargs):
        raise FredApiError("Series unavailable")

    monkeypatch.setattr(_FakeClient, "get_series", raising_get_series)
    result = runner.invoke(cli_module.cli, ["--api-key", "x", "pull", "UNRATE"])

    assert result.exit_code != 0
    assert "Series unavailable" in result.output


def test_tui_command_invokes_run_tui(monkeypatch) -> None:
    _patch_client(monkeypatch)
    runner = CliRunner()
    called: dict[str, str] = {}

    def fake_run_tui(api_key: str) -> None:
        called["api_key"] = api_key

    monkeypatch.setattr(cli_module, "run_tui", fake_run_tui)
    result = runner.invoke(cli_module.cli, ["--api-key", "x", "tui"])

    assert result.exit_code == 0
    assert called["api_key"] == "fake-key"
