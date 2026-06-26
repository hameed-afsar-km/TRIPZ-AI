from typing import TypedDict, Optional, List, Dict, Any, Annotated
import operator


def _last_writer(a, b):
    """Last-writer-wins reducer — replaces value instead of failing on concurrent writes."""
    return b if b is not None else a


class TripState(TypedDict, total=False):
    # ── User Input ──
    user_request: Annotated[str, _last_writer]
    provider: Annotated[str, _last_writer]
    api_key: Annotated[Optional[str], _last_writer]
    agent_providers: Annotated[Dict[str, str], _last_writer]
    destination: Annotated[str, _last_writer]
    origin: Annotated[str, _last_writer]
    travel_dates: Annotated[Dict[str, str], _last_writer]
    duration_days: Annotated[int, _last_writer]
    num_travelers: Annotated[int, _last_writer]
    adults: Annotated[int, _last_writer]
    kids: Annotated[int, _last_writer]
    infants: Annotated[int, _last_writer]
    trip_style: Annotated[str, _last_writer]
    preferences: Annotated[List[str], _last_writer]
    previous_context: Annotated[Optional[Dict[str, Any]], _last_writer]

    # ── Budget ──
    budget: Annotated[float, _last_writer]
    budget_breakdown: Annotated[Dict[str, float], _last_writer]
    currency: Annotated[str, _last_writer]

    # ── Parallel Tool Results ──
    weather: Annotated[Dict[str, Any], _last_writer]
    hotels: Annotated[List[Dict[str, Any]], _last_writer]
    activities: Annotated[List[Dict[str, Any]], _last_writer]
    transport: Annotated[Dict[str, Any], _last_writer]
    location_info: Annotated[Dict[str, Any], _last_writer]

    # ── Intelligence Layer ──
    routing_decision: Annotated[str, _last_writer]
    itinerary: Annotated[Dict[str, Any], _last_writer]
    critic_feedback: Annotated[str, _last_writer]
    critic_issues: Annotated[List[str], _last_writer]
    needs_replanning: Annotated[bool, _last_writer]
    replan_count: Annotated[int, _last_writer]
    replan_instructions: Annotated[str, _last_writer]

    # ── Execution Metadata ──
    error: Annotated[Optional[str], _last_writer]
    warnings: Annotated[List[str], operator.add]
    execution_trace: Annotated[List[str], operator.add]
    confidence_score: Annotated[float, _last_writer]

