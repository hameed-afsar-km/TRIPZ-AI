import asyncio, time, sys
sys.path.insert(0, r'D:\AI Agents\langgraph\TRIPZ-AI\backend')
from agents.supervisor_agent import supervisor_agent

async def test():
    start = time.time()
    result = await supervisor_agent({
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
    print(f'Destination: {result.get("destination")}')
    print(f'Budget: {result.get("budget")}')
    print(f'Error: {result.get("error")}')

asyncio.run(test())
