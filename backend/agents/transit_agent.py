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

        for result in results:
            if isinstance(result, Exception):
                warnings.append(f"Transit tool error: {str(result)}")
                continue
            if isinstance(result, dict):
                # Extract key fields
                if "weather" in result:
                    weather = result["weather"]
                if "transport" in result:
                    transport = result["transport"]
                # Extract warnings or errors if any
                if "error" in result:
                    warnings.append(f"Transit error: {result['error']}")

        return {
            "weather": weather,
            "transport": transport,
            "warnings": warnings,
            "execution_trace": ["transit_agent"],
        }
    except Exception as e:
        return {
            "weather": {"error": str(e)},
            "transport": {},
            "warnings": [f"Transit agent error: {str(e)}"],
            "execution_trace": ["transit_agent:error"],
        }

