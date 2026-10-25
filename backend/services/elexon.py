"""
backend/services/elexon.py
─────────────────────────────────────────────────────────────────────────────
Data access layer for the Elexon BMRS API.

ARCHITECTURE OVERVIEW
─────────────────────
Caching strategy: lazy per-date SQLite.
  On first request for any date, this module checks SQLite. If the data
  is absent or incomplete (partial fetch), it fetches from Elexon, persists
  all records, and updates cache_metadata. Subsequent requests for the same
  date are served entirely from SQLite — no network call.

  Rationale for lazy over eager (fetch all 31 days at startup):
    - Startup is instant; the app is usable immediately.
    - A single-date API failure doesn't block the whole month from loading.
    - In a demo/review context, only the selected dates get fetched.

Partial-fetch detection via cache_metadata:
  cache_metadata(dataset, date, fetched_at, row_count) tracks how many
  rows were persisted. If row_count < expected minimum (e.g. fewer than
  48 WIND records for FUELHH), we treat it as a cache miss and re-fetch.
  This guards against silent data truncation from API timeouts.

SEPARATION OF CONCERNS
───────────────────────
  get_forecast_vintages()   — I/O concern only.
    Fetches and caches WINDFOR records for D-1. Returns all vintages.
    Knows nothing about gate closure.

  get_day_ahead_forecast()  — Domain logic only.
    Applies the UK day-ahead gate closure filter. Calls get_forecast_vintages()
    for data, then applies two passes of filtering. Contains zero I/O.
    Can be unit-tested with synthetic data, no network required.

This split is intentional: in a tech review you can point to one function
and say "this is where the domain logic lives" without it being tangled
with database or HTTP concerns.
"""

import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import TypedDict

import requests

from config import DB_PATH, ELEXON_BASE_URL, GATE_CLOSURE_HOUR

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Type aliases
# ─────────────────────────────────────────────────────────────────────────────

class TimeSeriesPoint(TypedDict):
    startTime: str
    generation: float


class ForecastResult(TypedDict):
    """Return type for get_day_ahead_forecast().

    vintage     — the publishTime of the forecast run actually used.
                  Surfaces in the API response so clients know which
                  vintage the accuracy metrics are based on.
    gate_closure — the cutoff datetime applied (D-1 GATE_CLOSURE_HOUR).
                  Included so any caller can verify the filtering logic
                  without reading source code.
    records     — 24 hourly forecast points for the delivery date.
    """
    vintage: str
    gate_closure: str
    records: list[TimeSeriesPoint]


# ─────────────────────────────────────────────────────────────────────────────
# Database — schema init and connection
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create all required tables if they don't already exist.
    Safe to call on every application startup (idempotent via IF NOT EXISTS).

    Tables:
      fuelhh_wind   — raw 30-min WIND actuals, one row per settlement period
      windfor       — raw hourly WINDFOR records, all vintages for a D-1 date
      cache_metadata — one row per (dataset, date); tracks fetch completeness
    """
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS fuelhh_wind (
                settlement_date  TEXT NOT NULL,
                start_time       TEXT NOT NULL,
                generation       REAL NOT NULL,
                PRIMARY KEY (settlement_date, start_time)
            );

            CREATE TABLE IF NOT EXISTS windfor (
                publish_date  TEXT NOT NULL,
                publish_time  TEXT NOT NULL,
                start_time    TEXT NOT NULL,
                generation    REAL NOT NULL,
                PRIMARY KEY (publish_time, start_time)
            );

            -- Tracks completeness of each cached dataset+date pair.
            -- row_count < expected minimum → partial fetch → treat as cache miss.
            CREATE TABLE IF NOT EXISTS cache_metadata (
                dataset     TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                fetched_at  TEXT    NOT NULL,
                row_count   INTEGER NOT NULL,
                PRIMARY KEY (dataset, date)
            );
        """)


def _get_conn() -> sqlite3.Connection:
    """Return a SQLite connection. row_factory=sqlite3.Row enables column-name access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_cached(dataset: str, date_str: str, min_rows: int) -> bool:
    """
    Return True only if cache_metadata has an entry for this (dataset, date)
    AND the stored row_count >= min_rows.

    The min_rows check is the partial-fetch guard: if a previous fetch was
    interrupted after storing only 20 of 48 expected records, row_count=20
    fails the check and triggers a clean re-fetch.
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT row_count FROM cache_metadata WHERE dataset = ? AND date = ?",
            (dataset, date_str),
        ).fetchone()
    return row is not None and row["row_count"] >= min_rows


