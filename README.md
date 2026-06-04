# agent-freddy

Simple MVP for exploring and pulling FRED data from the console.

## Setup

1. Get a FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
2. Set it in your shell:

```bash
export FRED_API_KEY="your_32_char_key"
```

## Click CLI

Search for series:

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

## Textual interface

Launch the interactive explorer:

```bash
uv run fred tui
```

In the TUI:
- Type a query and press Enter (or click Search).
- Select a result row to view description, availability, and recent observations.