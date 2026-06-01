import json
from typing import Any, Dict
from services.llm_service import call_llm_json

ITINERARY_SYSTEM = "You are a travel planner. Output ONLY valid JSON."

ITINERARY_PROMPT_TEMPLATE = """Plan a {num_days}-day trip to {destination} from {origin}.
Budget: {currency} {budget}. Preferences: {preferences}.

Hotels: {hotels}
Transport: {transport}
Activities: {activities}
Weather: {weather_summary}

Rules:
- Stay within budget or close to it (unless budget is unlimited)
- Avoid outdoor activities on bad weather days
- Day 1: arrival and evening exploration
- Last day: departure  
- Fill all {num_days} days with activities
- Include variety: culture, food, adventure, relaxation where applicable
- Use the destination currency: {currency}
- If "visit all places" is a preference, include diverse activities covering different aspects

Return JSON:
{{"title":"","summary":"","days":[
{{"day":1,"theme":"","morning":"","afternoon":"","evening":"","estimated_cost":0}}
], "total_estimated_cost":0, "tips":[]}}"""


def _trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


async def itinerary_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    dates = state.get("travel_dates", {})
    currency = state.get("currency", "USD")
    
    try:
        from datetime import date
        start = date.fromisoformat(dates.get("start", "2025-06-01"))
        end = date.fromisoformat(dates.get("end", "2025-06-07"))
        num_days = max((end - start).days + 1, 1)  # +1 to include both start and end day
    except Exception:
        num_days = 7  # fallback

    prev = state.get("previous_context", {})
    if prev and prev.get("days") and prev.get("destination") == state.get("destination"):
        return {"itinerary": prev, "execution_trace": ["itinerary_agent:from_context"]}

    hotels = state.get("hotels", [])
    activities = state.get("activities", [])
    weather = state.get("weather", {})

    # Format budget with currency symbol
    budget = state.get("budget", 3000)
    budget_display = f"{budget:,.0f}" if budget < 999999 else "Unlimited"
    
    # Get origin with fallback
    origin = state.get("origin", "Unknown")

    prompt = ITINERARY_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=state.get("destination", "Unknown"),
        origin=origin,
        budget=budget_display,
        currency=currency,
        preferences=", ".join(state.get("preferences", [])) or "general",
        hotels=_trunc(json.dumps([{k: h[k] for k in ("name","price_per_night","stars","rating") if k in h} for h in hotels[:2]]), 300),
        transport=_trunc(json.dumps(state.get("transport", {}).get("recommended", {})), 200),
        activities=_trunc(json.dumps([{k: a[k] for k in ("name","cost","indoor","category") if k in a} for a in activities[:8]]), 500),
        weather_summary=_trunc(json.dumps([{"date":d.get("date"),"condition":d.get("condition"),"temp":d.get("temp_max_c")} for d in weather.get("forecast",[])[:3]]), 300),
    )

    itinerary = await call_llm_json(
        role="itinerary",
        prompt=prompt,
        system=ITINERARY_SYSTEM,
        provider=state.get("provider", "ollama"),
        api_key=state.get("api_key"),
    )

    result: Dict[str, Any] = {"itinerary": itinerary, "execution_trace": ["itinerary_agent"]}
    if isinstance(itinerary, dict) and "error" in itinerary:
        result["error"] = itinerary["error"]
        if "error_type" in itinerary:
            result["error_type"] = itinerary["error_type"]
    return result
