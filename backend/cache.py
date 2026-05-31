"""
Redis-backed cache with transparent fallback to an in-memory TTL dict.
All callers use get()/set()/delete() without knowing which backend is active.
"""
import json
import time
import logging
from typing import Any

log = logging.getLogger(__name__)

# ── In-memory fallback ────────────────────────────────────────────────────────
_mem: dict[str, tuple[Any, float]] = {}   # key → (value, expires_at)


def _mem_get(key: str) -> Any | None:
    item = _mem.get(key)
    if item is None:
        return None
    value, exp = item
    if time.time() > exp:
        del _mem[key]
        return None
    return value


def _mem_set(key: str, value: Any, ttl: int):
    _mem[key] = (value, time.time() + ttl)


def _mem_delete(key: str):
    _mem.pop(key, None)


# ── Redis client (optional) ───────────────────────────────────────────────────
_redis = None


def _init_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis as _r
        from config import REDIS_URL
        client = _r.from_url(REDIS_URL, socket_connect_timeout=2)
        client.ping()
        _redis = client
        log.info("Redis connected at %s", REDIS_URL)
    except Exception as e:
        log.warning("Redis unavailable (%s) — using in-memory cache", e)
        _redis = False   # sentinel: tried and failed
    return _redis


# ── Public API ────────────────────────────────────────────────────────────────

def get(key: str) -> Any | None:
    r = _init_redis()
    if r:
        raw = r.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw.decode() if isinstance(raw, bytes) else raw
    return _mem_get(key)


def set(key: str, value: Any, ttl: int = 300):
    """Cache value with TTL in seconds."""
    r = _init_redis()
    if r:
        try:
            r.setex(key, ttl, json.dumps(value))
            return
        except Exception as e:
            log.warning("Redis set failed (%s), falling back to mem", e)
    _mem_set(key, value, ttl)


def delete(key: str):
    r = _init_redis()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass
    _mem_delete(key)


def cached(key_prefix: str, ttl: int = 300):
    """Decorator — caches return value of the wrapped function."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            key = key_prefix + ":" + ":".join(str(a) for a in args)
            hit = get(key)
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            if result is not None:
                set(key, result, ttl)
            return result
        return wrapper
    return decorator


# TTL constants (seconds)
TTL_EIA_WEEKLY   = 7 * 24 * 3600   # EIA weekly data — 7 days
TTL_CRUDE        = 3600             # crude oil spot — 1 hour
TTL_NEWS         = 55 * 60          # news headlines — 55 min
TTL_TAX_RATES    = 30 * 24 * 3600  # tax/spec data — 30 days
TTL_GASBUDDY     = 1800             # GasBuddy station data — 30 min
