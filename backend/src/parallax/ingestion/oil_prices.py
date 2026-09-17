"""EIA API fetcher for Brent and WTI daily spot oil prices."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

# Series IDs for the two benchmarks
BRENT_SERIES = "RBRTE"
WTI_SERIES = "RWTC"


async def fetch_oil_prices(
    api_key: str,
    *,
    series: str = BRENT_SERIES,
    start_date: date | None = None,
    end_date: date | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch daily spot prices from EIA API v2.

    Returns list of dicts with keys: period, value, series-id.
    """
    params: dict[str, Any] = {
        "api_key": api_key,
        "frequency": "daily",
        "data[0]": "value",
        "facets[series][]": series,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 60,
    }
    if start_date:
        params["start"] = start_date.isoformat()
    if end_date:
        params["end"] = end_date.isoformat()

    should_close = client is None
    client = client or httpx.AsyncClient(timeout=30.0)

    try:
        resp = await client.get(EIA_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if should_close:
            await client.aclose()

    rows = data.get("response", {}).get("data", [])
    logger.info("EIA: fetched %d %s price rows", len(rows), series)

    # Gap detection: EIA returns weekday-only data. If the latest row is more
    # than 3 days stale (covers a long weekend / federal holiday), warn so
    # callers can decide whether to treat the price as still-fresh.
    fetched_at = datetime.now(timezone.utc)
    latest_period: date | None = None
    if rows:
        latest_str = rows[0].get("period", "")
        try:
            latest_period = date.fromisoformat(latest_str)
        except (TypeError, ValueError):
            latest_period = None

    if latest_period is not None:
        reference = end_date or fetched_at.date()
        gap_days = (reference - latest_period).days
        if gap_days > 3:
            logger.warning(
                "EIA %s: latest price is %s (%d days stale vs reference %s); "
                "possible long weekend, holiday, or data outage.",
                series,
                latest_period.isoformat(),
                gap_days,
                reference.isoformat(),
            )

    # Attach a non-mutating staleness marker on the first row so callers that
    # peek at rows[0] can read it without an extra round-trip. Keeps the
    # public return type (list[dict]) intact.
    if rows:
        rows[0].setdefault("_fetched_at", fetched_at.isoformat())
        if latest_period is not None:
            rows[0].setdefault("_data_as_of", latest_period.isoformat())

    return rows


async def fetch_brent(api_key: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Convenience: fetch Brent spot prices."""
    return await fetch_oil_prices(api_key, series=BRENT_SERIES, **kwargs)


async def fetch_wti(api_key: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Convenience: fetch WTI spot prices."""
    return await fetch_oil_prices(api_key, series=WTI_SERIES, **kwargs)
