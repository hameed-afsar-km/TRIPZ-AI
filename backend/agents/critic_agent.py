import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Tuple

from services.llm_service import call_llm_json, resolve_provider
from services.wikipedia_service import validate_venues

logger = logging.getLogger("tripz.agents")


CRITIC_SYSTEM = """You are a strict travel itinerary reviewer.
Check for: vague descriptions, repeated text, wrong day count, wrong currency, budget issues, lack of variety, budget arithmetic errors.
Output ONLY valid JSON."""


# ── Pre-LLM validation patterns ────────────────────────────────────────────────

_FINAL_SUMMARY_PATTERN = re.compile(
    r'\*\*Accommodation\*\*:.*?=\s*~\s*\w+\s*([\d,]+(?:\.\d{1,2})?)\s*\n'
    r'.*?\*\*Food\s*\(total\)\*\*:\s*~\s*\w+\s*([\d,]+(?:\.\d{1,2})?)\s*\n'
    r'.*?\*\*Activities\s*\(total\)\*\*:\s*~\s*\w+\s*([\d,]+(?:\.\d{1,2})?)\s*\n'
    r'.*?\*\*Transport\s*\(total\)\*\*:\s*~\s*\w+\s*([\d,]+(?:\.\d{1,2})?)\s*\n'
    r'.*?\*\*Grand Total\*\*:\s*~\s*\w+\s*([\d,]+(?:\.\d{1,2})?)',
    re.IGNORECASE | re.DOTALL,
)

_PER_NIGHT_PATTERN = re.compile(
    r'(?:×|@|per night|/night)[^0-9]*(\d[\d,]*\.?\d*)',
    re.IGNORECASE,
)

_VENUE_DUPLICATE_PATTERN = re.compile(r'\[([^\]]+)\]\(https?://(?:www\.)?google\.com/maps/[^)]+\)')


def _check_budget_arithmetic(markdown: str) -> List[str]:
    """Verify Accommodation + Food + Activities + Transport = Grand Total."""
    issues = []
    match = _FINAL_SUMMARY_PATTERN.search(markdown)
    if not match:
        issues.append("Could not find Final Cost Summary section with all 5 fields (Accommodation, Food, Activities, Transport, Grand Total).")
        return issues

    try:
        accommodation = float(match.group(1).replace(",", ""))
        food = float(match.group(2).replace(",", ""))
        activities = float(match.group(3).replace(",", ""))
        transport = float(match.group(4).replace(",", ""))
        grand_total = float(match.group(5).replace(",", ""))
    except (ValueError, IndexError):
        issues.append("Could not parse numbers in Final Cost Summary.")
        return issues

    computed = accommodation + food + activities + transport
    if abs(computed - grand_total) > 1.0:
        issues.append(
            f"Budget arithmetic error: {accommodation} (Acc) + {food} (Food) + {activities} (Act) + {transport} (Trans) = {computed}, "
            f"but Grand Total says {grand_total}. Difference: {abs(computed - grand_total):.0f}. Fix the numbers."
        )
    return issues


def _check_accommodation_consistency(markdown: str) -> List[str]:
    """Check that the same hotel has the same price per night throughout."""
    issues = []
    hotel_sections = re.findall(
        r'(?:Hotel|Accommodation|Stay at|at the)\s*\**([A-Z][A-Za-z\s\'-]+?)\**\s*[—–-]\s*\w+\s*(\d[\d,]*\.?\d*)\s*(?:/night|per night)?',
        markdown,
        re.IGNORECASE,
    )
    if not hotel_sections:
        return issues

    prices: Dict[str, List[float]] = {}
    for name, price_str in hotel_sections:
        name_clean = name.strip().rstrip('*—–- ')
        try:
            price = float(price_str.replace(",", ""))
        except ValueError:
            continue
        if name_clean not in prices:
            prices[name_clean] = []
        prices[name_clean].append(price)

    for hotel, price_list in prices.items():
        unique_prices = set(price_list)
        if len(unique_prices) > 1:
            issues.append(
                f"Accommodation inconsistency: '{hotel}' shows different prices across days: {', '.join(f'{p:.0f}' for p in price_list)}. "
                f"The same hotel must have the same price per night every day."
            )

    return issues


