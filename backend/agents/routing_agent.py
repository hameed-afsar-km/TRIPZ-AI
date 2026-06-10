from typing import Any, Dict
from services.llm_service import call_llm_json

ROUTING_SYSTEM = """You are a travel request classifier.
Analyze the extracted trip details and determine the optimal travel style.
Output ONLY valid JSON, no other text."""

ROUTING_PROMPT_TEMPLATE = """Trip request: "{request}"
Destination: {destination}
Origin: {origin}
Budget: {currency} {budget}
Duration: {duration_days} days
Travelers: {num_travelers}
Preferences: {preferences}

Classify into ONE travel style:
- "standard": balanced mix of activities, mid-range accommodations
- "budget": cost-conscious, affordable options, free activities
- "luxury": premium experiences, fine dining, high-end hotels

Return JSON:
{{"trip_type":"standard","focus_areas":["culture"],"vibe":"relaxed"}}

- trip_type: one of standard/budget/luxury
- focus_areas: 2-4 key focus areas from the preferences
- vibe: single word describing the trip energy (relaxed/adventurous/cultural/fast-paced)"""


async def routing_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    request = state.get("user_request", "")
    destination = state.get("destination", "Unknown")
    origin = state.get("origin", "Unknown")
    currency = state.get("currency", "USD")
    budget = state.get("budget", 3000)
    duration_days = state.get("duration_days", 7)
    num_travelers = state.get("num_travelers", 1)
    preferences = state.get("preferences", [])

    budget_display = f"{budget:,.0f}" if budget < 999999 else "Unlimited"

    prompt = ROUTING_PROMPT_TEMPLATE.format(
        request=request,
        destination=destination,
        origin=origin,
        currency=currency,
        budget=budget_display,
        duration_days=duration_days,
        num_travelers=num_travelers,
        preferences=", ".join(preferences) or "general",
    )

    result = await call_llm_json(
        role="routing",
        prompt=prompt,
        system=ROUTING_SYSTEM,
        provider=state.get("provider", "ollama"),
        api_key=state.get("api_key"),
        timeout=60,
    )

    if "error" in result:
        return {
            "routing_decision": "standard",
            "execution_trace": ["routing_agent:fallback"],
        }

    return {
        "routing_decision": result.get("trip_type", "standard"),
        "execution_trace": ["routing_agent"],
    }
