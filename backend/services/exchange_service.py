"""
Exchange Rate Service — live rates from Frankfurter API (free, no auth).
No fallback table. If the live API fails, an error is raised.
"""

import asyncio
import time
from typing import Dict
import httpx

_cache: Dict[str, float] = {}
_cache_time: float = 0
_CACHE_TTL: float = 3600
_LOCK = asyncio.Lock()

FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD"


async def fetch_live_rates() -> Dict[str, float]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(FRANKFURTER_URL)
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})


async def get_exchange_rate(target_currency: str) -> float:
    target = target_currency.upper().strip()
    if target == "USD":
        return 1.0

    async with _LOCK:
        now = time.time()
        if _cache and (now - _cache_time) < _CACHE_TTL and target in _cache:
            return _cache[target]

        rates = await fetch_live_rates()
        _cache.clear()
        _cache.update(rates)
        _cache_time = now
        if target in _cache:
            return _cache[target]

    raise RuntimeError(f"Exchange rate for {target_currency} not available from live API. "
                       f"The Frankfurter API at {FRANKFURTER_URL} did not return this currency.")


async def convert_price(price_usd: float, target_currency: str) -> float:
    if price_usd is None:
        return 0.0
    rate = await get_exchange_rate(target_currency)
    return round(price_usd * rate, 2)
