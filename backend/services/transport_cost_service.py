import math
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("tripz.agents")

# Per-city transport pricing: {city_key: {"taxi_per_km": float, "metro_base": float, "bus_base": float, "currency": str}}
# Sources: numbeo, local transport authority data (2025-2026 estimates)
_CITY_TRANSPORT_COSTS: Dict[str, Dict[str, float]] = {
    "dubai":            {"taxi_per_km": 2.0,  "metro_base": 5.0, "bus_base": 3.0,  "walk_speed_kmh": 5.0, "currency": "AED"},
    "abu dhabi":        {"taxi_per_km": 1.8,  "metro_base": 0.0, "bus_base": 2.0,  "walk_speed_kmh": 5.0, "currency": "AED"},
    "india":            {"taxi_per_km": 0.6,  "metro_base": 0.4, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "INR"},
    "mumbai":           {"taxi_per_km": 0.7,  "metro_base": 0.5, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "INR"},
    "delhi":            {"taxi_per_km": 0.6,  "metro_base": 0.4, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "INR"},
    "bangalore":        {"taxi_per_km": 0.7,  "metro_base": 0.5, "bus_base": 0.3,  "walk_speed_kmh": 5.0, "currency": "INR"},
    "paris":            {"taxi_per_km": 1.5,  "metro_base": 2.1, "bus_base": 2.1,  "walk_speed_kmh": 5.0, "currency": "EUR"},
    "london":           {"taxi_per_km": 2.5,  "metro_base": 3.5, "bus_base": 1.8,  "walk_speed_kmh": 5.0, "currency": "GBP"},
    "new york":         {"taxi_per_km": 2.5,  "metro_base": 2.9, "bus_base": 2.9,  "walk_speed_kmh": 5.0, "currency": "USD"},
    "tokyo":            {"taxi_per_km": 4.0,  "metro_base": 1.8, "bus_base": 1.5,  "walk_speed_kmh": 5.0, "currency": "JPY"},
    "kyoto":            {"taxi_per_km": 3.5,  "metro_base": 1.5, "bus_base": 1.3,  "walk_speed_kmh": 5.0, "currency": "JPY"},
    "bangkok":          {"taxi_per_km": 0.6,  "metro_base": 0.8, "bus_base": 0.3,  "walk_speed_kmh": 5.0, "currency": "THB"},
    "phuket":           {"taxi_per_km": 1.2,  "metro_base": 0.0, "bus_base": 0.5,  "walk_speed_kmh": 5.0, "currency": "THB"},
    "singapore":        {"taxi_per_km": 1.2,  "metro_base": 1.5, "bus_base": 1.2,  "walk_speed_kmh": 5.0, "currency": "SGD"},
    "kuala lumpur":     {"taxi_per_km": 0.5,  "metro_base": 0.8, "bus_base": 0.4,  "walk_speed_kmh": 5.0, "currency": "MYR"},
    "istanbul":         {"taxi_per_km": 0.8,  "metro_base": 0.6, "bus_base": 0.4,  "walk_speed_kmh": 5.0, "currency": "TRY"},
    "bali":             {"taxi_per_km": 0.5,  "metro_base": 0.0, "bus_base": 0.3,  "walk_speed_kmh": 5.0, "currency": "IDR"},
    "sydney":           {"taxi_per_km": 2.2,  "metro_base": 3.0, "bus_base": 2.5,  "walk_speed_kmh": 5.0, "currency": "AUD"},
    "melbourne":        {"taxi_per_km": 2.0,  "metro_base": 3.0, "bus_base": 2.5,  "walk_speed_kmh": 5.0, "currency": "AUD"},
    "rome":             {"taxi_per_km": 1.5,  "metro_base": 1.5, "bus_base": 1.5,  "walk_speed_kmh": 5.0, "currency": "EUR"},
    "barcelona":        {"taxi_per_km": 1.3,  "metro_base": 2.4, "bus_base": 2.4,  "walk_speed_kmh": 5.0, "currency": "EUR"},
    "hong kong":        {"taxi_per_km": 2.5,  "metro_base": 1.5, "bus_base": 1.2,  "walk_speed_kmh": 5.0, "currency": "HKD"},
    "seoul":            {"taxi_per_km": 1.2,  "metro_base": 1.4, "bus_base": 1.2,  "walk_speed_kmh": 5.0, "currency": "KRW"},
    "cairo":            {"taxi_per_km": 0.4,  "metro_base": 0.3, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "EGP"},
    "cape town":        {"taxi_per_km": 1.0,  "metro_base": 0.0, "bus_base": 0.8,  "walk_speed_kmh": 5.0, "currency": "ZAR"},
    "rio de janeiro":   {"taxi_per_km": 0.8,  "metro_base": 1.0, "bus_base": 0.6,  "walk_speed_kmh": 5.0, "currency": "BRL"},
    "mexico city":      {"taxi_per_km": 0.5,  "metro_base": 0.3, "bus_base": 0.3,  "walk_speed_kmh": 5.0, "currency": "MXN"},
    "toronto":          {"taxi_per_km": 2.0,  "metro_base": 3.3, "bus_base": 3.3,  "walk_speed_kmh": 5.0, "currency": "CAD"},
    "vancouver":        {"taxi_per_km": 2.2,  "metro_base": 3.1, "bus_base": 3.1,  "walk_speed_kmh": 5.0, "currency": "CAD"},
    "amsterdam":        {"taxi_per_km": 2.5,  "metro_base": 3.2, "bus_base": 3.2,  "walk_speed_kmh": 5.0, "currency": "EUR"},
    "berlin":           {"taxi_per_km": 2.0,  "metro_base": 3.0, "bus_base": 3.0,  "walk_speed_kmh": 5.0, "currency": "EUR"},
    "doha":             {"taxi_per_km": 1.5,  "metro_base": 2.0, "bus_base": 0.0,  "walk_speed_kmh": 5.0, "currency": "QAR"},
    "muscat":           {"taxi_per_km": 0.8,  "metro_base": 0.0, "bus_base": 0.3,  "walk_speed_kmh": 5.0, "currency": "OMR"},
    "marrakech":        {"taxi_per_km": 0.6,  "metro_base": 0.0, "bus_base": 0.3,  "walk_speed_kmh": 5.0, "currency": "MAD"},
    "manila":           {"taxi_per_km": 0.5,  "metro_base": 0.4, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "PHP"},
    "nairobi":          {"taxi_per_km": 0.8,  "metro_base": 0.0, "bus_base": 0.4,  "walk_speed_kmh": 5.0, "currency": "KES"},
    "hanoi":            {"taxi_per_km": 0.4,  "metro_base": 0.3, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "VND"},
    "ho chi minh":      {"taxi_per_km": 0.4,  "metro_base": 0.3, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "VND"},
    "colombo":          {"taxi_per_km": 0.4,  "metro_base": 0.0, "bus_base": 0.2,  "walk_speed_kmh": 5.0, "currency": "LKR"},
    "kathmandu":        {"taxi_per_km": 0.3,  "metro_base": 0.0, "bus_base": 0.1,  "walk_speed_kmh": 5.0, "currency": "NPR"},
    "dhaka":            {"taxi_per_km": 0.3,  "metro_base": 0.3, "bus_base": 0.1,  "walk_speed_kmh": 5.0, "currency": "BDT"},
}

