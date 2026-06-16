import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("tripz.agents")

WIKI_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "TRIPZ-AI/1.0 (travel planner; +https://github.com/tripz-ai)"


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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(WIKI_API, params=params, headers={"User-Agent": _USER_AGENT})
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(WIKI_API, params=params, headers={"User-Agent": _USER_AGENT})
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
    return len(orig_words & wiki_words) >= 1


async def validate_venue(name: str, city: str) -> Dict[str, Any]:
    """Check if a venue name matches a real place on Wikipedia.

    Returns:
        {
            "exists": bool,
            "original_name": str,
            "correct_name": str | None,
            "coordinates": [lat, lon] | None,
            "description": str,
            "city_hint": str | None,
        }
    """
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
        return result

    wiki_title = page.get("title", "")

    if not _title_matches(name, wiki_title):
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

    return result


async def validate_venues(names: List[str], city: str) -> List[Dict[str, Any]]:
    """Validate multiple venue names against Wikipedia in parallel (batched)."""
    results = []
    for i in range(0, len(names), 5):
        batch = names[i:i + 5]
        tasks = [validate_venue(name, city) for name in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in batch_results:
            if isinstance(r, dict):
                results.append(r)
            else:
                results.append({"exists": False, "original_name": "unknown", "error": str(r)})
    return results
