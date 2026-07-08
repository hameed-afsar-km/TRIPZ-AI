import json
import asyncio
import os
import time
import logging
from typing import AsyncGenerator, Optional

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from graphs.trip_graph import trip_graph
from services.llm_service import token_callback_var
from memory.session_memory import session_memory

logger = logging.getLogger("tripz.agents")

router = APIRouter(prefix="/api/v1", tags=["trip"])


class TripRequest(BaseModel):
    user_request: str = Field(..., min_length=5)
    stream: bool = Field(default=True)
    provider: str = Field(default="ollama")
    api_key: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    agent_providers: Optional[dict] = Field(default=None)
    adults: int = Field(default=1, ge=1)
    kids: int = Field(default=0, ge=0)
    infants: int = Field(default=0, ge=0)
    trip_style: str = Field(default="")  # "standard" | "budget" | "luxury" from UI


class TripResponse(BaseModel):
    success: bool
    itinerary: dict
    execution_trace: list
    warnings: list
    confidence_score: float
    duration_ms: float
    cached: bool = False


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/plan/stream")
async def plan_trip_stream(request: TripRequest):
    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = time.time()
        agent_start_times = {}
        token_queue: asyncio.Queue = asyncio.Queue()

        # Load session context if available
        prev = None
        if request.session_id:
            prev = await session_memory.load(request.session_id)

        travelers = request.adults + request.kids + request.infants

        # Agent providers: frontend controls which agents use which provider.
        # When None (not sent), all agents use the main provider (default: ollama).
        agent_providers = request.agent_providers if request.agent_providers is not None else {}
        _AGENT_PROVIDER_DEFAULTS = {
            "supervisor": "ollama",
            "critic": "ollama",
            "routing": "ollama",
            "validator": "ollama",
            "itinerary": "ollama",
        }
        agent_providers = {**_AGENT_PROVIDER_DEFAULTS, **agent_providers}

        initial_state = {
            "user_request": request.user_request,
            "provider": request.provider,
            "api_key": request.api_key,
            "agent_providers": agent_providers,
            "adults": request.adults,
            "kids": request.kids,
            "infants": request.infants,
            "num_travelers": travelers,
            "trip_style": request.trip_style,
            "replan_count": 0,
            "warnings": [],
            "execution_trace": [],
            "visited_places": [],
            "needs_replanning": False,
            "confidence_score": 0.0,
            "replan_instructions": "",
        }
        if prev:
            initial_state["previous_context"] = prev

        logger.info("")
        logger.info("  ═══════════════════════════════════════════")
        logger.info("  🚀 TRIPZ AGENTS LAUNCHED")
        logger.info("     Request: %s", request.user_request)
        logger.info("     Travelers: %d (%d adults, %d kids, %d infants)", travelers, request.adults, request.kids, request.infants)
        logger.info("  ═══════════════════════════════════════════")
        logger.info("")
        yield _sse("start", {"message": "TRIPZ agents initializing...", "request": request.user_request})

        # ── Pre-flight provider health check ──
        if request.provider == "ollama":
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get("http://localhost:11434/api/tags")
                    if resp.status_code != 200:
                        yield _sse("error", {"message": f"Ollama returned status {resp.status_code}. Is it running?"})
                        return
                # Warm up model BEFORE graph starts — cold start adds 20-40s
                try:
                    async with httpx.AsyncClient(timeout=30) as wc:
                        await wc.post("http://localhost:11434/api/generate", json={
                            "model": "qwen2.5:1.5b",
                            "prompt": "hello",
                            "stream": False,
                            "keep_alive": "5m",
                        })
                except Exception:
                    pass  # warmup failure is non-fatal
            except (httpx.ConnectError, httpx.TimeoutException):
                yield _sse("error", {"message": "Cannot reach Ollama at localhost:11434. Start Ollama and try again."})
                return

        # ── Token streaming callback ──
        async def on_token(token: str):
            await token_queue.put(token)

        token_callback_var.set(on_token)

        # ── Merge graph events with token stream ──
        final_state_result = [None]
        graph_errored = [False]

        async def merged_stream():
            graph_done = False
            graph_events: asyncio.Queue = asyncio.Queue()
            last_state = None

            async def collect():
                nonlocal graph_done
                deadline = asyncio.get_event_loop().time() + 300
                try:
                    ait = trip_graph.astream_events(initial_state, {"recursion_limit": 100}, version="v1")
                    while True:
                        remaining = deadline - asyncio.get_event_loop().time()
                        if remaining <= 0:
                            raise asyncio.TimeoutError()
                        ev = await asyncio.wait_for(ait.__anext__(), timeout=remaining)
                        await graph_events.put(ev)
                except StopAsyncIteration:
                    pass
                except asyncio.TimeoutError:
                    await graph_events.put({"__type": "error", "data": "Graph execution timed out. Please try again or switch to a faster provider."})
                except Exception as e:
                    await graph_events.put({"__type": "error", "data": str(e)})
                finally:
                    graph_done = True

            task = asyncio.create_task(collect())

            try:
                while True:
                    try:
                        event = await asyncio.wait_for(graph_events.get(), timeout=0.05)
                    except asyncio.TimeoutError:
                        event = None

                    if event and event.get("__type") == "error":
                        if not graph_errored[0]:
                            graph_errored[0] = True
                            yield _sse("error", {"message": event["data"]})
                        return

                    if event:
                        kind = event.get("event", "")
                        name = event.get("name", "")

                        # Skip internal LangGraph internals and routing functions
                        # (they are not real agents and confuse the frontend)
                        _SKIP_NAMES = {
                            "LangGraph", "__start__",
                            "route_after_supervisor",  # conditional edge fn
                            "route_after_critic",      # conditional edge fn
                            # clarify_node NOT skipped — its output (itinerary) must be captured
                        }

                        if kind == "on_chain_start" and name not in _SKIP_NAMES:
                            agent_start_times[name] = time.time()
                            logger.info("  ▶ AGENT STARTED: %-20s  %s", name, _agent_label(name))
                            yield _sse("agent_start", {"agent": name, "message": _agent_label(name)})

                        elif kind == "on_chain_end" and name not in _SKIP_NAMES:
                            duration = time.time() - agent_start_times.get(name, time.time())
                            output = event.get("data", {}).get("output", {})
                            preview = _extract_preview(name, output)
                            preview_str = ""
                            if preview:
                                preview_str = " | " + " ".join(f"{k}={v}" for k, v in preview.items() if v)
                            # Strip out large blobs for the log preview
                            output_clean = _sanitize_output(name, output) if output else {}
                            logger.info("  ✔ AGENT COMPLETED: %-18s  (%.1fs)%s", name, duration, preview_str)
                            yield _sse("agent_complete", {
                                "agent": name,
                                "preview": preview,
                                "output": output_clean,
                                "duration_sec": round(duration, 1),
                            })
                            if output:
                                if last_state is None:
                                    last_state = {}
                                last_state.update(output)

                        elif kind == "on_chain_error" and name not in _SKIP_NAMES:
                            error_data = event.get("data", {})
                            error_msg = str(error_data.get("error", "Unknown error"))
                            logger.error("  ✘ AGENT ERROR: %-18s  %s", name, error_msg)
                            yield _sse("error", {"agent": name, "message": error_msg})
                            # Graph run will fail after this; absorb the follow-up __type:error
                            graph_errored[0] = True

                    flushed = 0
                    while not token_queue.empty():
                        token = token_queue.get_nowait()
                        yield _sse("token", {"token": token})
                        flushed += 1
                        if flushed >= 20:
                            await asyncio.sleep(0)
                            flushed = 0

                    if graph_done and graph_events.empty():
                        break

                while not token_queue.empty():
                    yield _sse("token", {"token": token_queue.get_nowait()})

                await task
            finally:
                if not task.done():
                    task.cancel()

            final_state_result[0] = last_state

        async for sse_msg in merged_stream():
            yield sse_msg

        final_state = final_state_result[0]

        duration_ms = (time.time() - start_time) * 1000

        if final_state:
            itin = final_state.get("itinerary", {})
            itin_title = itin.get("title", "Untitled")
            itin_days = len(itin.get("days", []))
            logger.info("")
            logger.info("  ═══════════════════════════════════════════")
            logger.info("  ✅ TRIPZ PIPELINE COMPLETE")
            logger.info("     Title: %s", itin_title)
            logger.info("     Days:  %s", itin_days)
            logger.info("     Time:  %.1fs", duration_ms / 1000)
            logger.info("  ═══════════════════════════════════════════")
            logger.info("")
            itin_error = itin.get("error") if isinstance(itin, dict) else None
            itin_error_type = itin.get("error_type") if isinstance(itin, dict) else None
            yield _sse("done", {
                "success": not bool(itin_error),
                "itinerary": itin,
                "destination": final_state.get("destination", ""),
                "origin": final_state.get("origin", ""),
                "user_request": final_state.get("user_request", ""),
                "budget": final_state.get("budget", 0),
                "currency": final_state.get("currency", ""),
                "duration_days": final_state.get("duration_days", 0),
                "execution_trace": final_state.get("execution_trace", []),
                "warnings": final_state.get("warnings", []),
                "confidence_score": final_state.get("confidence_score", 0.0),
                "critic_feedback": final_state.get("critic_feedback", ""),
                "duration_ms": round(duration_ms, 1),
                "cached": False,
                "error": itin_error,
                "error_type": itin_error_type,
            })
            if request.session_id:
                await session_memory.save(request.session_id, final_state)
        elif not graph_errored[0]:
            yield _sse("error", {"message": "No output state from graph"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/plan", response_model=TripResponse)
async def plan_trip(request: TripRequest) -> TripResponse:
    start_time = time.time()
    prev = None
    if request.session_id:
        prev = await session_memory.load(request.session_id)

    travelers = request.adults + request.kids + request.infants

    agent_providers = request.agent_providers if request.agent_providers is not None else {}
    _AGENT_PROVIDER_DEFAULTS = {
        "supervisor": "ollama",
        "critic": "ollama",
        "routing": "ollama",
        "validator": "ollama",
        "itinerary": "ollama",
    }
    agent_providers = {**_AGENT_PROVIDER_DEFAULTS, **agent_providers}

    initial_state = {
        "user_request": request.user_request,
        "provider": request.provider,
        "api_key": request.api_key,
        "agent_providers": agent_providers,
        "adults": request.adults,
        "kids": request.kids,
        "infants": request.infants,
        "num_travelers": travelers,
        "trip_style": request.trip_style,
        "replan_count": 0,
        "warnings": [],
        "execution_trace": [],
        "visited_places": [],
        "needs_replanning": False,
        "confidence_score": 0.0,
        "replan_instructions": "",
    }
    if prev:
        initial_state["previous_context"] = prev

    result = await trip_graph.ainvoke(initial_state, {"recursion_limit": 100})
    duration_ms = (time.time() - start_time) * 1000

    if request.session_id:
        await session_memory.save(request.session_id, result)

    return TripResponse(
        success=not bool(result.get("error")),
        itinerary=result.get("itinerary", {}),
        execution_trace=result.get("execution_trace", []),
        warnings=result.get("warnings", []),
        confidence_score=result.get("confidence_score", 0.0),
        duration_ms=round(duration_ms, 1),
        cached=False,
    )


@router.get("/health")
async def health():
    return {"status": "ok", "service": "TRIPZ-AI Backend"}


def _agent_label(name: str) -> str:
    labels = {
        "supervisor_agent": "Parsing your travel request...",
        "routing_agent":    "Determining trip style...",
        "budget_agent":     "Calculating budget & hotel options...",
        "transit_agent":    "Checking weather & transport...",
        "curator_agent":    "Curating top activities & viewpoints...",
        "validator_agent":  "Filtering non-tourist attractions...",
        "itinerary_agent":  "Crafting your day-by-day itinerary...",
        "critic_agent":     "Reviewing & validating your trip...",
        "clarify_node":     "Request needs clarification...",
    }
    return labels.get(name, f"Running {name}...")


AGENT_OUTPUT_KEYS = {
    "supervisor_agent": ["destination", "origin", "travel_dates", "duration_days",
                         "num_travelers", "adults", "kids", "infants",
                         "budget", "currency", "preferences", "trip_style", "confidence_score"],
    "routing_agent":    ["routing_decision"],
    "budget_agent":     ["hotels", "budget_breakdown"],
    "transit_agent":    ["weather", "transport"],
    "curator_agent":    ["activities"],
    "validator_agent":  ["activities"],  # filtered list (pass-through)
    "itinerary_agent":  ["itinerary"],  # returns {"markdown": "..."}
    "critic_agent":     ["replan_instructions", "needs_replanning", "replan_count"],
    "clarify_node":     ["itinerary"],
}

def _sanitize_output(agent: str, output: dict) -> dict:
    """Extract only the keys that this agent produced."""
    keys = AGENT_OUTPUT_KEYS.get(agent, [])
    return {k: output[k] for k in keys if k in output}


def _extract_preview(agent: str, output: dict) -> dict:
    if not output or not isinstance(output, dict):
        return {}
    if agent == "supervisor_agent":
        return {"destination": output.get("destination"), "budget": output.get("budget")}
    if agent == "routing_agent":
        return {"trip_type": output.get("routing_decision")}
    if agent == "transit_agent":
        return {
            "weather_ok": bool(output.get("weather")),
            "transport_recommended": bool(output.get("transport", {}).get("recommended")),
        }
    if agent == "curator_agent":
        return {
            "activities_found": len(output.get("activities", [])),
        }
    if agent == "budget_agent":
        return {
            "hotels_found": len(output.get("hotels", [])),
            "budget_ok": bool(output.get("budget_breakdown")),
        }
    if agent == "validator_agent":
        return {
            "activities_approved": len(output.get("activities", [])),
        }
    if agent == "itinerary_agent":
        itin = output.get("itinerary", {})
        md = itin.get("markdown", "")
        return {"markdown_len": len(md), "preview": md[:80] + "..." if len(md) > 80 else md}
    return {}
