import json
from typing import Any, Dict
from services.llm_service import call_llm_json, resolve_provider

SUPERVISOR_SYSTEM = """You are a travel request parser. Extract ALL details from the user's request.
- Extract destination, origin, duration in days, budget, travelers breakdown, preferences
- ONLY use 999999 for budget if the user explicitly says "any budget" or "no limit". Otherwise use the exact number stated.
- Infer currency from origin (India→INR, USA→USD, etc.) or from explicit mentions like "rupees" (→INR)
- Capture preferences like "visit all places", "culture", "adventure", etc.
- Calculate start/end dates from duration
Return ONLY valid JSON, no other text."""

SUPERVISOR_PROMPT_TEMPLATE = """User request: "{request}"

Analyze and extract:
1. Destination city/country
2. Origin city/country (if not stated, default to "Unknown")
3. Trip duration in DAYS (count "10 days" as 10, "a week" as 7, etc.)
4. Total budget (use the EXACT number stated; ONLY use 999999 if user says "any budget" or "no limit"; if no number at all, default to 3000)
5. Currency (INR if from/in India or "rupees" mentioned, USD otherwise; infer from origin if possible)
6. Number of travelers breakdown:
   - adults: number of adults (default 1, minimum 1)
   - kids: number of children (default 0)
   - infants: number of infants (default 0)
   - num_travelers: total = adults + kids + infants (default 1)
7. Preferences list (culture, adventure, food, relaxation, budget, luxury, "visit all places", etc.)
8. Travel dates (calculate from duration: start today, end after N days)

Return ONLY this JSON structure, no markdown or explanation:
{{"destination":"Dubai","origin":"Mumbai","travel_dates":{{"start":"2025-06-01","end":"2025-06-10"}},"adults":2,"kids":1,"infants":0,"num_travelers":3,"budget":100000,"currency":"INR","preferences":["adventure","culture"],"duration_days":10,"confidence":0.9}}"""


