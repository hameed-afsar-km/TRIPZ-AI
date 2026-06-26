import json
import os
from typing import Dict, List, Optional


_known_attractions: Optional[Dict[str, List[str]]] = None


def _load() -> Dict[str, List[str]]:
    global _known_attractions
    if _known_attractions is not None:
        return _known_attractions
    path = os.path.join(os.path.dirname(__file__), "..", "data", "known_attractions.json")
    try:
        with open(path, encoding="utf-8") as f:
            _known_attractions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _known_attractions = {}
    return _known_attractions


def get_known_attractions(destination: str) -> List[str]:
    all_known = _load()
    key = destination.lower().strip()
    if key in all_known:
        return list(all_known[key])
    for known_key, attractions in all_known.items():
        if known_key in key or key in known_key:
            return list(attractions)
    return []


def is_known_attraction(name: str, destination: str) -> bool:
    known = get_known_attractions(destination)
    name_lower = name.lower().strip()
    for ka in known:
        if ka.lower().strip() == name_lower:
            return True
    return False
