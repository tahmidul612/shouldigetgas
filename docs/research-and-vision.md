# Research and Vision

This document preserves the original product research for **shouldigetgas** and updates it with what actually shipped in v1.

## ⚠️ Important disclaimer

This project was entirely **vibe-coded with Claude**, uses **Claude Haiku** internally for parts of data processing, and the output may not be **100% accurate**.

## What Changed (Plan vs. v1 Reality)

| Aspect | Original Plan | Actual Implementation |
|---|---|---|
| Frontend | Vanilla HTML/CSS/JS | React 18 UMD + Babel standalone (zero-build) |
| Backend | FastAPI API server | Backend writes `frontend/data/data.json` directly (no API server) |
| Prediction model | LSTM / ML models (v2) | Holt exponential smoothing for directional guidance |
| LLM usage | Not planned | Claude Haiku used for news analysis + batch processing |
| Regions | US-focused | 62 regions: 50 US states + DC + 10 CA provinces + Northern Canada |
| Data sources | EIA only | EIA + NRCAN + Ontario CKAN + GasBuddy fallback + GNews fallback |
| Pipeline cadence | Not defined | Two-speed pipeline: 30-minute collection, 6-hour analytics |
| Hosting | Railway/Render/Fly | Frontend currently hosted on Vercel |

## Original Core Idea

Most gas apps answer **where** prices are lowest right now.  
shouldigetgas focuses on **when** to fill up.

The goal is a plain-language recommendation such as:
- “Prices are near a weekly low. Good day to fill up.”
- “Prices are trending up. Consider topping off now.”
- “Regional supply risk detected. Fill up sooner.”

## Competitive Landscape (Original Research)

| App | What it does | Gap |
|---|---|---|
| GasBuddy | Crowdsourced station prices | No timing advice |
| Waze / Google Maps | Nearby station prices in navigation | No timing advice |
| Upside | Cashback after purchase | No timing guidance |
| AAA Mobile | Station finder | No timing guidance |

Research conclusion: there is room for a consumer-facing “buy now vs wait” advisor.

## How Gas Prices Work (Research Basis)

Approximate price components at the pump:

| Component | Share |
|---|---|
| Crude oil | ~61% |
| Refining | ~14% |
| Taxes | ~14% |
| Distribution/marketing | ~11% |

Key dynamics:
- Crude changes typically pass through with lag.
- Regional taxes and fuel formulations matter.
- Seasonal transitions can shift prices.
- Refinery outages and geopolitical events can create sharp moves.

## Prediction Approach: Then vs Now

- **Original direction:** investigate LSTM and hybrid ML approaches for higher-accuracy forecasting.
- **Shipped v1:** Holt exponential smoothing + directional verdicts (`buy` / `partial` / `wait`), optimized for practical signal quality and reliability over model complexity.

## Data and Signals in v1

- **US prices:** EIA API (weekly/state data with fallback logic)
- **Canada prices:** Ontario CKAN + NRCAN + fallback paths
- **Context inputs:** WTI crude, refinery utilization, and relevant news
- **News interpretation:** Claude Haiku with heuristic fallback when unavailable
- **Output artifact:** `frontend/data/data.json`

## Architecture Evolution

### Original proposal

Frontend calls a backend API server for recommendations and nearby data.

### Current production shape

- Backend jobs run independently.
- Jobs write snapshots directly to SQLite and `frontend/data/data.json`.
- Frontend is static and reads JSON snapshots.
- No runtime API server is required for the web app.

## Scope Notes

- This product is not a station-finder replacement.
- It is not a crude-trading signal.
- It is a consumer timing aid designed to be simple and fast.

## References

- EIA Open Data API: https://www.eia.gov/opendata/
- EIA Gasoline and Diesel Update: https://www.eia.gov/petroleum/gasdiesel/
- EIA gasoline price factors: https://www.eia.gov/energyexplained/gasoline/factors-affecting-gasoline-prices.php
- NRCAN fuel data: https://www2.nrcan.gc.ca/eneene/sources/pripri/prices_bycity_e.cfm
- Ontario CKAN dataset API: https://data.ontario.ca/