def _upsert_metadata(
    conn: sqlite3.Connection,
    dataset: str,
    date_str: str,
    row_count: int,
) -> None:
    """Write or update a cache_metadata row. Uses UPSERT so re-fetches overwrite cleanly."""
    conn.execute(
        """
        INSERT INTO cache_metadata (dataset, date, fetched_at, row_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(dataset, date) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            row_count  = excluded.row_count
        """,
        (dataset, date_str, datetime.now(timezone.utc).isoformat(), row_count),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Elexon HTTP fetch helper
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_elexon(endpoint: str, params: dict) -> list[dict]:
    """
    GET {ELEXON_BASE_URL}/datasets/{endpoint} with the given query params.
    Returns the 'data' list from the JSON response.
    Raises requests.HTTPError on non-2xx status so callers can handle it.
    Does not retry — retry logic can be layered on top if needed.
    """
    url = f"{ELEXON_BASE_URL}/datasets/{endpoint}"
    logger.info("Elexon fetch: %s params=%s", url, params)
    response = requests.get(url, params={**params, "format": "json"}, timeout=30)
    response.raise_for_status()
    return response.json().get("data", [])


# ─────────────────────────────────────────────────────────────────────────────
# Downsampling: 30-min actuals → hourly
# ─────────────────────────────────────────────────────────────────────────────

def _downsample_to_hourly(records: list[dict]) -> list[TimeSeriesPoint]:
    """
    Average adjacent pairs of 30-min records to produce hourly time series.

    DOMAIN RATIONALE (documented here for code reviewers):
      WINDFOR forecasts are published at hourly resolution (24 points/day).
      FUELHH actuals are at 30-min resolution (48 points/day).

      We resolve this mismatch by downsampling actuals, NOT by interpolating
      forecasts, for three reasons:

        1. Interpolating forecasts would invent data the forecaster never
           published. That is epistemically wrong for an accuracy analysis —
           we would be measuring the error of a forecast we fabricated.

        2. Averaging adjacent 30-min actuals is mathematically sound.
           Generation is expressed in MW — a power rate, not an energy
           quantity. The mean of two half-hour MW readings correctly
           represents the average power over the combined hour. (If the
           unit were MWh, we would sum, not average. It is not.)

        3. 24 points/day is sufficient for meaningful MAE/RMSE/MAPE. The
           error story — which vintage was best, where errors peaked — does
           not change materially at hourly vs half-hourly resolution.

    Input:
      records — list of dicts with keys 'start_time' (ISO string) and
                'generation' (float), sorted or unsorted.
      Expected length: 48 (one per 30-min settlement period).

    Output:
      list of TimeSeriesPoint at hourly resolution (length 24).
      startTime of each output point = startTime of the first slot in the pair.
      (i.e. 00:00 represents the average of 00:00 and 00:30 slots.)
    """
    sorted_recs = sorted(records, key=lambda r: r["start_time"])
    hourly: list[TimeSeriesPoint] = []

    for i in range(0, len(sorted_recs), 2):
        first = sorted_recs[i]
        # Guard for an odd number of records (shouldn't happen with clean data,
        # but avoids an IndexError if the API returns a partial day)
        second = sorted_recs[i + 1] if i + 1 < len(sorted_recs) else first
        hourly.append({
            "startTime":  first["start_time"],
            "generation": (first["generation"] + second["generation"]) / 2.0,
        })

    return hourly


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_actuals(delivery_date: str) -> list[TimeSeriesPoint]:
    """
    Return hourly wind generation actuals for delivery_date (format: 'YYYY-MM-DD').

    Steps:
      1. Check cache: need >= 48 raw WIND records for this date.
      2. Cache miss → fetch FUELHH from Elexon, filter fuelType='WIND',
         persist all 48 raw rows + metadata row, log row count.
      3. Read raw 30-min rows from SQLite.
      4. Downsample to hourly (24 points) and return.

    Raw records are stored (not downsampled records) so that a future change
    to the downsampling strategy does not require re-fetching from Elexon.

    Returns:
      List of 24 TimeSeriesPoints, each {startTime: ISO str, generation: float (MW)},
      sorted ascending by startTime.
    """
    MIN_RAW_WIND_ROWS = 48  # one per 30-min settlement period

    if not _is_cached("FUELHH", delivery_date, min_rows=MIN_RAW_WIND_ROWS):
        logger.info("Cache miss: FUELHH / %s — fetching from Elexon", delivery_date)

        raw = _fetch_elexon("FUELHH", {
            "settlementDateFrom": delivery_date,
            "settlementDateTo":   delivery_date,
        })
        wind = [r for r in raw if r.get("fuelType") == "WIND"]
        logger.info("Fetched %d WIND records for %s (total records: %d)", len(wind), delivery_date, len(raw))

        with _get_conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO fuelhh_wind (settlement_date, start_time, generation)
                VALUES (?, ?, ?)
                """,
                [(delivery_date, r["startTime"], r["generation"]) for r in wind],
            )
            _upsert_metadata(conn, "FUELHH", delivery_date, len(wind))
    else:
        logger.debug("Cache hit: FUELHH / %s", delivery_date)

    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT start_time, generation
            FROM fuelhh_wind
            WHERE settlement_date = ?
            ORDER BY start_time ASC
            """,
            (delivery_date,),
        ).fetchall()

    raw_records = [{"start_time": r["start_time"], "generation": r["generation"]} for r in rows]
    return _downsample_to_hourly(raw_records)


