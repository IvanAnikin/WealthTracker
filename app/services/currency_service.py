from __future__ import annotations
"""
Currency conversion service with caching and resilient fallbacks.

Strategy:
- Use exchangerate.host with base USD to get a full rate table.
- Cache for 1 hour.
- Fall back to static USD-based rates if API/rates unavailable.
"""
import time
import httpx
import threading
from typing import Dict, Iterable

_CACHE: Dict[str, Dict[str, float]] = {}
_CACHE_TIME: Dict[str, float] = {}
_CACHE_TTL = 60 * 60  # 1 hour
_LOCK = threading.Lock()

# Static fallback rates versus USD (approximate, updateable)
_STATIC_RATES_USD = {
    "USD": 1.0,
    "EUR": 0.91,
    "CZK": 22.7,
    "GBP": 0.79,
    "PLN": 3.95,
}


def _fetch_rates(base: str = "USD") -> Dict[str, float]:
    with httpx.Client(timeout=5) as client:
        resp = client.get("https://api.exchangerate.host/latest", params={"base": base})
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})


def _rate_via_base(base: str, rates: Dict[str, float], from_cur: str, to_cur: str) -> float:
    """Return multiplier to convert from -> to using a rates table based on `base`.
    amount_in_to = amount_in_from * (rate_to / rate_from)
    """
    rate_from = rates.get(from_cur)
    rate_to = rates.get(to_cur)
    if rate_from and rate_to:
        return rate_to / rate_from
    raise KeyError("missing rate")


def get_rate(from_currency: str, to_currency: str) -> float:
    from_currency = (from_currency or "").upper()
    to_currency = (to_currency or "").upper()
    if not from_currency or not to_currency:
        raise RuntimeError("FX rate unavailable: empty currency code")
    if from_currency == to_currency:
        return 1.0

    now = time.time()
    base = "USD"

    # Acquire lock to avoid thundering-herd on rate fetch
    with _LOCK:
        rates = _CACHE.get(base)
        if not rates or (now - _CACHE_TIME.get(base, 0)) >= _CACHE_TTL:
            try:
                fetched = _fetch_rates(base)
                if fetched:
                    _CACHE[base] = fetched
                    _CACHE_TIME[base] = now
                    rates = fetched
            except Exception:
                # keep existing cached if any
                rates = rates or None

        # If still no rates, fallback to static
        if not rates:
            rates = _STATIC_RATES_USD

    # Compute multiplier via base
    try:
        return _rate_via_base(base, rates, from_currency, to_currency)
    except Exception:
        # As last resort, if only one rate exists, try reciprocal logic
        rf = rates.get(from_currency)
        rt = rates.get(to_currency)
        if rf and rt:
            return rt / rf
        raise RuntimeError(f"FX rate unavailable for {from_currency}->{to_currency}")


def convert(amount: float, from_currency: str, to_currency: str) -> float:
    rate = get_rate(from_currency, to_currency)
    return amount * rate


def get_rate_map(from_currencies: Iterable[str], to_currency: str) -> Dict[str, float]:
    """
    Preload rates for a set of source currencies to a single target.

    This helps avoid repeated get_rate calls when bulk-converting many values.
    """
    target = (to_currency or "").upper()
    rate_map: Dict[str, float] = {}
    for cur in { (c or "USD").upper() for c in from_currencies }:
        rate_map[cur] = get_rate(cur, target)
    return rate_map
