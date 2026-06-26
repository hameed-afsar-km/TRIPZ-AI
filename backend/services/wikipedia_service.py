import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("tripz.agents")

WIKI_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "TRIPZ-AI/1.0 (travel planner; +https://github.com/tripz-ai)"

_shared_client: Optional[httpx.AsyncClient] = None
_venue_cache: Dict[str, Optional[Dict[str, Any]]] = {}
_SEMAPHORE_LIMIT = 5


async def _get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(timeout=3, headers={"User-Agent": _USER_AGENT})
    return _shared_client


async def _query_page(title: str) -> Optional[Dict[str, Any]]:
    """Fetch page data via action=query with extracts and coordinates."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|coordinates|pageprops",
        "exintro": 1,
        "explaintext": 1,
        "ppprop": "disambiguation",
        "format": "json",
        "redirects": 1,
    }
    try:
        client = await _get_client()
        resp = await client.get(WIKI_API, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            if pid == "-1":
                continue
            if "pageprops" in page and "disambiguation" in page["pageprops"]:
                return None
            return page
        return None
    except Exception:
        return None


async def _search_wikipedia(query: str) -> Optional[str]:
    """Search Wikipedia for a page title."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": 3,
    }
    try:
        client = await _get_client()
        resp = await client.get(WIKI_API, params=params)
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("search", [])
            if pages:
                return pages[0].get("title")
        return None
    except Exception:
        return None


_STOP_WORDS = {"the", "of", "in", "a", "an", "and", "at", "to", "for", "is", "on", "by", "de", "la", "el"}


def _title_matches(original: str, wiki_title: str) -> bool:
    """Check if the Wikipedia page title is reasonably related to the searched name."""
    if original.lower() == wiki_title.lower():
        return True
    orig_words = {w.lower() for w in original.split() if w.lower() not in _STOP_WORDS}
    wiki_words = {w.lower() for w in wiki_title.split() if w.lower() not in _STOP_WORDS}
    if not orig_words:
        return False
    overlap = len(orig_words & wiki_words)
    if len(orig_words) >= 3:
        return overlap >= 2
    return overlap >= 1


_venue_semaphore = asyncio.Semaphore(_SEMAPHORE_LIMIT)


async def _validate_single_venue(name: str, city: str) -> Dict[str, Any]:
    """Check if a venue name matches a real place on Wikipedia.

    Respects in-memory cache and concurrency semaphore.
    """
    cache_key = f"{name.lower()}|{city.lower()}"
    if cache_key in _venue_cache:
        cached = _venue_cache[cache_key]
        if cached is None:
            return {"exists": False, "original_name": name, "correct_name": None,
                    "coordinates": None, "description": "", "city_hint": None}
        return dict(cached)

    async with _venue_semaphore:
        result: Dict[str, Any] = {
            "exists": False,
            "original_name": name,
            "correct_name": None,
            "coordinates": None,
            "description": "",
            "city_hint": None,
        }

        page = await _query_page(name)
        if page is None:
            searched = await _search_wikipedia(f"{name} {city}")
            if searched:
                page = await _query_page(searched)
            if page is None:
                searched = await _search_wikipedia(name)
                if searched:
                    page = await _query_page(searched)

        if page is None:
            _venue_cache[cache_key] = None
            return result

        wiki_title = page.get("title", "")

        if not _title_matches(name, wiki_title):
            _venue_cache[cache_key] = None
            return result

        result["exists"] = True
        result["description"] = (page.get("extract", "") or "")[:300]
        result["correct_name"] = wiki_title

        coords = page.get("coordinates")
        if coords:
            result["coordinates"] = [coords[0].get("lat"), coords[0].get("lon")]

        extract = ((page.get("extract", "") or "")).lower()
        city_lower = city.lower()
        for part in city_lower.split(","):
            part = part.strip()
            if part and part in extract:
                result["city_hint"] = city
                break

        _venue_cache[cache_key] = result
        return result


async def validate_venues(names: List[str], city: str, max_venues: int = 10) -> List[Dict[str, Any]]:
    """Validate multiple venue names against Wikipedia in parallel.

    Only validates the first `max_venues` unique names to keep latency reasonable.
    Uses a semaphore to limit concurrent Wikipedia API calls and caches results.
    """
    seen = set()
    unique = []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            unique.append(n)

    unique = unique[:max_venues]
    if not unique:
        return []

    tasks = [validate_venue(name, city) for name in unique]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    final = []
    for r in results:
        if isinstance(r, dict):
            r["_batch_size"] = len(names)
            r["_validated_count"] = len(unique)
            final.append(r)
        else:
            final.append({"exists": False, "original_name": "unknown", "error": str(r)})
    return final


validate_venue = _validate_single_venue
