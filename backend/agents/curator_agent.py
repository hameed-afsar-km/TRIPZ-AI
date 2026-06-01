import asyncio
from typing import Any, Dict
from tools.activity_tool import activity_tool

async def curator_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Curator Agent: Gathers and structures activities for the trip plan.
    Uses the activity tool and structures results into the state.
    """
    result = await activity_tool(state)
    
    activities = []
    warnings = []
    
    if isinstance(result, dict):
        if "activities" in result:
            activities = result["activities"]
        # Extract warnings or errors if any
        if "error" in result:
            warnings.append(f"Curator error: {result['error']}")
        
    return {
        "activities": activities,
        "warnings": warnings,
        "execution_trace": ["curator_agent"],
    }

