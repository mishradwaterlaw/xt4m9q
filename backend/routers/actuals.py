"""
backend/routers/actuals.py
─────────────────────────────────────────────────────────────────────────────
GET /api/actuals?date=YYYY-MM-DD

Returns wind generation actuals (downsampled to hourly) for the given date.
Date must fall within the configured analysis window (DATE_RANGE_START to
DATE_RANGE_END). Requests outside that range get a 400 with a clear message
explaining the supported window — not a generic Pydantic validation error.

Response shape:
  {
    "date":       "2026-01-15",
    "resolution": "hourly",
    "records":    [{"startTime": "2026-01-15T00:00:00Z", "generation": 14456.5}, ...]
  }

The 'resolution' field is included explicitly so the frontend knows what
cadence to expect without guessing — no implicit contract between layers.
"""

from datetime import date as Date

from fastapi import APIRouter, HTTPException, Query

from config import DATE_RANGE_END, DATE_RANGE_START, RESOLUTION
from services.elexon import get_actuals

router = APIRouter()

_RANGE_START = Date.fromisoformat(DATE_RANGE_START)
_RANGE_END   = Date.fromisoformat(DATE_RANGE_END)


def _validate_date(date_str: str) -> Date:
    """
    Parse and validate the date query parameter.

    Raises HTTP 400 with a domain-specific message if:
      - the string is not a valid ISO date (YYYY-MM-DD)
      - the date is outside the configured analysis window
    """
    try:
        d = Date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid date format: '{date_str}'. "
                f"Expected YYYY-MM-DD (e.g. 2026-01-15)."
            ),
        )

    if not (_RANGE_START <= d <= _RANGE_END):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Date {date_str} is outside the supported analysis window. "
                f"This service covers {DATE_RANGE_START} to {DATE_RANGE_END} "
                f"(January 2026). Please request a date within that range."
            ),
        )
    return d


@router.get("/actuals")
def get_actuals_endpoint(
    date: str = Query(
        ...,
        description="Delivery date in YYYY-MM-DD format. Must be within January 2026.",
        examples=["2026-01-15"],
    ),
):
    """
    Return hourly wind generation actuals for the given settlement date.

    Data source: Elexon BMRS FUELHH dataset, filtered to fuelType=WIND,
    downsampled from 30-min to hourly resolution by averaging adjacent pairs.
    Results are cached in SQLite after the first fetch — subsequent calls
    for the same date are served from cache with no network request.
    """
    validated = _validate_date(date)
    records = get_actuals(validated.isoformat())

    return {
        "date":       validated.isoformat(),
        "resolution": RESOLUTION,
        "records":    records,
    }
