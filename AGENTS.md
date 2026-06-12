# AGENTS.md

**Generated:** 2026-05-31  
**Commit:** 311194e  
**Branch:** feat/backend-initial

Gas price prediction + timing advisor. Python backend (EIA API, analytics) + vanilla JS frontend (React 18 zero-build).

---

## Running the frontend

No build step. Serve `frontend/` with any static file server:

```bash
python3 -m http.server 8080 --directory frontend
```

Open `http://localhost:8080`. `file://` also works for most features (IP geolocation will fall back silently).

---

## Backend setup

```bash
# 1. Create venv
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Copy and fill in env vars
cp .env.example .env
# Edit .env with your API keys

# 4. Initialise the database
python backend/db.py
```

### Required environment variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `EIA_API_KEY` | Yes (US prices) | Free at eia.gov/opendata/register.php |
| `NEWS_API_KEY` | Optional | Free tier at newsapi.org |
| `ANTHROPIC_API_KEY` | Optional | For LLM news analysis; heuristic fallback if absent |
| `REDIS_URL` | Optional | Default `redis://localhost:6379/0`; in-memory cache used if Redis unreachable |
| `DB_PATH` | Optional | Default `data/shouldigetgas.db` |
| `DATA_JSON_PATH` | Optional | Default `frontend/data/data.json` |

---

## Running the pipeline

### One-off (useful for testing)

```bash
# Collect prices for all regions (or specify a subset)
python backend/price_collector.py
python backend/price_collector.py --regions ca tx on ab

# Run analytics and write data.json
python backend/snapshot.py
python backend/snapshot.py ca tx on

# Test data gathering only (no DB write)
python backend/analytics/gather.py
```

### Continuous (production)

```bash
# Runs price collection every 30 min + analytics every 6h
python backend/scheduler.py
```

### Cron-based

```
# /etc/cron.d/shouldigetgas
*/30 * * * *  user  /path/to/shouldigetgas/scripts/run_collector.sh
0 */6 * * *   user  /path/to/shouldigetgas/scripts/run_analytics.sh
```

---

## Architecture

### Two-speed cached-data model (Approach A)

The backend writes `frontend/data/data.json` directly. No API server. The frontend's `fetch('data/data.json')` call works unchanged.

**Part 1 — Price Collector** (`backend/price_collector.py`, every 30 min):
- US prices: EIA API v2 (`/petroleum/pri/gnd/data/` with `facets[stateid][]`) + PADD fallback
- Canada prices: Ontario CKAN API, NRCAN scraper, GasBuddy fallback
- Stores raw station prices in `stations` SQLite table
- Updates `regional_snapshot` table with fresh price fields

**Part 2 — Analytics Engine** (`backend/snapshot.py`, every 6 h):
- Module A (`analytics/gather.py`): EIA WTI crude, refinery utilization, NewsAPI headlines
- Module B (`analytics/news_analysis.py`): Claude Haiku → `why`/`advice`/`verdict`; VADER fallback
- Module C (`analytics/predictor.py`): Holt exponential smoothing → price direction, `bestDayIdx`, trend
- Module D (`analytics/breakdown.py`): Per-region `{crude, refining, taxes, dist}` breakdown
- Writes assembled payload to `frontend/data/data.json`

### Data storage

```
data/shouldigetgas.db  — SQLite
  stations            raw station-level prices
  regional_snapshot   current per-region analytics (1:1 with JSON output)
  crude_prices        WTI/Brent history
  news_cache          processed news articles
  prediction_log      audit trail
```

Redis is optional — all cache values fall back to an in-memory TTL dict.

### Region scope

62 regions total:
- **US:** 50 states + DC (51 regions), prices in $/gal, EIA stateid codes
- **Canada:** 10 provinces + "Northern Canada" (territories combined), prices in $/L CAD

### Frontend changes

- `js/data.js`: `detectRegionFromIP()` now covers all 50 US states + DC + all Canadian provinces; defaults to Ontario for unmatched Canadian IPs
- `js/components.js`: `LocationSheet` accepts a `regions` prop (uses loaded data, not hardcoded placeholder); `GasPriceDisplay` shows `/L` for Canadian regions
- `js/app.js`: `wti` state maintained and passed to `ContextContent`/`ContextSheet`

### Region data shape (extended)

