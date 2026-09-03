"""
graph.py — LangGraph multi-agent graph (Supervisor pattern).

Architecture
------------
  [START]
    │
    ▼
  manager_node          ← lightweight LLM routing call
    │
    ├─ "sales_agent"   → sales_agent_node   ← main customer-facing LLM
    ├─ "billing_agent" → billing_agent_node  (stub — routes to sales for now)
    └─ "promo_agent"   → promo_agent_node    (stub — routes to sales for now)
         │
        [END]

Streaming
---------
  Tokens are emitted from `astream_events()` in main.py.
  The manager's routing LLM call is intentionally excluded from the
  token stream (we only stream agent nodes, not manager).
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.config import get_llm, get_routing_llm

# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:    Annotated[list, add_messages]  # full conversation history
    next_agent:  str                             # routing decision by manager
    audit_log:   list[dict]                      # human-readable audit trail


# ── System Prompts ────────────────────────────────────────────────────────────

MANAGER_ROUTING_PROMPT = """\
You are the Store Manager AI. Your ONLY job is to route the user's message to the right agent.

Reply with EXACTLY one of these strings — nothing else, no punctuation, no explanation:
  sales_agent     → product questions, browsing, recommendations, upselling, general chat
  billing_agent   → checkout, payment, pricing, discount requests, coupon codes
  promo_agent     → complaints about no deals, requesting promotions, cart abandonment

User message: {message}"""


SALES_AGENT_PROMPT = """\
You are an expert Sales Agent for a modern e-commerce store powered by Razorpay Saathi.

Your personality: warm, knowledgeable, subtly persuasive.

Your rules:
1. Always try to cross-sell or upsell a complementary item when a user mentions any product.
   Example: User asks for "running shoes" → recommend moisture-wicking socks too.
2. Be concise — 2-3 sentences max per response unless the user asks for more detail.
3. Never fabricate prices or availability. Say you'll fetch real-time data if asked.
4. If the user wants to buy, tell them to type "checkout" and you'll hand them to the Billing Agent."""


BILLING_AGENT_PROMPT = """\
You are the Billing Agent for a modern e-commerce store powered by Razorpay Saathi.
You specialise in payments, discounts, and Razorpay integrations.
For now, acknowledge the user's intent and tell them the Razorpay checkout widget is coming soon."""


PROMO_AGENT_PROMPT = """\
You are the Promo / Marketing Agent for a modern e-commerce store powered by Razorpay Saathi.
You handle promotions, deals, and cart-recovery campaigns.
For now, acknowledge the user's interest in deals and tell them a personalized offer is being generated."""


# ── Nodes ─────────────────────────────────────────────────────────────────────

AGENT_PROMPTS = {
    "sales_agent":   SALES_AGENT_PROMPT,
    "billing_agent": BILLING_AGENT_PROMPT,
    "promo_agent":   PROMO_AGENT_PROMPT,
}

AGENT_LABELS = {
    "manager":       "Manager Agent",
    "sales_agent":   "Sales Agent",
    "billing_agent": "Billing Agent",
    "promo_agent":   "Promo Agent",
}


async def manager_node(state: AgentState) -> dict:
    """
    Lightweight routing decision.
    Uses get_routing_llm() — can be a cheaper/faster model than the main agents.
    Does NOT stream tokens (routing output never shown to the user).
    """
    llm = get_routing_llm()
    last_message = state["messages"][-1].content

    prompt = MANAGER_ROUTING_PROMPT.format(message=last_message)
    response = await llm.ainvoke([HumanMessage(content=prompt)])

    routing_decision = response.content.strip().lower().strip(".")
    valid_agents = {"sales_agent", "billing_agent", "promo_agent"}
    if routing_decision not in valid_agents:
        routing_decision = "sales_agent"   # safe default

    audit_entry = {
        "agent":  "Manager Agent",
        "detail": f"Routing → {routing_decision.replace('_', ' ').title()}",
    }

    return {
        "next_agent": routing_decision,
        "audit_log":  state.get("audit_log", []) + [audit_entry],
    }


async def _agent_node(state: AgentState, agent_key: str) -> dict:
    """Shared implementation for all customer-facing agent nodes."""
    llm = get_llm()
    system_prompt = AGENT_PROMPTS[agent_key]

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages)

    audit_entry = {
        "agent":  AGENT_LABELS[agent_key],
        "detail": f"Response generated ({len(response.content)} chars)",
    }

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }


async def sales_agent_node(state: AgentState) -> dict:
    return await _agent_node(state, "sales_agent")


async def billing_agent_node(state: AgentState) -> dict:
    return await _agent_node(state, "billing_agent")


async def promo_agent_node(state: AgentState) -> dict:
    return await _agent_node(state, "promo_agent")


# ── Routing edge ──────────────────────────────────────────────────────────────

def route_after_manager(
    state: AgentState,
) -> Literal["sales_agent", "billing_agent", "promo_agent"]:
    return state.get("next_agent", "sales_agent")  # type: ignore[return-value]


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("manager",       manager_node)
    g.add_node("sales_agent",   sales_agent_node)
    g.add_node("billing_agent", billing_agent_node)
    g.add_node("promo_agent",   promo_agent_node)

    g.set_entry_point("manager")

    g.add_conditional_edges(
        "manager",
        route_after_manager,
        {
            "sales_agent":   "sales_agent",
            "billing_agent": "billing_agent",
            "promo_agent":   "promo_agent",
        },
    )

    g.add_edge("sales_agent",   END)
    g.add_edge("billing_agent", END)
    g.add_edge("promo_agent",   END)

    return g.compile()
