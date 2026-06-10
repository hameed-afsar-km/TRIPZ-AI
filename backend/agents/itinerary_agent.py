import json
from typing import Any, Dict, List
from services.llm_service import call_llm_json

ITINERARY_SYSTEM = "You are a travel planner. Output ONLY valid JSON."

ITINERARY_PROMPT_TEMPLATE = """Plan a {num_days}-day trip to {destination} from {origin}.
Trip style: {trip_type}. Budget: {currency} {budget}. Preferences: {preferences}.

Hotels: {hotels}
Transport: {transport}
Activities: {activities}
Weather: {weather_summary}

{replan_context}
Rules:
- Stay within budget or close to it (unless budget is unlimited)
- Avoid outdoor activities on bad weather days
- Day 1: arrival and evening exploration
- Last day: departure
- Fill all {num_days} days with activities
- EVERY day MUST use specific named activities from the Activities list — NEVER use generic phrases like "Relax at the hotel", "Explore the city", "Visit local attractions", "Enjoy a nice dinner"
- Each day must have UNIQUE activities — never repeat the same morning/afternoon/evening text across different days
- Be specific: name actual landmarks, restaurants, beaches, museums, parks, malls
- All prices MUST be in {currency}
- Include variety across days (don't repeat the same theme)

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

    act_list = activities[:]
    acts_per_day = max(len(act_list) // max(num_days, 1), 1)

    for d in range(1, num_days + 1):
        day_acts = act_list[(d - 1) * acts_per_day : d * acts_per_day] if act_list else []
        theme_idx = (d - 1) % len(_SLOT_THEMES)
        day_cost = sum(a.get("cost", 0) or 0 for a in day_acts)
        total_cost += day_cost

        morning = ""
        afternoon = ""
        evening = ""

        if d == 1:
            morning = f"Arrive in {destination}"
            afternoon = f"Check in at {hotel_name}"
            evening = day_acts[0].get("name", f"Evening walk around {destination}") if day_acts else f"Explore {destination} downtown"
        elif d == num_days:
            morning = day_acts[0].get("name", f"Last morning at {hotel_name}") if day_acts else f"Breakfast at {hotel_name}"
            afternoon = "Souvenir shopping at local market"
            evening = f"Departure from {destination}"
        else:
            if len(day_acts) >= 3:
                morning = day_acts[0].get("name", f"Visit {destination} landmark")
                afternoon = day_acts[1].get("name", f"Explore {destination}")
                evening = day_acts[2].get("name", f"Dinner in {destination}")
            elif len(day_acts) == 2:
                morning = day_acts[0].get("name", f"Morning at {destination}")
                afternoon = day_acts[1].get("name", f"Afternoon activity")
                evening = f"Dinner at {destination} restaurant"
            elif len(day_acts) == 1:
                morning = day_acts[0].get("name", f"Activity in {destination}")
                afternoon = f"Lunch and shopping"
                evening = f"Evening stroll in {destination}"
            else:
                morning = f"Sightseeing in {destination}"
                afternoon = f"Visit {destination} attractions"
                evening = f"Dinner in {destination}"

        days.append({
            "day": d,
            "theme": _SLOT_THEMES[theme_idx],
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "estimated_cost": day_cost,
        })

    tip = "This itinerary was generated from available travel data. For a more refined plan, ensure the LLM provider is accessible."
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
    num_days = state.get("duration_days", 7)

    prev = state.get("previous_context", {})
    if prev and prev.get("days") and prev.get("destination") == state.get("destination"):
        return {"itinerary": prev, "execution_trace": ["itinerary_agent:from_context"]}

    hotels = state.get("hotels", [])
    activities = state.get("activities", [])
    weather = state.get("weather", {})

    budget = state.get("budget", 3000)
    budget_display = f"{budget:,.0f}" if budget < 999999 else "Unlimited"
    currency = state.get("currency", "USD")
    origin = state.get("origin", "Unknown")
    destination = state.get("destination", "Unknown")
    preferences = state.get("preferences", [])
    trip_type = state.get("routing_decision", "standard")

    replan_instructions = state.get("replan_instructions", "")
    replan_context = ""
    if replan_instructions:
        replan_context = f"Replan feedback from a reviewer:\n{replan_instructions}\n\nPlease fix ALL issues listed above."

    prompt = ITINERARY_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        origin=origin,
        trip_type=trip_type,
        budget=budget_display,
        currency=currency,
        preferences=", ".join(preferences) or "general",
        hotels=_trunc(json.dumps([{k: h[k] for k in ("name","price_per_night","stars","rating") if k in h} for h in hotels[:2]]), 300),
        transport=_trunc(json.dumps(state.get("transport", {}).get("recommended", {})), 200),
        activities=_trunc(json.dumps([{k: a[k] for k in ("name","cost","indoor","category","description") if k in a} for a in activities[:12]]), 1000),
        weather_summary=_trunc(json.dumps([{"date":d.get("date"),"condition":d.get("condition"),"temp":d.get("temp_max_c")} for d in weather.get("forecast",[])[:3]]), 300),
        replan_context=replan_context,
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
