import logging
import os
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
                logger.debug("SerpAPI returned %s for %s", resp.status_code, destination)
                return []
            data = resp.json()
            properties = data.get("properties", [])
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
            _cache[key] = {"data": results, "_ts": time.time()}
            return results
    except Exception:
        logger.debug("SerpAPI call failed for %s", destination, exc_info=True)
        return []
