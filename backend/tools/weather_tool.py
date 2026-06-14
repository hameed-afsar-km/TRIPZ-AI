"""
Weather Tool — zero AI calls.
Uses Open-Meteo (free, no API key required) to fetch real forecast data.
Returns structured dict that goes directly into TripState["weather"].
"""

import asyncio
from typing import Any, Dict
import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog", 51: "Light drizzle", 53: "Drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Heavy showers", 95: "Thunderstorm",
}


async def weather_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: fetches 7-day forecast for state["destination"].
    No LLM call. Pure HTTP + data transform.
    """
    destination = state.get("destination", "")
    if not destination:
        return {**state, "weather": {"error": "No destination provided"}}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                # Step 1: Geocode the destination name → lat/lon
                geo_resp = await asyncio.wait_for(
                    client.get(
                        GEOCODE_URL,
                        params={"name": destination, "count": 1, "language": "en", "format": "json"},
                    ),
                    timeout=5.0
                )
                geo_data = geo_resp.json()
                if not geo_data.get("results"):
                    return {**state, "weather": {"error": f"Location not found: {destination}"}}

                loc = geo_data["results"][0]
                lat, lon = loc["latitude"], loc["longitude"]
                tz = loc.get("timezone", "UTC")

                # Step 2: Fetch 7-day daily forecast
                forecast_resp = await asyncio.wait_for(
                    client.get(
                        FORECAST_URL,
                        params={
                            "latitude": lat,
                            "longitude": lon,
                            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                            "timezone": tz,
                            "forecast_days": 7,
                        },
                    ),
                    timeout=5.0
                )
                forecast_data = forecast_resp.json()
                daily = forecast_data.get("daily", {})

                # Step 3: Structure into readable format
                days = []
                for i, date in enumerate(daily.get("time", [])):
                    code = daily["weathercode"][i]
                    days.append({
                        "date": date,
                        "condition": WMO_DESCRIPTIONS.get(code, "Unknown"),
                        "temp_max_c": daily["temperature_2m_max"][i],
                        "temp_min_c": daily["temperature_2m_min"][i],
                        "precipitation_mm": daily["precipitation_sum"][i],
                        "wind_kmh": daily["wind_speed_10m_max"][i],
                        "is_bad_weather": code >= 61,   # Rain, snow, thunderstorm
                    })

                weather_result = {
                    "location": loc.get("name", destination),
                    "country": loc.get("country", ""),
                    "timezone": tz,
                    "forecast": days,
                    "any_bad_weather": any(d["is_bad_weather"] for d in days),
                }
            except asyncio.TimeoutError:
                weather_result = {"error": "Weather API timeout", "forecast": []}
            except Exception as e:
                weather_result = {"error": f"Weather API error: {str(e)}", "forecast": []}

    except Exception as e:
        weather_result = {"error": str(e), "forecast": []}

    return {**state, "weather": weather_result, "execution_trace": ["weather_tool"]}
