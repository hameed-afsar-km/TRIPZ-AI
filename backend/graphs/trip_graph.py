"""
TRIPZ-AI Core Orchestration Graph
===================================
This is the BRAIN of the system. Every agent and tool is wired here
as a LangGraph StateGraph with:
  - Conditional routing
  - Parallel branch execution
  - Critic → Replan feedback loop
  - Explicit START/END nodes
  - Full state propagation

Graph Flow:
  START
    └─► supervisor_agent          [AI #1: parse request]
          └─► routing_agent       [AI #2: classify workflow]
                └─► (conditional branch)
                      ├─► "standard"/"budget"/"luxury"
                      │     └─► PARALLEL EXECUTION:
                      │           ├─► weather_tool
                      │           ├─► hotel_tool
                      │           ├─► activity_tool
                      │           ├─► transport_tool
                      │           └─► budget_agent
                      │     └─► itinerary_agent     [AI #3: synthesize]
                      │           └─► critic_agent   [AI #4: validate]
                      │                 └─► (conditional)
                      │                       ├─► needs_replanning=True
                      │                       │     └─► replanning_agent
                      │                       │           └─► critic_agent (loop back)
                      │                       └─► needs_replanning=False
                      │                             └─► END
                      └─► "replan" → END (early exit, request clarification)
"""

import asyncio
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, START, END

from models.state import TripState
from agents.supervisor_agent import supervisor_agent
from agents.budget_agent import budget_agent
from agents.transit_agent import transit_agent
from agents.curator_agent import curator_agent
from agents.itinerary_agent import itinerary_agent


# ── Conditional Edge Functions ─────────────────────────────────────────────────
def route_after_supervisor(state: TripState) -> list[str]:
    """
    Conditional edge: only sends to clarify_node when the raw user
    input is completely empty or nonsensical (< 4 chars).
    We NEVER block on extracted destination being 'Unknown' because
    small local LLMs (Qwen, Gemma) can fail JSON parsing on valid
    requests, producing Unknown as a fallback artifact.
    """
    user_request = state.get("user_request", "").strip()

    # Only ask for clarification when there is virtually no input at all
    if len(user_request) < 4:
        return ["clarify_node"]
    return ["budget_agent", "transit_agent", "curator_agent"]


def clarify_node(state: TripState) -> TripState:
    """
    Lightweight terminal node for low-confidence/ambiguous requests.
    Adds a clarification message instead of generating a bad itinerary.
    """
    return {
        "itinerary": {
            "error": "clarification_needed",
            "message": (
                "Your request was too vague to generate a confident itinerary. "
                "Please provide: destination, approximate dates, budget, and number of travelers."
            ),
        },
        "execution_trace": ["clarify_node"],
    }


# ── Graph Assembly ─────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    """
    Assembles and compiles the full TRIPZ-AI LangGraph StateGraph.
    Call once at startup; reuse the compiled graph for all requests.
    """
    graph = StateGraph(TripState)

    # ── Register all nodes ────────────────────────────────────────────────────
    graph.add_node("supervisor_agent",    supervisor_agent)
    graph.add_node("budget_agent",        budget_agent)
    graph.add_node("transit_agent",       transit_agent)
    graph.add_node("curator_agent",       curator_agent)
    graph.add_node("itinerary_agent",     itinerary_agent)
    graph.add_node("clarify_node",        clarify_node)

    # ── Wire linear edges ─────────────────────────────────────────────────────
    graph.add_edge(START,                 "supervisor_agent")

    # ── Conditional edge: supervisor_agent → parallel agents OR clarify ────────
    graph.add_conditional_edges(
        "supervisor_agent",
        route_after_supervisor,
        {
            "budget_agent": "budget_agent",
            "transit_agent": "transit_agent",
            "curator_agent": "curator_agent",
            "clarify_node": "clarify_node",
        },
    )


    # ── Wire parallel outputs back to itinerary_agent ─────────────────────────
    graph.add_edge("budget_agent",        "itinerary_agent")
    graph.add_edge("transit_agent",       "itinerary_agent")
    graph.add_edge("curator_agent",       "itinerary_agent")

    # ── From synthesis to END ─────────────────────────────────────────────────
    graph.add_edge("itinerary_agent",     END)
    graph.add_edge("clarify_node",        END)

    return graph.compile()


# ── Singleton compiled graph (import this in API layer) ───────────────────────
trip_graph = build_graph()

