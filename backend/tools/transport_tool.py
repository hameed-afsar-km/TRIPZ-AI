"""
Transport Tool — zero AI calls.
Calculates transport options and estimated costs between origin and destination.
In production: swap with Amadeus Flight API, Rome2rio, or Skyscanner API.
"""

from typing import Any, Dict


def _estimate_flight_cost(origin: str, destination: str, travelers: int) -> Dict[str, Any]:
    """Rough cost simulation. Replace with real API."""
    # Intercontinental heuristic: $400-900/person, Regional: $80-300/person
    base = 450 if origin and destination else 300
    return {
        "type": "flight",
        "provider": "Simulated (replace with Amadeus API)",
        "cost_per_person": base,
        "total_cost": base * travelers,
        "duration_hours": 8,
        "direct": True,
    }


def _estimate_train_cost(origin: str, destination: str, travelers: int) -> Dict[str, Any]:
    base = 95
    return {
        "type": "train",
        "provider": "Simulated (replace with Rome2Rio API)",
        "cost_per_person": base,
        "total_cost": base * travelers,
        "duration_hours": 4,
        "direct": False,
    }


async def transport_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: builds transport options for origin → destination.
    Returns ranked options by cost and duration.
    No LLM call — pure calculation.
    """
    origin = state.get("origin", "Unknown")
    destination = state.get("destination", "Unknown")
    travelers = int(state.get("num_travelers", 1))
    budget = float(state.get("budget", 1000))

    options = [
        _estimate_flight_cost(origin, destination, travelers),
        _estimate_train_cost(origin, destination, travelers),
    ]

    # Filter: only show options within 40% of total budget
    budget_cap = budget * 0.40
    affordable = [o for o in options if o["total_cost"] <= budget_cap]
    if not affordable:
        affordable = [min(options, key=lambda x: x["total_cost"])]

    # Sort by cost ascending
    affordable.sort(key=lambda x: x["total_cost"])

    # Also add local transit estimate for within-city movement
    local_transit = {
        "type": "local_transit",
        "modes": ["metro", "bus", "taxi"],
        "estimated_daily_cost_per_person": 12,
        "notes": "Metro + occasional taxi recommended for speed",
    }

    transport_result = {
        "intercity_options": affordable,
        "recommended": affordable[0] if affordable else None,
        "local_transit": local_transit,
        "total_transport_budget_used": affordable[0]["total_cost"] if affordable else 0,
    }

    trace = state.get("execution_trace", [])
    return {
        **state,
        "transport": transport_result,
        "execution_trace": trace + ["transport_tool"],
    }