async def supervisor_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    user_request = state.get("user_request", "")
    if not user_request:
        return {
            **state,
            "error": "No user request provided",
            "duration_days": 7,
            "execution_trace": ["supervisor_agent:error"],
        }

    # If we have previous context, seed the parse faster
    prev_context = state.get("previous_context", {})
    if prev_context and prev_context.get("destination"):
        return {
            **state,
            "destination":    prev_context.get("destination", "Unknown"),
            "origin":         prev_context.get("origin", "Unknown"),
            "travel_dates":   prev_context.get("travel_dates", {}),
            "duration_days":  prev_context.get("duration_days", 7),
            "num_travelers":  prev_context.get("num_travelers", 1),
            "adults":         prev_context.get("adults", 1),
            "kids":           prev_context.get("kids", 0),
            "infants":        prev_context.get("infants", 0),
            "budget":         prev_context.get("budget", 3000),
            "currency":       prev_context.get("currency", "USD"),
            "preferences":    prev_context.get("preferences", []),
            "confidence_score": 0.9,
            "execution_trace": ["supervisor_agent:from_context"],
        }

    prompt = SUPERVISOR_PROMPT_TEMPLATE.format(request=user_request)

    parsed = await call_llm_json(
        role="supervisor",
        prompt=prompt,
        system=SUPERVISOR_SYSTEM,
        provider=resolve_provider(state, "supervisor"),
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

        # Pattern 1: explicit prepositions — "10 days in Dubai", "travel to London", "plan a trip to Dubai"
        m = re.search(r'\b(?:in|to|visit|explore)\s+([a-zA-Z][a-zA-Z\s,]+?)(?:\s+for|\s+from|\s+at|\s*$)', raw, re.IGNORECASE)
        if m:
            fallback_dest = m.group(1).strip().title()

        # Pattern 2: city at start of input — "dubai for 10 days", "Paris trip 3 days"
        if not fallback_dest:
            m = re.match(r'^([a-zA-Z][a-zA-Z\s,]+?)\s+(?:for|from|trip|tour|in|at)\b', raw, re.IGNORECASE)
            if m:
                fallback_dest = m.group(1).strip().title()

        # Pattern 3: "plan a trip to X", "plan X trip"
        if not fallback_dest:
            m = re.search(r'\b(?:trip|tour|travel|visit|go)\s+(?:to\s+)?([a-zA-Z][a-zA-Z\s,]+?)(?:\s+for|\s+from|\s+at|\s+with|\s*$)', raw, re.IGNORECASE)
            if m:
                fallback_dest = m.group(1).strip().title()

        # Pattern 4: any word(s) that look like a place name (title-cased words)
        if not fallback_dest:
            m = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', raw)
            if m:
                fallback_dest = m.group(1).strip()

        # Last resort: use the first word as the destination rather than Unknown
        if not fallback_dest:
            first_word = raw.split()[0] if raw.split() else ""
            fallback_dest = first_word.title() if first_word else "Unknown"

        # Extract duration in days (handles "10 days", "10-day", "7d")
        m = re.search(r'(\d+)\s*-?\s*(?:days?|d)\b', raw, re.IGNORECASE)
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
        if re.search(r'\b(?:any|unlimited|no\s+limit)\s+budget\b', raw, re.IGNORECASE):
            fallback_budget = 999999
        # Try to extract explicit budget amount with currency (handles 2L, 5Cr, 2 Lakh, 5 Crore)
        m_budget = re.search(r'(\d[\d,]*)\s*(L|lakh|crore|cr|rupees|rs|inr|usd|\$|euros?|dollars?)\b', raw, re.IGNORECASE)
        if m_budget:
            val = float(m_budget.group(1).replace(",", ""))
            unit = m_budget.group(2).lower()
            if unit in ("l", "lakh"):
                val *= 100000
            elif unit in ("cr", "crore"):
                val *= 10000000
            fallback_budget = val
        # Try to extract bare number near budget context (including 2L, 5Cr without explicit currency keyword)
        if not m_budget:
            m_bare = re.search(r'\b(?:budget|spend|cost)\s*(?:of\s*)?(\d[\d,]*)\s*(L|lakh|crore|cr)?\b', raw, re.IGNORECASE)
            if m_bare:
                val = float(m_bare.group(1).replace(",", ""))
                unit = (m_bare.group(2) or "").lower()
                if unit in ("l", "lakh"):
                    val *= 100000
                elif unit in ("cr", "crore"):
                    val *= 10000000
                fallback_budget = val
        if re.search(r'\b(?:visit|explore|see)\s+(?:all|every)\b', raw, re.IGNORECASE):
            fallback_preferences.append("visit all places")

        # Calculate dates (N days means Day1 to DayN, so end = start + N - 1)
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=max(fallback_duration - 1, 0))

        return {
            **state,
            "destination": fallback_dest,
            "origin": fallback_origin,
            "travel_dates": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "duration_days": fallback_duration,
            "budget": float(fallback_budget),
            "num_travelers": 1,
            "adults": 1,
            "kids": 0,
            "infants": 0,
            "trip_style": state.get("trip_style", ""),
            "preferences": fallback_preferences,
            "currency": fallback_currency,
            "warnings": [f"Supervisor LLM parsing failed ({parsed.get('error', 'unknown')}). "
                         "Used regex fallback on raw text — some fields may be wrong."],
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
    
    # Post-process: if budget is 999999 but the user explicitly stated a numeric budget,
    # # extract it from the raw request (qwen2.5 often gets this wrong)
    import re as _re
    if float(budget) >= 999999:
        m = _re.search(r'(\d[\d,]*)\s*(?:lakh|cr|crore|rupees|rs|inr|usd|\$|euros?|dollars?)\b', state.get("user_request", ""), _re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", ""))
            unit = m.group(0).lower()
            if "lakh" in unit:
                val *= 100000
            elif "crore" in unit or "cr" in unit:
                val *= 10000000
            budget = val
            parsed["budget"] = budget
    
    n_travelers = int(parsed.get("num_travelers", 1))
    adults = int(parsed.get("adults", 1))
    kids = int(parsed.get("kids", 0))
    infants = int(parsed.get("infants", 0))
    if adults < 1:
        adults = 1
    if n_travelers < 1:
        n_travelers = adults + kids + infants

    return {
        **state,
        "destination":    parsed.get("destination", "Unknown"),
        "origin":         parsed.get("origin", "Unknown"),
        "travel_dates":   travel_dates,
        "duration_days":  duration_days,
        "num_travelers":  n_travelers,
        "adults":         adults,
        "kids":           kids,
        "infants":        infants,
        "trip_style":     state.get("trip_style", ""),
        "budget":         float(budget),
        "currency":       parsed.get("currency", "USD"),
        "preferences":    parsed.get("preferences", []),
        "confidence_score": float(parsed.get("confidence", 0.5)),
        "execution_trace": ["supervisor_agent"],
    }
