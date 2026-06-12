// ─────────────────────────────────────────────────────────────
// data.js — data model, theme engine, and JSON loader
// ─────────────────────────────────────────────────────────────

const TODAY_IDX = new Date().getDay(); // 0=Sun … 6=Sat

const VERDICTS = {
  buy:     { label: 'FILL UP', tagline: 'Good day to fill up' },
  partial: { label: 'TOP OFF', tagline: 'Get a little — wait for the rest' },
  wait:    { label: 'WAIT',    tagline: 'Hold off if you can' },
};

const PALETTES = {
  classic: {
    buy:     { wash: 'radial-gradient(130% 115% at 50% -12%, #1fa365 0%, #0e6f42 36%, #063a24 100%)', accent: '#62f0a4', word: '#ecfff5' },
    partial: { wash: 'radial-gradient(130% 115% at 50% -12%, #d68d1c 0%, #9c5e0f 36%, #4d2d07 100%)', accent: '#ffd071', word: '#fff7e8' },
    wait:    { wash: 'radial-gradient(130% 115% at 50% -12%, #d2422f 0%, #97271b 36%, #4d130d 100%)', accent: '#ff9580', word: '#ffefe9' },
    tone: { buy: '#0e8a4f', partial: '#bf771a', wait: '#cf3f2e' },
  },
};

function getTheme(verdict) {
  const pal = PALETTES.classic;
  const v = pal[verdict];
  return {
    dark: true,
    wash: v.wash, accent: v.accent, word: v.word,
    text: v.word, textSoft: 'rgba(255,255,255,0.72)',
    cardBg: 'rgba(255,255,255,0.10)', cardBorder: 'rgba(255,255,255,0.18)',
    chipBg: 'rgba(255,255,255,0.12)', chipBorder: 'rgba(255,255,255,0.24)',
    onAccent: '#0c0f0c',
  };
}

const DAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

const SOURCES = {
  price:     { label: 'EIA',     full: 'EIA · Weekly Retail Prices',           url: 'https://www.eia.gov/petroleum/gasdiesel/' },
  crude:     { label: 'EIA',     full: 'EIA · WTI Spot Price',                 url: 'https://www.eia.gov/dnav/pet/hist/RWTCD.htm' },
  breakdown: { label: 'EIA',     full: 'EIA · What drives gas prices',         url: 'https://www.eia.gov/energyexplained/gasoline/factors-affecting-gasoline-prices.php' },
};

