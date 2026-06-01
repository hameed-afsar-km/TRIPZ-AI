"""
Routing Agent — AI Call #2 of ~4.
Decides conditional branching AFTER the supervisor has parsed the request.
Uses gemma2:2b — ultra-fast single-token decision.
"""

from typing import Any, Dict
from services.llm_service import call_llm

ROUTING_SYSTEM = "You are a routing classifier. Output ONE word only. No explanation."

ROUTING_PROMPT_TEMPLATE = """Given this travel context, which workflow path is best?

Destination: {destination}
Budget: ${budget}
Travelers: {travelers}
Preferences: {preferences}
Confidence score: {confidence}

Options:
- "standard"   → Normal full workflow (most cases)
- "budget"     → Very tight budget, skip luxury options
- "luxury"     → High budget, skip budget filters  
- "replan"     → Ambiguous/incomplete request needs clarification

Output ONE word:"""


async def routing_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: AI Call #2.
    Returns routing_decision which drives the conditional edge after this node.
    Uses gemma2:2b for single-word ultra-fast classification.
    """
    budget = float(state.get("budget", 1000))
    travelers = int(state.get("num_travelers", 1))
    budget_per_person = budget / max(travelers, 1)

    # Rule-based pre-classification to save an AI call in obvious cases
    if state.get("confidence_score", 1.0) < 0.4:
        routing = "replan"
    elif budget_per_person < 300:
        routing = "budget"
    elif budget_per_person > 2000:
        routing = "luxury"
    else:
        # Only call AI if truly ambiguous
        prompt = ROUTING_PROMPT_TEMPLATE.format(
            destination=state.get("destination", "Unknown"),
            budget=budget,
            travelers=travelers,
            preferences=", ".join(state.get("preferences", [])) or "none",
            confidence=state.get("confidence_score", 0.8),
        )
        raw = await call_llm(
            role="routing",
            prompt=prompt,
            system=ROUTING_SYSTEM,
            provider=state.get("provider", "ollama"),
            api_key=state.get("api_key"),
            temperature=0.1,  # Near-deterministic for routing
        )
        # Normalize output
        routing = raw.strip().lower().split()[0]
        if routing not in ("standard", "budget", "luxury", "replan"):
            routing = "standard"

    trace = state.get("execution_trace", [])
    return {
        **state,
        "routing_decision": routing,
        "execution_trace": trace + [f"routing_agent:{routing}"],
    }
