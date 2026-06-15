import asyncio
import json
import logging
from typing import Any, Dict

from services.llm_service import call_llm, resolve_provider

logger = logging.getLogger("tripz.agents")


ITINERARY_PROMPT_TEMPLATE = """You are a travel planner. Below is all the data gathered for a trip to {destination}.
Create a detailed day-by-day bullet-point itinerary covering ALL {num_days} days.

=== TRIP OVERVIEW ===
Destination: {destination}
Origin: {origin}
Duration: {num_days} days ({travel_dates})
Budget: {currency} {budget}
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
- Include a practical budget tip per day

OUTPUT FORMAT:
Start with "# {num_days}-Day Trip to {destination}"
Then for each day: "## Day N: Theme" followed by bullet points:
- **Morning**: Venue/activity
- **Afternoon**: Venue/activity  
- **Evening**: Venue/activity
- *Budget tip: ...*

Write the full raw markdown. Do NOT wrap in code blocks. Include ALL days."""


def _format_hotels(hotels: list) -> str:
    if not hotels:
        return "No hotels found."
    lines = []
    for h in hotels[:5]:
        name = h.get("name", "Unknown")
        price = h.get("price_per_night") or h.get("price", "N/A")
        stars = h.get("stars", "")
        htype = h.get("type", "hotel")
        line = f"- {name} ({htype})"
        if stars:
            line += f" - {stars} stars"
        if price:
            line += f" - ${price}/night"
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
    recommended = transport.get("recommended", "?")
    return f"- Distance: {dist} km\n- Recommended mode: {recommended}"


def _format_activities(activities: list) -> str:
    if not activities:
        return "No activities found."
    lines = []
    for a in activities[:20]:
        name = a.get("name", "?")
        cat = a.get("category", a.get("type", "activity"))
        cost = a.get("cost")
        cost_str = f" (${cost})" if cost else ""
        lines.append(f"- {name} [{cat}]{cost_str}")
    return "\n".join(lines)


async def itinerary_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    num_days = state.get("duration_days", 7)
    destination = state.get("destination", "Unknown")
    origin = state.get("origin", "Unknown")

    # Build a single formatted input string from all agent outputs
    inputs = {
        "destination": destination,
        "origin": origin,
        "num_days": num_days,
        "travel_dates": json.dumps(state.get("travel_dates", {})),
        "budget": f"{state.get('budget', 3000):,.0f}" if state.get("budget", 3000) < 999999 else "Unlimited",
        "currency": state.get("currency", "USD"),
        "trip_type": state.get("routing_decision", "standard"),
        "preferences": ", ".join(state.get("preferences", [])) or "general",
        "adults": state.get("adults", 1),
        "kids": state.get("kids", 0),
        "infants": state.get("infants", 0),
        "hotels": _format_hotels(state.get("hotels", [])),
        "weather": _format_weather(state.get("weather", {})),
        "transport": _format_transport(state.get("transport", {})),
        "activities": _format_activities(state.get("activities", [])),
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

    return {
        **state,
        "itinerary": {"markdown": markdown},
        "execution_trace": ["itinerary_agent"],
    }
