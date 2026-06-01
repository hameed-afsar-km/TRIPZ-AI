"""
Utility helpers shared across the system.
"""

import time
import functools
import asyncio
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger("tripz")


def timer(label: str = ""):
    """Decorator to log execution time of any async node."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await fn(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"[{label or fn.__name__}] completed in {elapsed:.1f}ms")
            return result
        return wrapper
    return decorator


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely coerce any value to float without raising."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 1) -> int:
    """Safely coerce any value to int without raising."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def truncate_for_prompt(text: str, max_chars: int = 2000) -> str:
    """
    Truncates text to a max character count before passing to an LLM prompt.
    Helps enforce token budgets and avoid context window overflow.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"


def merge_states(*states: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merges multiple partial state dicts into one.
    Later dicts take precedence for scalar values.
    Lists (traces, warnings) are concatenated.
    """
    merged: Dict[str, Any] = {}
    for state in states:
        if not isinstance(state, dict):
            continue
        for key, value in state.items():
            if key in ("execution_trace", "warnings", "critic_issues") and isinstance(value, list):
                existing = merged.get(key, [])
                merged[key] = existing + [v for v in value if v not in existing]
            else:
                merged[key] = value
    return merged
