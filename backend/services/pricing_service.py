import logging
from typing import Optional

import httpx

logger = logging.getLogger("tripz.agents")

_XOTELO_CACHE: dict[str, float] = {}


async def get_hotel_price(
    hotel_name: str,
    destination: str,
    currency: str = "USD",
) -> Optional[float]:
    """Try to get a real hotel price from Xotelo's free API (no key required)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            loc_resp = await client.get(
                "https://data.xotelo.com/api/list",
                params={"chk_in": "2026-07-01", "chk_out": "2026-07-02", "currency": currency},
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
                                "chk_in": "2026-07-01",
                                "chk_out": "2026-07-02",
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
