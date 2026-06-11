"""
Transport Tool — live distance calculation using OpenStreetMap geocoding.
Estimates flight cost based on real distance between origin and destination.
No API key required. Uses Nominatim (free) for geocoding.
"""

import math
from typing import Any, Dict, Tuple
from services.geo_service import geocode_city


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_flight_cost_km(distance_km: float, travelers: int) -> Dict[str, Any]:
    is_regional = distance_km < 1500
    cost_per_km = 0.08 if is_regional else 0.05
    base = max(distance_km * cost_per_km, 50)
    duration_h = round(distance_km / 850, 1)
    return {
        "type": "flight",
        "provider": "Estimated from distance",
        "cost_per_person": round(base, 0),
        "total_cost": round(base * travelers, 0),
        "duration_hours": max(duration_h, 1),
        "direct": not is_regional,
    }


def _estimate_train_cost_km(distance_km: float, travelers: int) -> Dict[str, Any]:
    if distance_km > 2000:
        return None
    cost_per_km = 0.04
    base = distance_km * cost_per_km
    duration_h = round(distance_km / 120, 1)
    return {
        "type": "train",
        "provider": "Estimated from distance",
        "cost_per_person": round(max(base, 15), 0),
        "total_cost": round(max(base, 15) * travelers, 0),
        "duration_hours": max(duration_h, 1),
        "direct": distance_km < 500,
    }


async def transport_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    origin = state.get("origin", "Unknown")
    destination = state.get("destination", "Unknown")
    travelers = int(state.get("num_travelers", 1))
    budget = float(state.get("budget", 1000))

    origin_geo = await geocode_city(origin) if origin and origin != "Unknown" else None
    dest_geo = await geocode_city(destination)

    options = []
    if origin_geo and dest_geo:
        dist = _haversine_km(
            origin_geo["lat"], origin_geo["lon"],
            dest_geo["lat"], dest_geo["lon"],
        )
        flight = _estimate_flight_cost_km(dist, travelers)
        options.append(flight)
        train = _estimate_train_cost_km(dist, travelers)
        if train:
            options.append(train)
    else:
        options.append({
            "type": "flight",
            "provider": "Estimated (coordinates unavailable)",
            "cost_per_person": 450,
            "total_cost": 450 * travelers,
            "duration_hours": 6,
            "direct": True,
        })

    budget_cap = budget * 0.40
    affordable = [o for o in options if o["total_cost"] <= budget_cap]
    if not affordable:
        affordable = [min(options, key=lambda x: x["total_cost"])]

    affordable.sort(key=lambda x: x["total_cost"])

    local_transit = {
        "type": "local_transit",
        "modes": ["metro", "bus", "taxi"],
        "estimated_daily_cost_per_person": 12,
        "notes": "Metro + occasional taxi recommended for speed",
    }

    transport_result = {
        "intercity_options": affordable,
        "recommended": affordable[0] if affordable else None,
        "local_transit": local_transit,
        "total_transport_budget_used": affordable[0]["total_cost"] if affordable else 0,
    }

    trace = state.get("execution_trace", [])
    return {
        **state,
        "transport": transport_result,
        "execution_trace": trace + ["transport_tool"],
    }
