from __future__ import annotations

from typing import Any

import pytest
import requests

from agent_freddy.fred_client import FredApiError, FredClient


class _FakeResponse:
    def __init__(
        self, payload: Any, *, status_code: int = 200, reason: str = "OK", json_raises: bool = False
    ) -> None:
        self.status_code = status_code
        self.reason = reason
        self._payload = payload
        self._json_raises = json_raises

    def json(self) -> Any:
        if self._json_raises:
            raise ValueError("invalid json")
        return self._payload


def test_request_includes_api_key_and_file_type(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_get(url: str, *, params: dict[str, Any], timeout: float) -> _FakeResponse:
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _FakeResponse({"observations": []})

    monkeypatch.setattr(requests, "get", fake_get)
    client = FredClient(api_key="test-key")

    payload = client._request("series/observations", series_id="UNRATE", limit=10)

    assert payload == {"observations": []}
    assert captured["url"].endswith("/series/observations")
    assert captured["params"]["api_key"] == "test-key"
    assert captured["params"]["file_type"] == "json"
    assert captured["params"]["series_id"] == "UNRATE"
    assert captured["params"]["limit"] == 10
    assert captured["timeout"] == 20.0


def test_request_raises_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, *, params: dict[str, Any], timeout: float) -> _FakeResponse:
        raise requests.RequestException("boom")

    monkeypatch.setattr(requests, "get", fake_get)
    client = FredClient(api_key="test-key")

    with pytest.raises(FredApiError, match="Network error calling series"):
        client._request("series", series_id="UNRATE")


def test_request_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, *, params: dict[str, Any], timeout: float) -> _FakeResponse:
        return _FakeResponse(
            {"error_message": "Bad request"},
            status_code=400,
            reason="Bad Request",
        )

    monkeypatch.setattr(requests, "get", fake_get)
    client = FredClient(api_key="test-key")

    with pytest.raises(FredApiError, match="Bad request"):
        client._request("series", series_id="UNRATE")


def test_get_series_returns_first_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        FredClient,
        "_request",
        lambda self, endpoint, **params: {"seriess": [{"id": "UNRATE"}]},
    )
    client = FredClient(api_key="test-key")

    series = client.get_series("UNRATE")

    assert series["id"] == "UNRATE"


def test_get_series_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(FredClient, "_request", lambda self, endpoint, **params: {"seriess": []})
    client = FredClient(api_key="test-key")

    with pytest.raises(FredApiError, match="No series found"):
        client.get_series("MISSING")


def test_get_all_series_observations_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int, str]] = []

    def fake_get_series_observations(
        self: FredClient,
        series_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        sort_order: str = "desc",
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> list[dict[str, Any]]:
        calls.append((limit, offset, sort_order))
        if offset == 0:
            return [{"date": "2024-01-01", "value": "1"}, {"date": "2024-02-01", "value": "2"}]
        if offset == 2:
            return [{"date": "2024-03-01", "value": "3"}]
        return []

    monkeypatch.setattr(FredClient, "get_series_observations", fake_get_series_observations)
    client = FredClient(api_key="test-key")

    observations = client.get_all_series_observations("UNRATE", page_size=2, sort_order="asc")

    assert [row["value"] for row in observations] == ["1", "2", "3"]
    assert calls == [(2, 0, "asc"), (2, 2, "asc")]
