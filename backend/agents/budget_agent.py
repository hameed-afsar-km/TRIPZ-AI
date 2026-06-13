"""
Budget Agent — real hotel prices from SerpAPI, food cost estimates via LLM.
"""

from typing import Any, Dict
from tools.hotel_tool import hotel_tool
from services.pricing_service import get_destination_avg_price
from services.serpapi_maps_service import estimate_daily_food_cost


async def budget_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        budget = float(state.get("budget", 0))
        travelers = int(state.get("num_travelers", 1))
        is_unlimited = budget >= 999999
        destination = state.get("destination", "Unknown")
        currency = state.get("currency", "USD")
        trace = state.get("execution_trace", [])

        if state.get("budget_breakdown"):
            return {"execution_trace": trace + ["budget_agent:from_cache"]}

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

        if not any(h.get("price_per_night") is not None for h in hotels):
            avg_price = await get_destination_avg_price(destination, currency)
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

        daily_food_cost = await estimate_daily_food_cost(destination, currency)

        budget_breakdown = {
            "total_budget": budget if not is_unlimited else "Unlimited",
            "currency": currency,
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
            "warnings": state.get("warnings", []) + warnings,
            "execution_trace": trace + ["budget_agent"],
        }
    except Exception as e:
        return {
            "budget_breakdown": {"error": str(e)},
            "hotels": [],
            "warnings": state.get("warnings", []) + [f"Budget agent error: {str(e)}"],
            "execution_trace": state.get("execution_trace", []) + ["budget_agent:error"],
        }
