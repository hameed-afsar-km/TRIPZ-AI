import asyncio, os, sys
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv()
import httpx

async def test():
    api_key = os.getenv('SERPAPI_API_KEY')
    print(f'Key loaded: {bool(api_key)}, length: {len(api_key) if api_key else 0}')

    params = {
        'engine': 'google_hotels',
        'q': 'hotels in Dubai',
        'check_in_date': '2026-07-01',
        'check_out_date': '2026-07-02',
        'currency': 'INR',
        'api_key': api_key,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get('https://serpapi.com/search', params=params)
        print(f'Status: {resp.status_code}')
        data = resp.json()
        if 'error' in data:
            print(f'API Error: {data["error"]}')
        else:
            props = data.get('properties', [])
            print(f'Properties found: {len(props)}')
            for p in props[:3]:
                print(f'  {p.get("name")} - rates: {p.get("rate_per_night")}')

asyncio.run(test())
