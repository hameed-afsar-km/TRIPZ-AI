"""
Hotel Tool — live data from OpenStreetMap (Overpass API).
Prices are not available from free APIs — this tool returns what OSM provides:
real hotel names, star ratings (when tagged), and types.
No fabricated prices or ratings.
"""

from typing import Any, Dict
from services.geo_service import fetch_hotels


async def hotel_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    destination = state.get("destination", "Unknown")

    hotels = await fetch_hotels(destination)

    return {
        **state,
        "hotels": hotels,
        "execution_trace": ["hotel_tool"],
    }
