"""
Geo Service — live location data from OpenStreetMap (free, no API key).
- Nominatim for geocoding (city → lat/lon/bbox)
- Overpass API for POIs (activities, hotels, etc.)
- 1-hour cache per destination
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "TRIPZ-AI/1.0 (travel planner)"

_cache: Dict[str, Any] = {}
_cache_time: float = 0
_CACHE_TTL: float = 3600
_LOCK = asyncio.Lock()
_last_nominatim: float = 0  # rate-limit: 1 req/sec


async def _geocode(city: str) -> Optional[Dict[str, Any]]:
    global _last_nominatim
    now = time.time()
    wait = 1.0 - (now - _last_nominatim)
    if wait > 0:
        await asyncio.sleep(wait)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": city, "format": "json", "limit": 1, "addressdetails": 0},
            headers={"User-Agent": _USER_AGENT},
        )
        _last_nominatim = time.time()
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        r = results[0]
        bb = r.get("boundingbox")
        return {
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "display_name": r.get("display_name", city),
            "bbox": (float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3])) if bb else None,
        }


async def geocode_city(city: str) -> Optional[Dict[str, Any]]:
    key = f"geo:{city.lower().strip()}"
    cached = _cache.get(key)
    if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
        return cached
    result = await _geocode(city)
    if result:
        # Cap bbox to ~0.5° (~55km) around center — avoids huge region timeouts
        MAX_BBOX_RADIUS = 0.5
        lat, lon = result["lat"], result["lon"]
        result["bbox"] = (
            lat - MAX_BBOX_RADIUS,
            lon - MAX_BBOX_RADIUS,
            lat + MAX_BBOX_RADIUS,
            lon + MAX_BBOX_RADIUS,
        )
        result["_ts"] = time.time()
        _cache[key] = result
    return result


async def _overpass_query(query: str, timeout_sec: int = 15) -> List[Dict[str, Any]]:
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(
                    OVERPASS_URL,
                    data={"data": query},
                    headers={"User-Agent": _USER_AGENT},
                )
                if resp.status_code == 429:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data.get("elements", [])
        except (httpx.TimeoutException, httpx.HTTPStatusError):
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            raise
    return []


def _build_bbox_str(bbox: Tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    return f"{south},{west},{north},{east}"


async def fetch_activities(destination: str) -> List[Dict[str, Any]]:
    key = f"act:{destination.lower().strip()}"
    async with _LOCK:
        cached = _cache.get(key)
        if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
            return cached["data"]

    geo = await geocode_city(destination)
    if not geo or not geo["bbox"]:
        async with _LOCK:
            _cache[key] = {"data": [], "_ts": time.time()}
        return []

    bbox_str = _build_bbox_str(geo["bbox"])
    # Fetch from 3 categories in parallel with simpler queries
    async def _fetch_cat(tag: str, regex: str) -> List[Dict]:
        q = f"""
        [out:json][timeout:20];
        (
          node[{tag}~"{regex}"]({bbox_str});
          way[{tag}~"{regex}"]({bbox_str});
        );
        out center 20;
        """
        try:
            return await _overpass_query(q, 20)
        except Exception:
            return []

    tourism_q = _fetch_cat("tourism", "attraction|museum|gallery|viewpoint|theme_park|nightclub")
    historic_q = _fetch_cat("historic", "monument|castle|ruins|archaeological_site")
    leisure_q = _fetch_cat("leisure", "park|garden|water_park")
    results = await asyncio.gather(tourism_q, historic_q, leisure_q)
    elements = results[0] + results[1] + results[2]

    if not elements:
        async with _LOCK:
            _cache[key] = {"data": [], "_ts": time.time()}
        return []

    cat_map = {
        "museum": "culture", "gallery": "art", "attraction": "sightseeing",
        "viewpoint": "nature", "theme_park": "adventure",
        "monument": "history", "castle": "history", "ruins": "history",
        "archaeological_site": "history",
        "park": "nature", "garden": "relaxation", "water_park": "adventure",
        "nightclub": "nightlife",
    }
    cost_map = {
        "museum": 15, "gallery": 10, "attraction": 20, "viewpoint": 0,
        "theme_park": 50, "monument": 10, "castle": 15, "ruins": 8,
        "archaeological_site": 12, "park": 0, "garden": 5, "water_park": 35,
        "nightclub": 20,
    }

    activities = []
    seen_names = set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())

        osm_type = (
            tags.get("tourism") or tags.get("historic") or
            tags.get("leisure") or tags.get("amenity") or ""
        )
        cat = cat_map.get(osm_type, "sightseeing")
        cost = cost_map.get(osm_type, 15)
        indoor = osm_type in ("museum", "gallery", "nightclub", "theme_park")

        activities.append({
            "name": name,
            "category": cat,
            "cost": cost,
            "duration_hours": 2,
            "indoor": indoor,
            "description": tags.get("description", tags.get("note",
                               f"Visit {name} in {destination}")),
            "lat": el.get("lat") or el.get("center", {}).get("lat"),
            "lon": el.get("lon") or el.get("center", {}).get("lon"),
        })

    async with _LOCK:
        _cache[key] = {"data": activities, "_ts": time.time()}
    return activities


async def fetch_hotels(destination: str) -> List[Dict[str, Any]]:
    key = f"hot:{destination.lower().strip()}"
    async with _LOCK:
        cached = _cache.get(key)
        if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
            return cached["data"]

    geo = await geocode_city(destination)
    if not geo or not geo["bbox"]:
        async with _LOCK:
            _cache[key] = {"data": [], "_ts": time.time()}
        return []

    bbox_str = _build_bbox_str(geo["bbox"])

    async def _fetch_hotels(type_filter: str) -> List[Dict]:
        q = f"""
        [out:json][timeout:20];
        (
          {type_filter}["tourism"~"hotel|hostel|guest_house|motel"]({bbox_str});
        );
        out center 25;
        """
        try:
            return await _overpass_query(q, 20)
        except Exception:
            return []

    node_hotels, way_hotels = await asyncio.gather(
        _fetch_hotels("node"), _fetch_hotels("way")
    )
    elements = node_hotels + way_hotels

    star_price = {1: 25, 2: 40, 3: 70, 4: 130, 5: 280}
    type_price = {"hostel": 15, "guest_house": 35, "motel": 45, "hotel": 60}

    hotels = []
    seen = set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        osm_type = tags.get("tourism", "hotel")
        stars_raw = tags.get("stars", "")
        try:
            stars = int(stars_raw) if stars_raw else 3
        except (ValueError, TypeError):
            stars = 3
        stars = max(1, min(5, stars))

        if osm_type in type_price:
            price = type_price[osm_type]
        else:
            price = star_price.get(stars, 60)

        # tilt price up/down by stars
        price = int(price * (0.7 + stars * 0.1))

        hotels.append({
            "name": name,
            "stars": stars,
            "price_per_night": price,
            "rating": round(3.5 + stars * 0.3, 1),
            "amenities": [],
        })

    async with _LOCK:
        _cache[key] = {"data": hotels, "_ts": time.time()}
    return hotels
