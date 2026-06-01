import json
from typing import Any, Dict, List
from services.llm_service import call_llm_json

CRITIC_SYSTEM = "You are a strict travel plan auditor. Return ONLY valid JSON. Be concise."

CRITIC_PROMPT_TEMPLATE = """Audit this {num_days}-day travel itinerary for {destination}:
BUDGET: {currency} {budget}
TRAVEL DAYS: {num_days}
PREFERENCES: {preferences}
ITINERARY:
{itinerary_summary}
WARNINGS: {warnings}

Check:
1. All {num_days} days are filled with activities (not just {min_days} days)
2. Budget overflow (if not unlimited)
3. Outdoor activities on bad weather days  
4. Missing meals
5. "visit all places" preference: diverse activities across different categories
6. Matches user origin ({origin}) and preferences

Return JSON:
{{
  "approved": true/false,
  "confidence": 0.0-1.0,
  "issues": ["issue 1"],
  "critical_issue_count": 0,
  "suggestions": ["fix 1"],
  "replan_instructions": "what to change (empty if approved)"
}}"""


def _summarize_itinerary(itinerary: dict) -> str:
    if not itinerary or "error" in itinerary:
        return "No valid itinerary"
    days = itinerary.get("days", [])
    lines = [
        f"Title: {itinerary.get('title', 'N/A')}",
        f"Total cost: ${itinerary.get('total_estimated_cost', 0)}",
        f"Hotel: {itinerary.get('hotel', {}).get('name', 'N/A')} @ ${itinerary.get('hotel', {}).get('total_hotel_cost', 0)}",
        f"Transport: {itinerary.get('transport', {}).get('mode', 'N/A')} @ ${itinerary.get('transport', {}).get('total_cost', 0)}",
    ]
    for day in days[:5]:
        acts = ", ".join(day.get("activities", []))
        lines.append(f"Day {day['day']}: {day.get('theme', '')} — {acts}")
    return "\n".join(lines)


def _rule_based_checks(state: dict) -> List[str]:
    issues = []
    budget = float(state.get("budget", 3000))
    is_unlimited = budget >= 999999
    itinerary = state.get("itinerary", {})
    dates = state.get("travel_dates", {})
    preferences = state.get("preferences", [])
    
    # Calculate expected number of days
    try:
        from datetime import date
        start = date.fromisoformat(dates.get("start", "2025-06-01"))
        end = date.fromisoformat(dates.get("end", "2025-06-07"))
        expected_days = max((end - start).days + 1, 1)
    except Exception:
        expected_days = 7
    
    # Check if all days are filled
    days = itinerary.get("days", [])
    if len(days) < expected_days:
        issues.append(f"CRITICAL: Only {len(days)} days planned, but {expected_days} days requested")
    
    total_cost = float(itinerary.get("total_estimated_cost", 0))
    
    # Only check budget if not unlimited
    if not is_unlimited and total_cost > budget * 1.1:
        issues.append(f"CRITICAL: Plan exceeds budget by {state.get('currency', 'USD')} {total_cost - budget:.0f}")
    
    transport = state.get("transport", {})
    tc = transport.get("recommended", {}).get("total_cost", 0)
    if not is_unlimited and tc > budget * 0.45:
        issues.append(f"CRITICAL: Transport ({tc}) uses {tc/budget*100:.0f}% of budget")
    
    # Check "visit all places" preference
    if any("all" in str(p).lower() for p in preferences):
        # Count activity categories in the itinerary
        categories = set()
        for day in days:
            # Try to extract categories from activity names
            acts = day.get("activities", []) or []
            # Simple heuristic: check for variety keywords
            for activity_text in acts:
                if isinstance(activity_text, str):
                    activity_lower = activity_text.lower()
                    for cat in ["culture", "history", "adventure", "food", "shopping", "nature", "art", "relaxation"]:
                        if cat in activity_lower:
                            categories.add(cat)
        
        if len(categories) < 3:
            issues.append(f"WARNING: 'visit all places' preference detected but only {len(categories)} activity categories covered")
    
    return issues


async def critic_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    itinerary = state.get("itinerary", {})
    budget = float(state.get("budget", 3000))
    weather = state.get("weather", {})
    replan_count = int(state.get("replan_count", 0))
    trace = state.get("execution_trace", [])
    currency = state.get("currency", "USD")
    destination = state.get("destination", "Unknown")
    origin = state.get("origin", "Unknown")
    preferences = state.get("preferences", [])
    dates = state.get("travel_dates", {})

    # Calculate number of days
    try:
        from datetime import date
        start = date.fromisoformat(dates.get("start", "2025-06-01"))
        end = date.fromisoformat(dates.get("end", "2025-06-07"))
        num_days = max((end - start).days + 1, 1)
    except Exception:
        num_days = 7

    # Hard limit: max 2 replan cycles
    if replan_count >= 2:
        return {
            **state,
            "needs_replanning": False,
            "critic_feedback": "Max replan cycles — accepting current plan",
            "critic_issues": [],
            "execution_trace": trace + ["critic_agent:max_replans"],
        }

    # Step 1: Fast rule-based checks
    rule_issues = _rule_based_checks(state)

    # If rule-based found critical issues, skip AI and trigger replan immediately
    if rule_issues:
        return {
            **state,
            "needs_replanning": True,
            "critic_feedback": "Rule-based checks failed — needs revision",
            "critic_issues": rule_issues,
            "replan_instructions": "Fix budget and/or transport costs to stay within limits, ensure all days are filled with activities",
            "execution_trace": trace + ["critic_agent:rule_failed"],
        }

    days = itinerary.get("days", [])
    bad_weather_days = sum(
        1 for d in weather.get("forecast", [])[:num_days] if d.get("is_bad_weather", False)
    )

    # Step 2: AI validation (only if rule checks passed)
    prompt = CRITIC_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        currency=currency,
        budget="Unlimited" if budget >= 999999 else f"{budget:,.0f}",
        origin=origin,
        preferences=", ".join(preferences) or "general travel",
        bad_weather_days=bad_weather_days,
        min_days=max(num_days - 2, 1),  # Allow 1-2 days margin
        itinerary_summary=_summarize_itinerary(itinerary),
        warnings="\n".join(state.get("warnings", [])) or "None",
    )

    ai_result = await call_llm_json(
        role="critic",
        prompt=prompt,
        system=CRITIC_SYSTEM,
        provider=state.get("provider", "ollama"),
        api_key=state.get("api_key"),
    )

    all_issues = ai_result.get("issues", [])
    critical_count = ai_result.get("critical_issue_count", 0)
    needs_replanning = not ai_result.get("approved", True) or critical_count > 0

    return {
        **state,
        "needs_replanning": needs_replanning,
        "critic_feedback": f"Confidence: {ai_result.get('confidence', 0.5)}. {'APPROVED' if not needs_replanning else 'NEEDS REVISION'}",
        "critic_issues": all_issues,
        "replan_instructions": ai_result.get("replan_instructions", ""),
        "confidence_score": float(ai_result.get("confidence", 0.5)),
        "execution_trace": trace + [f"critic_agent:{'approved' if not needs_replanning else 'replanning'}"],
    }
