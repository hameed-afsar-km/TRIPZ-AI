import logging
import re
from typing import Any, Dict, List, Optional

from duckduckgo_search import DDGS

logger = logging.getLogger("tripz.agents")

_CURRENCY_PATTERNS = re.compile(
    r'(AED|USD|INR|EUR|GBP|THB|SGD|MYR|TRY|AUD|CAD|CHF|CNY|JPY|KRW|EGP|ZAR|BRL|MXN|NZD|HKD|QAR|SAR|OMR|BHD|KWD|MVR|NPR|LKR|BDT|PHP|MAD|KES|NGN|VND|IDR)\s*[:\s]*([\d,]+(?:\.\d{1,2})?)',
    re.IGNORECASE,
)


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


async def search_hotel_price(hotel_name: str, destination: str, currency: str = "USD") -> Optional[float]:
    """Search DuckDuckGo for hotel price info. Returns median price found, or None."""
    query = f"{hotel_name} {destination} price per night"
    try:
        snippets = []
        with DDGS() as ddgs:
            for i, result in enumerate(ddgs.text(query, max_results=5)):
                snippet = result.get("body", "")
                title = result.get("title", "")
                if snippet:
                    snippets.append(snippet)
                if title:
                    snippets.append(title)

        if not snippets:
            logger.debug("DuckDuckGo: no results for '%s'", query)
            return None

        price = _parse_prices(snippets, currency)
        if price is not None:
            logger.info("DuckDuckGo: found %s %.2f for '%s'", currency, price, query)
        else:
            logger.debug("DuckDuckGo: no %s prices found in snippets for '%s'", currency, query)

        return price

    except Exception:
        logger.debug("DuckDuckGo search failed for '%s'", query, exc_info=True)
        return None


async def search_web_text(query: str) -> List[Dict[str, Any]]:
    """Generic DuckDuckGo search returning title + snippet."""
    try:
        results = []
        with DDGS() as ddgs:
            for i, result in enumerate(ddgs.text(query, max_results=5)):
                results.append({
                    "title": result.get("title", ""),
                    "snippet": result.get("body", ""),
                    "link": result.get("href", ""),
                })
        return results
    except Exception:
        logger.debug("DuckDuckGo search failed for '%s'", query, exc_info=True)
        return []
