"""
Exchange Rate Service — live rates from Frankfurter API (free, no auth).
Fetches USD-based rates, caches for 1 hour, falls back to hardcoded table.
"""

import asyncio
import time
from typing import Dict
import httpx

FALLBACK_RATES: Dict[str, float] = {
    "USD": 1.0,
    "INR": 83.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 151.0,
    "AUD": 1.54,
    "CAD": 1.37,
    "AED": 3.67,
    "SAR": 3.75,
    "QAR": 3.64,
    "MYR": 4.45,
    "SGD": 1.34,
    "THB": 34.0,
    "LKR": 295.0,
    "NPR": 133.0,
    "BDT": 110.0,
    "PKR": 278.0,
    "EGP": 48.5,
    "TRY": 29.0,
    "CHF": 0.89,
    "SEK": 10.5,
    "NOK": 10.8,
    "DKK": 6.9,
    "PLN": 4.0,
    "CNY": 7.2,
    "HKD": 7.8,
    "KRW": 1300.0,
    "MXN": 17.0,
    "NZD": 1.6,
    "ZAR": 18.5,
    "BRL": 5.0,
}

_cache: Dict[str, float] = {}
_cache_time: float = 0
_CACHE_TTL: float = 3600
_LOCK = asyncio.Lock()


async def fetch_live_rates() -> Dict[str, float]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://api.frankfurter.app/latest?from=USD")
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})


async def get_exchange_rate(target_currency: str) -> float:
    global _cache_time
    target = target_currency.upper().strip()
    if target == "USD":
        return 1.0

    async with _LOCK:
        now = time.time()
        if _cache and (now - _cache_time) < _CACHE_TTL and target in _cache:
            return _cache[target]

        try:
            rates = await fetch_live_rates()
            _cache.clear()
            _cache.update(rates)
            _cache_time = now
            if target in _cache:
                return _cache[target]
        except Exception:
            pass

    rate = FALLBACK_RATES.get(target)
    if rate is not None:
        async with _LOCK:
            _cache[target] = rate
            _cache_time = time.time()
        return rate

    return 1.0


async def convert_price(price_usd: float, target_currency: str) -> float:
    rate = await get_exchange_rate(target_currency)
    return round(price_usd * rate, 2)
