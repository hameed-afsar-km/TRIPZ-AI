import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("tripz.agents")

OSRM_BASE = "https://router.project-osrm.org"
_cache: Dict[str, Any] = {}
_CACHE_TTL = 86400


async def get_travel_time(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    profile: str = "driving",
) -> Optional[Dict[str, Any]]:
    """Get travel time and distance between two points using free OSRM API.

    Returns dict with 'duration_minutes' and 'distance_km', or None on failure.
    """
    key = f"osrm:{profile}:{from_lat:.4f},{from_lon:.4f};{to_lat:.4f},{to_lon:.4f}"
    cached = _cache.get(key)
    if cached and (time.time() - cached["_ts"]) < _CACHE_TTL:
        return cached["data"]

    coords = f"{from_lon},{from_lat};{to_lon},{to_lat}"
    url = f"{OSRM_BASE}/route/v1/{profile}/{coords}"
    params = {"overview": "false", "steps": "false"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning("OSRM returned %s for %s", resp.status_code, key)
                return None

            data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                logger.warning("OSRM no route for %s: %s", key, data.get("code"))
                return None

            route = data["routes"][0]
            duration_s = route.get("duration", 0)
            distance_m = route.get("distance", 0)

            result = {
                "duration_minutes": round(duration_s / 60, 1),
                "distance_km": round(distance_m / 1000, 1),
                "profile": profile,
            }
            _cache[key] = {"data": result, "_ts": time.time()}
            return result
    except httpx.TimeoutException:
        logger.debug("OSRM timeout for %s", key)
        return None
    except Exception:
        logger.debug("OSRM error for %s", key, exc_info=True)
        return None


async def build_distance_matrix(
    venues: List[Dict[str, Any]],
    profile: str = "driving",
) -> List[List[Optional[float]]]:
    """Build a travel-time matrix (in minutes) between all venue pairs."""
    n = len(venues)
    matrix = [[None] * n for _ in range(n)]

    for i in range(n):
        matrix[i][i] = 0.0
        vi = venues[i]
        vi_lat = vi.get("lat") or vi.get("latitude")
        vi_lon = vi.get("lon") or vi.get("longitude")
        if vi_lat is None or vi_lon is None:
            continue

        for j in range(i + 1, n):
            vj = venues[j]
            vj_lat = vj.get("lat") or vj.get("latitude")
            vj_lon = vj.get("lon") or vj.get("longitude")
            if vj_lat is None or vj_lon is None:
                continue

            result = await get_travel_time(vi_lat, vi_lon, vj_lat, vj_lon, profile)
            if result:
                matrix[i][j] = result["duration_minutes"]
                matrix[j][i] = result["duration_minutes"]

    return matrix


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km. Used as fast fallback."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)
