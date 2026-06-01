# backend/analytics/AGENTS.md

Analytics pipeline modules: data gathering, prediction, news analysis, cost breakdown.

---

## OVERVIEW

Four modules orchestrated by `snapshot.py`:
- **A (gather.py)**: Fetch WTI crude, refinery util, news headlines
- **B (news_analysis.py)**: Claude Haiku → `why`/`advice`/`verdict`; VADER sentiment fallback
- **C (predictor.py)**: Holt exponential smoothing → price direction, `bestDayIdx`, trend
- **D (breakdown.py)**: Per-region cost breakdown `{crude, refining, taxes, dist}` percentages

---

## STRUCTURE

```
analytics/
├── gather.py          Module A: EIA WTI/Brent, refinery util, NewsAPI headlines
├── news_analysis.py   Module B: LLM/heuristic analysis → why/advice/verdict
├── predictor.py       Module C: Time-series prediction (Holt smoothing)
└── breakdown.py       Module D: Price component breakdown (crude/refine/tax/dist)
```

---

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new data source | `gather.py` fetch_wti()/fetch_news() | EIA API v2 + NewsAPI |
| Change prediction model | `predictor.py` predict_direction() | Currently Holt exponential smoothing |
| Adjust LLM prompt | `news_analysis.py` ANALYSIS_PROMPT | Claude Haiku with VADER fallback |
| Modify breakdown logic | `breakdown.py` calculate_breakdown() | US vs CA tax rates differ |
| News relevance scoring | `news_analysis.py` score_news_relevance() | Keyword-based + LLM if available |

---

## CONVENTIONS

### Module inputs
- **gather.py**: No args → fetches latest data, returns dict
- **news_analysis.py**: Takes news headlines + WTI data → returns analysis dict
- **predictor.py**: Takes region_id + historical prices → returns prediction dict
- **breakdown.py**: Takes region_id + current price + WTI → returns breakdown dict

### Data flow
1. `snapshot.py` calls `gather.py` → gets WTI, news, refinery data
2. For each region: calls `news_analysis.py` + `predictor.py` + `breakdown.py`
3. Assembles final JSON payload → writes to `frontend/data/data.json`

### LLM usage
- **Claude Haiku** for news analysis (`ANTHROPIC_API_KEY` in .env)
- **Fallback**: VADER sentiment analysis (no API key required)
- Cost-conscious: Only analyze top 5 most relevant headlines per region

### Prediction approach
- **v1**: Holt exponential smoothing (statsmodels) on last 30 days of EIA data
- Directional signal only: "up" / "down" / "flat" over next 2-5 days
- `bestDayIdx`: Index (0-6) of predicted lowest price day in next week

---

## ANTI-PATTERNS

- **Over-reliance on LLM**: ALWAYS have heuristic fallback (VADER sentiment, keyword scoring)
- **Blocking on external API**: If EIA/NewsAPI/Anthropic fails → use cached data, log error, continue
- **Ignoring regional differences**: CA regions have different tax structures (carbon levy, provincial fuel tax) - use `CA_TAX_RATES` from config.py
- **Stateless prediction**: predictor.py should use historical DB data, not just latest snapshot

---

## COMMANDS

```bash
# Test data gathering only (no DB write, no analytics)
python backend/analytics/gather.py

# Run full analytics for specific regions (writes to DB + data.json)
cd ..  # from analytics/ to backend/
python snapshot.py ca tx on
```

---

## NOTES

- **Module independence**: Each analytics module can be tested standalone via direct import
- **Caching**: gather.py results cached in Redis (1 hour TTL) to avoid rate limits
- **News analysis cost**: Claude Haiku costs ~$0.25 per 1M tokens input - analyzing 5 headlines ≈ 200 tokens input + 100 output = $0.00003 per region per run (negligible)
- **Prediction log**: All predictions written to `prediction_log` table for audit/model improvement
