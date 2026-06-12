# Codebase Assessment — shouldigetgas
**Date:** 2026-06-07  
**Auditor:** Claude Sonnet 4.6  
**Scope:** Full codebase (backend, frontend, scripts, config, DB, live site)

---

## 1. Executive Summary

The `shouldigetgas` project has a solid architectural foundation — the two-speed cached-data model (Approach A), graceful API fallbacks, and React 18 zero-build frontend are all well-conceived. However, a cluster of **runtime data quality issues** means the live site is currently showing incorrect gas prices and analytically meaningless verdicts for the majority of users.

**Root cause chain:**
1. The EIA state-level API call likely sends malformed URL parameters (`facets[duoarea][0]=SCA` instead of repeated `facets[duoarea][]=SCA`), causing the API to return no state-level data for most states.
2. The PADD district fallback then provides a single district price (e.g., P3 Gulf Coast ~$4.06 for Texas, when actual TX price is ~$3.00).
3. The EIA WTI crude endpoint is also returning no data (crude_prices table is empty), so the hardcoded fallback `$71.2 flat` is served to all users.
4. Because week_delta is always 0 (price never changes in the DB) and WTI is "flat", the `determine_verdict` heuristic returns "buy" for all 51 US states — a meaningless uniform signal.

**Secondary issues:** The production site uses React development builds and in-browser Babel transpilation (slow, warns in console), has no favicon or Open Graph image, missing H1 accessibility landmark, and duplicate SVG gradient IDs.

---

## 2. Bug Findings

