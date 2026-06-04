# FRED Research Overview (Quick Catch-Up)

This is a lightweight summary of what we learned while planning a Python console app for finding FRED data series.

## 1) FRED API structure

- Main API docs hub: https://fred.stlouisfed.org/docs/api/fred/
- FRED has:
  - **API v1**: series-level and endpoint-based retrieval (good for interactive search apps).
  - **API v2**: bulk workflows and full history retrieval.
- For this project, v1 endpoints are the practical starting point.

Useful endpoint docs:
- Series search: https://fred.stlouisfed.org/docs/api/fred/series_search.html
- Series metadata: https://fred.stlouisfed.org/docs/api/fred/series.html
- Series observations: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- API key info: https://fred.stlouisfed.org/docs/api/api_key.html

## 2) Categories (high-level domains)

- Categories page: https://fred.stlouisfed.org/categories
- Major top-level domains include:
  - Money, Banking, & Finance
  - Population, Employment, & Labor Markets
  - National Accounts
  - Production & Business Activity
  - Prices
  - International Data
  - U.S. Regional Data
  - Academic Data

Takeaway: categories are a good browse-first path when users don’t know exact series IDs.

## 3) What a FRED "series" is

- Series browser/tag page used: https://fred.stlouisfed.org/tags/series
- A **series** is a time series with a unique series ID (examples: `UNRATE`, `CPIAUCSL`, `GDP`).
- Series generally include:
  - Title
  - Units
  - Frequency
  - Seasonal adjustment
  - Date coverage and update recency

Takeaway: search results should show enough metadata for users to distinguish similar variants.

## 4) Releases and release calendar

- Releases page: https://fred.stlouisfed.org/releases/
- Release calendar page: https://fred.stlouisfed.org/releases/calendar

API docs that map to release workflows:
- All releases: https://fred.stlouisfed.org/docs/api/fred/releases.html
- Dates across all releases: https://fred.stlouisfed.org/docs/api/fred/releases_dates.html
- Dates for one release: https://fred.stlouisfed.org/docs/api/fred/release_dates.html

Key nuance from docs:
- Release dates are source-published schedules and may not exactly match when data appears on FRED.
- `include_release_dates_with_no_data=true` can include future/scheduled dates.

## 5) Sources (data publishers)

- Sources page: https://fred.stlouisfed.org/sources
- A source is the originating provider (e.g., BLS, BEA, ECB, Fed entities, private providers, researchers), identified by source IDs.

Takeaway: source-first discovery is useful when users begin with the publisher instead of a keyword.

## 6) Practical app-planning implications

For a simple console app, the most useful discovery flows are:
1. **Keyword -> series search -> select series**
2. **Category -> series**
3. **Release -> series**
4. **Source -> releases/series**

Core API behavior to support early:
- API key configuration
- JSON responses (`file_type=json`)
- Pagination (`limit`, `offset`)
- Clear handling of API errors and empty results
