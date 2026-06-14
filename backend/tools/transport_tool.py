"""
Transport Tool — live distance calculation using OpenStreetMap geocoding.
Returns real distance in km. No fabricated prices.
"""

import math
from typing import Any, Dict
from services.geo_service import geocode_city


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def transport_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    origin = state.get("origin")
    destination = state.get("destination")

    if not origin or not destination:
        return {
            **state,
            "transport": {"error": "Origin and destination required for transport calculation"},
            "execution_trace": ["transport_tool:failed"],
        }

    origin_geo = await geocode_city(origin) if origin else None
    dest_geo = await geocode_city(destination)

    if not origin_geo or not dest_geo:
        return {
            **state,
            "transport": {"error": f"Could not geocode origin ({origin}) or destination ({destination})"},
            "execution_trace": ["transport_tool:failed"],
        }

    distance_km = _haversine_km(
        origin_geo["lat"], origin_geo["lon"],
        dest_geo["lat"], dest_geo["lon"],
    )

    transport_result = {
        "origin": origin,
        "destination": destination,
        "distance_km": round(distance_km, 1),
        "geocoded": {
            "origin": {"lat": origin_geo["lat"], "lon": origin_geo["lon"]},
            "destination": {"lat": dest_geo["lat"], "lon": dest_geo["lon"]},
        },
        "note": "Distance calculated from coordinates. No real-time pricing available from free APIs.",
    }

    return {
        **state,
        "transport": transport_result,
        "execution_trace": ["transport_tool"],
    }
