from __future__ import annotations

from typing import Any

import click

from .fred_client import FredApiError, FredClient
from .tui import run_tui


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 3].rstrip() + "..."


def _print_series_summary(item: dict[str, Any]) -> None:
    series_id = item.get("id", "?")
    title = item.get("title", "")
    frequency = item.get("frequency", "?")
    units = item.get("units", "?")
    start = item.get("observation_start", "?")
    end = item.get("observation_end", "?")
    notes = item.get("notes", "") or "No description available."

    click.echo(f"{series_id:<15} {_truncate(title, 72)}")
    click.echo(f"{'':15} {frequency} | {units} | available {start} -> {end}")
    click.echo(f"{'':15} {_truncate(notes.replace(chr(10), ' '), 100)}")
    click.echo()


def _client_or_exit(api_key: str | None) -> FredClient:
    if not api_key:
        raise click.ClickException(
            "FRED API key is required. Pass --api-key or set FRED_API_KEY in your environment."
        )
    return FredClient(api_key=api_key)


@click.group()
@click.option(
    "--api-key",
    envvar="FRED_API_KEY",
    help="FRED API key. If omitted, FRED_API_KEY environment variable is used.",
)
@click.pass_context
def cli(ctx: click.Context, api_key: str | None) -> None:
    """FRED data explorer MVP."""
    ctx.obj = _client_or_exit(api_key)


@cli.command()
@click.argument("query")
@click.option("--limit", default=10, show_default=True, type=click.IntRange(1, 1000))
@click.option("--offset", default=0, show_default=True, type=click.IntRange(0, None))
@click.pass_obj
def search(client: FredClient, query: str, limit: int, offset: int) -> None:
    """Search for data series by keyword."""
    try:
        results = client.search_series(query, limit=limit, offset=offset)
    except FredApiError as exc:
        raise click.ClickException(str(exc)) from exc

    if not results:
        click.echo("No matching series found.")
        return

    click.echo(f"Found {len(results)} series for query: {query!r}")
    click.echo()
    for item in results:
        _print_series_summary(item)


@cli.command()
@click.argument("series_id")
@click.pass_obj
def describe(client: FredClient, series_id: str) -> None:
    """Show metadata and availability for a series."""
    try:
        series = client.get_series(series_id)
    except FredApiError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Series ID:            {series.get('id', series_id)}")
    click.echo(f"Title:                {series.get('title', '')}")
    click.echo(f"Frequency:            {series.get('frequency', '')}")
    click.echo(f"Units:                {series.get('units', '')}")
    click.echo(f"Seasonal adjustment:  {series.get('seasonal_adjustment', '')}")
    click.echo(f"Availability start:   {series.get('observation_start', '')}")
    click.echo(f"Availability end:     {series.get('observation_end', '')}")
    click.echo(f"Last updated:         {series.get('last_updated', '')}")
    click.echo(f"Popularity:           {series.get('popularity', '')}")
    click.echo()
    click.echo("Description:")
    click.echo(series.get("notes", "No description available."))


@cli.command()
@click.argument("series_id")
@click.option("--limit", default=20, show_default=True, type=click.IntRange(1, 100000))
@click.option(
    "--sort-order",
    default="desc",
    show_default=True,
    type=click.Choice(["asc", "desc"], case_sensitive=False),
)
@click.option("--offset", default=0, show_default=True, type=click.IntRange(0, None))
@click.option("--observation-start", default=None, help="YYYY-MM-DD")
@click.option("--observation-end", default=None, help="YYYY-MM-DD")
@click.pass_obj
def pull(
    client: FredClient,
    series_id: str,
    limit: int,
    sort_order: str,
    offset: int,
    observation_start: str | None,
    observation_end: str | None,
) -> None:
    """Pull observations for a series and print to stdout."""
    try:
        series = client.get_series(series_id)
        observations = client.get_series_observations(
            series_id,
            limit=limit,
            offset=offset,
            sort_order=sort_order.lower(),
            observation_start=observation_start,
            observation_end=observation_end,
        )
    except FredApiError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"# {series.get('title', series_id)} ({series_id})")
    click.echo(
        f"# {series.get('units', '')}, {series.get('frequency', '')}, "
        f"available {series.get('observation_start', '?')} -> {series.get('observation_end', '?')}"
    )
    click.echo("date,value")

    for observation in observations:
        date = observation.get("date", "")
        value = observation.get("value", "")
        click.echo(f"{date},{value}")


@cli.command(name="tui")
@click.pass_obj
def tui_command(client: FredClient) -> None:
    """Launch interactive Textual explorer."""
    run_tui(client.api_key)


if __name__ == "__main__":
    cli()
