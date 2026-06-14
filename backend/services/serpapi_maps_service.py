import logging
import os
from typing import Any, Dict, Optional

from services.llm_service import call_llm_json

logger = logging.getLogger("tripz.agents")

FOOD_COST_SYSTEM = """You are a travel cost estimation assistant. Given a destination city/country and currency,
estimate typical daily food costs per person. Consider the local cost of living and typical meal prices.
Return ONLY valid JSON with no markdown."""

FOOD_COST_PROMPT_TEMPLATE = """Destination: {destination}
Currency: {currency}

Estimate the typical daily food cost per person (3 meals) in {currency}.
Return this exact JSON structure:
{{
  "estimated_daily_food_cost_per_person": <float>,
  "low_budget_daily": <float>,
  "mid_range_daily": <float>,
  "high_end_daily": <float>,
  "currency": "{currency}",
  "note": "<brief justification based on local cost of living>"
}}

Base your estimate on:
- A low-budget day: street food, local eateries, self-catering
- A mid-range day: casual restaurants, cafes
- A high-end day: nice restaurants, multiple courses

Return only the JSON object, no other text."""


async def estimate_daily_food_cost(destination: str, currency: str = "USD") -> Optional[float]:
    try:
        result = await call_llm_json(
            role="food_cost_estimator",
            prompt=FOOD_COST_PROMPT_TEMPLATE.format(destination=destination, currency=currency),
            system=FOOD_COST_SYSTEM,
            provider="groq",
            api_key=os.getenv("GROQ_API_KEY"),
            timeout=60,
        )
        if "error" in result:
            logger.debug("Food cost LLM estimation failed: %s", result["error"])
            return None

        daily = result.get("estimated_daily_food_cost_per_person")
        if daily is not None:
            return round(float(daily), 2)

        mid = result.get("mid_range_daily")
        if mid is not None:
            return round(float(mid), 2)

        return None
    except Exception:
        logger.debug("Food cost estimation error", exc_info=True)
        return None


async def search_restaurants(destination: str) -> list:
    """Deprecated — kept for import compatibility. Returns empty list."""
    return []


async def search_activities_maps(destination: str) -> list:
    """Deprecated — kept for import compatibility. Returns empty list."""
    return []
