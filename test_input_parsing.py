#!/usr/bin/env python3
"""
Test script to verify supervisor agent correctly parses user input.
Tests: "I want to go to Riyadh for 10 days from India, at any budget, but visit all the places."
"""

import asyncio
import sys
from datetime import datetime, timedelta

# Test the supervisor agent directly
async def test_supervisor():
    from backend.agents.supervisor_agent import supervisor_agent
    
    user_request = "I want to go to Riyadh for 10 days from India, at any budget, but visit all the places."
    
    state = {
        "user_request": user_request,
        "provider": "ollama",
        "api_key": None,
    }
    
    print("=" * 80)
    print("TEST: Supervisor Agent Parsing")
    print("=" * 80)
    print(f"\nInput: {user_request}\n")
    
    result = await supervisor_agent(state)
    
    print(f"Destination:       {result.get('destination')}")
    print(f"Origin:            {result.get('origin')}")
    print(f"Currency:          {result.get('currency')}")
    print(f"Budget:            {result.get('budget')}")
    print(f"Travel Dates:      {result.get('travel_dates')}")
    print(f"Preferences:       {result.get('preferences')}")
    print(f"Confidence Score:  {result.get('confidence_score')}")
    print(f"\nExecution Trace:   {result.get('execution_trace')}")
    print(f"Warnings:          {result.get('warnings', [])}")
    
    # Verify expectations
    print("\n" + "=" * 80)
    print("VERIFICATION:")
    print("=" * 80)
    
    checks = [
        ("Destination is Riyadh", result.get('destination') and 'riyadh' in result.get('destination', '').lower()),
        ("Origin is India", result.get('origin') and 'india' in result.get('origin', '').lower()),
        ("Currency is INR", result.get('currency') == 'INR'),
        ("Budget is unlimited (999999)", result.get('budget') == 999999),
        ("Has 'visit all places' preference", any('all' in str(p).lower() for p in result.get('preferences', []))),
        ("Travel dates calculated", bool(result.get('travel_dates', {}).get('start') and result.get('travel_dates', {}).get('end'))),
    ]
    
    if result.get('travel_dates'):
        try:
            start = datetime.fromisoformat(result['travel_dates'].get('start', ''))
            end = datetime.fromisoformat(result['travel_dates'].get('end', ''))
            duration = (end - start).days + 1
            checks.append(("Duration is 10 days", duration == 10))
        except:
            checks.append(("Duration is 10 days", False))
    
    all_passed = True
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL CHECKS PASSED!")
    else:
        print("✗ SOME CHECKS FAILED - See above")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    try:
        passed = asyncio.run(test_supervisor())
        sys.exit(0 if passed else 1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
