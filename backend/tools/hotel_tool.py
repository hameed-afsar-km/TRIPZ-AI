"""
Hotel Tool — zero AI calls.
Uses Nominatim OSM to get area info, then simulates hotel results.
In production: swap the mock with Booking.com, Amadeus, or RapidAPI Hotels.
"""

import asyncio
import random
from typing import Any, Dict, List
import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _generate_mock_hotels(destination: str, budget: float) -> List[Dict[str, Any]]:
    """
    Realistic mock hotel data. Replace with real API call in production.
    Filtered by per-night budget derived from total budget / travel days.
    """
    base_hotels = [
        {"name": f"Grand {destination} Palace", "stars": 5, "price_per_night": 280, "rating": 4.8, "amenities": ["pool", "spa", "gym", "restaurant"]},
        {"name": f"{destination} Boutique Hotel", "stars": 4, "price_per_night": 145, "rating": 4.5, "amenities": ["breakfast", "wifi", "bar"]},
        {"name": f"Central Inn {destination}", "stars": 3, "price_per_night": 85, "rating": 4.1, "amenities": ["wifi", "24h-reception"]},
        {"name": f"{destination} Budget Stay", "stars": 2, "price_per_night": 45, "rating": 3.7, "amenities": ["wifi"]},
        {"name": f"The {destination} Capsule", "stars": 2, "price_per_night": 28, "rating": 4.0, "amenities": ["locker", "shared-bathroom"]},
    ]

    # Filter: only show hotels the budget can realistically afford per night
    affordable = [h for h in base_hotels if h["price_per_night"] <= budget * 0.35]
    return affordable if affordable else [base_hotels[-1]]  # fallback to cheapest


async def hotel_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: finds hotels matching budget for destination.
    No LLM call. Pure data filtering and API simulation.
    """
    destination = state.get("destination", "Unknown")
    budget = float(state.get("budget", 500))

    hotels = _generate_mock_hotels(destination, budget)

    # Sort by rating descending
    hotels.sort(key=lambda h: h["rating"], reverse=True)

    # Add a value score (rating / price ratio — useful for critic)
    for h in hotels:
        h["value_score"] = round(h["rating"] / (h["price_per_night"] / 100), 2)

    trace = state.get("execution_trace", [])
    return {
        **state,
        "hotels": hotels,
        "execution_trace": trace + ["hotel_tool"],
    }
