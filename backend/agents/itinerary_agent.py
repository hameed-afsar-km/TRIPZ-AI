import asyncio
import json
import logging
import math
import re
from typing import Any, Dict, List, Tuple

from services.distance_service import get_travel_time, haversine_km
from services.llm_service import call_llm, resolve_provider

logger = logging.getLogger("tripz.agents")

_COUNTRY_CURRENCIES = {
    "united arab emirates": "AED", "dubai": "AED", "abu dhabi": "AED",
    "india": "INR", "mumbai": "INR", "delhi": "INR", "bangalore": "INR", "goa": "INR",
    "united kingdom": "GBP", "london": "GBP", "england": "GBP", "uk": "GBP",
    "japan": "JPY", "tokyo": "JPY", "kyoto": "JPY", "osaka": "JPY",
    "thailand": "THB", "bangkok": "THB", "phuket": "THB",
    "vietnam": "VND", "hanoi": "VND", "ho chi minh": "VND",
    "indonesia": "IDR", "bali": "IDR", "jakarta": "IDR",
    "australia": "AUD", "sydney": "AUD", "melbourne": "AUD",
    "europe": "EUR", "france": "EUR", "paris": "EUR", "italy": "EUR", "rome": "EUR",
    "germany": "EUR", "berlin": "EUR", "spain": "EUR", "barcelona": "EUR",
    "netherlands": "EUR", "amsterdam": "EUR", "greece": "EUR", "athens": "EUR",
    "portugal": "EUR", "lisbon": "EUR", "switzerland": "CHF", "zurich": "CHF",
    "turkey": "TRY", "istanbul": "TRY", "antalya": "TRY",
    "singapore": "SGD",
    "malaysia": "MYR", "kuala lumpur": "MYR",
    "china": "CNY", "beijing": "CNY", "shanghai": "CNY",
    "south korea": "KRW", "seoul": "KRW",
    "egypt": "EGP", "cairo": "EGP",
    "south africa": "ZAR", "cape town": "ZAR",
    "brazil": "BRL", "rio de janeiro": "BRL",
    "mexico": "MXN", "cancun": "MXN",
    "canada": "CAD", "toronto": "CAD", "vancouver": "CAD",
    "new zealand": "NZD", "auckland": "NZD",
    "usa": "USD", "united states": "USD", "new york": "USD", "los angeles": "USD",
    "hong kong": "HKD",
    "qatar": "QAR", "doha": "QAR",
    "saudi arabia": "SAR", "riyadh": "SAR",
    "kuwait": "KWD",
    "oman": "OMR", "muscat": "OMR",
    "bahrain": "BHD",
    "maldives": "MVR",
    "nepal": "NPR", "kathmandu": "NPR",
    "sri lanka": "LKR", "colombo": "LKR",
    "bangladesh": "BDT", "dhaka": "BDT",
    "philippines": "PHP", "manila": "PHP",
    "morocco": "MAD", "marrakech": "MAD",
    "kenya": "KES", "nairobi": "KES",
    "nigeria": "NGN", "lagos": "NGN",
}


def _resolve_destination_currency(destination: str) -> str | None:
    dest_lower = destination.lower().strip()
    if dest_lower in _COUNTRY_CURRENCIES:
        return _COUNTRY_CURRENCIES[dest_lower]
    for key, cur in _COUNTRY_CURRENCIES.items():
        if key in dest_lower or dest_lower in key:
            return cur
    return None