_DEFAULT_COST = {"taxi_per_km": 1.5, "metro_base": 2.0, "bus_base": 1.5, "walk_speed_kmh": 5.0, "currency": "USD"}


def _get_city_costs(destination: str) -> Dict[str, float]:
    dest_lower = destination.lower().strip()
    if dest_lower in _CITY_TRANSPORT_COSTS:
        return _CITY_TRANSPORT_COSTS[dest_lower]
    for key, costs in _CITY_TRANSPORT_COSTS.items():
        if key in dest_lower or dest_lower in key:
            return costs
    return dict(_DEFAULT_COST)


def estimate_transport_cost(
    distance_km: float,
    destination: str,
) -> List[Dict]:
    """Estimate transport cost and time between two venues.

    Returns list of transport options sorted by cost (cheapest first).
    Each option includes: mode, cost, duration_minutes, currency.
    """
    costs = _get_city_costs(destination)
    currency = costs["currency"]
    walk_speed = costs["walk_speed_kmh"]

    options = []

    # Walking (free, up to 2 km is reasonable)
    if distance_km <= 3:
        walk_min = round((distance_km / walk_speed) * 60, 0)
        options.append({
            "mode": "walk",
            "cost": 0.0,
            "duration_minutes": int(walk_min),
            "currency": currency,
        })

    # Metro (if available)
    if costs["metro_base"] > 0:
        metro_cost = costs["metro_base"]
        metro_speed_kmh = 35
        metro_min = round((distance_km / metro_speed_kmh) * 60 + 5, 0)
        options.append({
            "mode": "metro",
            "cost": metro_cost,
            "duration_minutes": max(5, int(metro_min)),
            "currency": currency,
        })

    # Bus (if available)
    if costs["bus_base"] > 0:
        bus_cost = costs["bus_base"]
        bus_speed_kmh = 20
        bus_min = round((distance_km / bus_speed_kmh) * 60 + 8, 0)
        options.append({
            "mode": "bus",
            "cost": bus_cost,
            "duration_minutes": max(8, int(bus_min)),
            "currency": currency,
        })

    # Taxi / rideshare
    taxi_cost = round(costs["taxi_per_km"] * distance_km, 1)
    taxi_speed_kmh = 30
    taxi_min = round((distance_km / taxi_speed_kmh) * 60 + 3, 0)
    options.append({
        "mode": "taxi",
        "cost": taxi_cost,
        "duration_minutes": max(3, int(taxi_min)),
        "currency": currency,
    })

    # Sort by cost (cheapest first)
    options.sort(key=lambda o: o["cost"])

    return options


def estimate_daily_transport_cost(
    num_legs: int,
    avg_distance_km: float,
    destination: str,
    preferred_mode: str = "taxi",
) -> Tuple[float, str]:
    """Estimate total daily transport cost for a given number of venue-to-venue legs.

    Returns (total_cost, currency).
    """
    options = estimate_transport_cost(avg_distance_km, destination)

    matched = [o for o in options if o["mode"] == preferred_mode]
    if not matched:
        matched = options

    if not matched:
        return 0.0, "USD"

    per_leg = matched[0]
    total = round(per_leg["cost"] * num_legs, 1)
    return total, per_leg["currency"]


def format_transport_for_prompt(destination: str) -> str:
    """Return a string for the itinerary prompt describing local transport costs."""
    costs = _get_city_costs(destination)
    currency = costs["currency"]

    lines = [f"Intra-city transport in {destination} (estimated costs in {currency}):"]
    if costs["metro_base"] > 0:
        lines.append(f"- Metro: ~{currency} {costs['metro_base']} per ride (fast, ~35 km/h)")
    if costs["bus_base"] > 0:
        lines.append(f"- Bus: ~{currency} {costs['bus_base']} per ride (cheap, ~20 km/h)")
    lines.append(f"- Taxi: ~{currency} {costs['taxi_per_km']}/km (convenient, ~30 km/h)")
    lines.append("- Walk: free (~5 km/h), good for short distances under 2 km")

    return "\n".join(lines)
