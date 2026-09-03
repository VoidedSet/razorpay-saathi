"""
graph.py — LangGraph multi-agent graph (Supervisor pattern).

Routing priority:
  1. Keyword match  (fast, deterministic — e.g. "checkout" → billing_agent)
  2. LLM routing    (flexible, for ambiguous messages)
  3. Safe default   → sales_agent

A2A support:
  Pass client_type="agent" + agent_profile={name, budget, preferences, currency}
  in the API request. System prompts adapt automatically.
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_llm, get_routing_llm


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:      Annotated[list, add_messages]
    next_agent:    str
    audit_log:     list[dict]
    client_type:   str         # "human" | "agent"
    cart:          list[dict]  # [{name, qty, price, currency}]
    agent_profile: dict        # A2A: {name, preferences, budget, currency}


# ── Routing helpers ───────────────────────────────────────────────────────────

# Checked BEFORE the LLM routing call. Order matters — first match wins.
_KEYWORD_ROUTES: list[tuple[str, list[str]]] = [
    ("billing_agent", [
        "checkout", "check out", "pay now", "proceed to pay", "i want to pay",
        "buy now", "place order", "complete purchase", "make payment",
        "proceed with purchase", "ready to buy", "i want to purchase",
        "proceed to purchase", "i want to buy", "want to order",
    ]),
    ("promo_agent", [
        "promo", "promotion", "coupon", "run campaign", "outreach",
        "best deal", "any deal", "any offer", "get a discount",
    ]),
]

_MANAGER_ROUTING_PROMPT = """\
Your only job: route the message to one agent. Reply with EXACTLY one of these \
three strings — nothing else, no punctuation, no explanation:

sales_agent
billing_agent
promo_agent

Rules:
- sales_agent   → browsing, product questions, recommendations, general chat
- billing_agent → checkout, payment, buy now, place order, complete purchase
- promo_agent   → deal requests, coupons, promotions, campaign creation

Message: {message}
Reply:"""


def _keyword_route(message: str) -> str | None:
    """O(n) keyword scan — checked before the LLM to catch obvious cases."""
    msg = message.lower()
    for agent, keywords in _KEYWORD_ROUTES:
        if any(kw in msg for kw in keywords):
            return agent
    return None


def _parse_routing_response(text: str) -> str:
    """
    Robustly extract agent name from potentially messy LLM output.
    Small models often add punctuation, caveats, or extra words.
    """
    text = text.lower().strip().rstrip(".")
    valid = {"sales_agent", "billing_agent", "promo_agent"}

    if text in valid:
        return text

    # Substring match — handles "I would say: billing_agent" etc.
    for agent in valid:
        if agent in text:
            return agent

    # Semantic keyword fallback — handles paraphrasing
    if any(w in text for w in ["billing", "checkout", "payment", "pay", "purchase"]):
        return "billing_agent"
    if any(w in text for w in ["promo", "marketing", "campaign", "deal", "coupon"]):
        return "promo_agent"

    return "sales_agent"   # safe default


# ── System prompts ────────────────────────────────────────────────────────────

_SALES_BASE = """\
You are an expert Sales Agent for a modern e-commerce store powered by Razorpay Saathi.

Rules:
1. Always cross-sell or upsell a complementary item when any product is mentioned.
   Example: User wants running shoes → also recommend moisture-wicking socks.
2. Keep replies concise (2–3 sentences) unless more detail is explicitly asked for.
3. Never fabricate prices or inventory — say you'll fetch live data from the store DB.
4. When the buyer signals intent to purchase, confirm the item(s) and instruct them \
to say "checkout" — you will hand them to the Billing Agent."""

_BILLING_BASE = """\
You are the Billing Agent for Razorpay Saathi — a checkout and payment specialist.

When a buyer says "checkout" or signals purchase intent:
1. Confirm the item(s) they want to buy and calculate an estimated total.
2. Announce that you are querying the Razorpay Offers API for bank-specific \
discounts (example: HDFC card → 5% cashback, Kotak → ₹500 off on orders above ₹10,000).
3. State that a Razorpay Payment Link is being generated and will appear as \
an interactive widget in this chat once the integration is wired.
4. Ask for any final confirmation (correct address, preferred payment method).

Be transactional, fast, and reassuring. The buyer is ready to pay — do not stall."""

_PROMO_BASE = """\
You are the Promo / Marketing Agent for Razorpay Saathi.

