import asyncio, sys
sys.path.insert(0, r'D:\AI Agents\langgraph\TRIPZ-AI\backend')

async def test():
    from graphs.trip_graph import trip_graph
    
    initial_state = {
        'user_request': '3 days in Tokyo with 1000 budget',
        'provider': 'ollama',
        'api_key': None,
        'replan_count': 0,
        'warnings': [],
        'execution_trace': [],
        'needs_replanning': False,
    }
    
    event_count = 0
    start = asyncio.get_event_loop().time()
    
    async for event in trip_graph.astream_events(initial_state, version="v2"):
        kind = event.get("event", "")
        name = event.get("name", "")
        event_count += 1
        elapsed = asyncio.get_event_loop().time() - start
        
        if kind in ("on_chain_start", "on_chain_end"):
            print(f"[{elapsed:6.1f}s] event={kind} name={name}")
        
        if event_count > 50:
            print("Too many events, stopping")
            break
    
    total = asyncio.get_event_loop().time() - start
    print(f"\nTotal events: {event_count}, Total time: {total:.1f}s")

asyncio.run(test())