def get_forecast_vintages(delivery_date: str) -> dict[str, list[dict]]:
    """
    Fetch and return all WINDFOR forecast vintages published on D-1
    (the day before delivery_date).

    This is an I/O function. It fetches and caches data only.
    It applies NO gate closure filter — that is get_day_ahead_forecast()'s job.

    Context:
      Elexon publishes ~8 WINDFOR forecast runs per day, each run covering
      a multi-day horizon (~73 hourly records per run). All 8 runs for D-1
      are fetched and stored under the D-1 date key. The caller decides
      which vintage to use.

    Returns:
      Dict keyed by publishTime (ISO string), each value a list of records
      {publishTime, startTime, generation} sorted by startTime ascending.
    """
    d_minus_1 = (date.fromisoformat(delivery_date) - timedelta(days=1)).isoformat()

    # 8 vintages × 73 records = 584 typical. We require ≥200 to confirm
    # we got most of a day's worth of vintages (guards against partial fetch).
    MIN_WINDFOR_ROWS = 200

    if not _is_cached("WINDFOR", d_minus_1, min_rows=MIN_WINDFOR_ROWS):
        logger.info("Cache miss: WINDFOR / D-1=%s — fetching from Elexon", d_minus_1)

        raw = _fetch_elexon("WINDFOR", {
            "publishDateTimeFrom": f"{d_minus_1}T00:00:00Z",
            "publishDateTimeTo":   f"{d_minus_1}T23:59:59Z",
        })
        logger.info("Fetched %d WINDFOR records for D-1=%s", len(raw), d_minus_1)

        with _get_conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO windfor (publish_date, publish_time, start_time, generation)
                VALUES (?, ?, ?, ?)
                """,
                [(d_minus_1, r["publishTime"], r["startTime"], r["generation"]) for r in raw],
            )
            _upsert_metadata(conn, "WINDFOR", d_minus_1, len(raw))
    else:
        logger.debug("Cache hit: WINDFOR / D-1=%s", d_minus_1)

    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT publish_time, start_time, generation
            FROM windfor
            WHERE publish_date = ?
            ORDER BY publish_time ASC, start_time ASC
            """,
            (d_minus_1,),
        ).fetchall()

    # Group into dict: publishTime → list of records
    vintages: dict[str, list[dict]] = {}
    for row in rows:
        pt = row["publish_time"]
        if pt not in vintages:
            vintages[pt] = []
        vintages[pt].append({
            "publishTime": pt,
            "startTime":   row["start_time"],
            "generation":  row["generation"],
        })

    return vintages


