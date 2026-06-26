import asyncio
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

{known_venues}

Venue validation results (from Wikipedia):
{venue_issues}

{cross_ref}

Non-linked venue names found in day sections:
{plain_venues}

Check for these issues:
1. Vague descriptions — any "Relax at the hotel", "Explore the city", "Visit local attractions", "Enjoy dinner" with no specific name = FAIL
2. Repeated text — same morning/afternoon/evening appearing on multiple days = FAIL
3. Wrong day count — if days don't match {num_days} = FAIL
4. Wrong currency — if prices use a different currency than {currency} = FAIL
5. Budget mismatch — if total cost far exceeds budget = FAIL
6. Missing variety — if same theme repeats every day = FAIL
7. Fake venues — cross-reference against the known real venues list above. Flag any venue that appears to be invented, misnamed, or is not a real tourist attraction for {destination}. Pay special attention to venues listed as "NOT FOUND", "SUSPICIOUS", "UNVERIFIED", or in the non-linked names.

Return JSON:
{{"pass":true,"issues":[],"feedback":"","needs_replanning":false}}

- pass: true only if ALL checks pass with zero issues
- issues: list of specific problems found (empty if pass)
- feedback: detailed instructions for what to fix (empty if pass)
- needs_replanning: true if issues are severe enough to regenerate"""


_VENUE_PATTERN = re.compile(r'\[([^\]]+)\]\(https?://(?:www\.)?google\.com/maps\?q=([^)]+)\)')

_VAGUE_WORDS = {"relax", "explore", "visit", "enjoy", "walk", "stroll", "shop", "dinner", "lunch", "breakfast", "go", "head", "drive", "take", "try", "see", "discover"}


def _extract_venue_names(markdown: str) -> List[str]:
    """Extract venue names from Google Maps links in the itinerary markdown."""
    names = []
    for match in _VENUE_PATTERN.finditer(markdown):
        name = match.group(1).strip()
        if name and len(name) > 2:
            names.append(name)
    return list(dict.fromkeys(names))  # deduplicate preserving order


def _extract_plain_venue_names(markdown: str) -> List[str]:
    """Extract potential venue names from day sections that lack Google Maps links."""
    names = []
    for section in [r'\*\*Morning\*\*:\s*(.+?)(?:\s*[—~]|\s*\n|$)',
                    r'\*\*Afternoon\*\*:\s*(.+?)(?:\s*[—~]|\s*\n|$)',
                    r'\*\*Evening\*\*:\s*(.+?)(?:\s*[—~]|\s*\n|$)']:
        for match in re.finditer(section, markdown, re.IGNORECASE | re.DOTALL):
            raw = match.group(1).strip().rstrip('—~ ')
            if not raw or raw.startswith('['):
                continue
            parts = raw.split(None, 1)
            if parts and parts[0].lower().strip(":") in _VAGUE_WORDS:
                if len(parts) > 1:
                    raw = parts[1].strip()
                else:
                    continue
            if raw and len(raw) > 2:
                names.append(raw)
    return list(dict.fromkeys(names))


def _build_known_venues_str(known_activities: List[Dict[str, Any]]) -> str:
    """Build a readable list of known real venues from the database."""
    known = [a.get("name", "") for a in known_activities if a.get("name")]
    if not known:
        return ""
    return "Known real venues: " + ", ".join(known) + "."


def _cross_reference_venues(markdown_venues: List[str], known_activities: List[Dict[str, Any]]) -> str:
    """Cross-reference venues in the itinerary against known database venues."""
    known = {a.get("name", "").lower().strip() for a in known_activities if a.get("name")}
    if not known:
        return ""
    unknown = [v for v in set(v.lower().strip() for v in markdown_venues) if v not in known]
    if not unknown:
        return "All linked venues match known real venues."
    return "Unverified venues: " + ", ".join(sorted(unknown)) + " — not found in our venue database."


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
        elif destination and not hint:
            lines.append(f"- SUSPICIOUS: \"{original}\" — exists on Wikipedia but has no clear connection to {destination}")
        else:
            lines.append(f"- OK: \"{original}\"")

    if not lines:
        return "No venues found to validate."
    return "\n".join(lines)


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

    markdown = itinerary.get("markdown", "")
    known_activities = state.get("activities", [])

    linked_venues = _extract_venue_names(markdown)
    plain_venues = _extract_plain_venue_names(markdown)
    all_venues = list(dict.fromkeys(linked_venues + [v for v in plain_venues if v not in linked_venues]))

    venue_issues_str = "No venues to validate."
    if linked_venues:
        try:
            validation = await asyncio.wait_for(
                validate_venues(linked_venues, destination, max_venues=10),
                timeout=15,
            )
            venue_issues_str = _format_venue_issues(validation, destination)
        except Exception:
            venue_issues_str = "Venue validation unavailable."

    known_venues_str = _build_known_venues_str(known_activities)
    cross_ref_str = _cross_reference_venues(all_venues, known_activities)
    plain_venues_str = ", ".join(plain_venues) if plain_venues else "None"

    itinerary_str = json.dumps(itinerary, indent=2)
    if len(itinerary_str) > 4000:
        itinerary_str = itinerary_str[:4000] + "\n... [truncated]"

    prompt = CRITIC_PROMPT_TEMPLATE.format(
        num_days=num_days,
        destination=destination,
        itinerary_json=itinerary_str,
        currency=currency,
        budget=f"{budget:,.0f}" if budget < 999999 else "Unlimited",
        preferences=", ".join(preferences) or "general",
        known_venues=known_venues_str,
        venue_issues=venue_issues_str,
        cross_ref=cross_ref_str,
        plain_venues=plain_venues_str,
    )

    result = await call_llm_json(
        role="critic",
        prompt=prompt,
        system=CRITIC_SYSTEM,
        provider=resolve_provider(state, "critic"),
        api_key=state.get("api_key"),
        retries=1,
        timeout=30,
    )

    if "error" in result:
        return {
            "replan_instructions": "",
            "needs_replanning": False,
            "warnings": [f"Critic review failed: {result.get('error')}. Itinerary was not validated."],
            "execution_trace": ["critic_agent:error"],
            "critic_prompt": prompt,
        }

    needs_replan = result.get("needs_replanning", False)
    feedback = result.get("feedback", "")
    return {
        "replan_instructions": feedback,
        "needs_replanning": needs_replan,
        "replan_count": replan_count + 1,
        "execution_trace": ["critic_agent"],
        "critic_prompt": prompt,
    }
