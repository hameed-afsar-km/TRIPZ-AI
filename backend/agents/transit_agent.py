import asyncio
from typing import Any, Dict
from tools.weather_tool import weather_tool
from tools.transport_tool import transport_tool

async def transit_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transit Agent: Executes the weather and transport gathering in parallel.
    Consolidates transport options and weather details into the state.
    """
    try:
        # Execute both tools concurrently
        results = await asyncio.gather(
            weather_tool(state),
            transport_tool(state),
            return_exceptions=True,
        )

        weather = {}
        transport = {}
        warnings = []
        trace = state.get("execution_trace", [])

        for result in results:
            if isinstance(result, Exception):
                warnings.append(f"Transit tool error: {str(result)}")
                continue
            if isinstance(result, dict):
                if "weather" in result:
                    weather = result["weather"]
                if "transport" in result:
                    transport = result["transport"]
                if "error" in result:
                    warnings.append(f"Transit error: {result['error']}")
                tool_trace = result.get("execution_trace", [])
                if tool_trace:
                    trace = tool_trace

        return {
            "weather": weather,
            "transport": transport,
            "warnings": state.get("warnings", []) + warnings,
            "execution_trace": trace + ["transit_agent"],
        }
    except Exception as e:
        return {
            "weather": {"error": str(e)},
            "transport": {},
            "warnings": state.get("warnings", []) + [f"Transit agent error: {str(e)}"],
            "execution_trace": state.get("execution_trace", []) + ["transit_agent:error"],
        }

