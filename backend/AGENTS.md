# backend/AGENTS.md

Python backend: price collection, caching, scheduling, DB.

---

## OVERVIEW

Two-speed pipeline: price_collector.py (30 min) → snapshot.py (6 h) → writes `frontend/data/data.json`.

---

## STRUCTURE

```
backend/
├── config.py          Region definitions (62 total), API endpoints, env vars
├── db.py              SQLite schema + helpers (run directly to init DB)
├── cache.py           Redis + in-memory fallback (graceful degradation)
├── price_collector.py Part 1: Fetch US (EIA) + Canada prices → update DB
├── snapshot.py        Part 2: Run analytics → write data.json
├── scheduler.py       APScheduler: runs collector + snapshot on intervals
└── analytics/         Prediction, news analysis, breakdown (see analytics/AGENTS.md)
```

---

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new region | `config.py` (US_REGIONS/CA_REGIONS) + BASELINE_PRICES | Also update frontend/js/data.js regionMap |
| Change API endpoint | `config.py` EIA_*_ENDPOINT | |
| DB schema change | `db.py` SCHEMA + run `python backend/db.py` | WAL mode enabled |
| Cache behavior | `cache.py` get_cache()/set_cache() | Redis → in-memory fallback |
| Price collection logic | `price_collector.py` fetch_us_prices()/fetch_ca_prices() | EIA API v2 + NRCAN scraper |
| Analytics trigger | `snapshot.py` main() | Calls gather → news_analysis → predictor → breakdown |
| Schedule config | `scheduler.py` + .env PRICE_REFRESH_MINUTES/ANALYTICS_REFRESH_HOURS | |

---

## CONVENTIONS

### Region tuples
- **US**: `(id, display_name, abbr, city, eia_stateid, padd)`
- **CA**: `(id, display_name, abbr, city, nrcan_city_key, country="CA")`
- Access via `get_region(region_id)` or `REGION_BY_ID[region_id]`

### Unit handling
- Use `region_unit(region_id)` → returns `"gal"` or `"L"`
- NEVER hardcode units - always derive from region

### API key loading
- All secrets from `.env` via `config.py` module-level vars
- Optional keys (NEWS_API_KEY, ANTHROPIC_API_KEY, REDIS_URL) → graceful degradation if missing
- **EIA_API_KEY is REQUIRED** for US price data

### Database access
- Use `get_connection()` context manager for sync queries
- WAL mode enabled by default - safe for concurrent reads
- `db.py` run directly = schema init/migration

---

## ANTI-PATTERNS

- **Mixing sync/async DB**: Use sync sqlite3 only - no aiosqlite in this project
- **Hardcoded prices**: Price collection must ALWAYS hit external APIs (EIA, NRCAN) - no fallback to static values except BASELINE_PRICES for missing data
- **Crashing on optional service failure**: Redis/NewsAPI/Anthropic unavailable → fallback, log warning, continue
- **Committing .env**: Secrets live in .env (gitignored) - config.py loads them, never hardcodes

---

## COMMANDS

```bash
# Init/migrate database
python backend/db.py

# One-off price collection (all regions or subset)
python backend/price_collector.py
python backend/price_collector.py --regions ca tx on

# One-off analytics + data.json write
python backend/snapshot.py
python backend/snapshot.py ca tx on

# Continuous pipeline (production)
python backend/scheduler.py

# Test data gathering (no DB write)
python backend/analytics/gather.py
```

---

## NOTES

- **Approach A (cached-data model)**: Backend writes `frontend/data/data.json` directly - no API server
- Price collector updates `stations` + `regional_snapshot` tables; snapshot.py reads from `regional_snapshot` + runs analytics
- Analytics modules (gather, news_analysis, predictor, breakdown) are orchestrated by snapshot.py - see `analytics/AGENTS.md` for details
