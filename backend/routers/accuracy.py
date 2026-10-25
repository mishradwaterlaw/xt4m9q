"""
backend/routers/accuracy.py
─────────────────────────────────────────────────────────────────────────────
GET /api/accuracy

Returns forecast accuracy metrics (MAE, RMSE, MAPE) for every day in the
configured analysis window (January 2026). No date parameter — always the
full month.

IMPORTANT — first-call latency:
  This endpoint triggers lazy cache population for any uncached dates.
  On a cold start (empty SQLite), it will make ~62 Elexon API calls
  (31 dates × 2 datasets). This takes approximately 60-90 seconds.
  Subsequent calls are served entirely from SQLite and respond in < 1s.
  Consider calling /api/actuals and /api/forecast for individual dates
  first if you want to pre-warm the cache before hitting this endpoint.

Response shape:
  {
    "monthly": {
      "mae":  float,   # MW
      "rmse": float,   # MW
      "mape": float    # %
    },
    "daily": [
      {
        "date":                 "2026-01-01",
        "mae":                  float,
        "rmse":                 float,
        "mape":                 float,
        "mape_excluded_slots":  int,
        "mean_bias":            float   # + = overestimate, - = underestimate
      },
      ...
    ],
    "insight": "Forecasts overestimated by 312 MW on average in January 2026"
  }

MAPE edge case (documented here for code reviewers):
  Slots where actual generation is below 5 MW are excluded from MAPE to
  avoid division by near-zero values. Wind can genuinely be near 0 during
  calm periods; those slots produce meaningless or infinite percentage errors.
  Excluded slots are counted per-day and surfaced in 'mape_excluded_slots'
  so the API response is transparent, not silently dropping data.
"""

import math
import logging
from datetime import date as Date, timedelta

from fastapi import APIRouter, HTTPException

from config import DATE_RANGE_END, DATE_RANGE_START
from services.elexon import get_actuals, get_day_ahead_forecast
from services.metrics import compute_all

router = APIRouter()
logger = logging.getLogger(__name__)

_RANGE_START = Date.fromisoformat(DATE_RANGE_START)
_RANGE_END   = Date.fromisoformat(DATE_RANGE_END)


def _date_range(start: Date, end: Date) -> list[Date]:
    """Inclusive date range, one step per day."""
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _align_pairs(
    actuals: list[dict],
    forecasts: list[dict],
) -> list[tuple[float, float]]:
    """
    Align actuals and forecasts by startTime, return (forecast, actual) pairs.

    Both series are hourly (24 points/day). Alignment is by exact ISO string
    match on startTime. Slots present in one series but not the other are
    silently dropped — partial coverage is better than a crash on missing data.
    """
    actual_map = {r["startTime"]: r["generation"] for r in actuals}
    pairs = []
    for rec in forecasts:
        st = rec["startTime"]
        if st in actual_map:
            pairs.append((rec["generation"], actual_map[st]))
    return pairs


def _safe_mean(values: list[float]) -> float:
    """Mean of a list, filtering out NaN values (from days with all slots excluded)."""
    valid = [v for v in values if not math.isnan(v)]
    return sum(valid) / len(valid) if valid else float("nan")


@router.get("/accuracy")
def get_accuracy():
    """
    Compute and return forecast accuracy metrics for all of January 2026.

    For each date in the analysis window:
      1. Fetch actuals via get_actuals()
      2. Fetch day-ahead forecast via get_day_ahead_forecast()
      3. Align on startTime
      4. Compute MAE, RMSE, MAPE (with MAPE near-zero guard)

    Monthly aggregates are simple means of daily values (not pooled across
    all 31×24 pairs), which is the standard approach for day-level reporting.

    The 'insight' string is computed from mean signed bias (not MAE) so it
    correctly distinguishes overestimation from underestimation — two very
    different business problems for a power purchaser.
    """
    daily_results = []
    all_pairs: list[tuple[float, float]] = []

    for d in _date_range(_RANGE_START, _RANGE_END):
        date_str = d.isoformat()
        try:
            actuals   = get_actuals(date_str)
            fc_result = get_day_ahead_forecast(date_str)
            forecasts = fc_result["records"]

            pairs = _align_pairs(actuals, forecasts)
            if not pairs:
                logger.warning("No aligned pairs for %s — skipping", date_str)
                continue

            metrics = compute_all(pairs)
            all_pairs.extend(pairs)

            daily_results.append({
                "date":                date_str,
                "mae":                 round(metrics.mae,  2),
                "rmse":                round(metrics.rmse, 2),
                "mape":                round(metrics.mape, 4) if not math.isnan(metrics.mape) else None,
                "mape_excluded_slots": metrics.mape_excluded_slots,
                "mean_bias":           round(metrics.mean_bias, 2),
            })

        except Exception as exc:
            logger.error("Failed to compute metrics for %s: %s", date_str, exc)
            # Include the error in the response so it's visible, not silently swallowed
            daily_results.append({
                "date":  date_str,
                "error": str(exc),
            })

    if not all_pairs:
        raise HTTPException(
            status_code=503,
            detail="No aligned data available for January 2026. Cache may be empty.",
        )

    # Monthly aggregates — mean of daily values
    valid_days    = [r for r in daily_results if "mae" in r]
    monthly_mae   = _safe_mean([r["mae"]  for r in valid_days])
    monthly_rmse  = _safe_mean([r["rmse"] for r in valid_days])
    monthly_mape  = _safe_mean([r["mape"] for r in valid_days if r.get("mape") is not None])

    # Insight: computed from pooled signed bias across all aligned pairs
    # Positive mean_bias → forecasts systematically overestimated
    # Negative mean_bias → forecasts systematically underestimated
    global_bias = sum(f - a for f, a in all_pairs) / len(all_pairs)
    direction   = "overestimated" if global_bias >= 0 else "underestimated"
    insight     = (
        f"Forecasts {direction} by {abs(global_bias):.0f} MW on average "
        f"in January 2026"
    )

    return {
        "monthly": {
            "mae":  round(monthly_mae,  2),
            "rmse": round(monthly_rmse, 2),
            "mape": round(monthly_mape, 4) if not math.isnan(monthly_mape) else None,
        },
        "daily":   daily_results,
        "insight": insight,
    }