| # | Severity | File | Line(s) | Issue | Impact |
|---|----------|------|---------|-------|--------|
| B1 | **Critical** | `backend/price_collector.py` | 70–71, 119–120 | EIA API array parameter format uses indexed notation `facets[duoarea][0]=SCA` but EIA v2 may require repeated `facets[duoarea][]=SCA`. The `facets[product][]` param on line 67 uses the correct `[]` notation while duoarea uses `[{i}]`. | Most state-level prices fail to fetch; PADD district prices used as fallback, showing prices 30–48% above real values (TX: $4.06 vs ~$3.00, FL: $4.30 vs ~$3.20, OH: $4.66 vs ~$3.30) |
| B2 | **Critical** | `backend/analytics/gather.py` | 337 | Hardcoded WTI fallback `{"price": 71.2, "dir": "flat", "change": 0.0}` is served when EIA crude endpoint fails. The `crude_prices` DB table is currently empty (0 rows), confirming EIA WTI fetch is failing silently. | WTI price shown to all users is a stale hardcoded constant; crude direction "flat" biases all verdicts toward "buy" |
| B3 | **Critical** | `backend/analytics/predictor.py` | 196 | `determine_verdict`: when `wti_dir="flat"` and `week_delta=0` (both true for almost all regions), condition `price_dir in ("down","flat") and wti_dir in ("down","flat") and week_delta <= 0.01` is always met — returns "buy" for every US region. | 51/51 US regions show "buy" regardless of actual market conditions |
| B4 | **Critical** | `data/shouldigetgas.db` | — | 61/62 regions have `analysis_updated_at = NULL` in `regional_snapshot`. Analytics (modules B, C, D) have only run for California. All other regions serve static baseline prices with heuristic verdicts. | Users in 61 regions see stale hardcoded prices with no real analysis |
| B5 | **High** | `frontend/js/components.js` | 67 | Sparkline SVG gradient ID `gid = 'spark-' + animKey` is the same for both the desktop rail card and mobile support cards when viewing the same region (e.g., `spark-ca-buy`). Confirmed duplicate by Playwright: `duplicateIds: ["spark-ca-buy"]`. | Second sparkline renders with wrong gradient (browser uses first `<defs>` definition it encounters); visual artifact |
| B6 | **High** | `frontend/js/components.js` | 59 | `Sparkline`: `values.length - 1` in denominator can be 0 if trend array has only 1 value. `x = pad + (W - 2 * pad) * (i / 0)` → `NaN` coordinates. | Sparkline renders blank / broken SVG for regions with thin history |
| B7 | **High** | `frontend/js/app.js` | 52–54 | `regions.find(...) || regions[0]` then immediately accesses `region.verdict` and `region.weekDelta`. If `regions` array is empty (e.g., API 404), `regions[0]` is `undefined` and the next line throws `TypeError`. No empty-regions guard. | Uncaught exception on load if data.json is temporarily unavailable (even with catch in `loadData`, regions defaults to `PLACEHOLDER_REGIONS` which is non-empty — but direct calls to `refresh()` do not reset to placeholder on failure) |
| B8 | **Medium** | `backend/price_collector.py` | 410 | Ontario CKAN price `toronto / 100.0` assumes the API returns ¢/L. If the CKAN schema changes to return $/L (as some API versions do), the price is divided by 100 a second time, yielding ~$0.012/L. No unit validation in the response. | Canadian Ontario price could show as $0.012/L if API format changes |
| B9 | **Medium** | `backend/price_collector.py` | 449 | `week_ago_price = history[-7][1] if len(history) >= 7 else history[0][1]`. When `len(history) == 7`, `history[-7]` is `history[0]` (oldest). This computes delta from oldest entry, not true 7-days-ago. The variable name is misleading. | Week delta calculation is off-by-one for short histories; trend direction may be inverted |
| B10 | **Medium** | `backend/snapshot.py` | 244–246 | `prices_updated = max(s.get("prices_updated_at") or "" for s in snapshots)` — uses string `max()` on ISO timestamps. If any timestamp uses `Z` suffix instead of `+00:00`, lexicographic ordering fails (`Z` < `a`). Inconsistent isoformat usage could produce wrong `pricesUpdatedAt` in the payload. | `meta.pricesUpdatedAt` in data.json could show an incorrect time |
| B11 | **Medium** | `backend/analytics/news_analysis.py` | 261–262 | Imports from `anthropic.types.message_create_params.MessageCreateParamsNonStreaming` and `anthropic.types.messages.batch_create_params.Request`. These are internal SDK type paths that changed between SDK versions and are not part of the public API. | Batch LLM analysis silently breaks if Anthropic SDK is upgraded (currently anthropic==0.87.0) |
| B12 | **Medium** | `backend/db.py` | 14–88 | `PRAGMA journal_mode = WAL` inside `executescript()`. SQLite's `executescript()` issues an implicit `COMMIT` before execution. WAL mode is set correctly on first run but future connections opened by `get_conn()` don't set WAL explicitly — WAL mode does persist in the DB file, but relying on this implicit persistence is fragile. | Potential WAL-mode failure on DB restoration or migration |
| B13 | **Low** | `frontend/js/data.js` | 165–167 | `if (!mapped)` check is dead code. After the `if country === 'CA'` block, `mapped` is always a string (`CA_MAP[code]` or `'on'`; else `US_MAP[code]` or `'ca'`). The `console.warn` on line 166 never fires. | Dead warning code confuses readers about what edge case exists |
| B14 | **Low** | `backend/cache.py` | 93–106 | `cached` decorator is defined but never used by any module. All callers use `cache.get()` / `cache.set()` directly. | Dead code |
| B15 | **Low** | `.env.example` | — | `GNEWS_API_KEY` is loaded in `config.py:34` and used in `gather.py` as a fallback news source, but it is undocumented in `.env.example`. | Developers won't know to set this variable; GNews fallback appears broken |
| B16 | **Low** | `scripts/run_collector.sh` | 8 | `exec python backend/price_collector.py` — no venv activation. System Python will be used unless the cron environment has packages installed globally. If packages are venv-only, the script fails silently (all errors go to the log file only). | Price collection cron jobs can fail silently with `ModuleNotFoundError` |
| B17 | **Low** | `scripts/run_analytics.sh` | 8 | Same as B16. `exec python backend/snapshot.py` without activating `.venv/`. | Analytics cron fails silently |

---

## 3. Playwright Visual Audit

### Screenshots

**Desktop (1440×900)**  
The desktop layout renders cleanly. The two-column grid (hero left, context rail right) is visually correct. The price display shows `$6.03` for California — which is ~30% above real-world CA price (~$4.50 in June 2026).

**Mobile (375×812)**  
Mobile layout is clean. The single-screen compression (100dvh) works correctly. The "FILL UP" verdict is prominent. Truncated `why` text (2-line clamp) functions correctly.

### Console Errors / Warnings

