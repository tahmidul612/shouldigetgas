"""
SQLite schema, migration, and sync/async connection helpers.
Run directly to initialise a fresh database: python backend/db.py
"""
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager

from config import DB_PATH

log = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id  TEXT,
    region_id   TEXT NOT NULL,
    price       REAL NOT NULL,   -- $/gal (US) or $/L (CA)
    unit        TEXT NOT NULL DEFAULT 'gal',
    lat         REAL,
    lon         REAL,
    city        TEXT,
    fetched_at  TEXT NOT NULL    -- ISO 8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_stations_region_time
    ON stations(region_id, fetched_at);

CREATE TABLE IF NOT EXISTS regional_snapshot (
    region_id       TEXT PRIMARY KEY,
    state           TEXT NOT NULL,
    abbr            TEXT NOT NULL,
    city            TEXT NOT NULL,
    country         TEXT NOT NULL DEFAULT 'US',
    unit            TEXT NOT NULL DEFAULT 'gal',
    verdict         TEXT NOT NULL DEFAULT 'partial',
    price           REAL,
    price_low       REAL,
    week_delta      REAL DEFAULT 0.0,
    why             TEXT DEFAULT '',
    advice          TEXT DEFAULT '',
    best_day_idx    INTEGER DEFAULT 2,
    wti_dir         TEXT DEFAULT 'flat',
    breakdown_json  TEXT DEFAULT '{}',  -- JSON string
    trend_json      TEXT DEFAULT '[]',  -- JSON string
    news_json       TEXT DEFAULT '[]',  -- JSON string
    prices_updated_at  TEXT,
    analysis_updated_at TEXT
);

CREATE TABLE IF NOT EXISTS crude_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,   -- 'WTI' or 'BRENT'
    price       REAL NOT NULL,   -- USD/barrel
    period      TEXT NOT NULL,   -- date string YYYY-MM-DD
    fetched_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_crude_symbol_period
    ON crude_prices(symbol, period);

CREATE TABLE IF NOT EXISTS news_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    headline        TEXT NOT NULL,
    source          TEXT,
    url             TEXT,
    published_at    TEXT,
    relevance_score REAL DEFAULT 0.5,
    impact_dir      TEXT,          -- 'up' | 'down' | 'flat' | NULL
    impact_mag      TEXT,          -- 'low' | 'medium' | 'high' | NULL
    affected_regions TEXT,         -- JSON array of region_ids, or 'all'
    fetched_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_fetched ON news_cache(fetched_at);

