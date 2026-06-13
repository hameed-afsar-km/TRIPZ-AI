from typing import Any, Dict
from services.geo_service import fetch_activities


async def activity_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    destination = state.get("destination", "Unknown")
    preferences = state.get("preferences", [])
    pref_lower = [p.lower().strip() for p in (preferences or [])]

    activities = await fetch_activities(destination)

    if not activities:
        trace = state.get("execution_trace", [])
        return {
            **state,
            "activities": [],
            "execution_trace": trace + ["activity_tool:empty"],
        }

    def _score(a: Dict) -> int:
        cat = a.get("category", "").lower()
        name = a.get("name", "").lower()
        score = 0
        for p in pref_lower:
            if p in cat or p in name:
                score += 1
        return score

    activities.sort(key=_score, reverse=True)

    trace = state.get("execution_trace", [])
    return {
        **state,
        "activities": activities,
        "execution_trace": trace + ["activity_tool"],
    }
