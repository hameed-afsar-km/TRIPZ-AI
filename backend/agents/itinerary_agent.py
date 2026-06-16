import asyncio
import json
import logging
import re
from typing import Any, Dict

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

IMPORTANT — You MUST include the following in the output for EACH day:

1. **Budget per day**: Show a clear budget allocation for each day (accommodation, food, activities, transport, misc). Ensure the SUM of all daily budgets stays within the Total Budget above. If the user explicitly mentioned a budget amount for a specific place or activity, use that amount primarily.

2. **Google Maps link for each venue**: For each activity/venue, include a Google Maps link using the EXACT coordinates provided in the Activities section below. Do NOT guess or substitute coordinates — use only the `[lat,lon]` values shown next to each venue. Format: `[Venue Name](https://www.google.com/maps?q=lat,lon&z=15)`

3. **Budget for each place**: Show an estimated cost in {currency} next to each venue/activity (use real pricing from the data if available, otherwise estimate based on the venue type and location).

4. **Food cost**: Include the average meal cost per person in {currency} at each restaurant or dining spot mentioned. Note that prices can vary.

5. **Famous food / signature dishes**: When mentioning a restaurant, include its famous or signature dish(es) (use your knowledge of the destination's cuisine).

6. **Flight / airline name**: Mention the airline and flight you're recommending for travel to/from the destination. If you know common carriers for this route, use a real airline name.

7. **Accommodation cost**: Include the price per night in {currency} for the recommended hotel.

OUTPUT FORMAT:
Start with "# {num_days}-Day Trip to {destination}"
Then for each day: "## Day N: Theme" followed by bullet points in this structure:

**Morning**: [Venue/activity name](https://www.google.com/maps?q=lat,lon&z=15) — ~{currency} XX/pp · *Famous dish: ...* (if restaurant)
**Afternoon**: [Venue/activity name](https://www.google.com/maps?q=lat,lon&z=15) — ~{currency} XX/pp
**Evening**: [Venue/activity name](https://www.google.com/maps?q=lat,lon&z=15) — ~{currency} XX/pp · *Famous dish: ...* (if restaurant)
**Food budget**: ~{currency} XX/pp for meals
**Day total**: ~{currency} XX (accommodation {currency} XX + food {currency} XX + activities {currency} XX + transport {currency} XX)
*Tip: ...*

After each day's section (including its tip), add a separator line `---` with a blank line before and after it to visually separate the days. For the last day, do NOT add a separator after it.

Write the full raw markdown. Do NOT wrap in code blocks. Include ALL days."""


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


def _format_activities(activities: list, currency: str = "USD") -> str:
    if not activities:
        return "No activities found."
    lines = []
    for a in activities[:20]:
        name = a.get("name", "?")
        cat = a.get("category", a.get("type", "activity"))
        cost = a.get("cost")
        lat = a.get("lat")
        lon = a.get("lon")
        indoor = a.get("indoor", False)
        desc = a.get("description", "")
        cost_str = f" (~{currency} {cost})" if cost else " (cost unknown)"
        coords = f" [{lat},{lon}]" if lat and lon else ""
        indoor_str = " [indoor]" if indoor else ""
        lines.append(f"- {name} [{cat}]{cost_str}{coords}{indoor_str} — {desc}")
    return "\n".join(lines)


_DAY_TOTAL_PATTERN = re.compile(r'\*\*Day total\*\*:\s*~\w+\s*([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE)
_RAW_PRICE_PATTERN = re.compile(r'~\s*(\w{3})\s*([\d,]+(?:\.\d{1,2})?)')


def _check_budget(markdown: str, budget: float, currency: str) -> str:
    """Check if the itinerary's day totals sum within budget.

    Returns a warning string if exceeded, empty string otherwise.
    """
    total = 0.0
    found = 0
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
        f"⚠️ The total estimated cost (~{currency} {total:,.0f}) "
        f"exceeds your budget of {currency} {budget:,.0f} "
        f"by {currency} {overshoot:,.0f}. "
        "Consider choosing a more affordable hotel, reducing premium activities, "
        "or shortening the trip duration."
    )


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
        "activities": _format_activities(state.get("activities", []), currency),
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
        return {**state, "itinerary": {"error": str(e), "error_type": "timeout"},
                "warnings": [str(e)], "execution_trace": ["itinerary_agent:timeout"]}
    except Exception as e:
        msg = str(e)
        logger.error("Itinerary LLM failed: %s", msg)
        # Clean up the error message for display
        if msg.startswith("[") and "]" in msg:
            err_type = msg[1:msg.index("]")]
            msg = msg[msg.index("]") + 1:].strip()
        else:
            err_type = "api_error"
        return {**state, "itinerary": {"error": msg, "error_type": err_type},
                "warnings": [msg], "execution_trace": ["itinerary_agent:failed"]}

    warnings = state.get("warnings", [])
    if total_budget < 999999:
        budget_warning = _check_budget(markdown, total_budget, currency)
        if budget_warning:
            warnings.append(budget_warning)

    return {
        **state,
        "itinerary": {"markdown": markdown},
        "warnings": warnings,
        "execution_trace": ["itinerary_agent"],
    }
