"""
In-memory session store for multi-turn conversation support.
Stores past TripState objects keyed by session_id.

Design:
- Simple dict-based store (swap with Redis in production)
- TTL-based expiry to avoid memory leaks
- Thread-safe via asyncio.Lock
"""

import asyncio
import time
from typing import Any, Dict, Optional

# TTL in seconds (30 minutes default)
SESSION_TTL = 60 * 30


class SessionMemory:
    def __init__(self, ttl: int = SESSION_TTL):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self._created: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self.ttl = ttl

    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        async with self._lock:
            self._store[session_id] = state
            now = time.time()
            self._timestamps[session_id] = now
            if session_id not in self._created:
                self._created[session_id] = now

    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            ts = self._timestamps.get(session_id)
            if ts and (time.time() - ts) > self.ttl:
                del self._store[session_id]
                del self._timestamps[session_id]
                self._created.pop(session_id, None)
                return None
            return self._store.get(session_id)

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._store.pop(session_id, None)
            self._timestamps.pop(session_id, None)
            self._created.pop(session_id, None)

    async def list_sessions(self) -> list[Dict[str, Any]]:
        """Return all non-expired sessions with summary metadata."""
        async with self._lock:
            now = time.time()
            sessions = []
            expired = []
            for k in list(self._store.keys()):
                ts = self._timestamps.get(k)
                if ts and (now - ts) > self.ttl:
                    expired.append(k)
                    continue
                state = self._store.get(k, {})
                itin = state.get("itinerary", {})
                created = self._created.get(k, ts)
                sessions.append({
                    "session_id": k,
                    "title": itin.get("title", "Untitled"),
                    "destination": state.get("destination", "Unknown"),
                    "timestamp": ts,
                    "created_at": created,
                })
            for k in expired:
                del self._store[k]
                del self._timestamps[k]
                self._created.pop(k, None)
            sessions.sort(key=lambda s: s["timestamp"], reverse=True)
            return sessions

    async def purge_expired(self) -> int:
        """Remove all expired sessions. Call periodically."""
        async with self._lock:
            now = time.time()
            expired = [k for k, ts in self._timestamps.items() if now - ts > self.ttl]
            for k in expired:
                del self._store[k]
                del self._timestamps[k]
                self._created.pop(k, None)
            return len(expired)


# Singleton — import this in routers that need session persistence
session_memory = SessionMemory()
