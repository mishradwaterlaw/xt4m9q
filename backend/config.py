"""
backend/config.py
─────────────────────────────────────────────────────────────────────────────
Central configuration for the Wind Forecast Accuracy Dashboard.

Every domain constant and every environment-specific value lives here.
No magic numbers or hardcoded strings appear in business logic — point to
this file during a tech review when asked "where do I change the gate
closure time?" or "how do I run this for February?".

Environment-specific values read from os.environ so the same codebase
works locally, in Docker, and on Railway/Render with no code changes.
"""

import os

# ─── Domain constants ──────────────────────────────────────────────────────

# UK day-ahead electricity market gate closure hour (24-hour clock, UTC).
# The EPEX SPOT UK day-ahead auction closes at approximately 22:00 on D-1,
# after which no new purchase orders may be submitted for the following day.
# We use 23:00 as a conservative industry-standard cutoff: any forecast with
# publishTime >= 23:00 on D-1 is considered unavailable to the day-ahead buyer.
# To change this (e.g. for intra-day analysis), update this single constant.
GATE_CLOSURE_HOUR: int = 23

# Analysis window.
# Driven by named constants so the data scope is visible in one place and
# trivially extensible — changing these two values covers the entire codebase.
DATE_RANGE_START: str = "2026-01-01"
DATE_RANGE_END:   str = "2026-01-31"

# Temporal resolution used for forecast-vs-actual alignment.
# WINDFOR forecasts are published at hourly resolution (24 points/day).
# FUELHH actuals are published at 30-min resolution (48 points/day).
# We resolve this mismatch by downsampling actuals to hourly — see
# services/elexon.py::_downsample_to_hourly() for the full rationale.
# Stored here so any future switch in strategy (e.g. interpolation) is
# visible as a config change, not buried in service logic.
RESOLUTION: str = "hourly"

# ─── Environment-specific values ───────────────────────────────────────────

# Root URL for the Elexon BMRS REST API (no trailing slash).
# Endpoints are appended as:  {ELEXON_BASE_URL}/datasets/{DATASET}
ELEXON_BASE_URL: str = os.getenv(
    "ELEXON_BASE_URL",
    "https://data.elexon.co.uk/bmrs/api/v1",
)

# Path to the SQLite cache file.
# In Docker: mount a named volume at this path to persist the cache across
# container restarts.  Example: docker run -v sqlite-data:/app/cache.db ...
DB_PATH: str = os.getenv("DB_PATH", "cache.db")

# Comma-separated allowed CORS origins for the FastAPI middleware.
# Must include the React dev server (localhost:3000) and the deployed
# Vercel URL once known.
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", os.getenv("FRONTEND_URL", "http://localhost:3000")).split(",")
    if o.strip()
]
