"""
Central configuration: region definitions, API key env-var names, paths.
All secrets read from environment variables — never hardcoded here.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
DB_PATH   = Path(os.getenv("DB_PATH",  REPO_ROOT / "data" / "shouldigetgas.db"))
DATA_JSON = Path(os.getenv("DATA_JSON_PATH", REPO_ROOT / "frontend" / "data" / "data.json"))

# ── API keys ───────────────────────────────────────────────────────────────────
EIA_API_KEY        = os.getenv("EIA_API_KEY", "")
NEWS_API_KEY       = os.getenv("NEWS_API_KEY", "")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
REDIS_URL          = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── GasBuddy (py-gasbuddy library) ────────────────────────────────────────────
# GasBuddy's GraphQL sits behind Cloudflare's interactive challenge. Optionally
# route the CSRF-token fetch through a FlareSolverr-compatible solver endpoint
# (py-gasbuddy `solver_url`); empty disables it and we rely on the host's own IP
# reputation (works from residential hosts, blocked from hardened datacenter IPs).
GASBUDDY_SOLVER_URL  = os.getenv("GASBUDDY_SOLVER_URL", "")
# Where py-gasbuddy caches the gbcsrf token (kept beside the DB so all runtime
# state lives in one directory).
GASBUDDY_TOKEN_CACHE = Path(os.getenv("GASBUDDY_TOKEN_CACHE", DB_PATH.parent / "gasbuddy_token"))

# ── Schedule intervals (minutes / hours) ─────────────────────────────────────
PRICE_REFRESH_MINUTES    = int(os.getenv("PRICE_REFRESH_MINUTES", "30"))
ANALYTICS_REFRESH_HOURS  = int(os.getenv("ANALYTICS_REFRESH_HOURS", "6"))

# ── EIA API endpoints ──────────────────────────────────────────────────────────
EIA_GAS_ENDPOINT   = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
EIA_SPT_ENDPOINT   = "https://api.eia.gov/v2/petroleum/pri/spt/data/"   # WTI/Brent
EIA_CAP_ENDPOINT   = "https://api.eia.gov/v2/petroleum/operate/cap/pct/data/"  # refinery util
EIA_V1_SERIES      = "https://api.eia.gov/series/"   # legacy v1 fallback for WTI

# ── News API ───────────────────────────────────────────────────────────────────
NEWS_API_ENDPOINT  = "https://newsapi.org/v2/everything"
GNEWS_API_KEY      = os.getenv("GNEWS_API_KEY", "")
GNEWS_API_ENDPOINT = "https://gnews.io/api/v4/search"

# ── Ontario open data ─────────────────────────────────────────────────────────
ONTARIO_FUEL_API   = "https://data.ontario.ca/api/3/action/datastore_search"
ONTARIO_RESOURCE_ID = "e8c2e491-ba6a-4f27-9428-e1cfe11b00fa"

# ── NRCAN Fuel Price Monitor (weekly city-level prices, scraped) ───────────────
NRCAN_PRICE_URL    = "https://www2.nrcan.gc.ca/eneene/sources/pripri/prices_bycity_e.cfm"

# ── US Regions: (id, display_name, abbr, reference_city, eia_stateid, padd) ──
# eia_stateid is the 2-letter code used with EIA API facets[stateid][]=
# padd is the fallback PAD district code if state-level data is sparse
US_REGIONS = [
    ("al", "Alabama",              "AL", "Birmingham",     "AL", "P3"),
    ("ak", "Alaska",               "AK", "Anchorage",      "AK", "P5"),
    ("az", "Arizona",              "AZ", "Phoenix",        "AZ", "P5"),
    ("ar", "Arkansas",             "AR", "Little Rock",    "AR", "P3"),
    ("ca", "California",           "CA", "Los Angeles",    "CA", "P5"),
    ("co", "Colorado",             "CO", "Denver",         "CO", "P4"),
    ("ct", "Connecticut",          "CT", "Hartford",       "CT", "P1"),
    ("de", "Delaware",             "DE", "Wilmington",     "DE", "P1"),
    ("fl", "Florida",              "FL", "Miami",          "FL", "P1"),
    ("ga", "Georgia",              "GA", "Atlanta",        "GA", "P1"),
    ("hi", "Hawaii",               "HI", "Honolulu",       "HI", "P5"),
    ("id", "Idaho",                "ID", "Boise",          "ID", "P4"),
    ("il", "Illinois",             "IL", "Chicago",        "IL", "P2"),
    ("in", "Indiana",              "IN", "Indianapolis",   "IN", "P2"),
    ("ia", "Iowa",                 "IA", "Des Moines",     "IA", "P2"),
    ("ks", "Kansas",               "KS", "Wichita",        "KS", "P2"),
    ("ky", "Kentucky",             "KY", "Louisville",     "KY", "P3"),
    ("la", "Louisiana",            "LA", "New Orleans",    "LA", "P3"),
    ("me", "Maine",                "ME", "Portland",       "ME", "P1"),
    ("md", "Maryland",             "MD", "Baltimore",      "MD", "P1"),
    ("ma", "Massachusetts",        "MA", "Boston",         "MA", "P1"),
    ("mi", "Michigan",             "MI", "Detroit",        "MI", "P2"),
    ("mn", "Minnesota",            "MN", "Minneapolis",    "MN", "P2"),
    ("ms", "Mississippi",          "MS", "Jackson",        "MS", "P3"),
    ("mo", "Missouri",             "MO", "Kansas City",    "MO", "P2"),
    ("mt", "Montana",              "MT", "Billings",       "MT", "P4"),
    ("ne", "Nebraska",             "NE", "Omaha",          "NE", "P2"),
    ("nv", "Nevada",               "NV", "Las Vegas",      "NV", "P5"),
    ("nh", "New Hampshire",        "NH", "Manchester",     "NH", "P1"),
    ("nj", "New Jersey",           "NJ", "Newark",         "NJ", "P1"),
    ("nm", "New Mexico",           "NM", "Albuquerque",    "NM", "P3"),
    ("ny", "New York",             "NY", "New York City",  "NY", "P1"),
    ("nc", "North Carolina",       "NC", "Charlotte",      "NC", "P1"),
    ("nd", "North Dakota",         "ND", "Fargo",          "ND", "P2"),
    ("oh", "Ohio",                 "OH", "Columbus",       "OH", "P2"),
    ("ok", "Oklahoma",             "OK", "Oklahoma City",  "OK", "P3"),
    ("or", "Oregon",               "OR", "Portland",       "OR", "P5"),
    ("pa", "Pennsylvania",         "PA", "Philadelphia",   "PA", "P1"),
    ("ri", "Rhode Island",         "RI", "Providence",     "RI", "P1"),
    ("sc", "South Carolina",       "SC", "Columbia",       "SC", "P1"),
    ("sd", "South Dakota",         "SD", "Sioux Falls",    "SD", "P2"),
    ("tn", "Tennessee",            "TN", "Nashville",      "TN", "P3"),
    ("tx", "Texas",                "TX", "Houston",        "TX", "P3"),
    ("ut", "Utah",                 "UT", "Salt Lake City", "UT", "P4"),
    ("vt", "Vermont",              "VT", "Burlington",     "VT", "P1"),
    ("va", "Virginia",             "VA", "Richmond",       "VA", "P1"),
    ("wa", "Washington",           "WA", "Seattle",        "WA", "P5"),
    ("wv", "West Virginia",        "WV", "Charleston",     "WV", "P1"),
    ("wi", "Wisconsin",            "WI", "Milwaukee",      "WI", "P2"),
    ("wy", "Wyoming",              "WY", "Cheyenne",       "WY", "P4"),
    ("dc", "District of Columbia", "DC", "Washington",     "DC", "P1"),
]

# EIA PADD district names (fallback area codes)
PADD_CODES = {
    "P1": "New England/East Coast",
    "P2": "Midwest",
    "P3": "Gulf Coast",
    "P4": "Rocky Mountain",
    "P5": "West Coast",
}

# ── Canadian Regions: (id, display_name, abbr, reference_city, nrcan_city_key, country) ──
# nrcan_city_key: city name used in NRCAN price data
# Prices stored in CAD/L; unit field = "L"
CA_REGIONS = [
    ("ab",    "Alberta",              "AB",       "Calgary",         "Calgary",      "CA"),
    ("bc",    "British Columbia",     "BC",       "Vancouver",       "Vancouver",    "CA"),
    ("mb",    "Manitoba",             "MB",       "Winnipeg",        "Winnipeg",     "CA"),
    ("nb",    "New Brunswick",        "NB",       "Moncton",         "Moncton",      "CA"),
    ("nl",    "Newfoundland",         "NL",       "St. John's",      "St. John's",   "CA"),
    ("ns",    "Nova Scotia",          "NS",       "Halifax",         "Halifax",      "CA"),
    ("on",    "Ontario",              "ON",       "Toronto",         "Toronto",      "CA"),
    ("pe",    "Prince Edward Island", "PE",       "Charlottetown",   "Charlottetown","CA"),
    ("qc",    "Quebec",               "QC",       "Montreal",        "Montreal",     "CA"),
    ("sk",    "Saskatchewan",         "SK",       "Regina",          "Regina",       "CA"),
    ("north", "Northern Canada",      "NT/NU/YT", "Whitehorse",      "Whitehorse",   "CA"),
]

# All regions combined
ALL_REGIONS = US_REGIONS + [
    # Expand CA_REGIONS to include country field in same tuple format
    (r[0], r[1], r[2], r[3], r[4], r[5]) for r in CA_REGIONS
]

# Lookup helpers
REGION_BY_ID = {r[0]: r for r in ALL_REGIONS}

def get_region(region_id: str):
    return REGION_BY_ID.get(region_id)

def is_canadian(region_id: str) -> bool:
    return region_id in {r[0] for r in CA_REGIONS}

def region_unit(region_id: str) -> str:
    return "L" if is_canadian(region_id) else "gal"

# ── Canadian provincial fuel taxes (approximate, for breakdown module) ─────────
# Format: (federal_excise_cpl, carbon_levy_cpl, provincial_fuel_tax_cpl, sales_tax_pct)
# cpl = cents per litre; sales_tax_pct applied to pre-tax price + specific taxes
CA_TAX_RATES = {
    "ab":    {"federal_excise": 10.0, "carbon_levy": 0.0,  "prov_fuel": 13.0, "sales_tax_pct": 5.0},   # TIER system, no carbon backstop
    "bc":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 18.5, "sales_tax_pct": 12.0},
    "mb":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 14.0, "sales_tax_pct": 12.0},
    "nb":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 15.5, "sales_tax_pct": 15.0},
    "nl":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 16.5, "sales_tax_pct": 15.0},
    "ns":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 15.5, "sales_tax_pct": 15.0},
    "on":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 14.7, "sales_tax_pct": 13.0},
    "pe":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 13.1, "sales_tax_pct": 15.0},
    "qc":    {"federal_excise": 10.0, "carbon_levy":  0.0, "prov_fuel": 19.2, "sales_tax_pct": 14.975},  # cap-and-trade ~5.5¢
    "sk":    {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 15.0, "sales_tax_pct": 14.0},
    "north": {"federal_excise": 10.0, "carbon_levy": 17.6, "prov_fuel": 10.7, "sales_tax_pct": 5.0},
}

# ── US state fuel taxes (¢/gallon) — federal + state ─────────────────────────
# Source: EIA state-by-state data (approximate 2024 figures)
US_TAX_CPG = {
    "al": 39.3, "ak": 14.7, "az": 37.4, "ar": 40.2, "ca": 73.1,
    "co": 40.4, "ct": 61.7, "de": 41.4, "fl": 59.9, "ga": 49.4,
    "hi": 60.6, "id": 51.4, "il": 78.3, "in": 65.5, "ia": 47.4,
    "ks": 43.4, "ky": 48.6, "la": 38.4, "me": 49.8, "md": 62.7,
    "ma": 44.9, "mi": 60.4, "mn": 51.9, "ms": 36.4, "mo": 35.7,
    "mt": 46.2, "ne": 46.4, "nv": 68.6, "nh": 36.0, "nj": 59.5,
    "nm": 37.3, "ny": 73.0, "nc": 50.3, "nd": 41.4, "oh": 56.5,
    "ok": 35.4, "or": 54.3, "pa": 77.0, "ri": 50.3, "sc": 41.8,
    "sd": 42.4, "tn": 40.7, "tx": 38.4, "ut": 49.2, "vt": 49.3,
    "va": 45.0, "wa": 82.8, "wv": 51.6, "wi": 54.4, "wy": 42.4,
    "dc": 43.5,
}

# ── Historical baseline prices (used as final fallback when APIs fail) ─────────
# US: $/gallon regular; CA: $/L (CAD)
BASELINE_PRICES = {
    # US states (approximate 2024-2026 averages)
    "al": 2.87, "ak": 3.72, "az": 3.21, "ar": 2.81, "ca": 4.62,
    "co": 3.18, "ct": 3.45, "de": 3.20, "fl": 3.12, "ga": 2.92,
    "hi": 4.55, "id": 3.28, "il": 3.62, "in": 3.24, "ia": 3.08,
    "ks": 3.02, "ky": 3.05, "la": 2.92, "me": 3.38, "md": 3.28,
    "ma": 3.38, "mi": 3.32, "mn": 3.18, "ms": 2.85, "mo": 2.98,
    "mt": 3.35, "ne": 3.09, "nv": 3.82, "nh": 3.28, "nj": 3.28,
    "nm": 3.15, "ny": 3.45, "nc": 3.05, "nd": 3.18, "oh": 3.28,
    "ok": 2.88, "or": 3.88, "pa": 3.52, "ri": 3.40, "sc": 3.05,
    "sd": 3.15, "tn": 2.95, "tx": 2.78, "ut": 3.35, "vt": 3.38,
    "va": 3.15, "wa": 4.42, "wv": 3.18, "wi": 3.28, "wy": 3.25,
    "dc": 3.55,
    # Canadian provinces (CAD/L approximate)
    "ab": 1.38, "bc": 1.72, "mb": 1.48, "nb": 1.55, "nl": 1.58,
    "ns": 1.55, "on": 1.52, "pe": 1.54, "qc": 1.58, "sk": 1.41,
    "north": 1.88,
}

# ── Reference-city coordinates per region (lat, lng) ──────────────────────────
# GasBuddy station lookups go through py-gasbuddy, which queries by coordinates
# (not free-text), so each region maps to its reference city — the 4th field of
# US_REGIONS / CA_REGIONS — for the nearest-stations query.
REGION_COORDS = {
    # US states / DC — reference city
    "al": (33.5186,  -86.8104),   # Birmingham
    "ak": (61.2181, -149.9003),   # Anchorage
    "az": (33.4484, -112.0740),   # Phoenix
    "ar": (34.7465,  -92.2896),   # Little Rock
    "ca": (34.0522, -118.2437),   # Los Angeles
    "co": (39.7392, -104.9903),   # Denver
    "ct": (41.7658,  -72.6734),   # Hartford
    "de": (39.7459,  -75.5466),   # Wilmington
    "fl": (25.7617,  -80.1918),   # Miami
    "ga": (33.7490,  -84.3880),   # Atlanta
    "hi": (21.3069, -157.8583),   # Honolulu
    "id": (43.6150, -116.2023),   # Boise
    "il": (41.8781,  -87.6298),   # Chicago
    "in": (39.7684,  -86.1581),   # Indianapolis
    "ia": (41.5868,  -93.6250),   # Des Moines
    "ks": (37.6872,  -97.3301),   # Wichita
    "ky": (38.2527,  -85.7585),   # Louisville
    "la": (29.9511,  -90.0715),   # New Orleans
    "me": (43.6591,  -70.2568),   # Portland, ME
    "md": (39.2904,  -76.6122),   # Baltimore
    "ma": (42.3601,  -71.0589),   # Boston
    "mi": (42.3314,  -83.0458),   # Detroit
    "mn": (44.9778,  -93.2650),   # Minneapolis
    "ms": (32.2988,  -90.1848),   # Jackson
    "mo": (39.0997,  -94.5786),   # Kansas City
    "mt": (45.7833, -108.5007),   # Billings
    "ne": (41.2565,  -95.9345),   # Omaha
    "nv": (36.1699, -115.1398),   # Las Vegas
    "nh": (42.9956,  -71.4548),   # Manchester
    "nj": (40.7357,  -74.1724),   # Newark
    "nm": (35.0844, -106.6504),   # Albuquerque
    "ny": (40.7128,  -74.0060),   # New York City
    "nc": (35.2271,  -80.8431),   # Charlotte
    "nd": (46.8772,  -96.7898),   # Fargo
    "oh": (39.9612,  -82.9988),   # Columbus
    "ok": (35.4676,  -97.5164),   # Oklahoma City
    "or": (45.5152, -122.6784),   # Portland, OR
    "pa": (39.9526,  -75.1652),   # Philadelphia
    "ri": (41.8240,  -71.4128),   # Providence
    "sc": (34.0007,  -81.0348),   # Columbia
    "sd": (43.5460,  -96.7313),   # Sioux Falls
    "tn": (36.1627,  -86.7816),   # Nashville
    "tx": (29.7604,  -95.3698),   # Houston
    "ut": (40.7608, -111.8910),   # Salt Lake City
    "vt": (44.4759,  -73.2121),   # Burlington
    "va": (37.5407,  -77.4360),   # Richmond
    "wa": (47.6062, -122.3321),   # Seattle
    "wv": (38.3498,  -81.6326),   # Charleston
    "wi": (43.0389,  -87.9065),   # Milwaukee
    "wy": (41.1400, -104.8202),   # Cheyenne
    "dc": (38.9072,  -77.0369),   # Washington
    # Canadian provinces / territories — reference city
    "ab":    (51.0447, -114.0719),   # Calgary
    "bc":    (49.2827, -123.1207),   # Vancouver
    "mb":    (49.8951,  -97.1384),   # Winnipeg
    "nb":    (46.0878,  -64.7782),   # Moncton
    "nl":    (47.5615,  -52.7126),   # St. John's
    "ns":    (44.6488,  -63.5752),   # Halifax
    "on":    (43.6532,  -79.3832),   # Toronto
    "pe":    (46.2382,  -63.1311),   # Charlottetown
    "qc":    (45.5017,  -73.5673),   # Montreal
    "sk":    (50.4452, -104.6189),   # Regina
    "north": (60.7212, -135.0568),   # Whitehorse
}
