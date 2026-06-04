from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
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


class ExportPathScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    ExportPathScreen {
        align: center middle;
    }

    #export-dialog {
        width: 88;
        max-width: 90%;
        border: round $accent;
        background: $panel;
        padding: 1 2;
    }

    #export-help {
        margin-top: 1;
    }

    #export-path-input {
        margin-top: 1;
    }

    #export-actions {
        margin-top: 1;
        height: 3;
    }

    #export-cancel {
        margin-right: 1;
    }
    """

    def __init__(self, default_path: str) -> None:
        super().__init__()
        self.default_path = default_path

    def compose(self) -> ComposeResult:
        with Vertical(id="export-dialog"):
            yield Static("Export full series to CSV")
            yield Static("Review the path below, then choose Save.", id="export-help")
            yield Input(value=self.default_path, id="export-path-input")
            with Horizontal(id="export-actions"):
                yield Button("Cancel", id="export-cancel")
                yield Button("Save", id="export-save", variant="success")

    def on_mount(self) -> None:
        self.query_one("#export-path-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-cancel":
            self.dismiss(None)
        elif event.button.id == "export-save":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "export-path-input":
            self._submit()

    def _submit(self) -> None:
        export_path = self.query_one("#export-path-input", Input).value.strip()
        if not export_path:
            self.query_one("#export-help", Static).update("Export path is required.")
            return
        self.dismiss(export_path)


class FredExplorerApp(App[None]):
    TITLE = "Agent Freddy"
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

    #export {
        width: 14;
        margin-left: 1;
        background: #2a9d47;
        color: #ffffff;
    }

    #export:hover {
        background: #23863d;
        color: #ffffff;
    }

    #export:focus {
        background: #23863d;
        color: #ffffff;
    }

    #export:disabled {
        background: #4b5563;
        color: #d1d5db;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, client: FredClient) -> None:
        super().__init__()
        self.client = client
        self.results: list[dict[str, Any]] = []
        self.current_series_id: str | None = None
        self.current_series: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            yield Input(placeholder="Search series (e.g. unemployment rate)", id="query")
            yield Button("Search", id="search", variant="primary")
            yield Button("Export CSV", id="export", disabled=True)
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
        elif event.button.id == "export":
            self._prompt_for_export_path()

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
            # Search rows are keyed by list index (stored as a string key on insert).
            idx = int(str(row_key))
            series = self.results[idx]
        except (ValueError, IndexError):
            return
        self._load_series(series["id"])

    def _search(self, query: str) -> None:
        details = self.query_one("#details", Static)
        results_table = self.query_one("#results", DataTable)
        obs_table = self.query_one("#observations", DataTable)
        export_button = self.query_one("#export", Button)

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
        export_button.disabled = True
        self.current_series_id = None
        self.current_series = None

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
        export_button = self.query_one("#export", Button)

        try:
            series = self.client.get_series(series_id)
            observations = self.client.get_series_observations(
                series_id,
                limit=30,
                sort_order="desc",
            )
        except FredApiError as exc:
            details.update(f"Unable to load series {series_id}:\n{exc}")
            return

        details.update(_series_details_text(series))
        self.current_series_id = series_id
        self.current_series = series
        export_button.disabled = False

        obs_table.clear()
        if not observations:
            obs_table.add_row("(no observations returned)", "")
            return

        for observation in observations:
            obs_table.add_row(observation.get("date", ""), observation.get("value", ""))

    def _prompt_for_export_path(self) -> None:
        details = self.query_one("#details", Static)
        series_id = self.current_series_id
        if not series_id:
            details.update("Select a series before exporting.")
            return

        suggested_path = str(Path.cwd() / f"{series_id}.csv")
        self.push_screen(ExportPathScreen(suggested_path), self._export_current_series)

    def _export_current_series(self, destination_path: str | None) -> None:
        if not destination_path:
            self.query_one("#query", Input).focus()
            return

        details = self.query_one("#details", Static)
        series_id = self.current_series_id
        if not series_id:
            details.update("Select a series before exporting.")
            self.query_one("#query", Input).focus()
            return

        output_path = Path(destination_path).expanduser()
        if output_path.exists() and output_path.is_dir():
            details.update(f"Unable to export: {output_path} is a directory.")
            self.query_one("#query", Input).focus()
            return

        details.update(f"Exporting full series to:\n{output_path}")

        try:
            observations = self.client.get_all_series_observations(series_id, sort_order="asc")
        except FredApiError as exc:
            details.update(f"Unable to export series {series_id}:\n{exc}")
            self.query_one("#query", Input).focus()
            return

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["date", "value"])
                for observation in observations:
                    writer.writerow([observation.get("date", ""), observation.get("value", "")])
        except OSError as exc:
            details.update(f"Unable to write {output_path.name}:\n{exc}")
            self.query_one("#query", Input).focus()
            return

        header = (
            _series_details_text(self.current_series)
            if self.current_series
            else f"ID: {series_id}"
        )
        details.update(
            f"{header}\n\nExported {len(observations)} observations to {output_path.name} "
            f"in {output_path.parent}"
        )
        self.query_one("#query", Input).focus()


def run_tui(api_key: str) -> None:
    app = FredExplorerApp(FredClient(api_key=api_key))
    app.run()


def run_from_env() -> None:
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise SystemExit("Set FRED_API_KEY before running fred-tui.")
    run_tui(api_key)
