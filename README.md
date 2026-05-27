# Should I Get Gas?

> An AI-powered gas price prediction and timing advisor — not just where prices are, but **when** to fill up.

---

## The Idea

Most gas price apps tell you *where* to find cheap gas right now. This project does something different: it tells you **whether today is a good day to fill up** — and if not, when you should.

The site analyzes historical price trends, crude oil futures, refinery news, geopolitical events, and seasonal patterns to generate a plain-English recommendation like:

- *"Prices are near a weekly low. Good day to fill up."*
- *"Prices are rising and likely to peak mid-week. Consider getting a little today and waiting until Thursday for a full tank."*
- *"Regional supply disruption detected. Prices may spike — fill up now if you can."*

You open the site, get an instant recommendation, and move on.

---

## Core Features (v1 Scope)

### Instant, Location-Aware Recommendations
- On load, the site detects your **approximate location from your IP address** (no permission prompt) to get state/regional gas prices
- Displays the current average price for your region and a simple **Buy / Wait / Partial** recommendation
- A single "Use My Exact Location" button unlocks nearby station prices (browser geolocation, opt-in)
- If a user wants granular station-level data, redirect to GasBuddy — we send them there rather than duplicate their core feature

### AI Timing Advisor
- Predicts whether prices in your region are likely to go **up, down, or stay flat** over the next 2–5 days
- Renders a small price-trend sparkline showing historical context (last 2 weeks vs. today)
- Explains *why* the recommendation was made: "Crude oil dropped 3% this week" or "Summer blend switchover driving refinery costs up"

### Context Panel
- Current crude oil price (WTI and Brent) and direction
- Relevant news headlines affecting gas prices (geopolitical events, OPEC decisions, refinery outages, hurricane season)
- Breakdown of what's driving today's price: crude oil, refining, taxes, distribution

---

## Research Findings

### Domain
`shouldigetgas.com` — DNS returns NXDOMAIN, indicating the domain is likely available for registration.

### Competitive Landscape
Existing gas apps focus on **real-time price comparison**, not prediction:

| App | What it does | Gap |
|-----|-------------|-----|
| GasBuddy | Crowdsourced current prices by station | No timing advice |
| Waze / Google Maps | Shows nearby prices during navigation | No timing advice |
| Upside | Cash back after purchase | No price intel |
| AAA Mobile | Station finder | No timing advice |

**No major consumer-facing product answers "should I fill up today or wait?"** This is the gap.

### Data Sources