ITINERARY_PROMPT_TEMPLATE = """You are a travel planner. Below is all the data gathered for a trip to {destination}.
Create a detailed day-by-day bullet-point itinerary covering ALL {num_days} days.

=== TRIP OVERVIEW ===
Destination: {destination}
Origin: {origin}
Duration: {num_days} days ({travel_dates})
Total Budget: {currency} {budget} (approx. {currency} {budget_per_day}/day)
Trip Style: {trip_type}
Travelers: {adults} adults, {kids} kids, {infants} infants
Preferences: {preferences}
{replan_section}

=== HOTELS ===
{hotels}

=== WEATHER FORECAST ===
{weather}

=== TRANSPORT ===
{transport}

=== ACTIVITIES & VENUES ===
{activities}

RULES:
- Plan EVERY day with morning, afternoon, and evening activities
- Day 1 = arrival + evening. Last day = morning + departure.
- Use REAL venue names from the Activities list
- Avoid outdoor activities on bad weather days (see Weather)
- Mix themes across days (culture, adventure, food, landmarks, relaxation)
- NEVER repeat an attraction, restaurant, or activity across different days. Every venue must appear exactly once.
- Group activities on the same day by geographic proximity. Activities listed under the same area (e.g., "Downtown Dubai", "Deira") should be visited on the same day. NEVER combine venues from different areas (e.g., Downtown Dubai + Deira) on the same day — they are too far apart.
- For each consecutive activity pair, estimate the transit time (driving) and include it in the schedule (e.g., "9:00 AM – 9:30 AM: Drive to venue").
{replan_rules}

IMPORTANT — You MUST include the following in the output for EACH day:

1. **Budget per day**: Show a clear budget allocation for each day (accommodation, food, activities, transport, misc). Ensure the SUM of all daily budgets stays within the Total Budget above. If the user explicitly mentioned a budget amount for a specific place or activity, use that amount primarily.

2. **Google Maps link for each venue**: For each activity/venue, include a Google Maps link using the name-based search URL. Format: `[Venue Name](https://www.google.com/maps/search/?api=1&query=Venue+Name+City)`

3. **Budget for each place**: Show an estimated cost in {currency} next to each venue/activity (use real pricing from the data if available, otherwise estimate based on the venue type and location).

4. **Restaurant data**: For every restaurant or food venue, include: signature dish(es), average price per person, cuisine type, and neighborhood/area.

5. **Nearby restaurants**: Restaurants should be in the same area/neighborhood as the day's activities. If visiting Dubai Aquarium in Dubai Mall, recommend restaurants in Dubai Mall or Downtown Dubai — not in Deira or Jumeirah.

6. **Flight / airline name**: Mention the airline and flight you're recommending for travel to/from the destination. If you know common carriers for this route, use a real airline name.

7. **Accommodation cost**: Include the price per night in {currency} for the recommended hotel.

8. **Timings**: For each activity, include the recommended time of visit. For example: `9:00 AM - Leave hotel | 9:40 AM - Reach venue | 11:00 AM - Finish | 11:20 AM - Taxi to next | 12:00 PM - Lunch`. This makes the itinerary feel like a real travel plan, not a list.

9. **Booking info**: For each venue, mention if booking is required, expected visit duration, and best visiting time.

OUTPUT FORMAT:
Start with "# {num_days}-Day Trip to {destination}"
Then for each day: "## Day N: Theme" followed by this structure:

**9:00 AM** — [Venue/activity name](https://www.google.com/maps/search/?api=1&query=Venue+Name+City) — ~{currency} XX/pp · *Famous dish: ...* (if restaurant) · ⏱ 1.5h · Booking recommended
**11:30 AM** — [Next venue](https://www.google.com/maps/search/?api=1&query=Name+City) — ~{currency} XX/pp · ⏱ 1h
**1:00 PM** — Lunch at [Restaurant name](https://www.google.com/maps/search/?api=1&query=Name+City) — ~{currency} XX/pp · *Signature: ...* · Cuisine: ... · Area: ...
**3:00 PM** — [Venue/activity name](https://www.google.com/maps/search/?api=1&query=Name+City) — ~{currency} XX/pp · ⏱ 2h · Closed on Mondays
**7:00 PM** — Dinner at [Restaurant name](https://www.google.com/maps/search/?api=1&query=Name+City) — ~{currency} XX/pp · *Signature: ...* · Cuisine: ... · Area: ...
**Day total**: ~{currency} XX (food {currency} XX + activities {currency} XX + transport {currency} XX)
*Tip: ...*

After each day's section (including its tip), add a separator line `---` with a blank line before and after it to visually separate the days. For the last day, do NOT add a separator after it.

Write the full raw markdown. Do NOT wrap in code blocks. Include ALL days.

After the last day, add a `---` separator, then a **Final Cost Summary** section:
```
**Accommodation**: {num_days} nights × {currency} XX/night = {currency} YY
**Food (total)**: ~{currency} ZZ
**Activities (total)**: ~{currency} WW
**Transport (total)**: ~{currency} VV
**Grand Total**: ~{currency} TT
```
Accommodation is `nights × price_per_night`. Food/Activities/Transport should be summed from your day totals. Grand Total = accommodation + food + activities + transport."""



