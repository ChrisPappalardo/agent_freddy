from __future__ import annotations

import os
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from .fred_client import FredApiError, FredClient


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 3].rstrip() + "..."


def _series_details_text(series: dict[str, Any]) -> str:
    notes = series.get("notes", "No description available.") or "No description available."
    return (
        f"{series.get('title', '')}\n"
        f"ID: {series.get('id', '')}\n"
        f"Frequency: {series.get('frequency', '')}\n"
        f"Units: {series.get('units', '')}\n"
        f"Seasonal adjustment: {series.get('seasonal_adjustment', '')}\n"
        f"Available: {series.get('observation_start', '')} -> {series.get('observation_end', '')}\n"
        f"Last updated: {series.get('last_updated', '')}\n"
        f"\nDescription:\n{notes}"
    )


class FredExplorerApp(App[None]):
    TITLE = "FRED Explorer MVP"
    CSS = """
    #top {
        height: 3;
        padding: 0 1;
    }

    #query {
        width: 1fr;
    }

    #search {
        width: 12;
        margin-left: 1;
    }

    #content {
        height: 1fr;
    }

    #results {
        width: 1fr;
    }

    #right {
        width: 1fr;
    }

    #details {
        height: 1fr;
        padding: 1;
        border: round $surface;
    }

    #observations {
        height: 12;
        margin-top: 1;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, client: FredClient) -> None:
        super().__init__()
        self.client = client
        self.results: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            yield Input(placeholder="Search series (e.g. unemployment rate)", id="query")
            yield Button("Search", id="search", variant="primary")
        with Horizontal(id="content"):
            yield DataTable(id="results")
            with Vertical(id="right"):
                yield Static("Search for a series to begin.", id="details")
                yield DataTable(id="observations")
        yield Footer()

    def on_mount(self) -> None:
        results_table = self.query_one("#results", DataTable)
        results_table.cursor_type = "row"
        results_table.add_columns("Series ID", "Title", "Frequency", "Available Through")

        obs_table = self.query_one("#observations", DataTable)
        obs_table.cursor_type = "row"
        obs_table.add_columns("Date", "Value")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search":
            query = self.query_one("#query", Input).value.strip()
            self._search(query)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "query":
            self._search(event.value.strip())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "results":
            return
        row_key = event.row_key.value
        if row_key is None:
            return
        try:
            idx = int(str(row_key))
            series = self.results[idx]
        except (ValueError, IndexError):
            return
        self._load_series(series["id"])

    def _search(self, query: str) -> None:
        details = self.query_one("#details", Static)
        results_table = self.query_one("#results", DataTable)
        obs_table = self.query_one("#observations", DataTable)

        if not query:
            details.update("Enter a search query.")
            return

        try:
            self.results = self.client.search_series(query, limit=50)
        except FredApiError as exc:
            details.update(f"Search failed:\n{exc}")
            return

        results_table.clear()
        obs_table.clear()

        if not self.results:
            details.update("No matching series found.")
            return

        for idx, item in enumerate(self.results):
            results_table.add_row(
                item.get("id", ""),
                _truncate(item.get("title", ""), 60),
                item.get("frequency", ""),
                item.get("observation_end", ""),
                key=str(idx),
            )

        details.update(
            f"Found {len(self.results)} series for: {query}\n"
            "Select a row to view description, availability, and recent observations."
        )

    def _load_series(self, series_id: str) -> None:
        details = self.query_one("#details", Static)
        obs_table = self.query_one("#observations", DataTable)

        try:
            series = self.client.get_series(series_id)
            observations = self.client.get_series_observations(series_id, limit=15, sort_order="desc")
        except FredApiError as exc:
            details.update(f"Unable to load series {series_id}:\n{exc}")
            return

        details.update(_series_details_text(series))

        obs_table.clear()
        if not observations:
            obs_table.add_row("(no observations returned)", "")
            return

        for observation in observations:
            obs_table.add_row(observation.get("date", ""), observation.get("value", ""))


def run_tui(api_key: str) -> None:
    app = FredExplorerApp(FredClient(api_key=api_key))
    app.run()


def run_from_env() -> None:
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise SystemExit("Set FRED_API_KEY before running fred-tui.")
    run_tui(api_key)

