import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from services.geo_service import geocode_city

logger = logging.getLogger("tripz.agents")

AVIATIONSTACK_BASE = "http://api.aviationstack.com/v1"
_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 7200

# Common city → IATA mappings (used when AviationStack airport lookup fails)
_KNOWN_AIRPORTS: Dict[str, str] = {
    "dubai": "DXB", "abu dhabi": "AUH", "sharjah": "SHJ", "al ain": "AAN",
    "mumbai": "BOM", "delhi": "DEL", "bangalore": "BLR", "goa": "GOI",
    "new delhi": "DEL", "bengaluru": "BLR", "chennai": "MAA", "kolkata": "CCU",
    "hyderabad": "HYD", "kochi": "COK", "ahmedabad": "AMD", "pune": "PNQ",
    "london": "LHR", "paris": "CDG", "new york": "JFK", "los angeles": "LAX",
    "chicago": "ORD", "san francisco": "SFO", "tokyo": "NRT", "osaka": "KIX",
    "kyoto": "KIX", "seoul": "ICN", "beijing": "PEK", "shanghai": "PVG",
    "hong kong": "HKG", "singapore": "SIN", "bangkok": "BKK", "phuket": "HKT",
    "kuala lumpur": "KUL", "bali": "DPS", "jakarta": "CGK", "manila": "MNL",
    "ho chi minh": "SGN", "hanoi": "HAN", "sydney": "SYD", "melbourne": "MEL",
    "auckland": "AKL", "rome": "FCO", "milan": "MXP", "barcelona": "BCN",
    "madrid": "MAD", "amsterdam": "AMS", "frankfurt": "FRA", "munich": "MUC",
    "zurich": "ZRH", "geneva": "GVA", "vienna": "VIE", "prague": "PRG",
    "budapest": "BUD", "warsaw": "WAW", "stockholm": "ARN", "oslo": "OSL",
    "copenhagen": "CPH", "helsinki": "HEL", "brussels": "BRU", "dublin": "DUB",
    "edinburgh": "EDI", "manchester": "MAN", "istanbul": "IST", "antalya": "AYT",
    "doha": "DOH", "riyadh": "RUH", "jeddah": "JED", "muscat": "MCT",
    "kuwait": "KWI", "bahrain": "BAH", "cairo": "CAI", "casablanca": "CMN",
    "tunis": "TUN", "johannesburg": "JNB", "cape town": "CPT",
    "nairobi": "NBO", "lagos": "LOS", "addis ababa": "ADD",
    "toronto": "YYZ", "vancouver": "YVR", "montreal": "YUL",
    "mexico city": "MEX", "cancun": "CUN", "sao paulo": "GRU",
    "rio de janeiro": "GIG", "buenos aires": "EZE", "santiago": "SCL",
    "maldives": "MLE", "male": "MLE", "mauritius": "MRU",
    "colombo": "CMB", "kathmandu": "KTM", "dhaka": "DAC",
    "cape town": "CPT", "marrakech": "RAK",
}


def _get_api_key() -> Optional[str]:
    return os.environ.get("AVIATIONSTACK_API_KEY")


