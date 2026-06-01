# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

There is no build step. Serve the `frontend/` directory with any static file server:

```bash
# Python (simplest)
python3 -m http.server 8080 --directory frontend

# Node
npx serve frontend
```

Then open `http://localhost:8080`. You can also open `frontend/index.html` directly in a browser — all assets are relative, so file:// works for most features (IP geolocation fetch will silently fall back to the first placeholder region).

## Architecture

This is a **zero-build frontend**: React 18 and Babel are loaded from CDN in `index.html`, and JSX is compiled in-browser at runtime. There is no `node_modules`, no bundler, no transpile step.

The three JS files are loaded as `type="text/babel"` scripts and communicate exclusively through `window` globals. Load order matters — `data.js` → `components.js` → `app.js`.

### JS module responsibilities

| File | Role |
|------|------|
| `js/data.js` | Data model, theme engine, placeholder regions, `loadData()` / `detectRegionFromIP()` helpers. Exports to `window`. |
| `js/components.js` | All presentational React components (`GasPriceDisplay`, `Sparkline`, `DayStrip`, `LocationSheet`, `ContextContent`, `Sheet`, `Toast`, etc.). Exports to `window`. |
| `js/app.js` | Root `App` component — state management, layout composition (hero + context rail + mobile sheets), entry point (`ReactDOM.createRoot`). |

### Data flow

On mount, `App` calls `loadData()` and `detectRegionFromIP()` in parallel. `loadData()` fetches `data/data.json` and falls back to `PLACEHOLDER_REGIONS` hardcoded in `data.js`. `detectRegionFromIP()` calls `ipapi.co` and maps the returned state code to a region id.

### Theme engine

Verdict (`buy` | `partial` | `wait`) drives the entire visual theme. `getTheme(verdict)` in `data.js` returns a `theme` object with all color tokens (`accent`, `word`, `wash`, `cardBg`, etc.) that components receive as props. The full-screen gradient background (`WashBackground`) cross-fades between themes when the region changes.

### Region data shape

Each region in `data/data.json` (and `PLACEHOLDER_REGIONS`) has:
- `verdict`: `'buy'` | `'partial'` | `'wait'`
- `price`: regional average $/gal
- `priceLow`: lowest nearby station price (used when `precise` mode is on)
- `weekDelta`: week-over-week change in dollars (positive = rising)
- `trend`: array of 14 price values for the sparkline
- `bestDayIdx`: 0–6 index into `DAYS` array for the DayStrip highlight
- `why`: plain-English explanation text
- `breakdown`: `{ crude, refining, taxes, dist }` percentages summing to 100
- `news`: array of `{ headline, source, url }`

### Responsive layout

CSS drives two layouts from the same JSX tree:
- **Mobile**: hero column → support cards (day strip + sparkline) → GasBuddy CTA. Context panel opens as a bottom sheet.
- **Desktop (≥900px)**: two-column grid — hero left, context rail right. Support cards and mobile GasBuddy button are hidden via `display: none`.

## Current status

The frontend is fully built with static/placeholder data. **No backend exists yet.** The planned FastAPI backend (EIA API integration, prediction model, news fetching) is described in `README.md`. `data/data.json` is hand-authored placeholder data that mimics the eventual API response shape.

To add a new region, add an entry to both `PLACEHOLDER_REGIONS` in `js/data.js` and `frontend/data/data.json`, and add its state code to the `regionMap` in `detectRegionFromIP()`.
