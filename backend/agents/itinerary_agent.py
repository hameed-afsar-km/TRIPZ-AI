import json
import logging
from typing import Any, Dict, List
from services.llm_service import call_llm_json

logger = logging.getLogger("tripz.agents")


ITINERARY_SYSTEM = "You are a travel planner. Output ONLY valid JSON."

ITINERARY_PROMPT_TEMPLATE = """Plan a {num_days}-day trip to {destination} from {origin}.
Trip style: {trip_type}. Budget: {currency} {budget}. Preferences: {preferences}.

Hotels: {hotels}
Transport: {transport}
Available venues: {activities}
Weather: {weather_summary}

{replan_context}
RULES:
1. Stay within budget or close to it (unless unlimited)
2. Avoid outdoor activities on bad weather days
3. Day 1: arrival + evening activity. Last day: departure + morning activity.
4. Fill ALL {num_days} days (3 slots each: morning, afternoon, evening)
5. Each venue name from the list can be used AT MOST ONCE
6. If there aren't enough unique venues for all slots, you MAY supplement with a short generic category description (e.g. "Local cuisine lunch", "Evening walk"). But NEVER more than 50% generic.
7. For venue slots: format as "Venue Name — short description"
8. Mix themes across days (culture, food, adventure, sightseeing, relaxation)
9. Include a budget_tip per day with a money-saving suggestion for {destination}
10. Keep descriptions SHORT — max 8 words each

Return ONLY valid JSON:
{{"title":"{num_days}-Day Trip to {destination}","currency":"{currency}","summary":"","days":[
{{"day":1,"theme":"","morning":"","afternoon":"","evening":"","estimated_cost":0,"budget_tip":""}}
], "total_estimated_cost":0,"tips":[]}}"""


def _trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


_SLOT_THEMES = [
    "Arrival & City Orientation",
    "Cultural Immersion & Heritage",
    "Adventure & Outdoor Exploration",
    "Food, Markets & Local Life",
    "Iconic Landmarks & Sightseeing",
    "Relaxation & Wellness",
    "Shopping & Entertainment",
    "Day Trip & Beyond",
]


async def _recalculate_costs(
    itinerary: Dict[str, Any],
    hotels: List[Dict],
    activities: List[Dict],
    currency: str,
    num_days: int,
    budget: float = 0,
) -> Dict[str, Any]:
    days = itinerary.get("days", [])
    recalculated_days = []
    used_names: set = set()

    daily_budget = (budget / num_days) if budget > 0 and budget < 999999 else 0

    venue_names = [a.get("name", "").lower().strip() for a in activities if a.get("name")]

    def _replace_duplicate(text: str) -> str:
        if not text:
            return text
        t = text.lower().strip()
        for vn in sorted(venue_names, key=len, reverse=True):
            if vn in t:
                if vn in used_names:
                    for alt in venue_names:
                        if alt not in used_names and alt != vn:
                            used_names.add(alt)
                            return text.lower().replace(vn, alt)
                else:
                    used_names.add(vn)
                    return text
        return text

    total_cost = 0.0
    for d in days:
        day_num = d.get("day", 1)
        morning = _replace_duplicate(d.get("morning", ""))
        afternoon = _replace_duplicate(d.get("afternoon", ""))
        evening = _replace_duplicate(d.get("evening", ""))
        day_cost = round(daily_budget, 2) if daily_budget else 0
        total_cost += day_cost

        recalculated_days.append({
            "day": day_num,
            "theme": d.get("theme", ""),
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "estimated_cost": day_cost,
            "budget_tip": d.get("budget_tip", ""),
        })

    return {
        **itinerary,
        "currency": itinerary.get("currency", currency),
        "days": recalculated_days,
        "total_estimated_cost": round(total_cost, 2),
    }





async def itinerary_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    num_days = state.get("duration_days", 7)

    prev = state.get("previous_context", {})
    if prev and prev.get("days") and prev.get("destination") == state.get("destination"):
        return {**state, "itinerary": prev, "execution_trace": state.get("execution_trace", []) + ["itinerary_agent:from_context"]}

    hotels = state.get("hotels", [])
    activities = state.get("activities", [])
    weather = state.get("weather", {})

    budget = state.get("budget", 3000)
    currency = state.get("currency", "USD")
    budget_display = f"{budget:,.0f}" if budget < 999999 else "Unlimited"
    origin = state.get("origin", "Unknown")
    destination = state.get("destination", "Unknown")
    preferences = state.get("preferences", [])
    trip_type = state.get("routing_decision", "standard")

    replan_instructions = state.get("replan_instructions", "")
    replan_context = ""
    if replan_instructions:
        replan_context = f"Replan feedback from a reviewer:\n{replan_instructions}\n\nPlease fix ALL issues listed above."

    # Dedupe activities by name
    seen_act_names = set()
    unique_activities = []
    for a in activities:
        n = a.get("name", "").lower().strip()
        if n and n not in seen_act_names:
            seen_act_names.add(n)
            unique_activities.append(a)

    hotel_data = [{k: h.get(k) for k in ("name","stars","type") if k in h} for h in hotels[:2]]
    transport_data = state.get("transport", {})
    if "distance_km" in transport_data:
        transport_data = {"distance_km": transport_data["distance_km"], "note": "Real-time pricing not available from free APIs"}
    act_data = [a.get("name", "") for a in unique_activities[:15]]  # just names, no cost/desc

    prompt = ITINERARY_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        origin=origin,
        trip_type=trip_type,
        budget=budget_display,
        currency=currency,
        preferences=", ".join(preferences) or "general",
        hotels=_trunc(json.dumps(hotel_data), 300),
        transport=_trunc(json.dumps(transport_data), 200),
        activities=_trunc(json.dumps(act_data), 1500),
        weather_summary=_trunc(json.dumps([{"date":d.get("date"),"condition":d.get("condition"),"temp":d.get("temp_max_c")} for d in weather.get("forecast",[])[:3]]), 300),
        replan_context=replan_context,
    )

    itinerary = await call_llm_json(
        role="itinerary",
        prompt=prompt,
        system=ITINERARY_SYSTEM,
        provider=state.get("provider", "ollama"),
        api_key=state.get("api_key"),
        retries=1,
        timeout=90,
    )

    trace = state.get("execution_trace", [])
    if isinstance(itinerary, dict) and "error" not in itinerary:
        itinerary = await _recalculate_costs(itinerary, hotels, activities, currency, num_days, budget)
        result: Dict[str, Any] = {**state, "itinerary": itinerary, "execution_trace": trace + ["itinerary_agent"]}
    else:
        err = itinerary.get("error", "LLM synthesis failed")
        raw = itinerary.get("raw", "(none)")
        logger.error("Itinerary LLM error: %s | raw output (partial): %s", err, raw[:300])
        result = {
            **state,
            "itinerary": {"error": err, "error_type": "llm_failure"},
            "warnings": [f"LLM synthesis failed: {err}. No fallback — fix the underlying issue."],
            "execution_trace": trace + ["itinerary_agent:failed"],
        }
    return result
