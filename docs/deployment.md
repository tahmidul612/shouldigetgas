# Deployment Guide

This guide describes how shouldigetgas is currently deployed and operated.

## ⚠️ Important disclaimer

This project was entirely **vibe-coded with Claude**, uses **Claude Haiku** internally for parts of data processing, and the output may not be **100% accurate**.

## Current hosting

- Frontend URL: https://shouldigetgas.vercel.app/
- Frontend is static and reads `frontend/data/data.json`
- Backend pipeline runs independently (not as an API service)

## Runtime architecture

- `backend/price_collector.py` runs every ~30 minutes
- `backend/snapshot.py` runs every ~6 hours
- `backend/scheduler.py` can orchestrate both in one long-running process

The pipeline updates SQLite and writes the static JSON consumed by the frontend.

## Environment variables for deployment

| Variable | Required | Notes |
|---|---|---|
| `EIA_API_KEY` | Yes | Required for US pricing data |
| `NEWS_API_KEY` | No | News enrichment |
| `ANTHROPIC_API_KEY` | No | Claude Haiku analysis |
| `GNEWS_API_KEY` | No | News fallback source |
| `REDIS_URL` | No | Optional cache service |
| `DB_PATH` | No | SQLite file location |
| `DATA_JSON_PATH` | No | JSON output path |
| `PRICE_REFRESH_MINUTES` | No | Defaults to 30 |
| `ANALYTICS_REFRESH_HOURS` | No | Defaults to 6 |

## Scheduling options

### Option A: built-in scheduler

```bash
python backend/scheduler.py
```

### Option B: cron jobs

```cron
# /etc/cron.d/shouldigetgas — system crontab format (includes user field)
*/30 * * * *  user  /path/to/shouldigetgas/scripts/run_collector.sh
0 */6 * * *   user  /path/to/shouldigetgas/scripts/run_analytics.sh
```

> For per-user crontab (`crontab -e`), omit the `user` column:
> ```cron
> */30 * * * *  /path/to/shouldigetgas/scripts/run_collector.sh
> 0 */6 * * *   /path/to/shouldigetgas/scripts/run_analytics.sh
> ```

## Service dependencies

- **Required:** EIA API key
- **Optional:** NewsAPI, Anthropic, Redis, GNews
- If optional services fail, the pipeline should continue with fallbacks

## Operational notes

- Keep `.env` out of source control.
- Monitor scheduler logs and JSON freshness.
- Ensure the frontend can read the latest `data.json` from the deployed static assets.
