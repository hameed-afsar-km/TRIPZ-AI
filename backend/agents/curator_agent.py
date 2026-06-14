import asyncio
from typing import Any, Dict
from tools.activity_tool import activity_tool

async def curator_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Curator Agent: Gathers and structures activities for the trip plan.
    Uses the activity tool and structures results into the state.
    """
    if state.get("activities"):
        return {"execution_trace": ["curator_agent:from_cache"]}

    result = await activity_tool(state)
    trace = state.get("execution_trace", [])
    
    activities = []
    warnings = []
    
    if isinstance(result, dict):
        if "activities" in result:
            activities = result["activities"]
        if "error" in result:
            warnings.append(f"Curator error: {result['error']}")
        tool_trace = result.get("execution_trace", [])
        if tool_trace:
            trace = tool_trace
        
    return {
        "activities": activities,
        "warnings": warnings,
        "execution_trace": trace + ["curator_agent"],
    }

