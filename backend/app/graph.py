from typing import Literal
from langgraph.graph import StateGraph, END

from app.state import AgentState
from app.agents.manager import manager_init_node, manager_audit_node
from app.agents.sales import sales_agent_node, sales_tools_node
from app.agents.billing import billing_agent_node
from app.agents.support import support_agent_node

# ── Routing ───────────────────────────────────────────────────────────────────

def route_to_agent(
    state: AgentState,
) -> Literal["sales_agent", "billing_agent", "support_agent"]:
    return {
        "checkout": "billing_agent",
        "support":  "support_agent",
    }.get(state.get("session_phase", "browsing"), "sales_agent")

def sales_should_continue(state: AgentState):
    """If the Sales Agent invoked tools, route to the tool executor."""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "sales_tools"
    return "manager_audit"

# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("manager_init",  manager_init_node)
    g.add_node("manager_audit", manager_audit_node)
    g.add_node("sales_agent",   sales_agent_node)
    g.add_node("sales_tools",   sales_tools_node)
    g.add_node("billing_agent", billing_agent_node)
    g.add_node("support_agent", support_agent_node)

    g.set_entry_point("manager_init")

    g.add_conditional_edges(
        "manager_init",
        route_to_agent,
        {
            "sales_agent":   "sales_agent",
            "billing_agent": "billing_agent",
            "support_agent": "support_agent",
        },
    )

    # Sales Agent can loop through tools before going to audit
    g.add_conditional_edges("sales_agent", sales_should_continue, {
        "sales_tools":   "sales_tools",
        "manager_audit": "manager_audit",
    })
    g.add_edge("sales_tools", "sales_agent")

    g.add_edge("billing_agent", "manager_audit")
    g.add_edge("support_agent", "manager_audit")

    g.add_edge("manager_audit", END)

    return g.compile()
