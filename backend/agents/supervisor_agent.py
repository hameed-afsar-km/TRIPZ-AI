import json
from typing import Any, Dict
from services.llm_service import call_llm_json

SUPERVISOR_SYSTEM = """You are a travel request parser. Extract ALL details from the user's request.
- Extract destination, origin, duration in days, budget, number of travelers, preferences
- Handle "any budget" as no limit (return 999999)
- Infer currency from origin (India→INR, USA→USD, etc.) or from explicit mentions like "rupees" (→INR)
- Capture preferences like "visit all places", "culture", "adventure", etc.
- Calculate start/end dates from duration
Return ONLY valid JSON, no other text."""

SUPERVISOR_PROMPT_TEMPLATE = """User request: "{request}"

Analyze and extract:
1. Destination city/country
2. Origin city/country (if not stated, default to "Unknown")
3. Trip duration in DAYS (count "10 days" as 10, "a week" as 7, etc.)
4. Total budget (if "any" or "no limit", use 999999; if no number, default to 3000)
5. Currency (INR if from/in India or "rupees" mentioned, USD otherwise; infer from origin if possible)
6. Number of travelers (default 1)
7. Preferences list (culture, adventure, food, relaxation, budget, luxury, "visit all places", etc.)
8. Travel dates (calculate from duration: start today, end after N days)

Return ONLY this JSON structure, no markdown or explanation:
{{"destination":"Dubai","origin":"Mumbai","travel_dates":{{"start":"2025-06-01","end":"2025-06-10"}},"num_travelers":1,"budget":100000,"currency":"INR","preferences":["adventure","culture"],"duration_days":10,"confidence":0.9}}"""


async def supervisor_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    user_request = state.get("user_request", "")
    if not user_request:
        return {
            "error": "No user request provided",
            "execution_trace": ["supervisor_agent:error"],
        }

    # If we have previous context, seed the parse faster
    prev_context = state.get("previous_context", {})
    if prev_context and prev_context.get("destination"):
        return {
            "destination":    prev_context.get("destination", "Unknown"),
            "origin":         prev_context.get("origin", "Unknown"),
            "travel_dates":   prev_context.get("travel_dates", {}),
            "duration_days":  prev_context.get("duration_days", 7),
            "num_travelers":  prev_context.get("num_travelers", 1),
            "budget":         prev_context.get("budget", 3000),
            "currency":       prev_context.get("currency", "USD"),
            "preferences":    prev_context.get("preferences", []),
            "confidence_score": 0.9,
            "provider":       state.get("provider", "ollama"),
            "api_key":        state.get("api_key"),
            "execution_trace": ["supervisor_agent:from_context"],
        }

    prompt = SUPERVISOR_PROMPT_TEMPLATE.format(request=user_request)

    parsed = await call_llm_json(
        role="supervisor",
        prompt=prompt,
        system=SUPERVISOR_SYSTEM,
        provider=state.get("provider", "ollama"),
        api_key=state.get("api_key"),
        timeout=60,
    )

    if "error" in parsed:
        # Try to salvage destination from the raw request rather than defaulting to Unknown
        import re
        from datetime import datetime, timedelta
        
        raw = user_request.strip()
        fallback_dest = None
        fallback_duration = 7
        fallback_origin = "Unknown"
        fallback_budget = 3000
        fallback_currency = "USD"
        fallback_preferences = []

        # Pattern 1: city at start of input — "dubai for 10 days", "Paris trip 3 days"
        m = re.match(r'^([a-zA-Z][a-zA-Z\s,]+?)\s+(?:for|from|trip|tour|in|at)\b', raw, re.IGNORECASE)
        if m:
            fallback_dest = m.group(1).strip().title()

        # Pattern 2: explicit prepositions — "10 days in Dubai", "travel to London"
        if not fallback_dest:
            m = re.search(r'\b(?:in|to|visit|explore)\s+([a-zA-Z][a-zA-Z\s,]+?)(?:\s+for|\s+from|\s+at|\s*$)', raw, re.IGNORECASE)
            if m:
                fallback_dest = m.group(1).strip().title()

        # Pattern 3: any word(s) that look like a place name (title-cased words)
        if not fallback_dest:
            m = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', raw)
            if m:
                fallback_dest = m.group(1).strip()

        # Last resort: use the first word as the destination rather than Unknown
        if not fallback_dest:
            first_word = raw.split()[0] if raw.split() else ""
            fallback_dest = first_word.title() if first_word else "Unknown"

        # Extract duration in days
        m = re.search(r'(\d+)\s*(?:days?|d)\b', raw, re.IGNORECASE)
        if m:
            fallback_duration = int(m.group(1))

        # Extract origin and currency
        if re.search(r'\bindia\b', raw, re.IGNORECASE):
            fallback_origin = "India"
            fallback_currency = "INR"
        elif re.search(r'\brupees?\b', raw, re.IGNORECASE):
            fallback_currency = "INR"
        elif re.search(r'\b(?:USA|United States|US)\b', raw, re.IGNORECASE):
            fallback_origin = "USA"
            fallback_currency = "USD"

        # Detect "any budget" or "all places"
        if re.search(r'\b(?:any|unlimited|no limit|all|budget)\s*budget\b', raw, re.IGNORECASE):
            fallback_budget = 999999
        if re.search(r'\b(?:visit|explore|see)\s+(?:all|every)\b', raw, re.IGNORECASE):
            fallback_preferences.append("visit all places")

        # Calculate dates (N days means Day1 to DayN, so end = start + N - 1)
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=max(fallback_duration - 1, 0))

        return {
            "destination": fallback_dest,
            "origin": fallback_origin,
            "travel_dates": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "duration_days": fallback_duration,
            "budget": float(fallback_budget),
            "num_travelers": 1,
            "preferences": fallback_preferences,
            "currency": fallback_currency,
            "provider":  state.get("provider", "ollama"),
            "api_key":   state.get("api_key"),
            "warnings": ["Supervisor JSON parsing failed — using regex fallback. Results may be incomplete."],
            "execution_trace": ["supervisor_agent:fallback"],
        }

    # Calculate dates from duration if not provided
    travel_dates = parsed.get("travel_dates", {})
    duration_days = int(parsed.get("duration_days", 7))
    if not travel_dates.get("start") or not travel_dates.get("end"):
        from datetime import datetime, timedelta
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=max(duration_days - 1, 0))
        travel_dates = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        }

    # Handle "any budget" scenarios
    budget = parsed.get("budget", 3000)
    if isinstance(budget, str) and budget.lower() in ["any", "unlimited", "no limit"]:
        budget = 999999.0
    
    return {
        "destination":    parsed.get("destination", "Unknown"),
        "origin":         parsed.get("origin", "Unknown"),
        "travel_dates":   travel_dates,
        "duration_days":  duration_days,
        "num_travelers":  int(parsed.get("num_travelers", 1)),
        "budget":         float(budget),
        "currency":       parsed.get("currency", "USD"),
        "preferences":    parsed.get("preferences", []),
        "confidence_score": float(parsed.get("confidence", 0.5)),
        "provider":       state.get("provider", "ollama"),
        "api_key":        state.get("api_key"),
        "execution_trace": ["supervisor_agent"],
    }