def _format_hotels(hotels: list, currency: str = "USD") -> str:
    if not hotels:
        return "No hotels found."
    lines = []
    for h in hotels[:10]:
        name = h.get("name", "Unknown")
        price = h.get("price_per_night") or h.get("price")
        stars = h.get("stars")
        rating = h.get("rating")
        htype = h.get("type", "hotel")
        line = f"- {name} ({htype})"
        if stars:
            line += f" — {stars}★"
        if price:
            line += f" — {currency} {price}/night"
        else:
            line += " — price unknown"
        if rating:
            line += f" — rating: {rating}/5"
        lines.append(line)
    return "\n".join(lines)


def _format_weather(weather: dict) -> str:
    forecast = weather.get("forecast", [])
    if not forecast:
        return "No weather data."
    lines = []
    for d in forecast[:5]:
        date = d.get("date", "?")
        cond = d.get("condition", "?")
        temp = d.get("temp_max_c", "?")
        lines.append(f"- {date}: {cond}, {temp}C")
    return "\n".join(lines)


def _format_transport(transport: dict) -> str:
    if not transport:
        return "No transport data."
    dist = transport.get("distance_km", "?")
    origin = transport.get("origin", "?")
    destination = transport.get("destination", "?")
    return f"- Route: {origin} → {destination}\n- Distance: {dist} km\n- Typical flight time: approx. {max(1, round(dist / 800))}h by air"


