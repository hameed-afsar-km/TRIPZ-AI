import json
import logging
from typing import Any, Dict, List, Optional

from services.llm_service import call_llm_json, resolve_provider
from services.pricing_service import get_hotel_price

logger = logging.getLogger("tripz.agents")


ITINERARY_SYSTEM = "You are a travel planner. Output ONLY valid JSON. Every slot must list a specific real venue name, not a generic description."

ITINERARY_PROMPT_TEMPLATE = """Plan a {num_days}-day trip to {destination} from {origin}.
Trip style: {trip_type}. Budget: {currency} {budget}. Preferences: {preferences}.

Hotels: {hotels}
Transport: {transport}
Available venues: {activities}
Weather: {weather_summary}

{replan_context}
RULES:
1. Stay within budget
2. Avoid outdoor activities on bad weather days
3. Day 1: arrival + evening activity. Last day: departure + morning activity.
4. Fill ALL {num_days} days — 3 slots each (morning, afternoon, evening) = {slot_count} total slots
5. Each venue name from the list can be used AT MOST ONCE
6. If you run out of venue names, REUSE the most relevant one with "(repeat)" in the description. NEVER invent fake venues.
7. Format: "Venue Name — short description" (venue name MUST be FROM THE LIST above)
8. Mix themes across days: pick from: Arrival & City Orientation, Cultural Immersion & Heritage, Adventure & Outdoor Exploration, Food Markets & Local Life, Iconic Landmarks & Sightseeing, Relaxation & Wellness, Shopping & Entertainment, Day Trip & Beyond
9. Include a budget_tip per day with a specific money-saving suggestion
10. BANNED generic phrases (NEVER use these): "Local cuisine lunch", "Evening walk", "Last minute shopping", "Departure", "Check-in", "Check-out", "Food tour", "Campfire", "Dune bashing", "Sightseeing", "Shopping", "Explore the city", "Relax at hotel"

Return ONLY valid JSON:
{{"title":"{num_days}-Day Trip to {destination}","currency":"{currency}","summary":"","days":[
{{"day":1,"theme":"","morning":"","afternoon":"","evening":"","estimated_cost":0,"budget_tip":""}}
], "total_estimated_cost":0,"tips":[]}}"""


def _trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


_GENERIC_PATTERNS = [
    "local cuisine", "evening walk", "last minute shopping", "departure",
    "check-in", "check-out", "check in", "check out", "food tour",
    "campfire", "dune bashing", "sightseeing", "explore the city",
    "relax at hotel", "local market", "shopping", "food tasting",
    "evening stroll", "morning walk", "walk around", "exploration",
    "prayer", "pray", "tasting", "thrill", "entertainment",
    "dinner", "lunch", "breakfast",
]

_HOTEL_PRICE_CACHE: dict[str, float] = {}


def _is_generic(text: str) -> bool:
    if not text:
        return True
    t = text.lower().strip()
    for pat in _GENERIC_PATTERNS:
        if pat in t:
            return True
    return False


def _clean_generic_slots(days: list, venue_names: list) -> list:
    cleaned = []
    used = set()
    for d in days:
        slots = {}
        for slot in ("morning", "afternoon", "evening"):
            val = d.get(slot, "")
            if _is_generic(val):
                # Try to fill with an unused real venue
                replacement = None
                for vn in venue_names:
                    if vn not in used:
                        replacement = vn
                        used.add(vn)
                        break
                slots[slot] = f"{replacement} — visit" if replacement else ""
            else:
                # Extract venue name from "Venue Name — desc"
                vname = val.split("—")[0].strip().lower() if "—" in val else val.strip().lower()
                used.add(vname)
                slots[slot] = val
        cleaned.append({**d, **slots})
    return cleaned


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

    hotel_price = 0.0
    if hotels:
        p = hotels[0].get("price_per_night")
        if p is not None:
            hotel_price = float(p)

    venue_names = [a.get("name", "").lower().strip() for a in activities if a.get("name")]
    venue_cost_map: dict = {}
    for a in activities:
        n = a.get("name", "").lower().strip()
        c = a.get("cost")
        if n and c is not None:
            venue_cost_map[n] = float(c)

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

    def _slot_cost(text: str) -> float:
        if not text:
            return 0.0
        t = text.lower().strip()
        for vn, cost in venue_cost_map.items():
            if vn in t:
                return cost
        return 0.0

    days = _clean_generic_slots(days, venue_names)

    total_cost = 0.0
    for d in days:
        day_num = d.get("day", 1)
        morning = _replace_duplicate(d.get("morning", ""))
        afternoon = _replace_duplicate(d.get("afternoon", ""))
        evening = _replace_duplicate(d.get("evening", ""))

        slot_costs = [_slot_cost(morning), _slot_cost(afternoon), _slot_cost(evening)]
        day_cost_from_activities = max(slot_costs) if any(slot_costs) else 0

        day_cost = day_cost_from_activities
        if day_num != num_days and hotel_price:
            day_cost += hotel_price

        if not day_cost and daily_budget:
            day_cost = round(daily_budget, 2)

        total_cost += day_cost

        recalculated_days.append({
            "day": day_num,
            "theme": d.get("theme", ""),
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "estimated_cost": round(day_cost, 2),
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

    # Attempt to enrich hotels with live pricing
    travel_dates = state.get("travel_dates", {})
    chk_in = travel_dates.get("start", "2026-07-01")
    chk_out = travel_dates.get("end", "2026-07-02")
    for h in hotels:
        name = h.get("name", "")
        if name and name not in _HOTEL_PRICE_CACHE:
            price = await get_hotel_price(name, destination, currency, chk_in, chk_out)
            if price is not None:
                _HOTEL_PRICE_CACHE[name] = price
                h["price_per_night"] = price

    transport_data = state.get("transport", {})
    if "distance_km" in transport_data:
        transport_data = {"distance_km": transport_data["distance_km"], "note": "Real-time pricing not available from free APIs"}
    act_data = [a.get("name", "") for a in unique_activities[:25]]  # just names

    prompt = ITINERARY_PROMPT_TEMPLATE.format(
        num_days=num_days,
        slot_count=num_days * 3,
        destination=destination,
        origin=origin,
        trip_type=trip_type,
        budget=budget_display,
        currency=currency,
        preferences=", ".join(preferences) or "general",
        hotels=_trunc(json.dumps(hotel_data), 300),
        transport=_trunc(json.dumps(transport_data), 200),
        activities=_trunc(json.dumps(act_data), 2000),
        weather_summary=_trunc(json.dumps([{"date":d.get("date"),"condition":d.get("condition"),"temp":d.get("temp_max_c")} for d in weather.get("forecast",[])[:3]]), 300),
        replan_context=replan_context,
    )

    itinerary = await call_llm_json(
        role="itinerary",
        prompt=prompt,
        system=ITINERARY_SYSTEM,
        provider=resolve_provider(state, "itinerary"),
        api_key=state.get("api_key"),
        retries=0,
        timeout=45,
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
