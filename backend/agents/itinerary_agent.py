import json
from datetime import date
from typing import Any, Dict, List
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

_SLOT_THEMES = ["Explore the City", "Cultural Immersion", "Adventure & Nature", "Food & Relaxation", "Local Experience"]


def _generate_fallback_itinerary(
    num_days: int,
    destination: str,
    origin: str,
    budget: float,
    currency: str,
    preferences: List[str],
    hotels: List[Dict],
    activities: List[Dict],
    weather: Dict,
) -> Dict[str, Any]:
    days: List[Dict] = []
    total_cost = 0
    hotel_name = hotels[0].get("name", "Selected Hotel") if hotels else "TBD"

    # Distribute activities across days
    act_list = activities[:]
    acts_per_day = max(len(act_list) // max(num_days, 1), 1)

    for d in range(1, num_days + 1):
        day_acts = act_list[(d - 1) * acts_per_day : d * acts_per_day] if act_list else []
        theme_idx = (d - 1) % len(_SLOT_THEMES)
        day_cost = sum(a.get("cost", 0) or 0 for a in day_acts)
        total_cost += day_cost

        # Determine slots
        morning = ""
        afternoon = ""
        evening = ""

        if d == 1:
            morning = f"Arrive in {destination}"
            afternoon = f"Check in at {hotel_name}"
            evening = day_acts[0].get("name", "Explore the city center") if day_acts else f"Evening walk around {destination}"
        elif d == num_days:
            morning = day_acts[0].get("name", f"Last morning exploring {destination}") if day_acts else f"Morning at {hotel_name}"
            afternoon = "Last-minute souvenir shopping"
            evening = f"Departure from {destination}"
        else:
            if len(day_acts) >= 3:
                morning = day_acts[0].get("name", f"Morning activity in {destination}")
                afternoon = day_acts[1].get("name", f"Afternoon exploration")
                evening = day_acts[2].get("name", f"Evening out in {destination}")
            elif len(day_acts) == 2:
                morning = day_acts[0].get("name", f"Morning activity")
                afternoon = day_acts[1].get("name", f"Afternoon activity")
                evening = f"Dinner at local restaurant"
            elif len(day_acts) == 1:
                morning = day_acts[0].get("name", f"Activity in {destination}")
                afternoon = f"Lunch and leisure time"
                evening = f"Evening stroll and dinner"
            else:
                morning = f"Explore {destination}"
                afternoon = f"Visit local attractions"
                evening = f"Dinner experience"

        days.append({
            "day": d,
            "theme": _SLOT_THEMES[theme_idx],
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "estimated_cost": day_cost,
        })

    tip = f"This itinerary was generated from available travel data. For a more refined plan, ensure the LLM provider is accessible."
    tips = [tip]
    if preferences:
        tips.append(f"Preferences included: {', '.join(preferences)}")

    return {
        "title": f"{num_days}-Day Trip to {destination}",
        "summary": f"A {num_days}-day trip to {destination} organized from your travel data. "
                   f"Total estimated cost: ~{currency} {total_cost:,}.",
        "days": days,
        "total_estimated_cost": total_cost,
        "tips": tips,
    }


async def itinerary_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    dates = state.get("travel_dates", {})
    currency = state.get("currency", "USD")
    
    try:
        start = date.fromisoformat(dates.get("start", "2025-06-01"))
        end = date.fromisoformat(dates.get("end", "2025-06-07"))
        num_days = max((end - start).days + 1, 1)
    except Exception:
        num_days = 7

    prev = state.get("previous_context", {})
    if prev and prev.get("days") and prev.get("destination") == state.get("destination"):
        return {"itinerary": prev, "execution_trace": ["itinerary_agent:from_context"]}

    hotels = state.get("hotels", [])
    activities = state.get("activities", [])
    weather = state.get("weather", {})

    budget = state.get("budget", 3000)
    budget_display = f"{budget:,.0f}" if budget < 999999 else "Unlimited"
    origin = state.get("origin", "Unknown")
    destination = state.get("destination", "Unknown")
    preferences = state.get("preferences", [])

    prompt = ITINERARY_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        origin=origin,
        budget=budget_display,
        currency=currency,
        preferences=", ".join(preferences) or "general",
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
        timeout=150,
    )

    result: Dict[str, Any] = {"itinerary": itinerary, "execution_trace": ["itinerary_agent"]}
    if isinstance(itinerary, dict) and "error" in itinerary:
        fallback = _generate_fallback_itinerary(
            num_days=num_days,
            destination=destination,
            origin=origin,
            budget=budget,
            currency=currency,
            preferences=preferences,
            hotels=hotels,
            activities=activities,
            weather=weather,
        )
        result = {
            "itinerary": fallback,
            "warnings": [f"LLM synthesis failed ({itinerary.get('error', 'unknown')}). Using template-based itinerary."],
            "execution_trace": ["itinerary_agent:fallback"],
        }
    return result