Each region now also includes:
- `country`: `"US"` | `"CA"`
- `unit`: `"gal"` | `"L"` (drives `/gal` vs `/L` display in the frontend)
- `advice`: short action phrase ≤30 chars (e.g., `"Fill up today"`, `"Hold until Thu"`)
- `weekDeltaDir`: `"up"` | `"down"` | `"flat"` — direction of `weekDelta`. Deltas under
  ½¢/unit are snapped to `0.0` and flagged `"flat"` in `snapshot.py` so the frontend
  never renders a directional zero (e.g. `↓ −0¢`). Optional; the frontend derives it
  via a 0.5¢ threshold when absent.

---

## Adding a new region

1. Add to `US_REGIONS` or `CA_REGIONS` in `backend/config.py`
2. Add a baseline price to `BASELINE_PRICES` in `config.py`
3. Add the IP geolocation mapping to `regionMap` in `frontend/js/data.js`
4. Run `python backend/snapshot.py` — it will generate a new entry in `data.json`

---

## File structure

```
shouldigetgas/
├── .env.example          API key template
├── frontend/             Zero-build React 18 app
│   ├── data/data.json    Auto-generated by backend (Approach A)
│   └── js/
│       ├── data.js       Data model + detectRegionFromIP (all 62 regions)
│       ├── components.js Presentational components (unit-aware)
│       └── app.js        Root App + WTI state
├── backend/
│   ├── requirements.txt
│   ├── config.py         Region definitions, env vars, API endpoints
│   ├── db.py             SQLite schema + helpers
│   ├── cache.py          Redis + in-memory fallback
│   ├── price_collector.py Part 1: 30-min price updates
│   ├── snapshot.py       Part 2: analytics + data.json writer
│   ├── scheduler.py      APScheduler orchestration
│   └── analytics/
│       ├── gather.py     EIA crude + news fetching
│       ├── news_analysis.py LLM/heuristic why+advice generation
│       ├── predictor.py  Holt smoothing + verdict logic
│       └── breakdown.py  Cost breakdown percentages
├── data/
│   └── shouldigetgas.db  SQLite database (auto-created)
└── scripts/
    ├── run_collector.sh  Cron wrapper for price_collector.py
    └── run_analytics.sh  Cron wrapper for snapshot.py
```

---

## CONVENTIONS

### Region handling
- **Units ALWAYS match region type**: US regions = $/gal, Canadian regions = $/L CAD
- Region IDs: 2-letter lowercase (e.g., `ca`, `on`, `tx`) + special `north` for Canadian territories
- 62 regions total: 50 US states + DC + 10 CA provinces + 1 "Northern Canada" aggregate
- All region tuples in `backend/config.py` follow: `(id, display_name, abbr, city, api_key, [country])`

### Data flow
- **Cached-data model (Approach A)**: Backend writes `frontend/data/data.json` directly, no API server
- Part 1 (price_collector.py, 30 min): Updates `stations` + `regional_snapshot` tables
- Part 2 (snapshot.py, 6 h): Runs analytics modules A-D → writes `data.json`
- Frontend fetches `data/data.json` on load (works offline after first load)

### API keys
- **NEVER commit secrets** - all keys loaded from `.env` via `backend/config.py`
- Optional keys degrade graceful ly: NEWS_API → no headlines, ANTHROPIC_API → heuristic fallback, REDIS → in-memory cache

### Database
- SQLite only, no PostgreSQL. WAL mode enabled by default.
- Run `python backend/db.py` to init/migrate schema
- Tables: `stations`, `regional_snapshot`, `crude_prices`, `news_cache`, `prediction_log`

---

## ANTI-PATTERNS (THIS PROJECT)

- **Unit confusion**: NEVER mix $/gal and $/L - always check `region_unit(region_id)` or use region tuple's country field
- **Hardcoded region lists**: Region definitions live ONLY in `backend/config.py` (US_REGIONS, CA_REGIONS)
- **Breaking cached-data contract**: Frontend expects `data.json` at `frontend/data/data.json` - do NOT introduce API server without updating frontend fetch logic
- **Blocking on optional services**: Redis/NewsAPI/Anthropic failures must NOT crash pipeline - all have fallbacks

---

## HIERARCHY

```
./AGENTS.md                     (this file - project overview)
├── backend/AGENTS.md           (Python backend: collectors, schedulers, DB)
│   └── backend/analytics/AGENTS.md  (Analytics modules: gather, predict, analyze)
└── frontend/AGENTS.md          (React 18 zero-build frontend)
```

---

## NOTES
