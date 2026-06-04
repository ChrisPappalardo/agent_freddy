from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any

import plotext as plt
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from .fred_client import FredApiError, FredClient

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _observations_chart_text(
    observations: list[dict[str, Any]], *, width: int = 70, height: int = 10
) -> str:
    points: list[tuple[str, float]] = []
    for observation in reversed(observations):
        raw_value = str(observation.get("value", "")).strip()
        try:
            numeric_value = float(raw_value)
        except ValueError:
            continue
        points.append((str(observation.get("date", "")), numeric_value))

    if len(points) < 2:
        return "Not enough numeric observations to render a chart."

    x_values = list(range(len(points)))
    dates = [date for date, _ in points]
    values = [value for _, value in points]
    tick_candidates = [0, len(points) // 2, len(points) - 1]
    tick_positions: list[int] = []
    for candidate in tick_candidates:
        if candidate not in tick_positions:
            tick_positions.append(candidate)

    plt.clear_figure()
    plt.plotsize(max(20, width - 4), max(6, height - 2))
    plt.plot(x_values, values)
    plt.xticks(tick_positions, [dates[idx] for idx in tick_positions])
    plt.xlabel("Date")
    plt.ylabel("Value")
    plt.title("Observation line chart")
    chart = plt.build()
    plt.clear_figure()
    return _ANSI_ESCAPE_RE.sub("", chart)


def _observation_date_bounds(observations: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    dates = [
        str(observation.get("date", "")).strip()
        for observation in observations
        if _DATE_RE.match(str(observation.get("date", "")).strip())
    ]
    if not dates:
        return None, None
    return min(dates), max(dates)


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


class ChartScreen(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close")]

    DEFAULT_CSS = """
    ChartScreen {
        align: center middle;
    }

    #chart-dialog {
        width: 96%;
        height: 96%;
        border: round $accent;
        background: $panel;
        padding: 1 2;
    }

    #chart-title {
        margin-bottom: 1;
    }

    #chart-content {
        height: 1fr;
        padding: 1;
    }

    #chart-range-row {
        height: 3;
        margin-bottom: 1;
    }

    #chart-start-label {
        width: 18;
        content-align: left middle;
    }

    #chart-end-label {
        width: 16;
        margin-left: 1;
        content-align: left middle;
    }

    #chart-start {
        width: 18;
    }

    #chart-end {
        width: 18;
    }

    #chart-apply {
        width: 12;
        margin-left: 1;
    }

    #chart-range-help {
        margin-bottom: 1;
    }

    #chart-close-row {
        height: 3;
        margin-top: 1;
    }

    #chart-close {
        width: 12;
        background: #1f6feb;
        color: #ffffff;
    }

    #chart-close:hover {
        background: #1158c7;
        color: #ffffff;
    }

    #chart-close:focus {
        background: #1158c7;
        color: #ffffff;
    }
    """

    def __init__(
        self, series_id: str, series_title: str, observations: list[dict[str, Any]]
    ) -> None:
        super().__init__()
        self.series_id = series_id
        self.series_title = series_title
        self.observations = observations
        self.default_start_date, self.default_end_date = _observation_date_bounds(observations)

    def compose(self) -> ComposeResult:
        with Vertical(id="chart-dialog"):
            yield Static(f"{self.series_title} ({self.series_id})", id="chart-title")
            with Horizontal(id="chart-range-row"):
                yield Static("Start (YYYY-MM-DD):", id="chart-start-label")
                yield Input(value=self.default_start_date or "", id="chart-start")
                yield Static("End (YYYY-MM-DD):", id="chart-end-label")
                yield Input(value=self.default_end_date or "", id="chart-end")
                yield Button("Apply", id="chart-apply", variant="primary")
            yield Static("", id="chart-range-help")
            yield Static("", id="chart-content", markup=False)
            with Horizontal(id="chart-close-row"):
                yield Button("Close", id="chart-close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#chart-close", Button).can_focus = False
        self.set_focus(None)
        self._render_chart()

    def on_resize(self, event: events.Resize) -> None:
        _ = event
        self._render_chart()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "chart-apply":
            self._render_chart()
        elif event.button.id == "chart-close":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in {"chart-start", "chart-end"}:
            self._render_chart()

    def action_close(self) -> None:
        self.dismiss(None)

    def _render_chart(self) -> None:
        chart = self.query_one("#chart-content", Static)
        help_text = self.query_one("#chart-range-help", Static)
        start_input = self.query_one("#chart-start", Input)
        end_input = self.query_one("#chart-end", Input)

        start_date = start_input.value.strip() or self.default_start_date
        end_date = end_input.value.strip() or self.default_end_date
        if start_date and not _DATE_RE.match(start_date):
            help_text.update("Start date must be YYYY-MM-DD.")
            chart.update("Unable to render chart for selected date range.")
            return
        if end_date and not _DATE_RE.match(end_date):
            help_text.update("End date must be YYYY-MM-DD.")
            chart.update("Unable to render chart for selected date range.")
            return
        if start_date and end_date and start_date > end_date:
            help_text.update("Start date must be on or before end date.")
            chart.update("Unable to render chart for selected date range.")
            return

        filtered_observations = self.observations
        if start_date or end_date:
            filtered_observations = []
            for observation in self.observations:
                date = str(observation.get("date", "")).strip()
                if not _DATE_RE.match(date):
                    continue
                if start_date and date < start_date:
                    continue
                if end_date and date > end_date:
                    continue
                filtered_observations.append(observation)

        if not filtered_observations:
            help_text.update("No observations available in that date range.")
            chart.update("Unable to render chart for selected date range.")
            return

        width = chart.size.width if chart.size.width > 0 else 110
        height = chart.size.height if chart.size.height > 0 else 30
        chart.update(_observations_chart_text(filtered_observations, width=width, height=height))
        rendered_start, rendered_end = _observation_date_bounds(filtered_observations)
        help_text.update(
            f"Showing {len(filtered_observations)} observations from "
            f"{rendered_start} to {rendered_end}."
        )


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

    #details-pane {
        height: 1fr;
        border: round $surface;
        overflow-y: auto;
        overflow-x: auto;
    }

    #details {
        padding: 1;
    }

    #observations {
        height: 12;
        margin-top: 1;
    }

    #chart {
        width: 12;
        margin-left: 1;
        background: #1f6feb;
        color: #ffffff;
    }

    #chart:hover {
        background: #1158c7;
        color: #ffffff;
    }

    #chart:focus {
        background: #1158c7;
        color: #ffffff;
    }

    #chart:disabled {
        background: #4b5563;
        color: #d1d5db;
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
        self.current_observations: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            yield Input(placeholder="Search series (e.g. unemployment rate)", id="query")
            yield Button("Search", id="search", variant="primary")
            yield Button("Show Chart", id="chart", disabled=True)
            yield Button("Export CSV", id="export", disabled=True)
        with Horizontal(id="content"):
            yield DataTable(id="results")
            with Vertical(id="right"):
                with VerticalScroll(id="details-pane"):
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

        details_pane = self.query_one("#details-pane", VerticalScroll)
        details_pane.can_focus = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search":
            query = self.query_one("#query", Input).value.strip()
            self._search(query)
        elif event.button.id == "chart":
            self._show_chart_popup()
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
        chart_button = self.query_one("#chart", Button)
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
        chart_button.disabled = True
        export_button.disabled = True
        self.current_series_id = None
        self.current_series = None
        self.current_observations = []

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
        chart_button = self.query_one("#chart", Button)
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
        self.current_observations = observations
        export_button.disabled = False

        obs_table.clear()
        if not observations:
            obs_table.add_row("(no observations returned)", "")
            chart_button.disabled = True
            return

        for observation in observations:
            obs_table.add_row(observation.get("date", ""), observation.get("value", ""))
        chart_button.disabled = False

    def _show_chart_popup(self) -> None:
        details = self.query_one("#details", Static)
        series_id = self.current_series_id
        if not series_id:
            details.update("Select a series before opening the chart.")
            return
        if not self.current_observations:
            details.update("No observations available for charting.")
            return

        series_title = (
            str(self.current_series.get("title", series_id))
            if self.current_series
            else series_id
        )
        self.push_screen(
            ChartScreen(series_id, series_title, self.current_observations),
            self._on_chart_closed,
        )

    def _on_chart_closed(self, _result: None) -> None:
        self.query_one("#query", Input).focus()

    def _prompt_for_export_path(self) -> None:
        details = self.query_one("#details", Static)
        series_id = self.current_series_id
        if not series_id:
            details.update("Select a series before exporting.")
            return

        suggested_path = str(Path.cwd() / ".export" / f"{series_id}.csv")
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
