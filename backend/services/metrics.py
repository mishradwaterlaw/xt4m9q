"""
backend/services/metrics.py
─────────────────────────────────────────────────────────────────────────────
Pure mathematical functions for forecast accuracy metrics.
No I/O, no database access, no business logic — just math on aligned pairs.

All functions accept a list of (forecast, actual) float tuples.
The caller (routers/accuracy.py) is responsible for:
  - fetching actuals and forecasts via the elexon service
  - aligning them by startTime before passing here

METRIC EXPLAINERS (for the tech review):

MAE — Mean Absolute Error
  mean(|forecast - actual|)
  Intuition: the average MW you are wrong by. Easy to explain to a non-
  technical client: "on average, we were off by 312 MW per hour."

RMSE — Root Mean Square Error
  sqrt(mean((forecast - actual)^2))
  Intuition: penalises large errors more than small ones because of the
  squaring. If RMSE >> MAE, there are occasional very bad forecasts
  dragging the score up. A useful diagnostic: "our average error is
  300 MW but RMSE is 500 MW, so there are some bad outlier days."

MAPE — Mean Absolute Percentage Error
  mean(|forecast - actual| / actual) * 100
  Intuition: percentage error, easier to compare across different scales.
  Critical edge case: if actual is near 0 (calm wind), the division
  produces infinity or misleadingly enormous percentages. We exclude any
  slot where actual < MAPE_THRESHOLD_MW and report the excluded count
  transparently in the API response — not silently dropped.
"""

import math
from typing import NamedTuple

# Slots with actual generation below this threshold (MW) are excluded from
# MAPE to avoid division by near-zero values. Wind can genuinely be near 0
# during calm periods; including those slots makes MAPE meaningless.
# 5 MW is a deliberately conservative threshold — low enough not to exclude
# legitimate low-wind readings, high enough to avoid numerical instability.
MAPE_THRESHOLD_MW: float = 5.0


class DayMetrics(NamedTuple):
    mae: float
    rmse: float
    mape: float             # NaN if every slot was excluded
    mape_excluded_slots: int
    mean_bias: float        # mean(forecast - actual); positive = overestimate


# ─────────────────────────────────────────────────────────────────────────────
# Individual metric functions
# ─────────────────────────────────────────────────────────────────────────────

def compute_mae(pairs: list[tuple[float, float]]) -> float:
    """Mean Absolute Error in MW. Returns 0.0 for an empty list."""
    if not pairs:
        return 0.0
    return sum(abs(f - a) for f, a in pairs) / len(pairs)


def compute_rmse(pairs: list[tuple[float, float]]) -> float:
    """Root Mean Square Error in MW. Returns 0.0 for an empty list."""
    if not pairs:
        return 0.0
    return math.sqrt(sum((f - a) ** 2 for f, a in pairs) / len(pairs))


def compute_mape(
    pairs: list[tuple[float, float]],
    threshold: float = MAPE_THRESHOLD_MW,
) -> tuple[float, int]:
    """
    Mean Absolute Percentage Error (%).

    Slots where actual < threshold are excluded entirely to avoid division
    by near-zero values. The number of excluded slots is returned alongside
    the MAPE so the API response can report it transparently.

    Returns:
      (mape_percent, excluded_slot_count)
      mape_percent is float('nan') if all slots were excluded.
    """
    valid = [(f, a) for f, a in pairs if a >= threshold]
    excluded = len(pairs) - len(valid)

    if not valid:
        return (float("nan"), excluded)

    mape = sum(abs(f - a) / a for f, a in valid) / len(valid) * 100.0
    return (mape, excluded)


def compute_mean_bias(pairs: list[tuple[float, float]]) -> float:
    """
    Mean signed error: mean(forecast - actual).
    Positive → systematic overestimate. Negative → systematic underestimate.
    Used to generate the 'insight' sentence in the accuracy response.
    """
    if not pairs:
        return 0.0
    return sum(f - a for f, a in pairs) / len(pairs)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

def compute_all(pairs: list[tuple[float, float]]) -> DayMetrics:
    """Compute all metrics in one call. Returns a DayMetrics NamedTuple."""
    mape, excluded = compute_mape(pairs)
    return DayMetrics(
        mae=compute_mae(pairs),
        rmse=compute_rmse(pairs),
        mape=mape,
        mape_excluded_slots=excluded,
        mean_bias=compute_mean_bias(pairs),
    )
