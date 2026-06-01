import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/api/v1/plan/stream",
            json={
                "user_request": "3 days in Tokyo with 1000 budget",
                "stream": True,
                "provider": "ollama",
                "api_key": None,
            }
        ) as resp:
            print(f"Status: {resp.status_code}")
            event_count = 0
            async for line in resp.aiter_lines():
                if line.startswith("event:") or line.startswith("data:"):
                    print(f"  {line}")
                    event_count += 1
                if event_count > 20:
                    break

asyncio.run(test())