def _cluster_activities(activities: List[Dict[str, Any]]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Group activities by proximity using grid-based clustering (~2km cells)."""
    clusters: List[dict] = []
    for a in activities:
        lat = a.get("lat")
        lon = a.get("lon")
        if lat is None or lon is None:
            clusters.append({"label": "Unknown area", "items": [a]})
            continue
        cell_lat = round(lat * 50) / 50
        cell_lon = round(lon * 50) / 50
        cell_key = f"{cell_lat:.2f},{cell_lon:.2f}"
        found = False
        for c in clusters:
            if c.get("cell") == cell_key:
                c["items"].append(a)
                found = True
                break
        if not found:
            clusters.append({"cell": cell_key, "label": f"Area ({cell_lat:.2f}, {cell_lon:.2f})", "items": [a]})
    result = [(c["label"], c["items"]) for c in clusters]
    return result


def _area_label_from_activities(activities: List[Dict[str, Any]], destination: str) -> str:
    """Generate a human-readable area label for a cluster of activities."""
    lat = activities[0].get("lat", 0)
    lon = activities[0].get("lon", 0)
    if not lat or not lon:
        return "General area"
    if "dubai" in destination.lower():
        if 55.27 <= lon <= 55.30 and 25.18 <= lat <= 25.22:
            return "Downtown Dubai"
        if 55.29 <= lon <= 55.33 and 25.26 <= lat <= 25.30:
            return "Deira / Old Dubai"
        if 55.13 <= lon <= 55.20 and 25.10 <= lat <= 25.17:
            return "Dubai Marina / JBR"
        if 55.14 <= lon <= 55.20 and 25.21 <= lat <= 25.26:
            return "Bur Dubai / Al Fahidi"
        if 55.30 <= lon <= 55.40 and 25.22 <= lat <= 25.28:
            return "Garhoud / Airport Area"
        if 55.30 <= lon <= 55.38 and 25.03 <= lat <= 25.12:
            return "Palm Jumeirah"
        if 55.20 <= lon <= 55.30 and 25.05 <= lat <= 25.15:
            return "Jumeirah / Beach Road"
    return f"Area ({lat:.2f}, {lon:.2f})"


def _format_activities(activities: list, destination: str = "", currency: str = "USD") -> str:
    if not activities:
        return "No activities found."
    clusters = _cluster_activities(activities[:35])
    sections = []
    for label, items in clusters:
        area_name = _area_label_from_activities(items, destination)
        lines = [f"\n  ── {area_name} ──"]
        for a in items[:8]:
            name = a.get("name", "?")
            cat = a.get("category", a.get("type", "activity"))
            cost = a.get("cost")
            lat = a.get("lat")
            lon = a.get("lon")
            indoor = a.get("indoor", False)
            desc = a.get("description", "")
            tags = a.get("tags", {})
            cost_str = f" (~{currency} {cost})" if cost else " (cost unknown)"
            coords = f" [{lat},{lon}]" if lat and lon else ""
            indoor_str = " [indoor]" if indoor else ""
            extra = ""
            if cat == "food":
                cuisine = tags.get("cuisine", "")
                hours = tags.get("opening_hours", "")
                if cuisine:
                    extra = f"  Cuisine: {cuisine}"
                if hours:
                    extra += f"  Hours: {hours}"
            lines.append(f"  - {name} [{cat}]{cost_str}{coords}{indoor_str}{extra}")
        sections.append("\n".join(lines))
    return "\n".join(sections)


_DAY_TOTAL_PATTERN = re.compile(r'\*\*Day total\*\*:\s*~\w+\s*([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE)
_RAW_PRICE_PATTERN = re.compile(r'~\s*(\w{3})\s*([\d,]+(?:\.\d{1,2})?)')
_GRAND_TOTAL_PATTERN = re.compile(r'\*\*Grand Total\*\*:\s*~\w+\s*([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE)
_GOOGLE_MAPS_PATTERN = re.compile(r'\[([^\]]+)\]\(https?://(?:www\.)?google\.com/maps/[^)]+\)')


def _check_budget(markdown: str, budget: float, currency: str) -> str:
    """Check if the itinerary's grand total or day totals sum within budget.

    Returns a warning string if exceeded, empty string otherwise.
    """
    total = 0.0
    found = 0

    grand_total_match = _GRAND_TOTAL_PATTERN.search(markdown)
    if grand_total_match:
        try:
            total = float(grand_total_match.group(1).replace(",", ""))
            found = 1
        except ValueError:
            pass

    if found == 0:
        for match in _DAY_TOTAL_PATTERN.finditer(markdown):
            try:
                total += float(match.group(1).replace(",", ""))
                found += 1
            except ValueError:
                continue

    if found == 0:
        for match in _RAW_PRICE_PATTERN.finditer(markdown):
            cur = match.group(1).upper()
            if cur == currency.upper():
                try:
                    total += float(match.group(2).replace(",", ""))
                except ValueError:
                    continue

    if total <= budget:
        return ""

    overshoot = total - budget
    return (
        f"The total estimated cost (~{currency} {total:,.0f}) "
        f"exceeds your budget of {currency} {budget:,.0f} "
        f"by {currency} {overshoot:,.0f}. "
        "Consider choosing a more affordable hotel, reducing premium activities, "
        "or shortening the trip duration."
    )


def _fix_maps_links(markdown: str, activities: list, destination: str) -> str:
    """Replace LLM-generated Google Maps URLs with correct name-based search URLs."""
    def _replace(match):
        name = match.group(1).strip()
        for a in activities:
            act_name = a.get("name", "")
            if act_name.lower() in name.lower() or name.lower() in act_name.lower():
                lat = a.get("lat")
                lon = a.get("lon")
                if lat and lon:
                    query = f"{name} {destination}".replace(" ", "+").replace("&", "%26")
                    return f"[{name}](https://www.google.com/maps/search/?api=1&query={query})"
        query = f"{name} {destination}".replace(" ", "+").replace("&", "%26")
        return f"[{name}](https://www.google.com/maps/search/?api=1&query={query})"
    return _GOOGLE_MAPS_PATTERN.sub(_replace, markdown)


def _extract_venue_names_from_markdown(markdown: str) -> list:
    """Extract all linked venue names from the itinerary markdown."""
    names = []
    for match in _GOOGLE_MAPS_PATTERN.finditer(markdown):
        name = match.group(1).strip()
        if name and len(name) > 2:
            names.append(name)
    return names


async def itinerary_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    num_days = state.get("duration_days", 7)
    destination = state.get("destination", "Unknown")
    origin = state.get("origin", "Unknown")

    total_budget = state.get("budget", 3000)
    original_currency = state.get("currency", "USD")
    currency = _resolve_destination_currency(destination) or original_currency

    # Convert budget to destination currency if they differ
    if currency != original_currency and total_budget < 999999:
        try:
            from services.exchange_service import convert_between_currencies
            converted = await convert_between_currencies(total_budget, original_currency, currency)
            total_budget = round(converted, 0)
        except Exception:
            logger.warning("Currency conversion failed, using original budget as-is")
            currency = original_currency

    budget_per_day = (total_budget / num_days) if num_days > 0 else total_budget

    budget_in_dest_currency = total_budget
    original_currency_for_warning = original_currency

    # Build replan instructions section (if this is a replan)
    replan_instructions = state.get("replan_instructions", "").strip()
    replan_section = ""
    if replan_instructions:
        replan_count = state.get("replan_count", 0)
        replan_section = (
            f"\n=== REPLAN FEEDBACK (attempt #{replan_count}) ===\n"
            f"The previous version was rejected. Please fix the following:\n"
            f"{replan_instructions}\n"
            "IMPORTANT: Use ONLY real venue names from the Activities list below. "
            "Do NOT invent attractions or venues."
        )

    # Build replan rules — don't repeat previously visited venues
    visited = state.get("visited_places", [])
    replan_rules = ""
    if visited:
        replan_rules = f"\n- DO NOT repeat any of these previously used venues: {', '.join(visited)}"

    # Build a single formatted input string from all agent outputs
    inputs = {
        "destination": destination,
        "origin": origin,
        "num_days": num_days,
        "travel_dates": json.dumps(state.get("travel_dates", {})),
        "budget": f"{total_budget:,.0f}" if total_budget < 999999 else "Unlimited",
        "budget_per_day": f"{budget_per_day:,.0f}" if total_budget < 999999 else "Unlimited",
        "currency": currency,
        "trip_type": state.get("routing_decision", "standard"),
        "preferences": ", ".join(state.get("preferences", [])) or "general",
        "adults": state.get("adults", 1),
        "kids": state.get("kids", 0),
        "infants": state.get("infants", 0),
        "hotels": _format_hotels(state.get("hotels", []), currency),
        "weather": _format_weather(state.get("weather", {})),
        "transport": _format_transport(state.get("transport", {})),
        "activities": _format_activities(state.get("activities", []), destination, currency),
        "replan_section": replan_section,
        "replan_rules": replan_rules,
    }

    prompt = ITINERARY_PROMPT_TEMPLATE.format(**inputs)

    try:
        markdown = await call_llm(
            role="itinerary",
            prompt=prompt,
            provider=resolve_provider(state, "itinerary"),
            api_key=state.get("api_key"),
            timeout=120,
        )
    except asyncio.TimeoutError as e:
        logger.error("Itinerary LLM timed out: %s", e)
        return {
            "itinerary": {"error": str(e), "error_type": "timeout"},
            "warnings": [str(e)],
            "execution_trace": ["itinerary_agent:timeout"],
        }
    except Exception as e:
        msg = str(e)
        logger.error("Itinerary LLM failed: %s", msg)
        if msg.startswith("[") and "]" in msg:
            err_type = msg[1:msg.index("]")]
            msg = msg[msg.index("]") + 1:].strip()
        else:
            err_type = "api_error"
        return {
            "itinerary": {"error": msg, "error_type": err_type},
            "warnings": [msg],
            "execution_trace": ["itinerary_agent:failed"],
        }

    markdown = _fix_maps_links(markdown, state.get("activities", []), destination)

    visited_places = _extract_venue_names_from_markdown(markdown)

    new_warnings = []
    if total_budget < 999999:
        budget_warning = _check_budget(markdown, total_budget, currency)
        if budget_warning:
            new_warnings.append(budget_warning)

    return {
        "itinerary": {"markdown": markdown},
        "warnings": new_warnings,
        "visited_places": visited_places,
        "execution_trace": ["itinerary_agent"],
    }