| Type | Message | Root Cause |
|------|---------|------------|
| Warning | `You are using the in-browser Babel transformer. Be sure to precompile your scripts for production` | `babel.min.js` is loaded in production; JSX is compiled client-side on every load |
| Error | `Failed to load resource: the server responded with a status of 404 ()` | `favicon.ico` returns 404 (confirmed: `https://shouldigetgas.vercel.app/favicon.ico` → 404) |

### Performance Metrics (Live Site, Desktop)

| Metric | Value | Assessment |
|--------|-------|------------|
| Total load time (wall clock) | 2.99 s | Slow for a static app — dominated by Babel transpilation |
| DOMContentLoaded | 1,189 ms | High due to Babel parse + React/Babel CDN bundles |
| Load event | 1,189 ms | Same |
| Resource count | 11 | react.development.js + react-dom.development.js + babel.min.js + fonts (3) + CSS + 3 JS files + data.json |
| Babel bundle (CDN) | ~1.3 MB | 2 of the 3 CDN scripts are the development React builds |

Switching to production React builds + removing Babel would reduce initial parse time by an estimated 60–70%.

### Accessibility Issues

| Severity | Issue |
|----------|-------|
| High | No `<h1>` heading on the page. The brand name and main verdict ("FILL UP") are unsemantic `<div>` elements. Screen readers cannot identify the page structure. |
| Medium | `SrcLink` anchor renders as `"EIA ↗"` — the arrow character `↗` is read aloud by screen readers as "north east arrow". `aria-label` would fix this. |
| Low | Location chip button announces as `"California ▾"` — the `▾` character is read aloud. Use CSS-only caret instead. |
| Low | Icon buttons (refresh, geolocation) have `title` attributes only. `title` is not a reliable accessible name for mobile/keyboard users — `aria-label` is preferred. |

### HTML Validity Issues

| Check | Result |
|-------|--------|
| Viewport meta | ✅ Present |
| Language attribute | ✅ `lang="en"` on `<html>` |
| Description meta | ✅ Present |
| Title | ✅ "Should I Get Gas?" |
| og:title | ✅ Present |
| **og:image** | ❌ Missing — social shares show no preview image |
| **Favicon** | ❌ Missing — 404 on `/favicon.ico`, no `<link rel="icon">` in HTML |
| **H1 heading** | ❌ Missing — accessibility violation |
| Duplicate IDs | ❌ `spark-ca-buy` — Sparkline gradient ID duplicated between mobile and desktop |

---

## 4. Code Quality & Anti-Patterns

### `backend/price_collector.py`

- **Line 37**: `NOW = lambda: datetime.now(timezone.utc).isoformat()` — module-level mutable lambda. Calling `NOW()` multiple times in `collect_us_prices` produces different timestamps. Assigning `now_ts = NOW()` once at the top of the function (line 344) is correct, but `collect_canada_prices` also calls `NOW()` on line 399, which means US and Canada collection timestamps will differ by however long US collection takes. Not a bug but inconsistent.
- **Line 286**: `price = round(statistics.median(raw_prices[:3]), 3)` — EIA data is weekly; `raw_prices[:3]` is "last 3 weeks," not last 3 data points. The comment says "last 3 readings" which is accurate — but the EIA series returned is already sorted newest-first, so this is valid. However, median of 3 weekly prices will always be the middle week price, not a rolling average.
- **Line 461**: `price_low = round(price_cdl * 0.95, 3)` — hardcoded 5% discount is an estimate for Canadian stations. No data-backed rationale. Displayed to users as a real "lowest nearby" price.

### `backend/analytics/news_analysis.py`

- **Lines 259–300**: `build_batch_payload` uses `requests = []` (line 264), shadowing the module-level `requests` import from `price_collector.py`. This file doesn't import `requests` itself, but the naming is confusing for readers.
- **Lines 304–362**: `submit_and_poll_batch` runs a synchronous `time.sleep(poll_interval)` loop polling Anthropic's Batch API. Default `poll_interval=30` and `timeout=3600`. During the 6-hour analytics run, this blocks the `scheduler.py` thread for the entire batch processing duration (potentially minutes). The `BlockingScheduler` in `scheduler.py` runs jobs in the same thread, so this will delay the next price collection job.
- **Line 379**: `int(result["bestDayIdx"]) % 7` — wraps bestDayIdx to valid day range. The `int()` call could raise `ValueError` if the LLM returns a non-numeric string. Should be `int(float(...))` or use a try/except.

