"""
Exchange Rate Service — live rates from CurrencyFreaks API.
Uses API key from CURRENCYFREAKS_API_KEY env var, with fallback to a hardcoded key.
"""

import asyncio
import os
import time
from typing import Dict
import httpx

_cache: Dict[str, float] = {}
_cache_time: float = 0
_CACHE_TTL: float = 3600
_LOCK = asyncio.Lock()

CURRENCYFREAKS_URL = "https://api.currencyfreaks.com/v2.0/rates/latest"


def _get_api_key() -> str:
    return os.environ.get("CURRENCYFREAKS_API_KEY") or "887c63d845814cf393071843d3dd4025"


async def fetch_live_rates() -> Dict[str, float]:
    api_key = _get_api_key()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            CURRENCYFREAKS_URL,
            params={"apikey": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("rates", {})
        return {k: float(v) for k, v in raw.items() if v != "N/A"}


async def get_exchange_rate(target_currency: str) -> float:
    global _cache_time
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
                       f"The CurrencyFreaks API did not return this currency.")


async def convert_price(price_usd: float, target_currency: str) -> float:
    if price_usd is None:
        return 0.0
    rate = await get_exchange_rate(target_currency)
    return round(price_usd * rate, 2)


async def convert_between_currencies(amount: float, from_currency: str, to_currency: str) -> float:
    if from_currency.upper() == to_currency.upper():
        return amount
    if from_currency.upper() == "USD":
        return await convert_price(amount, to_currency)
    rate_from = await get_exchange_rate(from_currency.upper())
    if rate_from == 0:
        return amount
    amount_usd = amount / rate_from
    if to_currency.upper() == "USD":
        return round(amount_usd, 2)
    return await convert_price(amount_usd, to_currency)
