from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class FredApiError(RuntimeError):
    """Raised when a FRED API call fails."""


@dataclass(slots=True)
class FredClient:
    """Minimal typed wrapper around core FRED API v1 endpoints."""

    api_key: str
    base_url: str = "https://api.stlouisfed.org/fred"
    timeout_seconds: float = 20.0

    def _request(self, endpoint: str, **params: Any) -> dict[str, Any]:
        query = {"api_key": self.api_key, "file_type": "json", **params}
        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.get(url, params=query, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise FredApiError(f"Network error calling {endpoint}: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise FredApiError(
                f"Unexpected response format for {endpoint} (status {response.status_code})."
            ) from exc

        if response.status_code != 200:
            message = payload.get("error_message") if isinstance(payload, dict) else None
            detail = message or response.reason or "Unknown HTTP error"
            raise FredApiError(f"FRED API error for {endpoint}: {detail}")

        if isinstance(payload, dict) and "error_message" in payload:
            raise FredApiError(f"FRED API error for {endpoint}: {payload['error_message']}")

        if not isinstance(payload, dict):
            raise FredApiError(f"Unexpected payload for {endpoint}: {type(payload).__name__}")

        return payload

    def search_series(
        self, search_text: str, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "series/search",
            search_text=search_text,
            limit=limit,
            offset=offset,
            order_by="search_rank",
            sort_order="desc",
        )
        # FRED uses the non-standard key name "seriess" for this endpoint family.
        seriess = payload.get("seriess", [])
        return seriess if isinstance(seriess, list) else []

    def get_series(self, series_id: str) -> dict[str, Any]:
        payload = self._request("series", series_id=series_id)
        # This endpoint also returns results under "seriess", usually as a single-item list.
        seriess = payload.get("seriess", [])
        if not isinstance(seriess, list) or not seriess:
            raise FredApiError(f"No series found for id '{series_id}'.")
        first = seriess[0]
        if not isinstance(first, dict):
            raise FredApiError(f"Unexpected series payload for id '{series_id}'.")
        return first

    def get_series_observations(
        self,
        series_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        sort_order: str = "desc",
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "series_id": series_id,
            "limit": limit,
            "offset": offset,
            "sort_order": sort_order,
        }
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end

        payload = self._request("series/observations", **params)
        observations = payload.get("observations", [])
        return observations if isinstance(observations, list) else []

    def get_all_series_observations(
        self, series_id: str, *, sort_order: str = "asc", page_size: int = 100000
    ) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        offset = 0

        while True:
            batch = self.get_series_observations(
                series_id,
                limit=page_size,
                offset=offset,
                sort_order=sort_order,
            )
            if not batch:
                break
            observations.extend(batch)
            if len(batch) < page_size:
                break
            offset += len(batch)

        return observations
