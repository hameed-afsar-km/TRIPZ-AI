import asyncio, time, sys
sys.path.insert(0, r'D:\AI Agents\langgraph\TRIPZ-AI\backend')
from agents.routing_agent import routing_agent

async def test():
    start = time.time()
    result = await routing_agent({
        'user_request': '3 days in Tokyo with 1000 budget',
        'destination': 'Tokyo',
        'budget': 1000.0,
        'num_travelers': 1,
        'preferences': ['adventure', 'food'],
        'confidence_score': 0.8,
        'provider': 'ollama',
        'api_key': None,
        'replan_count': 0,
        'warnings': [],
        'execution_trace': [],
        'needs_replanning': False,
    })
    elapsed = time.time() - start
    print(f'Took {elapsed:.1f}s')
    print(f'Routing decision: {result.get("routing_decision")}')
    trace = result.get('execution_trace', [])
    print(f'Trace: {trace}')

asyncio.run(test())
