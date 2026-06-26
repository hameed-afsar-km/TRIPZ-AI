import asyncio
import logging
from typing import Any, Dict
from tools.activity_tool import activity_tool

logger = logging.getLogger(__name__)

_CURATOR_TIMEOUT = 45  # seconds max for the full activity fetch pipeline

async def curator_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("activities"):
        return {"execution_trace": ["curator_agent:from_cache"]}

    try:
        result = await asyncio.wait_for(activity_tool(state), timeout=_CURATOR_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("curator_agent timed out after %ds — returning empty activities", _CURATOR_TIMEOUT)
        return {
            "activities": [],
            "warnings": ["Activity fetch timed out. Please try again or be more specific."],
            "execution_trace": ["curator_agent:timeout"],
        }

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

