"""
Activity Tool — zero AI calls.
Returns a curated list of activities for the destination,
filtered by user preferences and budget. No LLM needed.
"""

from typing import Any, Dict, List


ACTIVITY_DB: Dict[str, List[Dict[str, Any]]] = {
    "riyadh": [
        {"name": "Kingdom Centre Tower Visit", "category": "culture", "cost": 15, "duration_hours": 2, "indoor": True},
        {"name": "Al Masmak Fort Tour", "category": "history", "cost": 10, "duration_hours": 2, "indoor": False},
        {"name": "Riyadh National Museum", "category": "culture", "cost": 20, "duration_hours": 3, "indoor": True},
        {"name": "Al Bujairi Heritage Site", "category": "history", "cost": 5, "duration_hours": 2, "indoor": False},
        {"name": "Souq Al Zal Traditional Market", "category": "shopping", "cost": 0, "duration_hours": 3, "indoor": False},
        {"name": "Edge of the World (Tuwaiq Escarpment)", "category": "adventure", "cost": 50, "duration_hours": 6, "indoor": False},
        {"name": "Diriyah UNESCO Site", "category": "history", "cost": 25, "duration_hours": 4, "indoor": False},
        {"name": "Riyadh Contemporary Art Museum", "category": "art", "cost": 15, "duration_hours": 2, "indoor": True},
        {"name": "King Fahd Park Visit", "category": "nature", "cost": 0, "duration_hours": 2, "indoor": False},
        {"name": "Desert Safari & Dune Bashing", "category": "adventure", "cost": 80, "duration_hours": 5, "indoor": False},
        {"name": "Chop Chop Square Historical Tour", "category": "history", "cost": 0, "duration_hours": 1, "indoor": False},
        {"name": "Al Faisaliyah Center Food Court", "category": "food", "cost": 25, "duration_hours": 2, "indoor": True},
        {"name": "Camel Racing Track Experience", "category": "adventure", "cost": 40, "duration_hours": 3, "indoor": False},
        {"name": "Traditional Saudi Dinner Experience", "category": "food", "cost": 60, "duration_hours": 3, "indoor": True},
        {"name": "Shopping at Riyadh Gallery Mall", "category": "shopping", "cost": 0, "duration_hours": 4, "indoor": True},
        {"name": "Spa & Arabic Hammam", "category": "relaxation", "cost": 75, "duration_hours": 3, "indoor": True},
        {"name": "Stargazing Desert Night", "category": "adventure", "cost": 35, "duration_hours": 4, "indoor": False},
        {"name": "Falconry Museum & Experience", "category": "culture", "cost": 30, "duration_hours": 2, "indoor": True},
    ],
    "_default": [
        {"name": "City Walking Tour",       "category": "culture",    "cost": 15,  "duration_hours": 3,  "indoor": False},
        {"name": "Local Food Market Visit", "category": "food",       "cost": 20,  "duration_hours": 2,  "indoor": False},
        {"name": "Museum of History",       "category": "culture",    "cost": 12,  "duration_hours": 2,  "indoor": True},
        {"name": "Rooftop Bar Night",       "category": "nightlife",  "cost": 35,  "duration_hours": 3,  "indoor": True},
        {"name": "Day Hike to Viewpoint",   "category": "adventure",  "cost": 10,  "duration_hours": 5,  "indoor": False},
        {"name": "Cooking Class",           "category": "food",       "cost": 55,  "duration_hours": 3,  "indoor": True},
        {"name": "Sunrise Hot Air Balloon", "category": "adventure",  "cost": 120, "duration_hours": 4,  "indoor": False},
        {"name": "Local Art Gallery",       "category": "culture",    "cost": 8,   "duration_hours": 2,  "indoor": True},
        {"name": "Scuba Diving Lesson",     "category": "adventure",  "cost": 90,  "duration_hours": 4,  "indoor": False},
        {"name": "Spa & Wellness Day",      "category": "relaxation", "cost": 80,  "duration_hours": 5,  "indoor": True},
        {"name": "Night Photography Walk",  "category": "culture",    "cost": 0,   "duration_hours": 2,  "indoor": False},
        {"name": "Bike City Tour",          "category": "adventure",  "cost": 25,  "duration_hours": 3,  "indoor": False},
    ]
}


async def activity_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: selects and filters activities by:
    - user preferences (if provided)
    - bad weather days (prefer indoor alternatives)
    - per-activity budget headroom
    - "visit all places" preference: include ALL activities regardless of cost
    No LLM call — pure rule-based filtering and ranking.
    """
    destination = state.get("destination", "")
    preferences = state.get("preferences", [])
    budget = float(state.get("budget", 500))
    weather = state.get("weather", {})
    has_bad_weather = weather.get("any_bad_weather", False)
    
    # Check if user wants to visit all places
    visit_all_places = any("all" in str(p).lower() for p in preferences)

    # Fetch destination-specific or default activity list
    pool = ACTIVITY_DB.get(destination.lower(), ACTIVITY_DB["_default"])

    # Per-activity budget cap (max 25% of total budget on a single activity)
    # But if budget is unlimited (999999) or user wants all places, be more lenient
    if budget >= 999999 or visit_all_places:
        max_activity_cost = float('inf')  # No limit for unlimited budgets
    else:
        max_activity_cost = budget * 0.25

    filtered = []
    for act in pool:
        # Budget filter (skip if activity costs too much and not unlimited)
        if max_activity_cost != float('inf') and act["cost"] > max_activity_cost:
            continue

        # If any bad weather expected, deprioritize outdoor activities
        if has_bad_weather and not act["indoor"]:
            act["weather_warning"] = True
        else:
            act["weather_warning"] = False

        # Preference boost: flag as recommended if it matches a preference
        act["recommended"] = any(pref.lower() in act["category"] for pref in preferences)
        
        # If user wants to visit all places, mark all activities as recommended
        if visit_all_places:
            act["recommended"] = True

        filtered.append(act)

    # Sort: recommended first, then by cost ascending (for unlimited budgets, include all)
    filtered.sort(key=lambda a: (not a["recommended"], a["cost"]))

    trace = state.get("execution_trace", [])
    return {
        **state,
        "activities": filtered,
        "execution_trace": trace + ["activity_tool"],
    }
