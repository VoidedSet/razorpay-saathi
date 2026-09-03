"""
graph.py — LangGraph graph shell.
Currently a stub. Will grow into the full Supervisor → Agent graph.
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict


class AgentState(TypedDict):
    """Shared state that flows through every node in the graph."""
    messages: list
    active_agent: str
    audit_log: list


def _placeholder_node(state: AgentState) -> AgentState:
    """Temporary no-op node. Will be replaced by real agents."""
    state["audit_log"].append("placeholder_node: called")
    return state


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("placeholder", _placeholder_node)
    graph.set_entry_point("placeholder")
    graph.add_edge("placeholder", END)
    return graph.compile()