async def get_airport_code(city: str) -> Optional[str]:
    """Resolve a city name to its IATA airport code.

    First checks known airports dict, then falls back to AviationStack API.
    """
    city_lower = city.lower().strip()

    direct = _KNOWN_AIRPORTS.get(city_lower)
    if direct:
        return direct

    for key, code in _KNOWN_AIRPORTS.items():
        if key in city_lower or city_lower in key:
            return code

    api_key = _get_api_key()
    if not api_key:
        return None

    cache_key = f"as_airport:{city_lower}"
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached["_ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{AVIATIONSTACK_BASE}/airports",
                params={"access_key": api_key, "search": city, "limit": 5},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            airports = data.get("data", [])
            for ap in airports:
                iata = (ap.get("iata_code") or "").strip()
                airport_name = (ap.get("airport_name") or "").lower()
                if iata and len(iata) == 3 and (city_lower in airport_name or airport_name in city_lower):
                    _CACHE[cache_key] = {"data": iata, "_ts": time.time()}
                    return iata

            if airports:
                iata = (airports[0].get("iata_code") or "").strip()
                if iata and len(iata) == 3:
                    _CACHE[cache_key] = {"data": iata, "_ts": time.time()}
                    return iata

            return None
    except Exception:
        logger.debug("AviationStack airport lookup failed for '%s'", city, exc_info=True)
        return None


async def search_flights(
    origin_city: str,
    dest_city: str,
    date: str = "",
) -> List[Dict[str, Any]]:
    """Search for flights between two cities via AviationStack.

    Returns list of flight dicts with airline, flight number, departure/arrival,
    status, and estimated duration.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    origin_code = await get_airport_code(origin_city)
    dest_code = await get_airport_code(dest_city)

    if not origin_code or not dest_code:
        logger.warning("Could not resolve airport codes: %s → %s", origin_city, dest_city)
        return []

    cache_key = f"as_flights:{origin_code}:{dest_code}:{date}"
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached["_ts"]) < _CACHE_TTL:
        return cached["data"]

    params: Dict[str, Any] = {
        "access_key": api_key,
        "dep_iata": origin_code,
        "arr_iata": dest_code,
        "limit": 10,
    }
    if date:
        params["flight_date"] = date

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{AVIATIONSTACK_BASE}/flights", params=params)
            if resp.status_code != 200:
                logger.warning("AviationStack flights returned %s for %s→%s", resp.status_code, origin_code, dest_code)
                return []

            data = resp.json()
            flights = data.get("data", [])
            results = []
            for f in flights:
                flight = f.get("flight", {})
                departure = f.get("departure", {})
                arrival = f.get("arrival", {})
                airline = f.get("airline", {})

                dep_sched = departure.get("scheduled", "")
                arr_sched = arrival.get("scheduled", "")

                duration_min = None
                if dep_sched and arr_sched:
                    try:
                        from datetime import datetime
                        dep_dt = datetime.fromisoformat(dep_sched.replace("Z", "+00:00"))
                        arr_dt = datetime.fromisoformat(arr_sched.replace("Z", "+00:00"))
                        duration_min = int((arr_dt - dep_dt).total_seconds() / 60)
                    except Exception:
                        pass

                results.append({
                    "airline": airline.get("name", "Unknown"),
                    "airline_iata": airline.get("iata", ""),
                    "flight_number": flight.get("iata", flight.get("number", "")),
                    "flight_iata": flight.get("iata", ""),
                    "departure_airport": departure.get("iata", origin_code),
                    "departure_scheduled": dep_sched,
                    "departure_terminal": departure.get("terminal", ""),
                    "arrival_airport": arrival.get("iata", dest_code),
                    "arrival_scheduled": arr_sched,
                    "arrival_terminal": arrival.get("terminal", ""),
                    "duration_minutes": duration_min,
                    "status": f.get("flight_status", "unknown"),
                })

            _CACHE[cache_key] = {"data": results, "_ts": time.time()}
            logger.info("AviationStack: %d flights found %s→%s", len(results), origin_code, dest_code)
            return results

    except Exception:
        logger.debug("AviationStack flight search failed for %s→%s", origin_city, dest_city, exc_info=True)
        return []


async def search_routes(origin_city: str, dest_city: str) -> List[Dict[str, Any]]:
    """Search for available routes between two cities."""
    api_key = _get_api_key()
    if not api_key:
        return []

    origin_code = await get_airport_code(origin_city)
    dest_code = await get_airport_code(dest_city)

    if not origin_code or not dest_code:
        return []

    cache_key = f"as_routes:{origin_code}:{dest_code}"
    cached = _CACHE.get(cache_key)
    if cached and (time.time() - cached["_ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{AVIATIONSTACK_BASE}/routes",
                params={
                    "access_key": api_key,
                    "dep_iata": origin_code,
                    "arr_iata": dest_code,
                },
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            routes = data.get("data", [])
            _CACHE[cache_key] = {"data": routes, "_ts": time.time()}
            return routes

    except Exception:
        logger.debug("AviationStack route search failed for %s→%s", origin_city, dest_city, exc_info=True)
        return []


def estimate_flight_cost(
    origin_city: str,
    dest_city: str,
    distance_km: float,
    currency: str = "USD",
) -> Dict[str, Any]:
    """Estimate flight cost based on distance and typical airline pricing.

    Used when real pricing is unavailable (AviationStack free tier has no pricing).
    Gives a reasonable estimate that beats the current "no data" status.
    """
    if distance_km <= 0:
        return {"estimated": False, "note": "Distance unknown, cannot estimate flight cost."}

    cost_per_km_usd = 0.08
    estimated_usd = distance_km * cost_per_km_usd

    economy = round(estimated_usd * 0.8, 0)
    business = round(estimated_usd * 2.5, 0)

    return {
        "estimated": True,
        "economy": economy,
        "business": business,
        "currency": currency,
        "note": f"Estimated based on {distance_km:,.0f} km at ~${cost_per_km_usd}/km.",
    }