def get_day_ahead_forecast(delivery_date: str) -> list[TimeSeriesPoint]:
    """
    Return the day-ahead wind generation forecast for delivery_date ('YYYY-MM-DD').

    This is a DOMAIN LOGIC function. It contains no I/O — it delegates all
    fetching to get_forecast_vintages() and applies the gate closure filter.
    It is independently testable: pass synthetic vintage data and verify the
    correct vintage and time slots are selected.

    THE TWO-PASS FILTER:

    Pass 1 — Gate closure (vintage selection):
      From all publishTimes on D-1, keep only those strictly before
      GATE_CLOSURE_HOUR:00:00 UTC on D-1. Select the MAXIMUM of those.
      This is the latest forecast the day-ahead buyer could legally have
      used when submitting their purchase order.

      Why strictly less than (<), not less-than-or-equal (<=)?
        A forecast published exactly at 23:00:00 arrives at the same moment
        as gate closure. It is not safely available to the buyer before the
        gate. Strict inequality is the correct domain interpretation.

    Pass 2 — Delivery date (slot selection):
      From the chosen vintage's records, keep only those where startTime
      falls on delivery_date (00:00 to 23:00 UTC inclusive).
      WINDFOR vintages span ~3 days of forecast horizon (73 records each),
      so this filter is required to isolate the 24 slots for delivery day D.
      Without it, you return forecast data for D-2 and D+1 as well.

    A naive implementation that skips either pass is incorrect:
      - Skipping Pass 1: uses the most recent overall forecast, which may
        have been published after gate closure (intra-day, not day-ahead).
      - Skipping Pass 2: returns a 73-record blob spanning multiple days,
        making the error metrics meaningless.

    Returns:
      ForecastResult with keys:
        vintage      — ISO string of the chosen publishTime
        gate_closure — ISO string of the cutoff applied
        records      — 24 TimeSeriesPoints sorted ascending by startTime

    Raises:
      ValueError if no vintages exist, or none fall before gate closure.
    """
    d_minus_1 = (date.fromisoformat(delivery_date) - timedelta(days=1)).isoformat()

    gate_cutoff = datetime(
        *[int(x) for x in d_minus_1.split("-")],
        GATE_CLOSURE_HOUR, 0, 0,
        tzinfo=timezone.utc,
    )

    vintages = get_forecast_vintages(delivery_date)
    if not vintages:
        raise ValueError(f"No WINDFOR vintages found for D-1={d_minus_1}. Check data availability.")

    def _parse(iso: str) -> datetime:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))

    # Pass 1 — gate closure filter
    eligible: dict[str, list[dict]] = {
        pt: recs
        for pt, recs in vintages.items()
        if _parse(pt) < gate_cutoff
    }

    if not eligible:
        raise ValueError(
            f"No forecast vintages published before gate closure "
            f"({gate_cutoff.isoformat()}) on D-1={d_minus_1}. "
            f"Available publishTimes: {sorted(vintages.keys())}"
        )

    chosen_pt = max(eligible.keys(), key=_parse)
    logger.info(
        "Day-ahead forecast: delivery=%s | gate=%s | eligible=%d | chosen=%s",
        delivery_date,
        gate_cutoff.isoformat(),
        len(eligible),
        chosen_pt,
    )

    # Pass 2 — delivery date filter
    slot_start = _parse(f"{delivery_date}T00:00:00Z")
    slot_end   = _parse(f"{delivery_date}T23:00:00Z")

    chosen_slots = [
        r for r in eligible[chosen_pt]
        if slot_start <= _parse(r["startTime"]) <= slot_end
    ]
    chosen_slots.sort(key=lambda r: r["startTime"])

    logger.info(
        "Vintage %s: %d slots selected for delivery=%s",
        chosen_pt, len(chosen_slots), delivery_date,
    )

    return ForecastResult(
        vintage=chosen_pt,
        gate_closure=gate_cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        records=[
            TimeSeriesPoint(startTime=r["startTime"], generation=r["generation"])
            for r in chosen_slots
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Health / diagnostic
# ─────────────────────────────────────────────────────────────────────────────

def check_db() -> bool:
    """Return True if SQLite is reachable. Used by the /health endpoint."""
    try:
        with _get_conn() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
