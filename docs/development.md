# Development Guide

This guide covers local setup and day-to-day development for shouldigetgas.

## ⚠️ Important disclaimer

This project was entirely **vibe-coded with Claude**, uses **Claude Haiku** internally for parts of data processing, and the output may not be **100% accurate**.

## Prerequisites

- Python 3.10+
- `pip`
- Git

## Local setup

```bash
git clone https://github.com/tahmidul612/shouldigetgas.git
cd shouldigetgas

python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
python backend/db.py
```

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `EIA_API_KEY` | Yes | US gas price data |
| `NEWS_API_KEY` | No | News headlines |
| `ANTHROPIC_API_KEY` | No | Claude Haiku news analysis |
| `REDIS_URL` | No | Optional cache backend |
| `DB_PATH` | No | SQLite path override |
| `DATA_JSON_PATH` | No | Output JSON path override |

## Running the frontend (zero-build)

```bash
python3 -m http.server 8080 --directory frontend
```

Open `http://localhost:8080`.

## Running the pipeline

### One-off commands

```bash
python backend/price_collector.py         # ~every 30 min in production
python backend/snapshot.py                # ~every 6h in production
python backend/scheduler.py               # long-running scheduler
```

You can also pass specific regions:

```bash
python backend/price_collector.py --regions ca tx on
python backend/snapshot.py ca tx on
```

## Project structure

- `frontend/` — React 18 UMD + Babel standalone UI (no build step)
- `backend/` — collection, analytics, scheduling, and data assembly
- `backend/analytics/` — gather/news/predictor/breakdown modules
- `data/` — SQLite database files
- `scripts/` — cron-friendly wrappers for collector and analytics
- `docs/` — project documentation

## Data model

Primary SQLite tables:

- `stations` — raw fetched station/region prices over time
- `regional_snapshot` — latest per-region state used for JSON output
- `crude_prices` — crude history
- `news_cache` — headline cache and relevance metadata
- `prediction_log` — prediction audit records

`backend/snapshot.py` assembles these inputs and writes the frontend payload to:

- `frontend/data/data.json` (default)

## Region system

62 supported regions:
- US: all 50 states + DC
- Canada: 10 provinces + Northern Canada aggregate

To add a region:
1. Add region definition in `backend/config.py` (`US_REGIONS` or `CA_REGIONS`)
2. Add fallback baseline in `BASELINE_PRICES`
3. Update IP mapping in `frontend/js/data.js`
4. Run `python backend/snapshot.py` to generate updated JSON
