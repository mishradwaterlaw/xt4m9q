# Wind Forecast Accuracy Dashboard

A full-stack application that retrieves wind generation forecasts and actuals from the [Elexon BMRS API](https://developer.data.elexon.co.uk/), computes accuracy metrics (MAE, RMSE, MAPE, signed bias) for every day of January 2026, and presents the results in an interactive React dashboard.

Built as a hiring challenge to demonstrate end-to-end engineering: data pipeline, API design, metric computation, frontend visualisation, containerisation, and deployment.

---

## Deployed Application

- **Frontend:** [Frontend URL — to be added after deployment]
- **Backend API:** [Backend URL — to be added after deployment]
- **API docs (Swagger):** [Backend URL — to be added after deployment]/docs

---

## Directory Structure

```
challenge/
├── backend/                    # FastAPI application
│   ├── main.py                 # App entry point: CORS, routers, lifespan DB init, /health
│   ├── config.py               # Environment config: DB_PATH, CORS, gate closure hour
│   ├── requirements.txt        # Python dependencies with minimum version pins
│   ├── Dockerfile              # python:3.11-slim, layer-cached pip install, uvicorn CMD
│   ├── routers/
│   │   ├── actuals.py          # GET /api/actuals?date= — hourly wind actuals
│   │   ├── forecast.py         # GET /api/forecast?date= — day-ahead wind forecast
│   │   └── accuracy.py         # GET /api/accuracy — full-month MAE/RMSE/MAPE
│   └── services/
│       ├── elexon.py           # Elexon HTTP client, SQLite cache, downsampling, gate closure filter
│       └── metrics.py          # Pure math: MAE, RMSE, MAPE (with near-zero guard), mean bias
│
├── frontend/                   # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── types/index.ts      # Shared TypeScript interfaces for all API responses
│   │   ├── services/api.ts     # Typed API client with generic request<T> helper
│   │   ├── hooks/useApi.ts     # Generic useApi<T> hook with AbortController
│   │   ├── utils/format.ts     # formatMW / formatPct display helpers
│   │   ├── components/
│   │   │   ├── Navbar.tsx          # Top nav with live /health status indicator
│   │   │   ├── ForecastChart.tsx   # Dual-line Recharts chart (forecast vs actual)
│   │   │   ├── AccuracyCharts.tsx  # Three bar charts (MAE, RMSE, MAPE) + tier colouring
│   │   │   └── SummaryCards.tsx    # KPI summary card with optional delta arrow
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx   # Date picker, peak metrics, ForecastChart with vintage badge
│   │   │   └── Accuracy.tsx    # Monthly KPIs + daily bar charts wired to /api/accuracy
│   │   ├── App.tsx             # React Router setup (/ and /accuracy routes)
│   │   └── main.tsx            # React 18 createRoot entry point
│   ├── nginx.conf              # SPA fallback (try_files), gzip, /api/ + /health proxy
│   ├── Dockerfile              # Two-stage: node:20-slim builder then nginx:alpine server
│   ├── tsconfig.json           # strict: true, noUnusedLocals, noUnusedParameters
│   └── vite.config.ts          # Dev server on :3000, proxy /api to :8000
│
├── docker-compose.yml          # Orchestrates backend + frontend; sqlite_data named volume
├── .env.example                # Template for all required environment variables
├── .gitignore                  # Excludes .env, __pycache__, node_modules, *.db, dist/
└── README.md                   # This file
```

---

## How to Start the Application

### Method 1: Docker (recommended — single command)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
# From the project root:
docker compose up --build
```

This builds both images and starts both services. On first boot this takes ~2 minutes (pulling base images, running `npm ci` inside the builder). Subsequent starts are instant because layers are cached.

**Expected URLs once running:**

| Service | URL |
|---|---|
| Frontend (React) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

To stop:
```bash
docker compose down
```

---

### Method 2: Local development (hot reload)

#### Backend

Requires Python 3.11+.

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Copy environment template and adjust if needed
cp ../.env.example ../.env

# Start FastAPI with hot reload
uvicorn main:app --reload --port 8000
```

Backend available at http://localhost:8000. Interactive API docs at http://localhost:8000/docs.

#### Frontend

Requires Node.js 20+.

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

Frontend available at http://localhost:3000. The Vite dev server proxies `/api/` and `/health` to `http://localhost:8000` automatically — no CORS configuration needed in local dev.

---

## Environment Variables

Copy `.env.example` to `.env` at the project root and fill in values for your environment.

| Variable | Description | Default |
|---|---|---|
| `FRONTEND_URL` | Deployed frontend URL — used by FastAPI for CORS | `http://localhost:3000` |
| `VITE_API_URL` | Deployed backend URL — used by React in production | (empty — Vite proxy handles local dev) |
| `DB_PATH` | Path to the SQLite cache file | `/data/cache.db` |
| `ELEXON_BASE_URL` | Root URL for the Elexon BMRS REST API | `https://data.elexon.co.uk/bmrs/api/v1` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000` |

> **Important:** Never commit `.env` to version control. `.gitignore` excludes it. `.env.example` is the safe template.

---

## Architecture Decisions

### 1. SQLite with lazy per-date caching — not always-fetching from Elexon

**Plain English:** Every time you ask for data, the app checks a local database first. If the data is already there from a previous request, it returns it instantly without calling the Elexon API. Only on the first ever request for a particular date does it make the network call.

**Technical:** The Elexon BMRS API has rate limits and occasional latency. Fetching all 31 days at startup would delay the app 60–90 seconds and fail entirely if any one date was unavailable. Lazy caching means the app starts instantly, individual date failures are isolated, and the demo experience is fast after the first load. SQLite was chosen over Redis or Postgres because it requires zero infrastructure: one file, no server, works identically locally and in a Railway container with a persistent volume.

The cache is validated by row count (`cache_metadata.row_count`): if a previous fetch was interrupted after storing only 20 of 48 expected records, the partial fetch is detected and the date is re-fetched cleanly.

---

### 2. Actuals downsampled to hourly — not forecasts interpolated to 30-minute

**Plain English:** The Elexon forecast data comes in hourly chunks (24 readings per day). The actual generation data comes in 30-minute chunks (48 readings per day). To compare them, one series needs to match the other's resolution. We averaged pairs of actual readings to get hourly actuals — we did not invent extra forecast data points.

**Technical:** Interpolating forecasts to 30-minute resolution would fabricate data the forecaster never published. Measuring the error of a fabricated forecast is epistemologically unsound. Averaging adjacent 30-minute MW readings (a power rate, not energy) correctly represents average power over the combined hour. The accuracy story — which errors are systematic, where spikes occur — does not change materially at hourly versus half-hourly resolution.

---

### 3. publishTime filtering and the 23:00 D-1 gate closure cutoff

**Plain English:** The UK electricity market has a rule: day-ahead purchase orders must be submitted before 11 PM the evening before delivery. Any forecast published after that time is not available to the buyer. To measure day-ahead forecast accuracy honestly, we must use the same forecast the buyer would have had — the most recent one published before 11 PM on the day before delivery.

**Technical:** Elexon publishes approximately 8 WINDFOR forecast runs per day, each covering a multi-day horizon (~73 records per run). The gate closure filter is a two-pass operation:

- **Pass 1 (vintage selection):** From all `publishTime` values on D-1, keep only those strictly before `23:00:00 UTC`. Select the maximum (latest eligible). Strict `<` is used because a forecast published exactly at 23:00:00 arrives simultaneously with gate closure and is not safely available.
- **Pass 2 (slot selection):** From the chosen vintage's records, keep only slots where `startTime` falls on delivery date D (00:00–23:00 UTC). WINDFOR vintages span ~3 days, so this filter isolates the 24 slots relevant to day D.

The chosen `vintage` and `gate_closure` are included in every `/api/forecast` response — a reviewer can verify the filter without reading source code.

---

### 4. Generic `useApi<T>` hook with AbortController — not fetch in components

**Plain English:** All data-fetching logic lives in one reusable hook, not scattered across individual pages. This means every API call in the app automatically handles loading states, error messages, and cancellation if the user navigates away before data arrives.

**Technical:** A generic `useApi<T>(fetcher, params, deps)` hook encapsulates the `useState`/`useEffect` lifecycle pattern once. Each call site passes a typed fetcher function and receives `{ data: T | null, isLoading, error, refetch }`. The `AbortController` created on each effect run is cancelled on cleanup — preventing React 18 strict-mode double-invoke race conditions and stale responses from previous requests overwriting current ones.

---

## AI Tools Used

AI assistance (Google Gemini via Antigravity IDE) was used during development of this project.

**What AI helped with:**
- Initial scaffolding of the FastAPI project structure and router layout
- Generating boilerplate TypeScript types and React component shells
- Suggesting the two-pass gate closure filter structure and documenting the domain rationale
- Writing the downsampling rationale comments in `elexon.py`
- Drafting this README

**What was reviewed and owned by the developer:**
- All domain logic decisions (gate closure interpretation, MAPE threshold, downsampling direction)
- The caching strategy choice (lazy SQLite vs eager fetch vs Redis)
- The `useApi<T>` generic hook design
- The metric formulas and their business interpretations
- All TypeScript type definitions and strict-mode compliance
- Docker and nginx configuration choices

AI tools accelerated implementation but every architectural decision, domain logic choice, and piece of code was reviewed, understood, and consciously chosen by the developer.

---

## API Reference

| Endpoint | Method | Parameters | Description |
|---|---|---|---|
| `/api/actuals` | GET | `date=YYYY-MM-DD` | Hourly wind generation actuals (downsampled from 30-min FUELHH, filtered fuelType=WIND) |
| `/api/forecast` | GET | `date=YYYY-MM-DD` | Day-ahead wind forecast with `vintage` and `gate_closure` |
| `/api/accuracy` | GET | — | Full-month MAE, RMSE, MAPE, signed bias for all 31 days of January 2026 |
| `/health` | GET | — | Liveness probe: `{"status": "ok", "db": "connected"}` |

All dates must fall within `2026-01-01` to `2026-01-31`. Dates outside this range return HTTP 400.

Interactive docs: http://localhost:8000/docs (local) or `[Backend URL]/docs` (deployed).
