"""
scripts/explore_elexon.py
─────────────────────────────────────────────────────────────────────────────
Standalone exploration script — NOT part of the application.
Purpose: Fetch raw data from both Elexon BMRS endpoints for January 15, 2025
         and pretty-print the first 5 records from each so we can verify:
           * Field names match what the data layer will depend on
           * publishTime format (for gate closure filtering)
           * startTime format (for delivery date alignment)
           * generation values look plausible (MW scale)

Run from project root:
    py scripts/explore_elexon.py
"""

import requests
from datetime import datetime, timezone

BASE_URL      = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
DELIVERY_DATE = "2025-01-15"   # The day we're buying power FOR
D_MINUS_1     = "2025-01-14"   # The day the purchase decision is MADE
SEP           = "-" * 72


def pretty(records: list, n: int = 5) -> None:
    """Print the first n records, one field per line for readability."""
    for i, rec in enumerate(records[:n], start=1):
        print(f"  Record {i}:")
        for key, val in rec.items():
            print(f"    {key:<22} {val}")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# 1.  FUELHH — Wind generation ACTUALS for the delivery date
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  FUELHH  |  Actuals  |  Delivery date: {DELIVERY_DATE}")
print(SEP)

r_actuals = requests.get(
    f"{BASE_URL}/FUELHH",
    params={
        "settlementDateFrom": DELIVERY_DATE,
        "settlementDateTo":   DELIVERY_DATE,
        "format":             "json",
    },
    timeout=30,
)
print(f"URL    : {r_actuals.url}")
print(f"Status : {r_actuals.status_code}")

all_records = r_actuals.json().get("data", [])
fuel_types  = sorted(set(r.get("fuelType", "?") for r in all_records))
wind_records = [r for r in all_records if r.get("fuelType") == "WIND"]

print(f"Total records (all fuels) : {len(all_records)}")
print(f"Fuel types present        : {fuel_types}")
print(f"WIND records only         : {len(wind_records)}")
print()
print("First 5 WIND records:")
pretty(wind_records, n=5)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  WINDFOR — Wind generation FORECASTS published on D-1
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  WINDFOR  |  Forecasts published on D-1: {D_MINUS_1}")
print(SEP)

r_forecast = requests.get(
    f"{BASE_URL}/WINDFOR",
    params={
        "publishDateTimeFrom": f"{D_MINUS_1}T00:00:00Z",
        "publishDateTimeTo":   f"{D_MINUS_1}T23:59:59Z",
        "format":              "json",
    },
    timeout=30,
)
print(f"URL    : {r_forecast.url}")
print(f"Status : {r_forecast.status_code}")

forecast_records = r_forecast.json().get("data", [])
pub_times        = sorted(set(r["publishTime"] for r in forecast_records))

print(f"Total records returned : {len(forecast_records)}")
print(f"Distinct publishTimes  : {len(pub_times)}  (= number of forecast vintages)")
print("  publishTime values:")
for pt in pub_times:
    count = sum(1 for r in forecast_records if r["publishTime"] == pt)
    print(f"    {pt}   ({count} records in this vintage)")

print()
print("First 5 records (any vintage):")
pretty(forecast_records, n=5)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Gate closure filter — transparent two-pass demo, no abstractions
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  Gate closure filter demo  |  Cutoff: {D_MINUS_1}T23:00:00Z")
print(SEP)

GATE_CUTOFF = datetime(2025, 1, 14, 23, 0, 0, tzinfo=timezone.utc)


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# Pass 1: find the latest publishTime strictly before gate closure
eligible = [parse_dt(pt) for pt in pub_times if parse_dt(pt) < GATE_CUTOFF]

if not eligible:
    print("ERROR: No forecast vintages found before gate closure — check D-1 date.")
else:
    chosen_vintage    = max(eligible)
    chosen_vintage_str = chosen_vintage.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Eligible vintages before cutoff : {len(eligible)}")
    print(f"Chosen vintage (latest eligible): {chosen_vintage_str}")

    # Pass 2: keep only startTime slots on the delivery date
    day_start = datetime(2025, 1, 15,  0,  0, 0, tzinfo=timezone.utc)
    day_end   = datetime(2025, 1, 15, 23, 30, 0, tzinfo=timezone.utc)

    chosen_records = [
        r for r in forecast_records
        if r["publishTime"] == chosen_vintage_str
        and day_start <= parse_dt(r["startTime"]) <= day_end
    ]

    print(f"Records for delivery date {DELIVERY_DATE}: {len(chosen_records)}")
    print(f"(Expected: 48 — one per 30-min slot)")
    print()
    print("First 5 records of chosen forecast vintage:")
    pretty(chosen_records, n=5)

print(SEP)
print("Exploration complete.\n")
