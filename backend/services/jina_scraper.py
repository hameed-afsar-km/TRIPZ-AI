import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger("tripz.agents")

JINA_BASE = "https://r.jina.ai"

_CURRENCY_PATTERNS = re.compile(
    r'(AED|USD|INR|EUR|GBP|THB|SGD|MYR|TRY|AUD|CAD|CHF|CNY|JPY|KRW|EGP|ZAR|BRL|MXN|NZD|HKD|QAR|SAR|OMR|BHD|KWD|MVR|NPR|LKR|BDT|PHP|MAD|KES|NGN|VND|IDR)\s*[:\s]*([\d,]+(?:\.\d{1,2})?)',
    re.IGNORECASE,
)


def _parse_prices(text: str, currency: str) -> Optional[float]:
    candidates = []
    for match in _CURRENCY_PATTERNS.finditer(text):
        cur = match.group(1).upper()
        try:
            val = float(match.group(2).replace(",", ""))
        except ValueError:
            continue
        if cur == currency.upper():
            if val < 10_000_000:
                candidates.append(val)
    if not candidates:
        return None
    candidates.sort()
    n = len(candidates)
    return candidates[n // 2]


async def scrape_page(url: str) -> Optional[str]:
    """Fetch a URL via Jina Reader and return the markdown text."""
    target = f"{JINA_BASE}/{url}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(target, headers={"Accept": "text/plain"})
            if resp.status_code != 200:
                logger.debug("Jina returned %s for %s", resp.status_code, url)
                return None
            return resp.text
    except Exception:
        logger.debug("Jina scrape failed for %s", url, exc_info=True)
        return None


async def scrape_hotel_price(hotel_name: str, destination: str, currency: str = "USD") -> Optional[float]:
    """Try to scrape a hotel booking page for price info via Jina Reader."""
    search_query = f"{hotel_name} {destination} booking"
    try:
        from services.duckduckgo_service import search_web_text
        results = await search_web_text(search_query)
        if not results:
            return None

        for r in results:
            link = r.get("link", "")
            if not link or not any(domain in link for domain in ["booking.com", "expedia.com", "hotels.com", "agoda.com", "trip.com"]):
                continue

            text = await scrape_page(link)
            if not text:
                continue

            price = _parse_prices(text, currency)
            if price is not None:
                logger.info("Jina: found %s %.2f from %s", currency, price, link)
                return price

        return None

    except Exception:
        logger.debug("Jina scrape_hotel_price failed for %s", hotel_name, exc_info=True)
        return None
