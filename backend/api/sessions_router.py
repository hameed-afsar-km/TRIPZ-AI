from fastapi import APIRouter, HTTPException

from memory.session_memory import session_memory

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.get("")
async def list_sessions():
    sessions = await session_memory.list_sessions()
    return {"sessions": sessions}


@router.get("/{session_id}")
async def get_session(session_id: str):
    state = await session_memory.load(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    itin = state.get("itinerary", {})
    return {
        "session_id": session_id,
        "itinerary": itin,
        "destination": state.get("destination"),
        "execution_trace": state.get("execution_trace", []),
        "warnings": state.get("warnings", []),
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    await session_memory.delete(session_id)
    return {"deleted": True}
