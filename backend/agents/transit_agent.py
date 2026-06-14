import asyncio
from typing import Any, Dict
from tools.weather_tool import weather_tool
from tools.transport_tool import transport_tool

def _recommend_transport(distance_km: float | None, origin: str, destination: str) -> Dict[str, Any]:
    if distance_km is None:
        return {"recommended_mode": "unknown", "note": "Distance unknown, cannot recommend transport."}
    if distance_km > 2000:
        return {
            "recommended_mode": "flight",
            "estimated_duration_hours": round(distance_km / 850, 1),
            "note": f"Long distance ({distance_km} km) — flying is the best option.",
        }
    elif distance_km > 500:
        return {
            "recommended_mode": "train",
            "estimated_duration_hours": round(distance_km / 120, 1),
            "note": f"Moderate distance ({distance_km} km) — train is comfortable and efficient.",
        }
    else:
        return {
            "recommended_mode": "bus",
            "estimated_duration_hours": round(distance_km / 60, 1),
            "note": f"Short distance ({distance_km} km) — bus or car is the most practical.",
        }


async def transit_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transit Agent: Executes weather + transport gathering in parallel.
    Then recommends best transport mode (flight/train/bus) based on distance.
    """
    if state.get("weather") and state.get("transport"):
        return {"execution_trace": ["transit_agent:from_cache"]}

    try:
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

        distance_km = transport.get("distance_km") if isinstance(transport, dict) else None
        origin = state.get("origin", "Unknown")
        destination = state.get("destination", "Unknown")
        recommendation = _recommend_transport(distance_km, origin, destination)
        transport["recommended"] = recommendation

        return {
            "weather": weather,
            "transport": transport,
            "warnings": warnings,
            "execution_trace": trace + ["transit_agent"],
        }
    except Exception as e:
        return {
            "weather": {"error": str(e)},
            "transport": {},
            "warnings": state.get("warnings", []) + [f"Transit agent error: {str(e)}"],
            "execution_trace": ["transit_agent:error"],
        }