### `backend/analytics/predictor.py`

- **Line 119**: `int(np.argmin(forecast))` — `numpy.argmin` returns a numpy int64. While Python generally handles this transparently, `json.dumps()` of a numpy int fails unless a custom encoder is used. The snapshot writer calls `json.dumps` on the breakdown dict. This particular value goes into `best_day_idx` which gets stored as a DB INTEGER — SQLite handles numpy ints fine. But it's a subtle type risk.
- **Line 47**: Pure-Python Holt fallback initializes `trend = series[1] - series[0]`. With only 3 data points (the minimum), this is a single-step initialization which may produce unstable forecasts.

### `backend/snapshot.py`

- **Lines 98–128**: `run_analytics_for_region` first runs `compute_week_delta`, then on line 91 checks if `snapshot.get("week_delta")` exists and overrides it. This means `compute_week_delta` is called (and hits the DB) even when the snapshot already has a valid week_delta — wasted work for 62 regions × 6h.
- **Lines 211–234**: The "create minimal snap from config" block uses `"best_day_idx": 2` (Wednesday) and `"wti_dir": "flat"` hardcoded. These fallbacks persist to the DB and data.json if analytics never fully run.

### `backend/db.py`

- **Lines 228–238**: `get_price_history` uses `GROUP BY date(datetime(fetched_at))` but selects `fetched_at` (the full timestamp). In SQLite, selecting a non-aggregated column not in GROUP BY is allowed but the returned value is arbitrary (usually the max row's value, but not guaranteed). The returned `(fetched_at, avg_price)` has a potentially wrong timestamp. Since the caller only uses the price (`[p for _, p in history]`), this doesn't cause a practical bug — but the timestamp is misleading.

### `backend/cache.py`

- **Line 96**: `key = key_prefix + ":" + ":".join(str(a) for a in args)` — for large or complex arguments (e.g., lists, dicts), `str()` produces ugly/non-unique keys. The `cached` decorator is unused, but if adopted it would produce cache key collisions for list arguments.
- No thread-safety on `_mem` dict. In Python, dict operations are GIL-protected for single operations but not for multi-step read-modify-write sequences. For single-process use this is fine, but worth noting.

### `frontend/js/app.js`

- **Line 53**: `const theme = window.getTheme(region.verdict)` — `region.verdict` can be any string. `getTheme` calls `PALETTES.classic[verdict]` which returns `undefined` for unknown verdicts. All theme properties then become `undefined`, breaking all inline styles silently. No default/guard in `getTheme`.
- **Line 79**: `refresh()` calls `window.loadData()` and updates state on success, but on failure (the `catch` block in `loadData` returns placeholder data), the user gets stale placeholders re-rendered with no indication of failure.

### `frontend/js/components.js`

- **Line 200**: `const source = regions || window.PLACEHOLDER_REGIONS` — `regions` prop is always passed from `app.js` as the live regions array. The fallback `|| window.PLACEHOLDER_REGIONS` would activate if `regions` is falsy — but since it's an array it can be empty `[]`, which is falsy-ish but actually truthy in JS. So the fallback actually triggers only if `regions` is `null`/`undefined`. Minor: an empty `regions` array would show "No match found" rather than placeholder — acceptable behavior but undocumented.

### `scripts/update_and_push.sh`

- **Line 73**: `git commit --no-gpg-sign` — explicitly bypasses commit signing. If the repo requires signed commits this would fail push hooks on the remote. The `--no-gpg-sign` is unconditional and cannot be overridden.
- **Lines 83–84**: `REPO_OWNER="tahmidul612"` and `REPO_NAME="shouldigetgas"` are hardcoded strings in a committed script. While not secrets, hardcoding makes forks or renames require manual script edits.

---

## 5. Performance Assessment

### Backend Pipeline

| Stage | Current | Concern |
|-------|---------|---------|
| EIA state price fetch | 1 HTTP call for all states in one batch | Correct but likely failing (see B1) |
| PADD fallback | 1 HTTP call per distinct PADD code | May return wrong fuel grade data |
| Canadian NRCAN scrape | `lxml` BeautifulSoup parse on full HTML page | Fragile (scraping) |
| Batch LLM analysis | Synchronous polling loop up to 3600s | Blocks scheduler thread during 6h analytics job |
| `run_analytics_for_region` × 62 | Calls `compute_week_delta` + `build_trend_array` (2 DB queries each) | 124 DB reads per analytics run |
| `db.get_price_history` | Full table scan of `stations` with date filtering | No index on `region_id + date(fetched_at)`; the index is on `(region_id, fetched_at)` — substring functions negate the index |

### Frontend

| Metric | Current | Better |
|--------|---------|--------|
| React build | `react.development.js` (730KB) + Babel (1.3MB) | `react.production.min.js` (45KB) + pre-compiled JSX |
| IP geolocation | `ipapi.co` with 4s timeout, no caching | Cache in sessionStorage after first lookup |
| Data refresh | Full JSON re-fetch with `cache: 'no-cache'` | Use `If-None-Match` / ETag for conditional fetch |

---

## 6. Security Observations

| Item | Severity | Details |
|------|----------|---------|
| No Content-Security-Policy header | Medium | Live site has no CSP. The app loads React and Babel from `unpkg.com` CDN — integrity SRI attributes are present (good), but no CSP means XSS vectors are not restricted. |
| No `X-Frame-Options` header | Low | Site can be embedded in iframes on any domain (potential clickjacking). Add `X-Frame-Options: DENY` or equivalent CSP `frame-ancestors` directive. |
| API keys in `.env` not committed | ✅ OK | `.gitignore` correctly excludes `.env`. |
| PAT token file path exposed in script | Low | `scripts/update_and_push.sh:83` has `REPO_OWNER="tahmidul612"` and `REPO_NAME="shouldigetgas"` hardcoded. Not a secret but reduces portability. |
| `git commit --no-gpg-sign` | Warning | Bypasses GPG commit signing unconditionally in the automation script. |
| No HTTPS enforcement meta | Info | Site is served over HTTPS via Vercel (OK), but no HSTS header observed. |
| External IP geolocation service | Info | `ipapi.co` collects user IP addresses. No privacy disclosure to users about this third-party call. |
| news article URLs in data.json | Info | External article URLs are embedded in data.json and rendered as `<a>` links. `rel="noopener"` is correctly applied. |

---

## 7. Dependency Health

### Python (backend/requirements.txt)

| Package | Pinned | Installed | Notes |
|---------|--------|-----------|-------|
| `requests` | `>=2.31.0` | latest | No upper bound — fine |
| `anthropic` | `>=0.40.0` | `0.87.0` | B11: internal type imports may break on SDK bumps |
| `beautifulsoup4` | `>=4.12.0` | `4.14.3` | Scraping NRCAN; fragile to page changes |
| `lxml` | `>=4.9.0` | installed | Used as BS4 parser |
| `statsmodels` | `>=0.14.0` | installed | Used for Holt smoothing |
| `numpy` | `>=1.24.0` | installed | Used only for `np.argmin` — heavy dep for one call |
| `py-gasbuddy` | `>=0.4.0` | installed | Async library called with `asyncio.new_event_loop()` in sync context; creates a new event loop per call — potentially slow and fragile |
| `vaderSentiment` | `>=3.3.2` | installed | Old but stable |
| `APScheduler` | `>=3.10.0` | `3.11.2` | OK |
| `redis` | `>=5.0.0` | installed | Optional, graceful fallback |
| `python-dotenv` | `>=1.0.0` | installed | OK |

### Frontend (CDN)

| Library | Version | Notes |
|---------|---------|-------|
| React | `18.3.1` (development build) | Should use `react.production.min.js` in production |
| ReactDOM | `18.3.1` (development build) | Same — development build is ~3× larger |
| Babel Standalone | `7.29.0` | Should only be used for prototyping; client-side transpilation in production is a significant perf issue |

### Missing .gitignore Entries

| Path | Risk |
|------|------|
| `*.pdf` | `README.pdf` is untracked (in gitStatus) — if committed, adds large binary to git history |
| `fix_env.py` | Untracked utility script — could accidentally commit sensitive logic |
| `scripts/update_and_push.sh` | Currently tracked but contains automation config that may include sensitive path info |

---

## 8. Refactoring Opportunities

### Low Hanging Fruit (1–2 hours each)

1. **Fix EIA array parameter format** (`price_collector.py:70–71`, `119–120`): Change `facets[duoarea][{i}]` to use a list of tuples in `params` so `requests` sends repeated `facets[duoarea][]=...` keys. This likely fixes B1 and unlocks correct state-level prices for all US states.

   ```python
   # Current (likely broken for EIA)
   for i, sid in enumerate(state_ids):
       params[f"facets[duoarea][{i}]"] = f"S{sid}"
   
   # Better — use list of tuples to allow repeated keys
   param_list = list(params.items())
   for sid in state_ids:
       param_list.append(("facets[duoarea][]", f"S{sid}"))
   resp = SESSION.get(EIA_GAS_ENDPOINT, params=param_list, timeout=30)
   ```

2. **Add favicon + og:image**: Drop a `favicon.ico` into `frontend/`, add `<link rel="icon">` to `index.html`, and add an og:image meta tag. Eliminates 404, improves social sharing.

3. **Fix duplicate Sparkline gradient IDs** (`components.js:67`): Append a suffix to distinguish desktop vs. mobile renders: `gid = 'spark-' + animKey + (isMobile ? '-m' : '-d')`. Since the component doesn't know its context, an easier fix is to use a global incrementing counter via `useRef`.

4. **Switch to production React builds** (`index.html:27–35`): Replace `react.development.js` with `react.production.min.js` and `react-dom.development.js` with `react-dom.production.min.js`. Remove or replace Babel in-browser transpilation with a pre-compilation step.

5. **Add `GNEWS_API_KEY` to `.env.example`** (`backend/config.py:34`): Document this undiscovered variable.

6. **Add H1 to the page** (`frontend/index.html` or `app.js`): Wrap brand text in an `<h1>` (visually styled to match current appearance) for screen reader compatibility.

7. **Activate venv in shell scripts** (`scripts/run_collector.sh`, `scripts/run_analytics.sh`, `scripts/update_and_push.sh`): Add `. "$REPO/.venv/bin/activate"` before the `python` invocations, or use the full path `"$REPO/.venv/bin/python"`.

### Medium (half-day each)

8. **Fix `determine_verdict` uniformity** (`analytics/predictor.py:184–202`): When there is no real price history (week_delta=0, wti_dir="flat"), the verdict should be "partial" (uncertain), not "buy". Add a guard: if data confidence is below a threshold, return "partial".

9. **Add Sparkline single-value guard** (`components.js:59`): `if (values.length <= 1) return <div className="spark" />` early return to prevent divide-by-zero.

10. **Cache Vercel API response** (`api/data.js`): Add `Cache-Control: public, max-age=300, stale-while-revalidate=600` response headers so Vercel's CDN caches the JSON and reduces cold-read latency.

11. **Cache IP geolocation in sessionStorage** (`data.js:132`): `sessionStorage.getItem('sig-region')` check before fetching ipapi.co. Store the result after detection. Eliminates the 4s external request on every page refresh.

12. **Remove `compute_week_delta` call when snapshot already has it** (`snapshot.py:85`): Skip `compute_week_delta` if `snapshot.get("week_delta") is not None` to avoid 62 redundant DB reads per analytics run.

13. **Replace `np.argmin` with pure Python** (`predictor.py:120`): Remove numpy dependency for a single call: `min_idx = min(range(len(forecast)), key=lambda i: forecast[i])`. Then remove numpy from `requirements.txt` if no other use exists.

### Architectural (multi-day)

14. **Pre-build JSX** (or use an ESM CDN): Replace Babel standalone + development React with either (a) a minimal Vite/esbuild build step that produces pre-compiled `app.bundle.js`, or (b) use the `esm.sh` CDN with pre-compiled ESM React. Option (b) requires no build tooling and maintains the zero-build spirit.

15. **Async batch polling** (`news_analysis.py:304`): Move `submit_and_poll_batch` to use `asyncio` + the Anthropic async client, or run it in a `ThreadPoolExecutor`, so the scheduler is not blocked during LLM batch completion.

16. **Proper EIA data validation layer**: After fetching EIA prices, validate that returned values are within ±50% of the baseline price. If outside this range, flag the data for manual review and fall back to the previous day's price rather than the PADD district price. This prevents the $6.03/gal California price from reaching users.

17. **Price freshness indicator** in the frontend: Show a stale-data warning if `meta.pricesUpdatedAt` is older than 2 hours, to communicate data quality to users when EIA fetches are failing.

---

## 9. Documentation Gaps

| Gap | File | Details |
|-----|------|---------|
| `GNEWS_API_KEY` undocumented | `.env.example` | Variable exists in `config.py:34` and is used as news fallback but not listed in the env template |
| EIA API v2 parameter format not specified | `AGENTS.md`, `backend/AGENTS.md` | The indexed vs. repeated array parameter issue is undocumented; future developers will repeat the mistake |
| Canadian price units | `AGENTS.md` | Documents `$/L` but doesn't explain the ¢/L → $/L conversion in NRCAN scraper or Ontario CKAN; the `/100` on line 233 is undocumented |
| Batch LLM polling behavior | `backend/analytics/AGENTS.md` | Doesn't mention that `submit_and_poll_batch` blocks the scheduler thread for up to 3600s |
| Venv activation for cron scripts | `docs/deployment.md` | Shell script wrappers in `scripts/` don't activate the venv — not documented or addressed |
| Data freshness contract | `docs/deployment.md` | No documented expectation for how stale data.json can be before it should be considered invalid |
| EIA API key registration | `.env.example` comments | Correctly links to EIA registration, but doesn't explain which API endpoints are used or how to verify the key works |

---

## 10. Recommended Action Plan

| Priority | Action | Complexity | Expected Outcome |
|----------|--------|------------|-----------------|
|| P0 — Fix data immediately | **B1**: Fix EIA API `facets[duoarea][]` parameter format in `price_collector.py` | Low (20 lines) | Real state-level prices for all 50 US states + DC |
|| P0 — Fix data immediately | **B2/B3**: Verify EIA WTI endpoint; fix parameter format for crude fetch; add data validation to reject implausible prices | Low (30 lines) | Real WTI price; meaningful verdict distribution |
|| P1 — Data trust | Add price sanity check (>±50% of baseline → use previous price, log warning) | Low (15 lines) | Prevents $6.03/CA-style anomalies from reaching users |
|| P1 — Data trust | Set `analysis_updated_at` properly; ensure all 62 regions get analytics on each run | Investigate only | Confirm analytics running correctly after B1/B2 fix |
|| P1 — iOS Critical | **M1**: Add `viewport-fit=cover` to viewport meta in `index.html` | Trivial (1 attr) | Notch/Dynamic Island respected; env(safe-area-*) values work |
|| P1 — iOS Critical | **M2**: Fix `.loc-search` font-size to 16px in `styles.css` | Trivial (1 value) | No auto-zoom on iOS input focus |
|| P1 — iOS Layout | **M4**: Change `.site-wrap` overflow from `hidden` to `clip` | Trivial (1 word) | Sticky topbar works on iOS |
|| P1 — Performance/UX | **M3**: Switch to production React builds; remove in-browser Babel | Low (HTML edit) | ~97% JS size reduction (6MB→171KB); eliminate console warning |
|| P1 — Performance/UX | Remove Babel standalone; pre-compile JSX with esbuild | Low (build step) | ~70% reduction in JS parse time; zero compilation at runtime |
|| P2 — iOS Polish | **M6–M8**: Add `-webkit-text-size-adjust`, `-webkit-tap-highlight-color`, `touch-action: manipulation` to CSS | Low (CSS) | Proper iOS tap/text/zoom behavior |
|| P2 — Accessibility | Add H1 heading (visually hidden or styled) | Low (5 lines) | WCAG 2.1 compliance for screen readers |
| P2 — Accessibility | Replace `title` attributes on icon buttons with `aria-label` | Low (5 lines) | Keyboard/screen reader accessible controls |
| P2 — SEO/Social | Add `favicon.ico`, `<link rel="icon">`, and `og:image` | Low (assets + HTML) | Eliminates 404, enables social card previews |
| P2 — Bug fix | Fix duplicate Sparkline gradient ID (B5) | Low (10 lines) | Correct gradient rendering on both mobile and desktop |
| P2 — Bug fix | Guard against empty `values` array in Sparkline (B6) | Low (5 lines) | No broken SVG for thin-history regions |
| P3 — Robustness | Venv activation in shell scripts (B16, B17) | Low (1 line each) | Reliable cron execution |
| P3 — Robustness | Document `GNEWS_API_KEY` in `.env.example` | Trivial | Discoverable fallback news source |
| P3 — Robustness | Cache IP geolocation result in sessionStorage | Low (10 lines) | Eliminates 4s external fetch on every refresh |
| P3 — Robustness | Add `Cache-Control` header in `api/data.js` | Trivial | Vercel CDN caches JSON; reduces cold reads |
| P4 — Refactor | Replace `np.argmin` with pure Python; remove numpy dep | Low (5 lines) | Lighter backend install |
| P4 — Refactor | Move `submit_and_poll_batch` off the scheduler thread | Medium (async refactor) | Non-blocking 6h analytics job |
| P5 — Architecture | Pre-build JSX (esbuild or esm.sh) | Medium | Production-grade load performance |

---

*Assessment complete. The most impactful single fix is **B1** (EIA parameter format) — resolving it will likely cascade to fix B2, B3, and B4, restoring real data to all 62 regions.*

---

## 11. Mobile SPA Compliance (iOS & Cross-Browser)

A dedicated mobile SPA research document has been compiled at **`mobile-spa-research.md`** (52KB, 1,308 lines, 30+ sources). It covers five research areas specific to this codebase:

| Part | Topic | Key Findings for shouldigetgas |
|------|-------|-------------------------------|
| 1 | iOS Safari & WebKit Quirks | 100dvh implementation is correct; **`viewport-fit=cover` missing** (all `env(safe-area-*)` resolve to 0px); `overflow: hidden` on `.site-wrap` breaks sticky topbar; font-size 15px on search input triggers zoom |
| 2 | PWA Requirements | No apple-mobile-web-app meta tags; no manifest; no service worker; no apple-touch-icons; Home Screen installs behave as plain Safari tabs |
| 3 | Cross-Browser SPA Best Practices | Missing `touch-action: manipulation`, `-webkit-tap-highlight-color`, `-webkit-text-size-adjust`; no overscroll-behavior guard |
| 4 | Performance on Mobile | React dev builds are ~6MB vs 171KB production; Babel standalone adds ~2MB of in-browser compilation |
| 5 | iOS-Specific Issues | Visual Viewport API needed for keyboard avoidance; touch targets below 44×44pt HIG minimum; backdrop-filter performance concerns |

### Critical Findings for Current Codebase

| # | Issue | File | Impact | Fix |
|---|-------|------|--------|-----|
| M1 | Missing `viewport-fit=cover` — `env(safe-area-*)` values silently resolve to 0px | `frontend/index.html` | Notch/Dynamic Island ignored; content not edge-to-edge | Add `viewport-fit=cover` to viewport meta |
| M2 | Input `font-size: 15px` triggers iOS auto-zoom on focus | `frontend/css/styles.css` | Jarring zoom on every location search tap | Set to `16px` minimum |
| M3 | React dev builds — 730KB vs 45KB for production | `frontend/index.html` | ~6MB JS payload vs 171KB | Switch to `.production.min.js` URLs |
| M4 | `overflow: hidden` on `.site-wrap` breaks `position: sticky` on topbar | `frontend/css/styles.css` | Topbar scrolls away with content on iOS | Change to `overflow: clip` |
| M5 | No PWA meta tags or icons | `frontend/index.html` | Home Screen installs behave as plain Safari tabs | Add `apple-mobile-web-app-*` meta + icons |
| M6 | No `-webkit-text-size-adjust: 100%` | `frontend/css/styles.css` | iOS scales text in landscape | Add to root CSS |
| M7 | No `-webkit-tap-highlight-color: transparent` | `frontend/css/styles.css` | Grey flash on tap on iOS | Add to universal selector |
| M8 | No `touch-action: manipulation` | `frontend/css/styles.css` | Potential 300ms tap delay on some browsers | Add to interactive elements |
| M9 | No service worker — no offline fallback | New file needed | App is non-functional without network | Implement cache-first SW for static assets |
| M10 | No `overscroll-behavior` — pull-to-refresh can reload the SPA | `frontend/css/styles.css` | Accidental page reload when scrolling | Add `overscroll-behavior-y: none` |

### References Added to Action Plan

The Priority 1 items in §10 have been updated to include mobile-critical fixes. See `mobile-spa-research.md` for the full research document with source URLs, iOS version applicability, and code examples for every fix.

---\n|
