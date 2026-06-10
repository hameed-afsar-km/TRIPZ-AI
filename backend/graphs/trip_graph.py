"""
TRIPZ-AI Core Orchestration Graph
===================================
LangGraph StateGraph with:
  - Conditional routing
  - Parallel branch execution
  - Critic → Replan feedback loop (max 2 replans)
  - Explicit START/END nodes
  - Full state propagation

Graph Flow:
  START
    └─► supervisor_agent          [AI #1: parse request]
          └─► PARALLEL EXECUTION:
                ├─► routing_agent  [AI #2: classify workflow]
                ├─► budget_agent   [deterministic math]
                ├─► transit_agent  [tool calls]
                └─► curator_agent  [tool calls]
          └─► itinerary_agent      [AI #3: synthesize plan]
                └─► critic_agent   [AI #4: validate quality]
                      └─► (conditional)
                            ├─► needs_replanning=True → itinerary_agent [AI #5]
                            └─► needs_replanning=False → END
"""

import asyncio
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, START, END

from models.state import TripState
from agents.supervisor_agent import supervisor_agent
from agents.routing_agent import routing_agent
from agents.budget_agent import budget_agent
from agents.transit_agent import transit_agent
from agents.curator_agent import curator_agent
from agents.itinerary_agent import itinerary_agent
from agents.critic_agent import critic_agent


# ── Conditional Edge Functions ─────────────────────────────────────────────────
def route_after_supervisor(state: TripState) -> list[str]:
    user_request = state.get("user_request", "").strip()
    if len(user_request) < 4:
        return ["clarify_node"]
    return ["budget_agent", "transit_agent", "curator_agent", "routing_agent"]


def route_after_critic(state: TripState) -> Literal["itinerary_agent", "__end__"]:
    needs_replan = state.get("needs_replanning", False)
    replan_count = state.get("replan_count", 0)
    if needs_replan and replan_count < 2:
        return "itinerary_agent"
    return "__end__"


def clarify_node(state: TripState) -> TripState:
    return {
        **state,
        "itinerary": {
            "error": "clarification_needed",
            "message": (
                "Your request was too vague to generate a confident itinerary. "
                "Please provide: destination, approximate dates, budget, and number of travelers."
            ),
        },
        "execution_trace": state.get("execution_trace", []) + ["clarify_node"],
    }


# ── Graph Assembly ─────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(TripState)

    # ── Register all nodes ────────────────────────────────────────────────────
    graph.add_node("supervisor_agent",    supervisor_agent)
    graph.add_node("routing_agent",       routing_agent)
    graph.add_node("budget_agent",        budget_agent)
    graph.add_node("transit_agent",       transit_agent)
    graph.add_node("curator_agent",       curator_agent)
    graph.add_node("itinerary_agent",     itinerary_agent)
    graph.add_node("critic_agent",        critic_agent)
    graph.add_node("clarify_node",        clarify_node)

    # ── Wire edges ────────────────────────────────────────────────────────────
    graph.add_edge(START, "supervisor_agent")

    # supervisor → parallel agents (conditional)
    graph.add_conditional_edges(
        "supervisor_agent",
        route_after_supervisor,
        {
            "budget_agent":    "budget_agent",
            "transit_agent":   "transit_agent",
            "curator_agent":   "curator_agent",
            "routing_agent":   "routing_agent",
            "clarify_node":    "clarify_node",
        },
    )

    # Parallel agents → itinerary_agent
    graph.add_edge("budget_agent",        "itinerary_agent")
    graph.add_edge("transit_agent",       "itinerary_agent")
    graph.add_edge("curator_agent",       "itinerary_agent")
    graph.add_edge("routing_agent",       "itinerary_agent")

    # itinerary → critic
    graph.add_edge("itinerary_agent",     "critic_agent")

    # critic → itinerary (replan loop) or END
    graph.add_conditional_edges(
        "critic_agent",
        route_after_critic,
        {
            "itinerary_agent": "itinerary_agent",
            "__end__":         END,
        },
    )

    # clarify → END
    graph.add_edge("clarify_node",        END)

    return graph.compile()


# ── Singleton compiled graph (import this in API layer) ───────────────────────
trip_graph = build_graph()
