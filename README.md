# agent-freddy

`agent-freddy` is a small Python MVP for finding FRED time series and pulling observations from the terminal.
It includes both a Click-based CLI and an interactive Textual TUI.

## Setup

1. Install dependencies:

```bash
uv sync
```

2. Get a FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
3. Set it in your shell:

```bash
export FRED_API_KEY="your_32_char_key"
```

## Click CLI

Search for series by keyword:

```bash
uv run fred search "unemployment rate" --limit 5
```

Describe metadata and availability:

```bash
uv run fred describe UNRATE
```

Pull observations to stdout:

```bash
uv run fred pull UNRATE --limit 12 --sort-order desc
```

Show command help:

```bash
uv run fred --help
```

## Textual interface

Launch the interactive explorer:

```bash
uv run fred tui
```

In the TUI:
- Type a query and press Enter (or click Search).
- Select a result row to view description, availability, and recent observations.
- Use **Export CSV** to open a path prompt (prefilled with a suggested filename) and write all available observations.
- Press `q` to quit.