CREATE TABLE IF NOT EXISTS prediction_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id       TEXT NOT NULL,
    predicted_at    TEXT NOT NULL,
    predicted_dir   TEXT,          -- 'up' | 'down' | 'flat'
    predicted_delta REAL,
    actual_delta    REAL,          -- filled in later by comparison
    verdict         TEXT
);
CREATE INDEX IF NOT EXISTS idx_pred_region ON prediction_log(region_id, predicted_at);
"""


def get_db_path() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    path = get_db_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        log.info("Database initialised at %s", path)
    finally:
        conn.close()


@contextmanager
def get_conn():
    """Synchronous connection context manager with row_factory."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_snapshot(region_id: str, data: dict):
    """Write or update a single region's snapshot row."""
    import json
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO regional_snapshot (
                region_id, state, abbr, city, country, unit,
                verdict, price, price_low, week_delta,
                why, advice, best_day_idx, wti_dir,
                breakdown_json, trend_json, news_json,
                prices_updated_at, analysis_updated_at
            ) VALUES (
                :region_id, :state, :abbr, :city, :country, :unit,
                :verdict, :price, :price_low, :week_delta,
                :why, :advice, :best_day_idx, :wti_dir,
                :breakdown_json, :trend_json, :news_json,
                :prices_updated_at, :analysis_updated_at
            )
            ON CONFLICT(region_id) DO UPDATE SET
                state               = excluded.state,
                abbr                = excluded.abbr,
                city                = excluded.city,
                country             = excluded.country,
                unit                = excluded.unit,
                verdict             = excluded.verdict,
                price               = excluded.price,
                price_low           = excluded.price_low,
                week_delta          = excluded.week_delta,
                why                 = excluded.why,
                advice              = excluded.advice,
                best_day_idx        = excluded.best_day_idx,
                wti_dir             = excluded.wti_dir,
                breakdown_json      = excluded.breakdown_json,
                trend_json          = excluded.trend_json,
                news_json           = excluded.news_json,
                prices_updated_at   = COALESCE(excluded.prices_updated_at, regional_snapshot.prices_updated_at),
                analysis_updated_at = COALESCE(excluded.analysis_updated_at, regional_snapshot.analysis_updated_at)
        """, {
            "region_id":          region_id,
            "state":              data.get("state", ""),
            "abbr":               data.get("abbr", ""),
            "city":               data.get("city", ""),
            "country":            data.get("country", "US"),
            "unit":               data.get("unit", "gal"),
            "verdict":            data.get("verdict", "partial"),
            "price":              data.get("price"),
            "price_low":          data.get("price_low"),
            "week_delta":         data.get("week_delta", 0.0),
            "why":                data.get("why", ""),
            "advice":             data.get("advice", ""),
            "best_day_idx":       data.get("best_day_idx", 2),
            "wti_dir":            data.get("wti_dir", "flat"),
            "breakdown_json":     json.dumps(data.get("breakdown", {})),
            "trend_json":         json.dumps(data.get("trend", [])),
            "news_json":          json.dumps(data.get("news", [])),
            "prices_updated_at":  data.get("prices_updated_at"),
            "analysis_updated_at": data.get("analysis_updated_at"),
        })


def get_snapshot(region_id: str) -> dict | None:
    """Return the current snapshot row for a region as a dict."""
    import json
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM regional_snapshot WHERE region_id = ?", (region_id,)
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["breakdown"] = json.loads(d.pop("breakdown_json", "{}"))
    d["trend"]     = json.loads(d.pop("trend_json", "[]"))
    d["news"]      = json.loads(d.pop("news_json", "[]"))
    return d


def get_all_snapshots() -> list[dict]:
    import json
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM regional_snapshot").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["breakdown"] = json.loads(d.pop("breakdown_json", "{}"))
        d["trend"]     = json.loads(d.pop("trend_json", "[]"))
        d["news"]      = json.loads(d.pop("news_json", "[]"))
        result.append(d)
    return result


def store_station_price(region_id: str, price: float, unit: str,
                        station_id: str = None, lat: float = None,
                        lon: float = None, city: str = None,
                        fetched_at: str = None):
    from datetime import datetime, timezone
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO stations (station_id, region_id, price, unit, lat, lon, city, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (station_id, region_id, price, unit, lat, lon, city, fetched_at)
        )


def get_price_history(region_id: str, days: int = 90) -> list[tuple]:
    """Return (fetched_at, price) pairs for a region over the last N days."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT fetched_at, AVG(price) as avg_price
            FROM stations
            WHERE region_id = ?
              AND datetime(fetched_at) >= datetime('now', ?)
            GROUP BY date(datetime(fetched_at))
            ORDER BY datetime(fetched_at) ASC
        """, (region_id, f"-{days} days")).fetchall()
    return [(r["fetched_at"], r["avg_price"]) for r in rows]


def store_crude(symbol: str, price: float, period: str, fetched_at: str = None):
    from datetime import datetime, timezone
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO crude_prices (symbol, price, period, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol, period) DO UPDATE SET
                price = excluded.price,
                fetched_at = excluded.fetched_at
        """, (symbol, price, period, fetched_at))


def get_latest_crude(symbol: str = "WTI") -> tuple[float, float] | None:
    """Return (current_price, prev_price) or None."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT price FROM crude_prices WHERE symbol = ? ORDER BY period DESC LIMIT 2",
            (symbol,)
        ).fetchall()
    if not rows:
        return None
    curr = rows[0]["price"]
    prev = rows[1]["price"] if len(rows) > 1 else curr
    return curr, prev


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print(f"Database ready at: {DB_PATH}")
