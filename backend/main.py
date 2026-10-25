"""
backend/main.py
─────────────────────────────────────────────────────────────────────────────
FastAPI application entry point.

Responsibilities:
  - Instantiate the FastAPI app with metadata (title, version)
  - Configure CORS so the React frontend can call this API
  - Register all three routers under the /api prefix
  - Initialise SQLite tables on startup via a lifespan handler
  - Expose a /health endpoint for Railway/Render health checks

CORS configuration:
  Origins are read from the CORS_ORIGINS config constant, which is itself
  parsed from the CORS_ORIGINS environment variable (see config.py).
  This means dev, Docker, and production all use the same code — only
  the .env file changes.

Startup vs. on-first-request DB init:
  Tables are created in the lifespan handler, not lazily on the first API
  request. This means the app fails fast and visibly if SQLite is broken
  (e.g. wrong DB_PATH, disk full) rather than failing on a user request
  with a cryptic 500 error. It also means /health can confirm DB access
  immediately after the process starts.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from routers import actuals, accuracy, forecast
from services.elexon import check_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — runs once at startup and once at shutdown
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialise resources on startup, release on shutdown.

    Using the lifespan pattern (FastAPI >= 0.93) rather than the deprecated
    @app.on_event("startup") decorator. Any failure here (e.g. can't create
    SQLite file) raises immediately and prevents the app from starting,
    which is the correct behaviour — fail fast, fail loudly.
    """
    logger.info("Starting up — initialising SQLite database tables")
    init_db()
    logger.info("Database ready. CORS origins: %s", CORS_ORIGINS)
    yield
    logger.info("Shutting down")


# ─────────────────────────────────────────────────────────────────────────────
# App instantiation
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Wind Forecast Accuracy API",
    description=(
        "Serves wind generation actuals and day-ahead forecasts from the "
        "Elexon BMRS API, with accuracy metrics (MAE, RMSE, MAPE) for "
        "January 2026. Implements UK day-ahead gate closure filtering: "
        "forecasts are selected based on publishTime < 23:00 on D-1."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# CORS middleware
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],          # this API is read-only
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(actuals.router,  prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(accuracy.router, prefix="/api")


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
def health():
    """
    Liveness/readiness probe for Railway, Render, and Docker health checks.

    Returns 200 {"status": "ok", "db": "connected"} when everything is healthy.
    Returns 503 {"status": "degraded", "db": "unreachable"} if SQLite fails.

    This endpoint is production-aware: a load balancer or deployment platform
    will stop sending traffic to an instance that returns 503 here.
    """
    db_ok = check_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "db":     "connected" if db_ok else "unreachable",
    }
