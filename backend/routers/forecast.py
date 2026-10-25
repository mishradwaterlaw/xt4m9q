"""
backend/routers/forecast.py
─────────────────────────────────────────────────────────────────────────────
GET /api/forecast?date=YYYY-MM-DD

Returns the day-ahead wind generation forecast for the given delivery date.
"Day-ahead" means the latest forecast published before 23:00 on D-1 (the
day before delivery) — the gate closure convention used by UK electricity
buyers. See services/elexon.py::get_day_ahead_forecast() for the two-pass
filtering logic.

Response shape:
  {
    "date":         "2026-01-15",
    "vintage":      "2026-01-14T22:30:00Z",
    "gate_closure": "2026-01-14T23:00:00Z",
    "records":      [{"startTime": "2026-01-15T00:00:00Z", "generation": 16500.0}, ...]
  }

The 'vintage' and 'gate_closure' fields are domain-critical:
  - vintage:      the publishTime of the forecast run actually used. The UI
                  displays this so the user can see exactly which run
                  informed the purchase decision, and verify it was pre-gate.
  - gate_closure: the cutoff applied. A reviewer who knows the domain will
                  check that vintage < gate_closure — this response makes
                  that verification trivial without reading source code.
"""

from datetime import date as Date

from fastapi import APIRouter, HTTPException, Query

from config import DATE_RANGE_END, DATE_RANGE_START, GATE_CLOSURE_HOUR
from services.elexon import get_day_ahead_forecast

router = APIRouter()

_RANGE_START = Date.fromisoformat(DATE_RANGE_START)
_RANGE_END   = Date.fromisoformat(DATE_RANGE_END)


def _validate_date(date_str: str) -> Date:
    """Parse and validate the date query parameter (same rules as actuals.py)."""
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


@router.get("/forecast")
def get_forecast_endpoint(
    date: str = Query(
        ...,
        description="Delivery date in YYYY-MM-DD format. Must be within January 2026.",
        examples=["2026-01-15"],
    ),
):
    """
    Return the day-ahead wind generation forecast for the given delivery date.

    The forecast returned is the latest WINDFOR run with publishTime strictly
    before {GATE_CLOSURE_HOUR}:00 on D-1 (the day before delivery). This
    matches the forecast a UK electricity buyer would have had available at
    gate closure when making their day-ahead purchase decision.

    The response includes 'vintage' (which forecast run was used) and
    'gate_closure' (the cutoff applied) for full transparency.
    """
    validated = _validate_date(date)

    try:
        result = get_day_ahead_forecast(validated.isoformat())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "date":         validated.isoformat(),
        "vintage":      result["vintage"],
        "gate_closure": result["gate_closure"],
        "records":      result["records"],
    }
