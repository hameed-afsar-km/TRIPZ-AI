import asyncio, time, sys
sys.path.insert(0, r'D:\AI Agents\langgraph\TRIPZ-AI\backend')

async def test():
    print("Importing graph...")
    from graphs.trip_graph import trip_graph
    
    print("Starting graph invoke...")
    start = time.time()
    state = await trip_graph.ainvoke({
        'user_request': '3 days in Tokyo with 1000 budget',
        'provider': 'ollama',
        'api_key': None,
        'replan_count': 0,
        'warnings': [],
        'execution_trace': [],
        'needs_replanning': False,
    })
    elapsed = time.time() - start
    print(f'Took {elapsed:.1f}s')
    print(f'Destination: {state.get("destination")}')
    print(f'Routing: {state.get("routing_decision")}')
    trace = state.get('execution_trace', [])
    print(f'Trace (last 10): {trace[-10:]}')
    itin = state.get('itinerary', {})
    if 'error' in itin:
        print(f'Error itinerary: {itin.get("message", itin["error"])}')
    else:
        print(f'Title: {itin.get("title", "N/A")}')
        print(f'Days: {len(itin.get("days", []))}')

asyncio.run(test())
