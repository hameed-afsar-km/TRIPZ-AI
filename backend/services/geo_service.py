"""
Geo Service — live location data from OpenStreetMap (free, no API key).
- Nominatim for geocoding (city → lat/lon/bbox)
- Overpass API for POIs (activities, hotels, etc.)
- 1-hour cache per destination
"""

import asyncio
import json
import re
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
_inflight: Dict[str, asyncio.Future] = {}  # in-flight geocode requests


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

    async with _LOCK:
        # Check again under lock (another coroutine may have cached it)
        cached = _cache.get(key)
        if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
            return cached
        # Check if another coroutine is already fetching this city
        fut = _inflight.get(key)
        if fut is not None:
            return await fut

    # No cache hit and no in-flight — start a new request
    fut = asyncio.ensure_future(_geocode(city))
    _inflight[key] = fut
    try:
        result = await fut
    finally:
        async with _LOCK:
            _inflight.pop(key, None)

    if result:
        MAX_BBOX_RADIUS = 0.2
        lat, lon = result["lat"], result["lon"]
        result["bbox"] = (
            lat - MAX_BBOX_RADIUS,
            lon - MAX_BBOX_RADIUS,
            lat + MAX_BBOX_RADIUS,
            lon + MAX_BBOX_RADIUS,
        )
        result["_ts"] = time.time()
        async with _LOCK:
            _cache[key] = result
    return result


_NEIGHBOR_CITIES = {
    "dubai": ["sharjah", "abu dhabi", "ajman", "ras al khaimah", "fujairah", "umm al quwain"],
    "abu dhabi": ["dubai", "sharjah", "ajman", "al ain"],
    "mumbai": ["navi mumbai", "thane", "pune"],
    "delhi": ["gurgaon", "noida", "ghaziabad", "faridabad"],
    "bangkok": ["nonthaburi", "samut prakan", "pathum thani"],
    "paris": ["issy-les-moulineaux", "boulogne-billancourt", "montreuil", "saint-denis"],
    "london": ["greenwich", "croydon", "brent", "ealing"],
}


def _is_in_correct_city(tags: Dict[str, Any], destination: str, venue_name: str = "") -> bool:
    """Filter out venues whose OSM address or name says a different city."""
    dest_lower = destination.lower().strip()

    addr_city = (tags.get("addr:city") or "").strip().lower()
    if addr_city and dest_lower not in addr_city and addr_city not in dest_lower:
        return False

    name_lower = venue_name.lower().strip()
    excluded = _NEIGHBOR_CITIES.get(dest_lower, [])
    if excluded:
        for neighbor in excluded:
            if neighbor in name_lower or name_lower in neighbor:
                return False

    return True


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


def _has_latin(text: str) -> bool:
    return bool(re.search(r'[a-zA-Z]', text))


def _best_name(tags: Dict[str, Any]) -> str:
    name = (tags.get("name:en") or tags.get("name") or "").strip()
    if not name:
        return ""
    if not _has_latin(name):
        for tag in ("name:en", "int_name", "official_name", "alt_name", "name"):
            val = tags.get(tag, "").strip()
            if val and _has_latin(val):
                return val
    return name


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
    # Single combined query — much faster than 3 parallel queries
    q = f"""
    [out:json][timeout:20];
    (
      node["tourism"~"attraction|museum|gallery|viewpoint|theme_park|nightclub"]({bbox_str});
      way["tourism"~"attraction|museum|gallery|viewpoint|theme_park|nightclub"]({bbox_str});
      node["historic"~"monument|castle|ruins|archaeological_site"]({bbox_str});
      way["historic"~"monument|castle|ruins|archaeological_site"]({bbox_str});
      node["leisure"~"park|garden|water_park"]({bbox_str});
      way["leisure"~"park|garden|water_park"]({bbox_str});
    );
    out center 30;
    """
    try:
        elements = await _overpass_query(q, 20)
    except Exception:
        async with _LOCK:
            _cache[key] = {"data": [], "_ts": time.time()}
        return []

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

    activities = []
    seen_names = set()
    for el in elements:
        tags = el.get("tags", {})
        name = _best_name(tags)
        if not name or name.lower() in seen_names:
            continue
        if not _is_in_correct_city(tags, destination, name):
            continue
        seen_names.add(name.lower())

        osm_type = (
            tags.get("tourism") or tags.get("historic") or
            tags.get("leisure") or tags.get("amenity") or ""
        )
        cat = cat_map.get(osm_type, "sightseeing")
        indoor = osm_type in ("museum", "gallery", "nightclub", "theme_park")

        activities.append({
            "name": name,
            "category": cat,
            "cost": None,
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
    q = f"""
    [out:json][timeout:20];
    (
      node["tourism"~"hotel|hostel|guest_house|motel"]({bbox_str});
      way["tourism"~"hotel|hostel|guest_house|motel"]({bbox_str});
    );
    out center 30;
    """
    try:
        elements = await _overpass_query(q, 20)
    except Exception:
        async with _LOCK:
            _cache[key] = {"data": [], "_ts": time.time()}
        return []

    hotels = []
    seen = set()
    for el in elements:
        tags = el.get("tags", {})
        name = _best_name(tags)
        if not name or name.lower() in seen:
            continue
        if not _is_in_correct_city(tags, destination, name):
            continue
        seen.add(name.lower())

        osm_type = tags.get("tourism", "hotel")
        stars_raw = tags.get("stars", "")
        try:
            stars = int(stars_raw) if stars_raw else None
        except (ValueError, TypeError):
            stars = None
        if stars is not None:
            stars = max(1, min(5, stars))

        hotels.append({
            "name": name,
            "type": osm_type,
            "stars": stars,
            "price_per_night": None,
            "rating": None,
        })

    async with _LOCK:
        _cache[key] = {"data": hotels, "_ts": time.time()}
    return hotels
