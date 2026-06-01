import json
from typing import Any, Dict
from services.llm_service import call_llm_json

REPLAN_SYSTEM = "You are a travel plan editor. Fix ONLY identified issues. Return full corrected itinerary JSON."

REPLAN_PROMPT_TEMPLATE = """Fix these issues in the itinerary:
ISSUES: {issues}
INSTRUCTIONS: {replan_instructions}
CONSTRAINTS: Budget {budget_constraint}. Keep destination & dates. Prefer indoor on: {bad_weather_dates}. Duration: {num_days} days. Currency: {currency}

CURRENT ITINERARY (modify this):
{current_itinerary}

Return the corrected itinerary using the SAME JSON structure. Ensure ALL {num_days} days are filled."""


def _get_bad_weather_dates(state: dict) -> str:
    forecast = state.get("weather", {}).get("forecast", [])
    bad = [d["date"] for d in forecast if d.get("is_bad_weather", False)]
    return ", ".join(bad) if bad else "none"


async def replanning_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    issues = state.get("critic_issues", [])
    replan_instructions = state.get("replan_instructions", "Fix all issues")
    current_itinerary = state.get("itinerary", {})
    budget = float(state.get("budget", 3000))
    currency = state.get("currency", "USD")
    dates = state.get("travel_dates", {})
    trace = state.get("execution_trace", [])
    
    # Calculate number of days
    try:
        from datetime import date
        start = date.fromisoformat(dates.get("start", "2025-06-01"))
        end = date.fromisoformat(dates.get("end", "2025-06-07"))
        num_days = max((end - start).days + 1, 1)
    except Exception:
        num_days = 7

    if not issues and not replan_instructions:
        return {
            **state,
            "replan_count": state.get("replan_count", 0) + 1,
            "execution_trace": trace + ["replanning_agent:skipped"],
        }

    itinerary_json = json.dumps(current_itinerary, indent=None)
    if len(itinerary_json) > 3000:
        compact = {
            "days": current_itinerary.get("days", []),
            "hotel": current_itinerary.get("hotel", {}),
            "transport": current_itinerary.get("transport", {}),
            "total_estimated_cost": current_itinerary.get("total_estimated_cost", 0),
        }
        itinerary_json = json.dumps(compact, indent=None)

    # Format budget constraint
    if budget >= 999999:
        budget_constraint = "is unlimited"
    else:
        budget_constraint = f"< {currency} {budget:,.0f}"

    prompt = REPLAN_PROMPT_TEMPLATE.format(
        issues="\n".join(f"- {issue}" for issue in issues),
        replan_instructions=replan_instructions,
        budget_constraint=budget_constraint,
        currency=currency,
        num_days=num_days,
        bad_weather_dates=_get_bad_weather_dates(state),
        current_itinerary=itinerary_json,
    )

    patched = await call_llm_json(
        role="replanning",
        prompt=prompt,
        system=REPLAN_SYSTEM,
        provider=state.get("provider", "ollama"),
        api_key=state.get("api_key"),
    )

    if "error" in patched or not patched.get("days"):
        return {
            **state,
            "warnings": state.get("warnings", []) + ["Replanning failed — keeping original"],
            "replan_count": state.get("replan_count", 0) + 1,
            "needs_replanning": False,
            "execution_trace": trace + ["replanning_agent:failed"],
        }

    return {
        **state,
        "itinerary": patched,
        "replan_count": state.get("replan_count", 0) + 1,
        "needs_replanning": False,
        "critic_feedback": "",
        "critic_issues": [],
        "execution_trace": trace + ["replanning_agent:patched"],
    }