// Placeholder regions — overwritten when data.json loads
const PLACEHOLDER_REGIONS = [
  {
    id: 'ca', state: 'California', abbr: 'CA', city: 'San Francisco',
    verdict: 'wait', price: 4.62, priceLow: 4.31, weekDelta: +0.06,
    why: 'Prices are climbing toward a mid-week peak as refineries finish the summer-blend switchover.',
    advice: 'Hold until Thursday', bestDayIdx: 4,
    wtiDir: 'down',
    news: [
      { headline: 'West Coast refinery maintenance is tightening regional supply this week.', source: 'Reuters', url: 'https://www.reuters.com/business/energy/' },
      { headline: 'California summer-blend switchover adds a seasonal premium at the pump.', source: 'EIA', url: 'https://www.eia.gov/petroleum/gasdiesel/' },
      { headline: 'Crude eases as OPEC+ signals steady output into next quarter.', source: 'Bloomberg', url: 'https://www.bloomberg.com/energy' },
    ],
    breakdown: { crude: 58, refining: 18, taxes: 15, dist: 9 },
    trend: [4.41,4.40,4.43,4.45,4.44,4.48,4.50,4.52,4.51,4.55,4.57,4.58,4.60,4.62],
    priceSource: 'gasbuddy',
    lowStation: { id: '187', name: 'Costco', price: 4.31, lat: 37.77, lng: -122.42, url: 'https://www.gasbuddy.com/station/187' },
  },
  {
    id: 'tx', state: 'Texas', abbr: 'TX', city: 'Austin',
    verdict: 'buy', price: 2.74, priceLow: 2.61, weekDelta: -0.11,
    why: 'Prices are near a two-week low — crude slipped 3% and Gulf refineries are running hot.',
    advice: 'Fill up today', bestDayIdx: 2,
    wtiDir: 'down',
    news: [
      { headline: 'Ample Gulf Coast supply is keeping pump prices soft across Texas.', source: 'AP News', url: 'https://apnews.com/hub/energy' },
      { headline: 'Gulf refineries run near peak utilization, easing local prices.', source: 'EIA', url: 'https://www.eia.gov/petroleum/gasdiesel/' },
      { headline: 'WTI crude dips 3% on a softer global demand outlook.', source: 'Reuters', url: 'https://www.reuters.com/business/energy/' },
    ],
    breakdown: { crude: 64, refining: 13, taxes: 12, dist: 11 },
    trend: [3.05,3.02,2.99,2.98,2.95,2.92,2.90,2.88,2.85,2.83,2.80,2.78,2.76,2.74],
  },
  {
    id: 'ny', state: 'New York', abbr: 'NY', city: 'Brooklyn',
    verdict: 'partial', price: 3.41, priceLow: 3.18, weekDelta: +0.04,
    why: 'Rising now, but futures point to a small dip Thursday. Half a tank covers you until then.',
    advice: 'Half now · full Thu', bestDayIdx: 4,
    wtiDir: 'down',
    news: [
      { headline: 'Northeast demand is firm ahead of the holiday travel weekend.', source: 'Bloomberg', url: 'https://www.bloomberg.com/energy' },
      { headline: 'Harbor inventories hold steady as imports arrive on schedule.', source: 'OPIS', url: 'https://www.opisnet.com/' },
      { headline: 'Futures point to a brief mid-week dip in retail prices.', source: 'Reuters', url: 'https://www.reuters.com/business/energy/' },
    ],
    breakdown: { crude: 60, refining: 15, taxes: 16, dist: 9 },
    trend: [3.22,3.24,3.23,3.27,3.30,3.29,3.33,3.35,3.34,3.37,3.39,3.38,3.40,3.41],
  },
  {
    id: 'fl', state: 'Florida', abbr: 'FL', city: 'Miami',
    verdict: 'buy', price: 3.05, priceLow: 2.89, weekDelta: -0.07,
    why: 'Steady decline all week with no supply pressure on the horizon. Good time to fill.',
    advice: 'Fill up today', bestDayIdx: 2,
    wtiDir: 'down',
    news: [
      { headline: 'A calm hurricane outlook is keeping Southeast supply stable.', source: 'AP News', url: 'https://apnews.com/hub/energy' },
      { headline: 'Florida demand cools after the spring-break travel peak.', source: 'Bloomberg', url: 'https://www.bloomberg.com/energy' },
      { headline: 'Lower crude costs continue to filter through to the pump.', source: 'EIA', url: 'https://www.eia.gov/petroleum/gasdiesel/' },
    ],
    breakdown: { crude: 62, refining: 14, taxes: 13, dist: 11 },
    trend: [3.20,3.18,3.19,3.16,3.14,3.12,3.10,3.11,3.09,3.08,3.07,3.06,3.05,3.05],
  },
  {
    id: 'wa', state: 'Washington', abbr: 'WA', city: 'Seattle',
    verdict: 'wait', price: 4.38, priceLow: 4.09, weekDelta: +0.08,
    why: 'A steady climb driven by higher state taxes and tight Pacific Northwest supply.',
    advice: 'Wait a few days', bestDayIdx: 5,
    wtiDir: 'down',
    news: [
      { headline: 'Pipeline scheduling is limiting deliveries into the Pacific Northwest.', source: 'Reuters', url: 'https://www.reuters.com/business/energy/' },
      { headline: 'State carbon program keeps Washington prices above the national average.', source: 'OPIS', url: 'https://www.opisnet.com/' },
      { headline: 'Regional refiners enter spring turnaround season.', source: 'EIA', url: 'https://www.eia.gov/petroleum/gasdiesel/' },
    ],
    breakdown: { crude: 55, refining: 17, taxes: 19, dist: 9 },
    trend: [4.18,4.20,4.19,4.23,4.25,4.24,4.28,4.30,4.31,4.33,4.34,4.36,4.37,4.38],
  },
  {
    id: 'il', state: 'Illinois', abbr: 'IL', city: 'Chicago',
    verdict: 'partial', price: 3.58, priceLow: 3.34, weekDelta: +0.05,
    why: 'Edging up, but a refinery returning from maintenance should ease prices late this week.',
    advice: 'Half now · full Fri', bestDayIdx: 5,
    wtiDir: 'down',
    news: [
      { headline: 'A Midwest refinery is ramping back up after planned maintenance.', source: 'Reuters', url: 'https://www.reuters.com/business/energy/' },
      { headline: 'Chicago spot prices ease as regional supply normalizes.', source: 'OPIS', url: 'https://www.opisnet.com/' },
      { headline: 'A crude pullback should reach Midwest pumps within two weeks.', source: 'EIA', url: 'https://www.eia.gov/petroleum/gasdiesel/' },
    ],
    breakdown: { crude: 59, refining: 16, taxes: 16, dist: 9 },
    trend: [3.40,3.42,3.41,3.45,3.47,3.46,3.49,3.51,3.50,3.53,3.55,3.54,3.56,3.58],
  },
];

