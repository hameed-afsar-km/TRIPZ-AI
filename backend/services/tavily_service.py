import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("tripz.agents")

TAVILY_API_URL = "https://api.tavily.com/search"
_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 3600

_CURRENCY_PATTERNS = re.compile(
    r'(AED|USD|INR|EUR|GBP|THB|SGD|MYR|TRY|AUD|CAD|CHF|CNY|JPY|KRW|EGP|ZAR|BRL|MXN|NZD|HKD|QAR|SAR|OMR|BHD|KWD|MVR|NPR|LKR|BDT|PHP|MAD|KES|NGN|VND|IDR)\s*[:\s]*([\d,]+(?:\.\d{1,2})?)',
    re.IGNORECASE,
)


def _get_api_key() -> Optional[str]:
    return os.environ.get("TAVILY_API_KEY")


async def search_web(query: str, max_results: int = 5, search_depth: str = "advanced") -> List[Dict[str, Any]]:
    """Search the web via Tavily API. Returns list of {title, snippet, url}."""
    api_key = _get_api_key()
    if not api_key:
        logger.warning("TAVILY_API_KEY not set")
        return []

    cache_key = f"tavily_web:{query.lower().strip()}:{max_results}"
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached["_ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TAVILY_API_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                    "include_answer": False,
                    "include_raw_content": False,
                },
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning("Tavily search returned %s for: %s", resp.status_code, query)
                return []

            data = resp.json()
            results = data.get("results", [])
            out = []
            for r in results:
                out.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("content", ""),
                    "url": r.get("url", ""),
                })

            _CACHE[cache_key] = {"data": out, "_ts": time.time()}
            logger.info("Tavily search: %d results for '%s'", len(out), query)
            return out

    except Exception:
        logger.debug("Tavily search failed for '%s'", query, exc_info=True)
        return []


async def search_hotel_prices(hotel_name: str, destination: str, currency: str = "USD") -> Optional[float]:
    """Search Tavily for hotel price info. Returns median price found, or None."""
    query = f"{hotel_name} {destination} price per night {currency}"
    results = await search_web(query, max_results=5)
    if not results:
        return None

    snippets = []
    for r in results:
        if r.get("snippet"):
            snippets.append(r["snippet"])
        if r.get("title"):
            snippets.append(r["title"])

    return _parse_prices(snippets, currency)


async def search_food_costs(destination: str, currency: str = "USD") -> Optional[Dict[str, float]]:
    """Search Tavily for real food cost data in a destination.

    Returns dict with low/medium/high daily estimates, or None.
    """
    query = f"average daily food cost per person {destination} {currency} restaurants"
    results = await search_web(query, max_results=5)
    if not results:
        return None

    snippets = []
    for r in results:
        if r.get("snippet"):
            snippets.append(r["snippet"])
        if r.get("title"):
            snippets.append(r["title"])

    prices = _parse_all_prices(snippets, currency)
    if not prices:
        return None

    prices.sort()
    n = len(prices)
    return {
        "low": prices[0],
        "medium": prices[n // 2],
        "high": prices[-1],
        "currency": currency,
    }


async def search_venue_info(venue_name: str, destination: str) -> Optional[Dict[str, Any]]:
    """Search Tavily for information about a specific venue.

    Returns dict with summary, categories, opening hours if found.
    """
    query = f"{venue_name} {destination} tourist attraction opening hours"
    results = await search_web(query, max_results=3)
    if not results:
        return None

    combined = " ".join(r.get("snippet", "") + " " + r.get("title", "") for r in results)
    if not combined:
        return None

    is_tourist = any(kw in combined.lower() for kw in [
        "tourist", "attraction", "museum", "landmark", "historic",
        "gallery", "park", "beach", "fort", "palace", "temple",
        "mosque", "church", "souk", "market", "viewpoint",
    ])

    return {
        "venue": venue_name,
        "is_tourist_attraction": is_tourist,
        "summary": combined[:500],
    }


def _parse_prices(snippets: List[str], currency: str) -> Optional[float]:
    candidates = []
    for snippet in snippets:
        for match in _CURRENCY_PATTERNS.finditer(snippet):
            cur = match.group(1).upper()
            try:
                val = float(match.group(2).replace(",", ""))
            except ValueError:
                continue
            if cur == currency.upper():
                candidates.append(val)
    if not candidates:
        return None
    candidates.sort()
    n = len(candidates)
    return candidates[n // 2]


def _parse_all_prices(snippets: List[str], currency: str) -> List[float]:
    candidates = []
    for snippet in snippets:
        for match in _CURRENCY_PATTERNS.finditer(snippet):
            cur = match.group(1).upper()
            try:
                val = float(match.group(2).replace(",", ""))
            except ValueError:
                continue
            if cur == currency.upper():
                candidates.append(val)
    return candidates
