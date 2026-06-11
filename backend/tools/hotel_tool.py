"""
Hotel Tool — live data from OpenStreetMap (Overpass API).
Fetches real hotels, hostels, guest houses for any destination.
Free, no API key required. 1-hour cache.
Budget-filtered using live exchange rates.
"""

from typing import Any, Dict
from services.geo_service import fetch_hotels
from services.exchange_service import get_exchange_rate


async def hotel_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    destination = state.get("destination", "Unknown")
    budget = float(state.get("budget", 500))
    currency = state.get("currency", "USD")

    hotels = await fetch_hotels(destination)

    rate = await get_exchange_rate(currency)
    budget_usd = budget / rate if rate > 0 else 500
    num_days = max(float(state.get("duration_days", 7)), 1)
    daily_budget_usd = budget_usd / num_days
    trip_type = state.get("routing_decision", "standard")
    hotel_share = {"budget": 0.3, "standard": 0.4, "luxury": 0.55}.get(trip_type, 0.4)
    max_price = int(daily_budget_usd * hotel_share)

    affordable = [h for h in hotels if h["price_per_night"] <= max_price]
    if not affordable and hotels:
        affordable = [min(hotels, key=lambda h: h["price_per_night"])]

    affordable.sort(key=lambda h: h.get("rating", 0), reverse=True)

    for h in affordable:
        h["value_score"] = round(h.get("rating", 3) / (h["price_per_night"] / 100), 2)

    trace = state.get("execution_trace", [])
    return {
        **state,
        "hotels": affordable,
        "execution_trace": trace + ["hotel_tool"],
    }
