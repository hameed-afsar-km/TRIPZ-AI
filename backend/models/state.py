from typing import TypedDict, Optional, List, Dict, Any, Annotated
import operator


class TripState(TypedDict, total=False):
    # ── User Input ──
    user_request: str
    provider: str
    api_key: Optional[str]
    destination: str
    origin: str
    travel_dates: Dict[str, str]
    duration_days: int
    num_travelers: int
    adults: int
    kids: int
    infants: int
    trip_style: str  # "standard" | "budget" | "luxury" — preselected from UI
    preferences: List[str]
    previous_context: Optional[Dict[str, Any]]

    # ── Budget ──
    budget: float
    budget_breakdown: Dict[str, float]
    currency: str

    # ── Parallel Tool Results ──
    weather: Dict[str, Any]
    hotels: List[Dict[str, Any]]
    activities: List[Dict[str, Any]]
    transport: Dict[str, Any]
    location_info: Dict[str, Any]

    # ── Intelligence Layer ──
    routing_decision: str
    itinerary: Dict[str, Any]
    critic_feedback: str
    critic_issues: List[str]
    needs_replanning: bool
    replan_count: int
    replan_instructions: str

    # ── Execution Metadata ──
    error: Optional[str]
    warnings: Annotated[List[str], operator.add]
    execution_trace: Annotated[List[str], operator.add]
    confidence_score: float

