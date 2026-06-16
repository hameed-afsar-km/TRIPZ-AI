import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("tripz.agents")

SERPAPI_BASE = "https://serpapi.com/search"
_cache: Dict[str, Any] = {}
_CACHE_TTL = 3600


async def search_hotels(
    destination: str,
    chk_in: str,
    chk_out: str,
    currency: str = "USD",
) -> List[Dict[str, Any]]:
    key = f"serp:{destination.lower().strip()}:{chk_in}:{chk_out}:{currency}"
    cached = _cache.get(key)
    if cached and (time.time() - cached["_ts"]) < _CACHE_TTL:
        return cached["data"]

    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        logger.warning("SERPAPI_API_KEY not set — cannot search Google Hotels")
        return []

    params = {
        "engine": "google_hotels",
        "q": f"hotels in {destination}",
        "check_in_date": chk_in,
        "check_out_date": chk_out,
        "currency": currency,
        "api_key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(SERPAPI_BASE, params=params)
            if resp.status_code != 200:
                body_preview = resp.text[:500]
                logger.warning("SerpAPI hotels returned %s for %s: %s", resp.status_code, destination, body_preview)
                return []

            data = resp.json()
            properties = data.get("properties", [])
            logger.info("SerpAPI hotels: returned %d properties for %s", len(properties), destination)

            results = []
            for p in properties:
                name = p.get("name", "").strip()
                if not name:
                    continue

                rate = p.get("rate_per_night", {}).get("extracted_lowest")
                if rate is None:
                    rate = p.get("rate_per_night", {}).get("lowest")
                if rate is None:
                    rate = p.get("rate_per_night", {}).get("extracted")
                if rate is None:
                    rate = p.get("total_rate", {}).get("amount")
                if rate is None:
                    rate = p.get("lowest_price")
                if rate is None:
                    rate = p.get("price")
                if rate is not None:
                    try:
                        rate = float(rate)
                    except (ValueError, TypeError):
                        rate = None

                stars_raw = p.get("extracted_hotel_class")
                if stars_raw is not None:
                    try:
                        stars = int(stars_raw)
                    except (ValueError, TypeError):
                        stars = None
                else:
                    stars = None

                rating = p.get("overall_rating")
                if rating is not None:
                    try:
                        rating = float(rating)
                    except (ValueError, TypeError):
                        rating = None

                results.append({
                    "name": name,
                    "price_per_night": rate,
                    "stars": stars,
                    "rating": rating,
                })

            prices_found = sum(1 for r in results if r["price_per_night"] is not None)
            logger.info("SerpAPI hotels: %d/%d properties have prices for %s", prices_found, len(results), destination)

            if prices_found == 0 and results:
                logger.debug("First property raw keys: %s", list(properties[0].keys()))

            _cache[key] = {"data": results, "_ts": time.time()}
            return results

    except Exception:
        logger.warning("SerpAPI hotels call failed for %s", destination, exc_info=True)
        return []


async def search_web(query: str) -> List[Dict[str, str]]:
    """Search the web via SerpAPI (Google organic) and return result snippets."""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        logger.warning("SERPAPI_API_KEY not set — cannot search web")
        return []

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": 5,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(SERPAPI_BASE, params=params)
            if resp.status_code != 200:
                logger.warning("SerpAPI web search returned %s for: %s", resp.status_code, query)
                return []

            data = resp.json()
            organic = data.get("organic_results", [])
            results = []
            for r in organic:
                snippet = r.get("snippet", "")
                title = r.get("title", "")
                link = r.get("link", "")
                if snippet or title:
                    results.append({"title": title, "snippet": snippet, "link": link})

            logger.info("SerpAPI web search: %d results for: %s", len(results), query)
            return results

    except Exception:
        logger.debug("SerpAPI web search failed for: %s", query, exc_info=True)
        return []


_CURRENCY_PATTERNS = re.compile(
    r'(AED|USD|INR|EUR|GBP|THB|SGD|MYR|TRY|AUD|CAD|CHF|CNY|JPY|KRW|EGP|ZAR|BRL|MXN|NZD|HKD|QAR|SAR|OMR|BHD|KWD|MVR|NPR|LKR|BDT|PHP|MAD|KES|NGN|VND|IDR)\s*[:\s]*([\d,]+(?:\.\d{1,2})?)',
    re.IGNORECASE,
)

def extract_price_from_snippets(snippets: List[str], currency: str = "AED") -> Optional[float]:
    """Parse price mentions from search result snippets."""
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
