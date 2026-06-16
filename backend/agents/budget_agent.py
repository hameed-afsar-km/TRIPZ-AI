"""
Budget Agent — real hotel prices from SerpAPI, food cost estimates via LLM.
"""

from typing import Any, Dict
from tools.hotel_tool import hotel_tool
from services.pricing_service import get_hotel_price, get_destination_avg_price
from services.serpapi_maps_service import estimate_daily_food_cost

_COUNTRY_CURRENCIES = {
    "united arab emirates": "AED", "dubai": "AED", "abu dhabi": "AED",
    "india": "INR", "mumbai": "INR", "delhi": "INR", "bangalore": "INR", "goa": "INR",
    "united kingdom": "GBP", "london": "GBP", "england": "GBP", "uk": "GBP",
    "japan": "JPY", "tokyo": "JPY", "kyoto": "JPY", "osaka": "JPY",
    "thailand": "THB", "bangkok": "THB", "phuket": "THB",
    "vietnam": "VND", "hanoi": "VND", "ho chi minh": "VND",
    "indonesia": "IDR", "bali": "IDR", "jakarta": "IDR",
    "australia": "AUD", "sydney": "AUD", "melbourne": "AUD",
    "europe": "EUR", "france": "EUR", "paris": "EUR", "italy": "EUR", "rome": "EUR",
    "germany": "EUR", "berlin": "EUR", "spain": "EUR", "barcelona": "EUR",
    "netherlands": "EUR", "amsterdam": "EUR", "greece": "EUR", "athens": "EUR",
    "portugal": "EUR", "lisbon": "EUR", "switzerland": "CHF", "zurich": "CHF",
    "turkey": "TRY", "istanbul": "TRY", "antalya": "TRY",
    "singapore": "SGD",
    "malaysia": "MYR", "kuala lumpur": "MYR",
    "china": "CNY", "beijing": "CNY", "shanghai": "CNY",
    "south korea": "KRW", "seoul": "KRW",
    "egypt": "EGP", "cairo": "EGP",
    "south africa": "ZAR", "cape town": "ZAR",
    "brazil": "BRL", "rio de janeiro": "BRL",
    "mexico": "MXN", "cancun": "MXN",
    "canada": "CAD", "toronto": "CAD", "vancouver": "CAD",
    "new zealand": "NZD", "auckland": "NZD",
    "usa": "USD", "united states": "USD", "new york": "USD", "los angeles": "USD",
    "hong kong": "HKD",
    "qatar": "QAR", "doha": "QAR",
    "saudi arabia": "SAR", "riyadh": "SAR",
    "kuwait": "KWD",
    "oman": "OMR", "muscat": "OMR",
    "bahrain": "BHD",
    "maldives": "MVR",
    "nepal": "NPR", "kathmandu": "NPR",
    "sri lanka": "LKR", "colombo": "LKR",
    "bangladesh": "BDT", "dhaka": "BDT",
    "philippines": "PHP", "manila": "PHP",
    "morocco": "MAD", "marrakech": "MAD",
    "kenya": "KES", "nairobi": "KES",
    "nigeria": "NGN", "lagos": "NGN",
}


def _resolve_destination_currency(destination: str) -> str | None:
    dest_lower = destination.lower().strip()
    if dest_lower in _COUNTRY_CURRENCIES:
        return _COUNTRY_CURRENCIES[dest_lower]
    for key, cur in _COUNTRY_CURRENCIES.items():
        if key in dest_lower or dest_lower in key:
            return cur
    return None


async def budget_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        budget = float(state.get("budget", 0))
        travelers = int(state.get("num_travelers", 1))
        is_unlimited = budget >= 999999
        destination = state.get("destination", "Unknown")
        original_currency = state.get("currency", "USD")
        dest_currency = _resolve_destination_currency(destination) or original_currency
        trace = state.get("execution_trace", [])

        if state.get("budget_breakdown"):
            return {"execution_trace": ["budget_agent:from_cache"]}

        warnings: list = []

        hotels = state.get("hotels", [])
        if not hotels:
            try:
                hotel_res = await hotel_tool(state)
                hotels = hotel_res.get("hotels", [])
                tool_trace = hotel_res.get("execution_trace", [])
                if tool_trace:
                    trace = tool_trace
            except Exception:
                warnings.append("Hotel data unavailable — budget cannot verify accommodation costs.")

        transport = state.get("transport", {})
        activities = state.get("activities", [])

        # Pre-fetch destination avg in destination currency (populates SerpAPI cache)
        avg_price = await get_destination_avg_price(destination, dest_currency)

        # Try per-hotel match from cache (fast, no extra network if cache populated)
        for h in hotels:
            if h.get("price_per_night") is None:
                price = await get_hotel_price(h["name"], destination, dest_currency)
                if price is not None:
                    h["price_per_night"] = price
                    h["price_estimated"] = True

        # Fall back to destination avg for any hotels still missing prices
        if avg_price is not None:
            for h in hotels:
                if h.get("price_per_night") is None:
                    h["price_per_night"] = avg_price
                    h["price_estimated"] = True

        has_hotel_prices = any(h.get("price_per_night") is not None for h in hotels)
        has_activity_costs = any(a.get("cost") is not None for a in activities)
        has_transport_cost = isinstance(transport.get("distance_km"), (int, float))

        if not has_hotel_prices and hotels:
            warnings.append("Hotel prices unavailable for this destination. Try a more specific hotel name.")

        if not has_activity_costs and activities:
            warnings.append("Most activities show venue names only — check official sites for ticket prices.")

        if not has_transport_cost and "distance_km" in transport:
            warnings.append("Transport distance calculated but no real-time pricing available.")

        daily_food_cost = await estimate_daily_food_cost(destination, dest_currency)

        budget_breakdown = {
            "total_budget": budget if not is_unlimited else "Unlimited",
            "currency": dest_currency,
            "num_travelers": travelers,
            "hotels_found": len(hotels),
            "activities_found": len(activities),
            "transport_distance_km": transport.get("distance_km"),
            "estimated_daily_food_cost_per_person": daily_food_cost,
            "note": "Hotel prices from Google Hotels (SerpAPI). Food costs estimated via LLM based on local cost of living.",
        }

        return {
            "budget_breakdown": budget_breakdown,
            "hotels": hotels,
            "warnings": warnings,
            "execution_trace": trace + ["budget_agent"],
        }
    except Exception as e:
        return {
            "budget_breakdown": {"error": str(e)},
            "hotels": [],
            "warnings": state.get("warnings", []) + [f"Budget agent error: {str(e)}"],
            "execution_trace": ["budget_agent:error"],
        }