def _check_duplicate_venues(markdown: str) -> List[str]:
    """Detect venues that appear in multiple days."""
    issues = []
    venue_days: Dict[str, List[int]] = {}
    current_day = 0

    for line in markdown.split("\n"):
        day_match = re.match(r'##\s+Day\s+(\d+)', line, re.IGNORECASE)
        if day_match:
            current_day = int(day_match.group(1))

        for vm in _VENUE_DUPLICATE_PATTERN.finditer(line):
            venue = vm.group(1).strip().lower()
            if venue not in venue_days:
                venue_days[venue] = []
            venue_days[venue].append(current_day)

    for venue, days in venue_days.items():
        unique_days = set(days)
        if len(unique_days) > 1:
            issues.append(
                f"Duplicate venue: '{venue.title()}' appears on days {', '.join(f'Day {d}' for d in sorted(unique_days))}. "
                f"Every venue must appear exactly once."
            )

    return issues


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

Pre-validation issues found (automated checks):
{pre_checks}

Check for these issues:
1. Vague descriptions — any "Relax at the hotel", "Explore the city", "Visit local attractions", "Enjoy dinner" with no specific name = FAIL
2. Repeated text — same morning/afternoon/evening appearing on multiple days = FAIL
3. Wrong day count — if days don't match {num_days} = FAIL
4. Wrong currency — if prices use a different currency than {currency} = FAIL
5. Budget mismatch — if total cost far exceeds budget = FAIL
6. Missing variety — if same theme repeats every day = FAIL
7. Fake venues — cross-reference against the known real venues list above. Flag any venue that appears to be invented, misnamed, or is not a real tourist attraction for {destination}. Pay special attention to venues listed as "NOT FOUND", "SUSPICIOUS", "UNVERIFIED", or in the non-linked names.
8. **Budget arithmetic** — Extract the Accommodation, Food, Activities, Transport, and Grand Total from the Final Cost Summary. Verify that Accommodation + Food + Activities + Transport = Grand Total. If the sum does not match, flag as FAIL and include the correct total in the feedback.
9. **Duplicate venues** — Check if any venue name appears on multiple different days. If so, flag as FAIL.
10. **Accommodation consistency** — If the same hotel appears on multiple days, verify the price per night is identical. A different price for the same hotel is a FAIL.

Return JSON:
{{"pass":true,"issues":[],"feedback":"","needs_replanning":false}}

- pass: true only if ALL checks pass with zero issues
- issues: list of specific problems found (empty if pass)
- feedback: detailed instructions for what to fix (empty if pass)
- needs_replanning: true if issues are severe enough to regenerate"""


_VENUE_PATTERN = re.compile(r'\[([^\]]+)\]\(https?://(?:www\.)?google\.com/maps/(?:search/?\?api=1&query=[^)]+|\\?q=[^)]+)\)')

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

    # Run pre-LLM validation checks
    pre_check_issues = []
    pre_check_issues.extend(_check_budget_arithmetic(markdown))
    pre_check_issues.extend(_check_accommodation_consistency(markdown))
    pre_check_issues.extend(_check_duplicate_venues(markdown))
    pre_checks_str = "\n".join(f"- {issue}" for issue in pre_check_issues) if pre_check_issues else "None found."

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
        pre_checks=pre_checks_str,
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
    llm_issues = result.get("issues", [])

    # Merge pre-LLM issues with LLM issues
    all_issues = pre_check_issues + llm_issues
    if pre_check_issues and not needs_replan:
        needs_replan = True
        pre_feedback = "Automated checks found issues:\n" + "\n".join(f"- {i}" for i in pre_check_issues)
        if feedback:
            feedback = pre_feedback + "\n\n" + feedback
        else:
            feedback = pre_feedback

    return {
        "replan_instructions": feedback,
        "needs_replanning": needs_replan,
        "replan_count": replan_count + 1,
        "execution_trace": ["critic_agent"],
        "critic_prompt": prompt,
        "critic_issues": all_issues,
    }
