"""
Cloudflare-resilient HTTP layer.

GasBuddy (and some scraped sources) sit behind Cloudflare, which rejects plain
`requests` traffic with an HTTP 403 "Just a moment…" interstitial because of TLS
(JA3) fingerprinting. When `curl_cffi` is installed we issue requests with a real
browser TLS fingerprint via `impersonate=`, which clears the passive checks. When
it is not installed (or the import fails) we transparently fall back to the stdlib
`requests` session so the pipeline still runs — callers must always handle a
``None`` return (block / network error) gracefully.

NOTE: a full interactive JS challenge (the managed "Just a moment…" page) cannot be
solved by any non-browser HTTP client, including curl_cffi. From hardened datacenter
IPs GasBuddy may stay blocked; from a residential host it typically succeeds. Treat
GasBuddy as an *enhancement* layer, never a hard dependency.
"""
import logging

log = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_IMPERSONATE = "chrome"
_TIMEOUT = 30

# ── Pick the best available HTTP backend ─────────────────────────────────────
try:
    from curl_cffi import requests as _curl
    _HAVE_CURL = True
except Exception:                                  # pragma: no cover - env dependent
    _curl = None
    _HAVE_CURL = False

import requests as _requests

_plain_session = _requests.Session()
_plain_session.headers.update({"User-Agent": _UA})


def have_impersonation() -> bool:
    """True when curl_cffi browser impersonation is available."""
    return _HAVE_CURL


class _Resp:
    """Minimal normalized response: .status_code / .text / .json()."""

    __slots__ = ("status_code", "text")

    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def json(self):
        import json
        return json.loads(self.text)


def _looks_blocked(resp: "_Resp") -> bool:
    if resp.status_code in (403, 429, 503):
        return True
    # Cloudflare interstitial served with a 200 in some configs
    head = resp.text[:600].lower()
    return "just a moment" in head or "cf-challenge" in head or "cf_chl" in head


def get(url: str, *, params=None, headers=None, impersonate: bool = True,
        timeout: int = _TIMEOUT) -> "_Resp | None":
    """GET a URL. Returns a normalized response, or None on block/error."""
    hdrs = {"User-Agent": _UA}
    if headers:
        hdrs.update(headers)
    try:
        if impersonate and _HAVE_CURL:
            r = _curl.get(url, params=params, headers=hdrs,
                          impersonate=_IMPERSONATE, timeout=timeout)
        else:
            r = _plain_session.get(url, params=params, headers=hdrs, timeout=timeout)
        resp = _Resp(r.status_code, r.text)
    except Exception as e:
        log.debug("http_client.get failed for %s: %s", url, e)
        return None
    if _looks_blocked(resp):
        log.debug("http_client.get blocked (%s) for %s", resp.status_code, url)
        return None
    return resp


def post_json(url: str, json_body: dict, *, headers=None, impersonate: bool = True,
              timeout: int = _TIMEOUT) -> "_Resp | None":
    """POST a JSON body. Returns a normalized response, or None on block/error."""
    hdrs = {
        "User-Agent": _UA,
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    if headers:
        hdrs.update(headers)
    try:
        if impersonate and _HAVE_CURL:
            r = _curl.post(url, json=json_body, headers=hdrs,
                           impersonate=_IMPERSONATE, timeout=timeout)
        else:
            r = _plain_session.post(url, json=json_body, headers=hdrs, timeout=timeout)
        resp = _Resp(r.status_code, r.text)
    except Exception as e:
        log.debug("http_client.post_json failed for %s: %s", url, e)
        return None
    if _looks_blocked(resp):
        log.debug("http_client.post_json blocked (%s) for %s", resp.status_code, url)
        return None
    return resp
