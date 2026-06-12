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

# EIA `gnd` (gasoline) dataset duoarea codes for PADD districts.
# NOTE: the petroleum/pri/gnd dataset addresses PADD districts as "R10".."R50",
# NOT "P1".."P5" (those return zero rows). This map is the difference between a
# real, weekly-moving fallback price and a flat baseline for the ~42 US states
# that have no state-level weekly EIA series.
PADD_DUOAREA = {
    "P1": "R10",
    "P2": "R20",
    "P3": "R30",
    "P4": "R40",
    "P5": "R50",
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
