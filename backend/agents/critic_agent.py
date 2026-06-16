import json
import re
from typing import Any, Dict, List

from services.llm_service import call_llm_json, resolve_provider
from services.wikipedia_service import validate_venues


CRITIC_SYSTEM = """You are a strict travel itinerary reviewer.
Check for: vague descriptions, repeated text, wrong day count, wrong currency, budget issues, lack of variety.
Output ONLY valid JSON."""


CRITIC_PROMPT_TEMPLATE = """Review this {num_days}-day itinerary for {destination}:

Itinerary: {itinerary_json}

Trip details:
- Budget: {currency} {budget}
- Requested days: {num_days}
- Preferences: {preferences}

Venue validation results (from Wikipedia):
{venue_issues}

Check for these issues:
1. Vague descriptions — any "Relax at the hotel", "Explore the city", "Visit local attractions", "Enjoy dinner" with no specific name = FAIL
2. Repeated text — same morning/afternoon/evening appearing on multiple days = FAIL
3. Wrong day count — if days don't match {num_days} = FAIL
4. Wrong currency — if prices use a different currency than {currency} = FAIL
5. Budget mismatch — if total cost far exceeds budget = FAIL
6. Missing variety — if same theme repeats every day = FAIL
7. Fake venues — if the venue validation found non-existent places, flag them = FAIL

Return JSON:
{{"pass":true,"issues":[],"feedback":"","needs_replanning":false}}

- pass: true only if ALL checks pass with zero issues
- issues: list of specific problems found (empty if pass)
- feedback: detailed instructions for what to fix (empty if pass)
- needs_replanning: true if issues are severe enough to regenerate"""


_VENUE_PATTERN = re.compile(r'\[([^\]]+)\]\(https?://(?:www\.)?google\.com/maps\?q=([^)]+)\)')


def _extract_venue_names(markdown: str) -> List[str]:
    """Extract venue names from Google Maps links in the itinerary markdown."""
    names = []
    for match in _VENUE_PATTERN.finditer(markdown):
        name = match.group(1).strip()
        if name and len(name) > 2:
            names.append(name)
    return list(dict.fromkeys(names))  # deduplicate preserving order


def _format_venue_issues(validation_results: List[Dict[str, Any]], destination: str = "") -> str:
    """Format venue validation results for the critic prompt."""
    if not validation_results:
        return "No venues found to validate."

    lines = []
    for v in validation_results:
        original = v.get("original_name", "?")
        exists = v.get("exists", False)
        correct = v.get("correct_name")
        hint = v.get("city_hint")

        if not exists:
            lines.append(f"- NOT FOUND: \"{original}\" — this venue does not appear to exist on Wikipedia")
        elif correct and correct.lower() != original.lower():
            lines.append(f"- MISNAMED: \"{original}\" → Wikipedia page is \"{correct}\" (check if this is the right place)")
        elif hint and destination and destination.lower() not in hint.lower():
            lines.append(f"- WRONG CITY: \"{original}\" — likely not in {destination}")
        else:
            lines.append(f"- OK: \"{original}\"")

    if not lines:
        return "No venues found to validate."
    return "\n".join(lines)


async def critic_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    itinerary = state.get("itinerary", {})
    if not itinerary or "error" in itinerary:
        return {
            **state,
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
            **state,
            "replan_instructions": "",
            "needs_replanning": False,
            "execution_trace": ["critic_agent:max_replan"],
        }

    markdown = itinerary.get("markdown", "")
    venue_names = _extract_venue_names(markdown)

    venue_issues_str = "No venues to validate."
    if venue_names:
        try:
            validation = await validate_venues(venue_names, destination, max_venues=10)
            venue_issues_str = _format_venue_issues(validation, destination)
        except Exception:
            venue_issues_str = "Venue validation unavailable."

    prompt = CRITIC_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        itinerary_json=json.dumps(itinerary, indent=2),
        currency=currency,
        budget=f"{budget:,.0f}" if budget < 999999 else "Unlimited",
        preferences=", ".join(preferences) or "general",
        venue_issues=venue_issues_str,
    )

    result = await call_llm_json(
        role="critic",
        prompt=prompt,
        system=CRITIC_SYSTEM,
        provider=resolve_provider(state, "critic"),
        api_key=state.get("api_key"),
        retries=0,
        timeout=30,
    )

    if "error" in result:
        warnings = state.get("warnings", [])
        warnings.append(f"Critic review failed: {result.get('error')}. Itinerary was not validated.")
        return {
            **state,
            "replan_instructions": "",
            "needs_replanning": False,
            "warnings": warnings,
            "execution_trace": ["critic_agent:error"],
        }

    needs_replan = result.get("needs_replanning", False)
    feedback = result.get("feedback", "")
    return {
        **state,
        "replan_instructions": feedback,
        "needs_replanning": needs_replan,
        "replan_count": replan_count + 1,
        "execution_trace": ["critic_agent"],
    }
