from __future__ import annotations

from agent_freddy.tui import _series_details_text, _truncate


def test_truncate_short_text_returns_original() -> None:
    assert _truncate("abc", 5) == "abc"


def test_truncate_long_text_adds_ellipsis() -> None:
    assert _truncate("abcdefghij", 8) == "abcde..."


def test_series_details_text_includes_metadata_and_fallback_notes() -> None:
    details = _series_details_text(
        {
            "id": "UNRATE",
            "title": "Unemployment Rate",
            "frequency": "Monthly",
            "units": "Percent",
            "seasonal_adjustment": "Seasonally Adjusted",
            "observation_start": "1948-01-01",
            "observation_end": "2026-01-01",
            "last_updated": "2026-02-01",
            "notes": "",
        }
    )

    assert "ID: UNRATE" in details
    assert "Frequency: Monthly" in details
    assert "Description:\nNo description available." in details
