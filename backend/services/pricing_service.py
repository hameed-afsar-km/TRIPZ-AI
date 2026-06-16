import logging
from typing import Any, Dict, List, Optional

import httpx

from services.serpapi_service import search_hotels, search_web, extract_price_from_snippets
from services.duckduckgo_service import search_hotel_price as ddg_search_price
from services.jina_scraper import scrape_hotel_price as jina_search_price

logger = logging.getLogger("tripz.agents")

_SERPAPI_DEST_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_SERPAPI_AVG_CACHE: Dict[str, float] = {}
_XOTELO_CACHE: dict[str, float] = {}


def _average_price(results: List[Dict[str, Any]]) -> Optional[float]:
    prices = [r["price_per_night"] for r in results if r.get("price_per_night") is not None]
    if not prices:
        return None
    prices.sort()
    n = len(prices)
    median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2
    return round(median, 2)


async def get_destination_avg_price(
    destination: str,
    currency: str = "USD",
    chk_in: str = "2026-07-01",
    chk_out: str = "2026-07-02",
) -> Optional[float]:
    cache_key = f"{destination.lower().strip()}:{chk_in}:{chk_out}:{currency}"
    if cache_key in _SERPAPI_AVG_CACHE:
        return _SERPAPI_AVG_CACHE[cache_key]
    if cache_key not in _SERPAPI_DEST_CACHE:
        serp_results = await search_hotels(destination, chk_in, chk_out, currency)
        _SERPAPI_DEST_CACHE[cache_key] = serp_results
    else:
        serp_results = _SERPAPI_DEST_CACHE[cache_key]
    avg = _average_price(serp_results)
    if avg is not None:
        _SERPAPI_AVG_CACHE[cache_key] = avg
    return avg


async def get_hotel_price(
    hotel_name: str,
    destination: str,
    currency: str = "USD",
    chk_in: str = "2026-07-01",
    chk_out: str = "2026-07-02",
) -> Optional[float]:
    cache_key = f"{destination.lower().strip()}:{chk_in}:{chk_out}:{currency}"
    if cache_key not in _SERPAPI_DEST_CACHE:
        serp_results = await search_hotels(destination, chk_in, chk_out, currency)
        _SERPAPI_DEST_CACHE[cache_key] = serp_results
    else:
        serp_results = _SERPAPI_DEST_CACHE[cache_key]

    for h in serp_results:
        if hotel_name.lower() in h.get("name", "").lower() or h.get("name", "").lower() in hotel_name.lower():
            price = h.get("price_per_night")
            if price is not None:
                logger.info("Hotels price found via SerpAPI hotels: %s = %.2f %s", hotel_name, price, currency)
                return float(price)

    xotelo = await _xotelo_fallback(hotel_name, destination, currency, chk_in, chk_out)
    if xotelo is not None:
        return xotelo

    serp_snippets = await search_web(f"{hotel_name} {destination} price per night")
    if serp_snippets:
        snippet_texts = [s.get("snippet", "") + " " + s.get("title", "") for s in serp_snippets]
        price = extract_price_from_snippets(snippet_texts, currency)
        if price is not None:
            logger.info("Hotels price found via SerpAPI web: %s = %.2f %s", hotel_name, price, currency)
            return price

    ddg_price = await ddg_search_price(hotel_name, destination, currency)
    if ddg_price is not None:
        logger.info("Hotels price found via DuckDuckGo: %s = %.2f %s", hotel_name, ddg_price, currency)
        return ddg_price

    jina_price = await jina_search_price(hotel_name, destination, currency)
    if jina_price is not None:
        logger.info("Hotels price found via Jina: %s = %.2f %s", hotel_name, jina_price, currency)
        return jina_price

    avg = _average_price(serp_results)
    if avg is not None:
        logger.info("Hotels price: using destination avg %.2f %s for %s", avg, currency, hotel_name)
    else:
        logger.warning("No price found for %s in %s after all fallbacks", hotel_name, destination)
    return avg


async def _xotelo_fallback(
    hotel_name: str,
    destination: str,
    currency: str = "USD",
    chk_in: str = "2026-07-01",
    chk_out: str = "2026-07-02",
) -> Optional[float]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            loc_resp = await client.get(
                "https://data.xotelo.com/api/list",
                params={"chk_in": chk_in, "chk_out": chk_out, "currency": currency},
            )
            if loc_resp.status_code != 200:
                return None

            data = loc_resp.json()
            hotels_list = data.get("list", [])
            if not hotels_list:
                return None

            for h in hotels_list:
                if hotel_name.lower() in h.get("name", "").lower():
                    hotel_key = h.get("hotel_key") or h.get("key")
                    if hotel_key:
                        rate_resp = await client.get(
                            "https://data.xotelo.com/api/rates",
                            params={
                                "hotel_key": hotel_key,
                                "chk_in": chk_in,
                                "chk_out": chk_out,
                                "currency": currency,
                            },
                        )
                        if rate_resp.status_code == 200:
                            rates = rate_resp.json().get("rates", [])
                            if rates:
                                price = rates[0].get("rate")
                                if price:
                                    _XOTELO_CACHE[hotel_name] = float(price)
                                    return float(price)
            return None
    except Exception:
        logger.debug("Xotelo API call failed for %s", hotel_name, exc_info=True)
        return None
