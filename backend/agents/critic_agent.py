import json
from typing import Any, Dict, List
from services.llm_service import call_llm_json

CRITIC_SYSTEM = """You are a strict travel itinerary reviewer.
Check for: vague descriptions, repeated text, wrong day count, wrong currency, budget issues, lack of variety.
Output ONLY valid JSON."""

CRITIC_PROMPT_TEMPLATE = """Review this {num_days}-day itinerary for {destination}:

Itinerary: {itinerary_json}

Trip details:
- Budget: {currency} {budget}
- Requested days: {num_days}
- Preferences: {preferences}

Check for these issues:
1. Vague descriptions — any "Relax at the hotel", "Explore the city", "Visit local attractions", "Enjoy dinner" with no specific name = FAIL
2. Repeated text — same morning/afternoon/evening appearing on multiple days = FAIL
3. Wrong day count — if days don't match {num_days} = FAIL
4. Wrong currency — if prices use a different currency than {currency} = FAIL
5. Budget mismatch — if total cost far exceeds budget = FAIL
6. Missing variety — if same theme repeats every day = FAIL

Return JSON:
{{"pass":true,"issues":[],"feedback":"","needs_replanning":false}}

- pass: true only if ALL checks pass with zero issues
- issues: list of specific problems found (empty if pass)
- feedback: detailed instructions for what to fix (empty if pass)
- needs_replanning: true if issues are severe enough to regenerate"""


async def critic_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    itinerary = state.get("itinerary", {})
    if not itinerary or "error" in itinerary:
        return {
            "replan_instructions": "",
            "needs_replanning": False,
            "execution_trace": ["critic_agent:skip"],
        }

    destination = state.get("destination", "Unknown")
    num_days = state.get("duration_days", 7)
    currency = state.get("currency", "USD")
    budget = state.get("budget", 3000)
    preferences = state.get("preferences", [])

    replan_count = state.get("replan_count", 0)
    if replan_count >= 2:
        return {
            "replan_instructions": "",
            "needs_replanning": False,
            "execution_trace": ["critic_agent:max_replan"],
        }

    prompt = CRITIC_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        itinerary_json=json.dumps(itinerary, indent=2),
        currency=currency,
        budget=f"{budget:,.0f}" if budget < 999999 else "Unlimited",
        preferences=", ".join(preferences) or "general",
    )

    result = await call_llm_json(
        role="critic",
        prompt=prompt,
        system=CRITIC_SYSTEM,
        provider=state.get("provider", "ollama"),
        api_key=state.get("api_key"),
        timeout=60,
    )

    if "error" in result:
        return {
            "replan_instructions": "",
            "needs_replanning": False,
            "execution_trace": ["critic_agent:error"],
        }

    needs_replan = result.get("needs_replanning", False)
    feedback = result.get("feedback", "")

    return {
        "replan_instructions": feedback,
        "needs_replanning": needs_replan,
        "replan_count": replan_count + 1,
        "execution_trace": ["critic_agent"],
    }
