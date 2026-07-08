import asyncio
import json
from typing import Any, Dict, List

from services.llm_service import call_llm_json, resolve_provider
from services.attraction_cache import get_known_attractions, is_known_attraction
from services.tavily_service import search_venue_info

VALIDATOR_SYSTEM = """You are a professional travel expert. Your job is to filter a list of locations
and determine which ones are legitimate tourist attractions that real travellers would visit.

Categories you may assign:
- Landmark — iconic building, monument, or structure worth visiting
- Museum — any museum, gallery, or cultural exhibition space
- Historical Site — fort, castle, ruins, archaeological site
- Beach — beach, coastline, waterfront promenade
- Nature — park, garden, viewpoint, natural feature
- Shopping — mall, souk, market, retail district
- Entertainment — theme park, water park, arcade, nightlife
- Religious Site — mosque, temple, church, shrine
- Restaurant — dining establishment (keep only if famous/signature)
- Other — catch-all

REJECT any location that matches these patterns:
- Residential compound, apartment complex, housing community
- School, university, educational institution
- Office building, business park, corporate headquarters
- Bus station, metro station, transport hub (unless it's a historic landmark station)
- Internal courtyard, unnamed plaza, generic public square
- Warehouse, industrial site, factory
- Generic business (real estate office, travel agency, auto repair, etc.)
- Single shop, convenience store, grocery
- Medical clinic, hospital, pharmacy

Return ONLY valid JSON with no markdown."""

VALIDATOR_PROMPT_TEMPLATE = """Destination: {destination}
Trip preferences: {preferences}

Review each location below and determine if it's worth visiting for a tourist.
For each location, decide:
1. pass — true if tourists would realistically visit this place
2. category — one of the categories listed above
3. reason — brief justification

{locations}

Return JSON:
{{"approved":[{{"name":"...","category":"...","reason":"..."}}],"rejected":[{{"name":"...","reason":"..."}}]}}"""


def _build_locations_text(activities: List[Dict[str, Any]]) -> str:
    lines = []
    for i, a in enumerate(activities, 1):
        name = a.get("name", "?")
        cat = a.get("category", "?")
        desc = a.get("description", "")[:120]
        lines.append(f"{i}. \"{name}\" [{cat}] — {desc}")
    return "\n".join(lines)


async def validator_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    activities = state.get("activities", [])
    if not activities:
        return {"execution_trace": ["validator_agent:no_activities"]}

    destination = state.get("destination", "Unknown")
    preferences = state.get("preferences", [])

    approved: List[Dict[str, Any]] = []
    unknown_venues: List[Dict[str, Any]] = []

    for a in activities:
        name = a.get("name", "")
        if not name:
            continue
        if is_known_attraction(name, destination):
            a["_validated"] = True
            a["_validation_source"] = "known_cache"
            approved.append(a)
        else:
            unknown_venues.append(a)

    # Tavily pre-filter: web-search unknown venues before LLM validation
    if unknown_venues:
        async def _tavily_check(a: Dict[str, Any]) -> bool:
            info = await search_venue_info(a.get("name", ""), destination)
            if info and info.get("is_tourist_attraction"):
                a["_validated"] = True
                a["_validation_source"] = "tavily_web"
                return True
            return False

        checked = await asyncio.gather(*[_tavily_check(a) for a in unknown_venues], return_exceptions=True)
        still_unknown = []
        for a, ok in zip(unknown_venues, checked):
            if isinstance(ok, Exception) or not ok:
                still_unknown.append(a)
            else:
                approved.append(a)
        unknown_venues = still_unknown

    if not unknown_venues:
        return {
            "activities": approved,
            "execution_trace": ["validator_agent:all_known"],
        }

    locations_text = _build_locations_text(unknown_venues)
    prefs_str = ", ".join(preferences) if preferences else "general"

    prompt = VALIDATOR_PROMPT_TEMPLATE.format(
        destination=destination,
        preferences=prefs_str,
        locations=locations_text,
    )

    result = await call_llm_json(
        role="validator",
        prompt=prompt,
        system=VALIDATOR_SYSTEM,
        provider=resolve_provider(state, "validator"),
        api_key=state.get("api_key"),
        retries=1,
        timeout=30,
    )

    if "error" in result:
        approved.extend(unknown_venues)
        return {
            "activities": approved,
            "warnings": [f"Validator LLM failed ({result.get('error')}). All venues kept as-is."],
            "execution_trace": ["validator_agent:fallback"],
        }

    llm_approved_names = {a.get("name", "").lower().strip() for a in result.get("approved", [])}

    for a in unknown_venues:
        name = a.get("name", "").lower().strip()
        if name in llm_approved_names:
            a["_validated"] = True
            a["_validation_source"] = "llm"
            approved.append(a)

    return {
        "activities": approved,
        "execution_trace": ["validator_agent"],
    }