Capabilities:
- Surface current promotional offers and applicable Razorpay bank deals.
- Draft outreach copy (email / tweet) for stagnant inventory campaigns.
- Generate Razorpay Payment Links with Manager-approved discounts.

For this session: describe the promotion you would create and which \
Razorpay API calls you would make (Offers API + Payment Links API)."""

_AGENT_PROMPTS = {
    "sales_agent":   _SALES_BASE,
    "billing_agent": _BILLING_BASE,
    "promo_agent":   _PROMO_BASE,
}


def _build_system_prompt(base: str, state: AgentState) -> str:
    """Augment base prompt with buyer context — works for both human and AI agent."""
    client_type   = state.get("client_type", "human")
    agent_profile = state.get("agent_profile", {})
    cart          = state.get("cart", [])
    lines: list[str] = []

    # ── A2A client context ────────────────────────────────────────────────────
    if client_type == "agent":
        name   = agent_profile.get("name", "Automated Shopping Agent")
        budget = agent_profile.get("budget")
        prefs  = agent_profile.get("preferences", [])
        curr   = agent_profile.get("currency", "INR")

        lines.append("\n\n── A2A CLIENT ──────────────────────────────────────")
        lines.append(f"Type        : Automated AI shopping agent")
        lines.append(f"Name        : {name}")
        if budget:
            lines.append(f"Budget      : {curr} {budget:,}")
        if prefs:
            lines.append(f"Preferences : {', '.join(prefs)}")
        lines.append(
            "Behaviour   : Skip pleasantries. Be structured and efficient. "
            "Lead every response with data: price, availability, discount."
        )

    # ── Cart context ──────────────────────────────────────────────────────────
    if cart:
        lines.append("\n── CURRENT CART ────────────────────────────────────")
        total = 0
        for item in cart:
            curr_sym = item.get("currency", "INR")
            price    = item.get("price", 0)
            qty      = item.get("qty", 1)
            subtotal = price * qty
            total   += subtotal
            lines.append(
                f"  • {item.get('name', 'Item')} × {qty}  "
                f"@ {curr_sym} {price:,}  = {curr_sym} {subtotal:,}"
            )
        if total:
            lines.append(f"  TOTAL : {cart[0].get('currency', 'INR')} {total:,}")

    return base + "\n".join(lines)


# ── Agent labels (used by main.py for SSE audit events) ──────────────────────

AGENT_LABELS = {
    "manager":       "Manager Agent",
    "sales_agent":   "Sales Agent",
    "billing_agent": "Billing Agent",
    "promo_agent":   "Promo Agent",
}


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def manager_node(state: AgentState) -> dict:
    """
    Routing supervisor. Uses keyword matching first, LLM routing as fallback.
    Never streams tokens — this call is invisible to the user.
    """
    last_msg = state["messages"][-1].content

    # 1. Fast keyword routing
    keyword_hit = _keyword_route(last_msg)
    if keyword_hit:
        routing_decision = keyword_hit
        method = "keyword"
    else:
        # 2. LLM routing (small / fast model)
        llm    = get_routing_llm()
        prompt = _MANAGER_ROUTING_PROMPT.format(message=last_msg)
        resp   = await llm.ainvoke([HumanMessage(content=prompt)])
        routing_decision = _parse_routing_response(resp.content)
        method = "llm"

    label = AGENT_LABELS.get(routing_decision, routing_decision)
    return {
        "next_agent": routing_decision,
        "audit_log":  state.get("audit_log", []) + [{
            "agent":  "Manager Agent",
            "detail": f"[{method}] → {label}",
        }],
    }


async def _agent_node(state: AgentState, agent_key: str) -> dict:
    llm           = get_llm()
    system_prompt = _build_system_prompt(_AGENT_PROMPTS[agent_key], state)
    messages      = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response      = await llm.ainvoke(messages)

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + [{
            "agent":  AGENT_LABELS[agent_key],
            "detail": f"Response generated ({len(response.content)} chars)",
        }],
    }


async def sales_agent_node(state: AgentState)   -> dict:
    return await _agent_node(state, "sales_agent")

async def billing_agent_node(state: AgentState) -> dict:
    return await _agent_node(state, "billing_agent")

async def promo_agent_node(state: AgentState)   -> dict:
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