#### Primary — EIA Open Data API (Free, Official)
The U.S. Energy Information Administration publishes weekly retail gasoline prices by region and state, freely available via their [Open Data API](https://www.eia.gov/opendata/). No cost, just an API key.

- Weekly average prices by state and metro area
- Historical data going back decades (ideal for training a prediction model)
- Also provides crude oil spot prices (WTI), refinery utilization, and import data
- Endpoint: `https://api.eia.gov/v2/petroleum/pri/gnd/data/`

#### Secondary — GasBuddy (No Official Public API)
GasBuddy does not offer a documented public API. Options include:
- `py-gasbuddy` — an unofficial Python wrapper around GasBuddy's GraphQL API (updated May 2026)
- Third-party scraping services (Apify, ScrapingBee) — check terms of service before use
- Commercial data licensing — contact GasBuddy directly
- **Recommended v1 approach**: Use EIA for price trends/predictions, deep-link users to GasBuddy for exact station prices

#### News & Sentiment
- [NewsAPI](https://newsapi.org/) or GDELT for real-time headlines on crude oil, OPEC, refinery disruptions
- Crude oil futures: EIA API, or [OilPriceAPI](https://www.oilpriceapi.com/) (has a free tier)

#### IP Geolocation
- [ipapi.co](https://ipapi.co/) or MaxMind GeoIP2 — map IP address to state/country silently on page load
- No permission prompt; resolution is state-level (sufficient to pull EIA regional data)

### How Gas Prices Work

Gas prices at the pump break down roughly as:

| Component | Share |
|-----------|-------|
| Crude oil | ~61% |
| Refining costs | ~14% |
| Federal + state taxes | ~14% |
| Distribution & marketing | ~11% |

**Key dynamics to model:**
- Crude oil changes pass through to pump prices within ~2 weeks (EIA data)
- Prices vary significantly by state due to taxes and reformulation requirements
- Seasonal patterns: prices typically rise in spring (summer blend switchover, higher demand) and fall in autumn
- Geopolitical events (OPEC cuts, sanctions, conflicts) can cause rapid crude swings
- Refinery outages (fire, maintenance, hurricanes) create regional spikes independent of crude prices

### Prediction Approach

Academic research (2024–2025) shows LSTM (Long Short-Term Memory) neural networks achieve ~8.5% MAPE on 1-step gas price forecasting, outperforming simpler models. Hybrid CNN-LSTM-Attention architectures push accuracy further.

For v1, a simpler time-series approach (exponential smoothing, linear regression on recent EIA weekly data + crude oil trend) is likely sufficient to produce a directional "up / down / flat over next week" signal with reasonable confidence. Reserve ML complexity for v2.

---

## Proposed Architecture

```
User Browser
    │
    ├─ IP → ipapi.co ──────────────────────── State/Region
    │
    └─ Frontend (HTML + JS)
            │
            ├── GET /api/recommendation?state=CA
            │        │
            │    Backend (Python/FastAPI)
            │        ├── EIA API ─────────── Weekly state gas prices (cached)
            │        ├── EIA API ─────────── WTI crude oil price
            │        ├── News API ────────── Relevant headlines
            │        └── Prediction model ── "prices rising, wait 2 days"
            │
            └── "Use My Location" click → browser geolocation
                    → /api/nearby-stations → deep-link to GasBuddy
```

---

## Potential Monetization (Later)

- Affiliate link to GasBuddy Pay / GasBuddy+ when redirecting users
- GasBuddy commercial data license (if volume warrants)
- Optional: a "Gas Budget Tracker" feature (enter your car's tank size, get weekly spend estimates)

---

## Tech Stack (Proposed)

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | Vanilla HTML/CSS/JS | Zero build complexity for v1 |
| Backend | Python + FastAPI | Fast to iterate, great data science libs |
| Prediction | `statsmodels` / `scikit-learn` | Sufficient for v1 trend detection |
| Data cache | Redis or SQLite | Cache EIA weekly data, avoid rate limits |
| Hosting | Railway / Render / Fly.io | Free tier, simple deploy |
| IP Geo | ipapi.co | Free tier, no signup for basic use |

---

## What This Is Not

- Not a replacement for GasBuddy's station-level data (we'll link out)
- Not a commodity trading signal (we're predicting retail pump prices, not crude futures)
- Not a navigation app

---

## Status

**Early prototype / research phase.** No code yet — this README is the starting point.

Next steps:
1. Register domain (if available — DNS check suggests it is)
2. Prototype EIA API integration and regional price fetch
3. Build minimal frontend with IP geolocation → state price display
4. Add simple week-over-week trend indicator
5. Iterate on the prediction model

---

## Sources & References

- [EIA Open Data API](https://www.eia.gov/opendata/) — free weekly gas price data by state/region
- [EIA Factors Affecting Gasoline Prices](https://www.eia.gov/energyexplained/gasoline/factors-affecting-gasoline-prices.php)
- [EIA Gasoline & Diesel Weekly Update](https://www.eia.gov/petroleum/gasdiesel/)
- [American Petroleum Institute — How Gas Prices Are Determined](https://www.api.org/oil-and-natural-gas/energy-primers/gas-prices-explained)
- [py-gasbuddy (PyPI)](https://pypi.org/project/py-gasbuddy/) — unofficial GasBuddy GraphQL wrapper
- [PMC — Natural Gas Price Prediction Using AI Models](https://pmc.ncbi.nlm.nih.gov/articles/PMC12668636/)
- [GitHub — Gas Price ML Analysis](https://github.com/FIRE-Phoebe/Gas_Price_analysis)
