import json
from typing import Any, Dict, List
from services.llm_service import call_llm_json
from services.exchange_service import convert_price


ITINERARY_SYSTEM = "You are a travel planner. Output ONLY valid JSON."

ITINERARY_PROMPT_TEMPLATE = """Plan a {num_days}-day trip to {destination} from {origin}.
Trip style: {trip_type}. Budget: {currency} {budget}. Preferences: {preferences}.

All prices below are ALREADY in {currency} — use them EXACTLY as shown.

Hotels: {hotels}
Transport: {transport}
Activities: {activities}
Weather: {weather_summary}

{replan_context}
STRICT RULES:
1. Stay within budget or close to it (unless budget is unlimited)
2. Avoid outdoor activities on bad weather days
3. Day 1: arrival and evening exploration with a light activity
4. Last day: departure with morning activity
5. Fill all {num_days} days — each day MUST have EXACT activity venue names from the list
6. Each activity venue can be used AT MOST ONCE across the entire trip. Never repeat the same venue on different days.
7. NEVER use generic phrases like "Relax at the hotel", "Explore the city", "Visit local attractions", "Enjoy a nice dinner", "Sightseeing", "Shopping". Use ONLY the EXACT venue names from the list.
8. Include variety: don't repeat the same theme on consecutive days; mix culture, food, adventure, relaxation, sightseeing
9. For morning/afternoon/evening use format: "Activity Name — description" where Activity Name is the EXACT venue name from the list
10. Use the EXACT prices from Hotels and Activities above. Do NOT guess or modify prices.
11. Include a budget_tip for each day with a specific money-saving suggestion for {destination}
12. Show the amount in {currency} for each day's estimated_cost

Return JSON:
{{"title":"{num_days}-Day {trip_type} Trip to {destination}","currency":"{currency}","summary":"","days":[
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
) -> Dict[str, Any]:
    days = itinerary.get("days", [])
    recalculated_days = []
    total_cost = 0.0

    hotel_cost_per_night = 0.0
    if hotels:
        hotel_cost_per_night = await convert_price(hotels[0].get("price_per_night", 0), currency)

    activity_name_to_cost: Dict[str, float] = {}
    activity_name_to_obj: Dict[str, Dict] = {}
    for a in activities:
        name = a.get("name", "").lower().strip()
        if name:
            cost_usd = a.get("cost", 0) or 0
            activity_name_to_cost[name] = await convert_price(float(cost_usd), currency)
            activity_name_to_obj[name] = a

    used_names: set = set()
    unused_names: list = [n for n in activity_name_to_cost if n]

    def _find_activity(text: str) -> str:
        if not text:
            return text
        text_lower = text.lower().strip()
        for act_name in sorted(activity_name_to_cost.keys(), key=len, reverse=True):
            if act_name in text_lower or text_lower in act_name:
                if act_name in used_names:
                    # Find a replacement from unused
                    for alt in unused_names:
                        if alt not in used_names and alt != act_name:
                            used_names.add(alt)
                            return text_lower.replace(act_name, alt)
                else:
                    used_names.add(act_name)
                    return text
        return text

    def _match_cost(text: str) -> float:
        if not text:
            return 0.0
        text_lower = text.lower().strip()
        for act_name, cost in activity_name_to_cost.items():
            if act_name in text_lower or text_lower in act_name:
                return cost
        return 0.0

    for d in days:
        day_num = d.get("day", 1)
        morning = _find_activity(d.get("morning", ""))
        afternoon = _find_activity(d.get("afternoon", ""))
        evening = _find_activity(d.get("evening", ""))

        morning_cost = _match_cost(morning)
        afternoon_cost = _match_cost(afternoon)
        evening_cost = _match_cost(evening)

        day_activities_cost = max(morning_cost, afternoon_cost, evening_cost)

        day_cost = day_activities_cost
        if day_num != num_days:
            day_cost += hotel_cost_per_night

        recalculated_days.append({
            "day": day_num,
            "theme": d.get("theme", ""),
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "estimated_cost": round(day_cost, 2),
            "budget_tip": d.get("budget_tip", ""),
        })
        total_cost += day_cost

    return {
        **itinerary,
        "currency": itinerary.get("currency", currency),
        "days": recalculated_days,
        "total_estimated_cost": round(total_cost, 2),
    }


async def _convert_hotel_prices(hotels: List[Dict], currency: str) -> List[Dict]:
    converted = []
    for h in hotels:
        h = {**h}
        if "price_per_night" in h:
            h["price_per_night"] = await convert_price(h["price_per_night"], currency)
        converted.append(h)
    return converted


async def _convert_activity_prices(activities: List[Dict], currency: str) -> List[Dict]:
    converted = []
    for a in activities:
        a = {**a}
        if "cost" in a:
            a["cost"] = await convert_price(a["cost"], currency)
        converted.append(a)
    return converted


async def _generate_fallback_itinerary(
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
    hotel_price = await convert_price(hotels[0].get("price_per_night", 0), currency) if hotels else 0

    act_list = []
    for a in activities:
        converted_a = {**a}
        if "cost" in converted_a:
            converted_a["cost"] = await convert_price(converted_a["cost"], currency)
        act_list.append(converted_a)

    acts_per_day = max(len(act_list) // max(num_days, 1), 1)
    daily_budget = budget / num_days if budget < 999999 else 0

    for d in range(1, num_days + 1):
        day_acts = act_list[(d - 1) * acts_per_day : d * acts_per_day] if act_list else []
        theme_idx = (d - 1) % len(_SLOT_THEMES)

        act_cost = sum(a.get("cost", 0) or 0 for a in day_acts)
        night_cost = hotel_price if d != num_days else 0
        day_cost = act_cost + night_cost
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

        if daily_budget > 0:
            budget_tip = f"Daily budget: ~{currency} {daily_budget:,.0f}. Meals ~{currency} {daily_budget*0.3:,.0f}, entry fees ~{currency} {daily_budget*0.2:,.0f}."
        else:
            budget_tip = f"Budget accordingly for meals, transport, and entry fees."

        days.append({
            "day": d,
            "theme": _SLOT_THEMES[theme_idx],
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "estimated_cost": round(day_cost, 2),
            "budget_tip": budget_tip,
        })

    tips = [
        f"Daily meals budget: allocate ~{currency} {daily_budget*0.3:,.0f} per day (~10% of daily budget) for breakfast, lunch, and dinner at {destination}." if daily_budget > 0 else f"Pack snacks and water for long exploration days.",
        f"Top attraction tickets often save money when booked online in advance — check official {destination} tourism websites.",
        f"Public transport or ride-sharing is usually cheaper than taxis for getting around {destination}.",
        f"Preferences included: {', '.join(preferences)}" if preferences else f"Staying at {hotel_name} — check if they offer complimentary breakfast to save on meals.",
    ]

    return {
        "title": f"{num_days}-Day Trip to {destination}",
        "currency": currency,
        "summary": f"A {num_days}-day trip to {destination} from {origin}. "
                   f"Total estimated cost: ~{currency} {total_cost:,.2f}. "
                   f"Accommodation at {hotel_name}.",
        "days": days,
        "total_estimated_cost": round(total_cost, 2),
        "tips": tips,
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

    converted_hotels = await _convert_hotel_prices(hotels, currency)
    converted_activities = await _convert_activity_prices(activities, currency)

    # Give LLM up to 20 unique activities — sorted by preference match, deduped
    seen_act_names = set()
    unique_activities = []
    for a in converted_activities:
        n = a.get("name", "").lower().strip()
        if n and n not in seen_act_names:
            seen_act_names.add(n)
            unique_activities.append(a)

    prompt = ITINERARY_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        origin=origin,
        trip_type=trip_type,
        budget=budget_display,
        currency=currency,
        preferences=", ".join(preferences) or "general",
        hotels=_trunc(json.dumps([{k: h[k] for k in ("name","price_per_night","stars","rating") if k in h} for h in converted_hotels[:2]]), 300),
        transport=_trunc(json.dumps(state.get("transport", {}).get("recommended", {})), 200),
        activities=_trunc(json.dumps([{k: a[k] for k in ("name","cost","indoor","category","description") if k in a} for a in unique_activities[:20]]), 1500),
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

    trace = state.get("execution_trace", [])
    if isinstance(itinerary, dict) and "error" not in itinerary:
        itinerary = await _recalculate_costs(itinerary, hotels, activities, currency, num_days)
        result: Dict[str, Any] = {**state, "itinerary": itinerary, "execution_trace": trace + ["itinerary_agent"]}
    else:
        fallback = await _generate_fallback_itinerary(
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
            **state,
            "itinerary": fallback,
            "warnings": [f"LLM synthesis failed ({itinerary.get('error', 'unknown')}). Using template-based itinerary."],
            "execution_trace": trace + ["itinerary_agent:fallback"],
        }
    return result