// IP-based region detection — returns a region id string.
async function detectRegionFromIP() {
  try {
    const cached = sessionStorage.getItem('sig-region');
    if (cached) return cached;
  } catch (_) { /* storage unavailable — treat as cache miss */ }
  try {
    const res = await fetch('https://ipapi.co/json/', { signal: AbortSignal.timeout(4000) });
    if (!res.ok) return null;
    const data = await res.json();
    const stateCode = (data.region_code || '').toUpperCase();
    const country   = (data.country_code || '').toUpperCase();

    // US states (50 + DC)
    const US_MAP = {
      AL:'al', AK:'ak', AZ:'az', AR:'ar', CA:'ca', CO:'co', CT:'ct', DE:'de',
      FL:'fl', GA:'ga', HI:'hi', ID:'id', IL:'il', IN:'in', IA:'ia', KS:'ks',
      KY:'ky', LA:'la', ME:'me', MD:'md', MA:'ma', MI:'mi', MN:'mn', MS:'ms',
      MO:'mo', MT:'mt', NE:'ne', NV:'nv', NH:'nh', NJ:'nj', NM:'nm', NY:'ny',
      NC:'nc', ND:'nd', OH:'oh', OK:'ok', OR:'or', PA:'pa', RI:'ri', SC:'sc',
      SD:'sd', TN:'tn', TX:'tx', UT:'ut', VT:'vt', VA:'va', WA:'wa', WV:'wv',
      WI:'wi', WY:'wy', DC:'dc',
    };

    // Canadian provinces and territories
    const CA_MAP = {
      AB:'ab', BC:'bc', MB:'mb', NB:'nb', NL:'nl', NS:'ns',
      ON:'on', PE:'pe', QC:'qc', SK:'sk',
      NT:'north', NU:'north', YT:'north',
    };

    let mapped = null;
    if (country === 'CA') {
      mapped = CA_MAP[stateCode] || 'on';   // Ontario default for unmatched CA
    } else {
      mapped = US_MAP[stateCode] || 'ca';
    }

    if (!mapped) {
      console.warn('[shouldigetgas] IP detection: region not mapped —', stateCode, country, '— defaulting to CA');
    }
    try { if (mapped) sessionStorage.setItem('sig-region', mapped); } catch (_) { /* best-effort cache write */ }
    return mapped;
  } catch (err) {
    console.warn('[shouldigetgas] IP detection failed:', err?.message ?? err);
    return null;
  }
}

// Load data from the JSON file, falling back to placeholder data.
async function loadData() {
  try {
    const res = await fetch('/data/data.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error('fetch failed');
    const json = await res.json();
    return {
      regions: json.regions || PLACEHOLDER_REGIONS,
      meta: json.meta || {},
      wti: json.wti || { price: 71.2, dir: 'down', change: -1.4 },
    };
  } catch {
    return { regions: PLACEHOLDER_REGIONS, meta: {}, wti: { price: 71.2, dir: 'down', change: -1.4 } };
  }
}

// Format relative time for "updated X ago"
function formatRelativeTime(isoString) {
  if (!isoString) return '';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// Price precision is unit-aware: US gallons use 2 decimals ($3.45), Canadian
// litres use 3 (tenths of a cent matter and the backend `why` copy quotes them
// at 3 decimals, e.g. $1.683/L). Keep the headline consistent with that copy.
function formatPrice(value, unit) {
  return Number(value).toFixed(unit === 'L' ? 3 : 2);
}

// Week-over-week delta for display. A move under half a cent is "flat" — no
// arrow, no sign — so we never render a directional zero like "↓ −0¢". Honours
// the backend's explicit weekDeltaDir when present, else derives from the value.
function formatDelta(weekDelta, dir) {
  const cents = Math.abs(weekDelta * 100);
  const flat = dir === 'flat' || cents < 0.5;
  const up = flat ? false : (dir ? dir === 'up' : weekDelta >= 0);
  return {
    flat,
    up,
    arrow: flat ? '' : (up ? '↑' : '↓'),
    sign: flat ? '' : (up ? '+' : '−'),
    cents: cents.toFixed(0),
    label: flat ? 'flat this week' : `${up ? '+' : '−'}${cents.toFixed(0)}¢ this week`,
  };
}

Object.assign(window, {
  VERDICTS, PALETTES, getTheme, TODAY_IDX, DAYS, SOURCES,
  PLACEHOLDER_REGIONS, detectRegionFromIP, loadData, formatRelativeTime,
  formatPrice, formatDelta,
});
