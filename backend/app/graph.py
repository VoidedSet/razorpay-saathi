"""
graph.py — LangGraph multi-agent supervisor graph.

Architecture (from design doc):

                    ┌────────────────────────────────┐
                    │        Manager Agent            │
                    │  (Supervisor — never visible    │
                    │   to user, always watching)     │
                    └──────┬──────────────────────────┘
              oversees ↕   ↕   ↕   ↕
     ┌──────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐
     │  Sales Agent │←→│ Billing Agent │  │Marketing Agent│  │ Support Agent   │
     └──────────────┘  └───────────────┘  │(async/outbound│  │(direct access)  │
                                           │not in chat UI)│  └─────────────────┘
                                           └───────────────┘

User flow:
  1. User/Agent enters → manager_init fetches profile, sets discount ceiling
  2. User talks ONLY to Sales Agent (browsing, recommendations, upsell)
  3. When cart finalised → Sales Agent hands off → Billing Agent
  4. Billing Agent: Razorpay Offers API → discount → Payment Link
  5. manager_audit always runs AFTER agent: logs response, flags violations

The Manager is NOT a router. It is a supervisor with guardrails.
Phase (browsing/checkout/support) is derived from conversation state — not LLM.
Marketing Agent is async/outbound only (not in this conversational graph).
"""

import re
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.config import get_llm


# ── Mock data (replaced by SQLite in next step) ───────────────────────────────

_MOCK_PROFILES: dict[str, dict] = {
    "usr_default": {
        "user_id":           "usr_001",
        "name":              "Alex",
        "tier":              "gold",
        "purchase_history":  ["Samsung Galaxy S10", "AirPods Pro", "Mi Band 6"],
        "preferences":       ["electronics", "Samsung", "premium"],
        "total_spend_inr":   145_000,
        "discount_ceiling_pct": 10,   # manager-approved max for this user
    },
    "agent_default": {
        "user_id":           "agt_001",
        "name":              "Automated Agent",
        "tier":              "enterprise",
        "purchase_history":  [],
        "preferences":       [],
        "total_spend_inr":   0,
        "discount_ceiling_pct": 5,
    },
}

_STORE_POLICY = {
    "max_discount_pct":          15,    # hard ceiling — no agent can exceed this
    "min_order_for_discount_inr": 5_000,
}


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:          Annotated[list, add_messages]  # full conversation
    session_phase:     str        # "browsing" | "checkout" | "support"
    user_profile:      dict       # loaded by manager_init on first turn
    cart:              list[dict] # [{name, qty, price, currency}]
    audit_log:         list[dict] # running log of all agent actions
    manager_notes:     list[str]  # guardrail flags accumulated by manager
    discount_ceiling:  float      # max discount % manager has approved for session
    client_type:       str        # "human" | "agent"
    agent_profile:     dict       # A2A: {name, preferences, budget, currency}


# ── Phase detection (pure function — no LLM) ──────────────────────────────────

_CHECKOUT_KEYWORDS = [
    "checkout", "check out", "pay now", "proceed to pay", "i want to pay",
    "buy now", "place order", "complete purchase", "make payment",
    "ready to buy", "i want to purchase", "i want to buy", "want to order",
    "proceed to purchase", "proceed with purchase",
]

_SUPPORT_KEYWORDS = [
    "support", "customer care", "complaint", "issue with my order",
    "return", "refund", "exchange", "my order is wrong",
]

_BACK_TO_BROWSE_KEYWORDS = [
    "continue shopping", "add more", "keep browsing", "show me more",
    "back to shopping",
]

def _detect_phase(message: str, current_phase: str) -> str:
    """
    Deterministic phase detection. No LLM involved.
    Priority: checkout > support > back-to-browse > keep current > default browsing
    """
    msg = message.lower()
    if any(kw in msg for kw in _CHECKOUT_KEYWORDS):
        return "checkout"
    if any(kw in msg for kw in _SUPPORT_KEYWORDS):
        return "support"
    if any(kw in msg for kw in _BACK_TO_BROWSE_KEYWORDS):
        return "browsing"
    # Sticky: once in checkout or support, stay unless explicitly switching
    if current_phase in ("checkout", "support"):
        return current_phase
    return "browsing"


# ── Guardrail patterns ────────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+|previous\s+|your\s+)?instructions", "prompt injection attempt"),
    (r"(100|full|complete)\s*%\s*(off|discount)",           "extreme discount request"),
    (r"you\s+are\s+now\s+",                                  "role override attempt"),
    (r"\bact\s+as\b",                                        "role override attempt"),
    (r"\bbypass\b",                                          "bypass attempt"),
    (r"DAN\b",                                               "jailbreak pattern"),
]


# ── System prompts ────────────────────────────────────────────────────────────

def _sales_system_prompt(state: AgentState) -> str:
    profile  = state.get("user_profile", {})
    cart     = state.get("cart", [])
    ceiling  = state.get("discount_ceiling", _STORE_POLICY["max_discount_pct"])
    is_agent = state.get("client_type") == "agent"

    name     = profile.get("name", "Customer")
    tier     = profile.get("tier", "standard").title()
    history  = profile.get("purchase_history", [])
    prefs    = profile.get("preferences", [])

    history_str = ", ".join(history[-3:]) if history else "none on record"
    prefs_str   = ", ".join(prefs) if prefs else "not specified"

    a2a_note = (
        "\nCLIENT TYPE: Automated AI shopping agent. Skip pleasantries. "
        "Lead with product specs, price, and availability."
        if is_agent else ""
    )

    cart_note = ""
    if cart:
        cart_note = "\nCURRENT CART:\n" + "\n".join(
            f"  • {i.get('name')} × {i.get('qty',1)} @ ₹{i.get('price',0):,}"
            for i in cart
        )

    return f"""You are the Sales Agent for Razorpay Saathi's agentic store.{a2a_note}

CUSTOMER PROFILE (provided by Manager Agent):
  Name           : {name}
  Tier           : {tier}
  Past purchases : {history_str}
  Preferences    : {prefs_str}
  Max discount   : {ceiling}% (Manager-approved ceiling — do NOT exceed this)
{cart_note}

YOUR RULES:
1. Personalise every response using the profile above — reference past purchases and preferences.
2. Always cross-sell a complementary product when any item is mentioned.
3. Never fabricate prices — say you will fetch live data from the store database.
4. Never offer more than {ceiling}% discount — the Manager Agent audits every response.
5. When the customer signals purchase intent, confirm the item(s) and explicitly tell them
   you are now handing them off to the Billing Agent to complete checkout.
6. Keep replies to 2–3 sentences unless more detail is requested."""


def _billing_system_prompt(state: AgentState) -> str:
    profile  = state.get("user_profile", {})
    cart     = state.get("cart", [])
    ceiling  = state.get("discount_ceiling", _STORE_POLICY["max_discount_pct"])
    is_agent = state.get("client_type") == "agent"

    name = profile.get("name", "Customer")
    tier = profile.get("tier", "standard").title()

    a2a_note = (
        "\nCLIENT TYPE: Automated agent. Provide structured payment data."
        if is_agent else ""
    )

    cart_block = ""
    if cart:
        total = sum(i.get("price", 0) * i.get("qty", 1) for i in cart)
        cart_block = "\nCART:\n" + "\n".join(
            f"  • {i.get('name','Item')} × {i.get('qty',1)}  @ ₹{i.get('price',0):,}"
            for i in cart
        ) + f"\n  ─────────────────────\n  TOTAL  : ₹{total:,}"

    return f"""You are the Billing Agent for Razorpay Saathi — checkout and payment specialist.
You were handed this customer by the Sales Agent because they are ready to buy.{a2a_note}

CUSTOMER : {name} ({tier} tier)
MANAGER-APPROVED DISCOUNT CEILING : {ceiling}%
{cart_block}

YOUR STEPS:
1. Confirm the items and total from the cart (or what the customer stated).
2. Check Razorpay Offers API for bank-specific discounts. Examples:
     - HDFC credit card  → 5% cashback (up to ₹1,000)
     - Kotak debit card  → ₹500 off on orders ≥ ₹10,000
     - Only apply if total discount stays within the {ceiling}% ceiling.
3. State that a Razorpay Payment Link is being generated and will appear
   as an interactive widget in this chat.
4. Confirm payment method preference (UPI / card / net banking).

Be transactional, fast, and reassuring. Do NOT exceed the Manager's discount ceiling."""


def _support_system_prompt(state: AgentState) -> str:
    profile = state.get("user_profile", {})
    name    = profile.get("name", "Customer")
    history = profile.get("purchase_history", [])
    return f"""You are the Customer Support Agent for Razorpay Saathi.
Customer: {name} | Recent purchases: {', '.join(history[-2:]) if history else 'none'}
Help with order issues, returns, refunds, complaints. Be empathetic and solution-focused.
Escalate financial decisions (refunds > ₹1,000) to the Manager Agent."""


_PROMPT_BUILDERS = {
    "sales_agent":   _sales_system_prompt,
    "billing_agent": _billing_system_prompt,
    "support_agent": _support_system_prompt,
}


# ── Agent labels (for SSE audit events) ──────────────────────────────────────

AGENT_LABELS = {
    "manager_init":  "Manager Agent",
    "manager_audit": "Manager Agent",
    "sales_agent":   "Sales Agent",
    "billing_agent": "Billing Agent",
    "support_agent": "Support Agent",
}


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def manager_init_node(state: AgentState) -> dict:
    """
    Supervisor — runs BEFORE every agent turn.
    1. Load user profile (first turn only)
    2. Set discount ceiling (user tier × store policy)
    3. Detect session phase (browsing / checkout / support)
    4. Run guardrails on incoming message
    """
    updates: dict = {}
    new_entries: list[dict] = []
    notes = list(state.get("manager_notes", []))

    # ── 1. Load profile ───────────────────────────────────────────────────────
    profile = state.get("user_profile", {})
    if not profile:
        key     = "agent_default" if state.get("client_type") == "agent" else "usr_default"
        profile = dict(_MOCK_PROFILES[key])
        # Overlay A2A agent_profile fields if provided
        ap = state.get("agent_profile", {})
        if ap:
            if "name"        in ap: profile["name"]        = ap["name"]
            if "preferences" in ap: profile["preferences"] = ap["preferences"]
            if "budget"      in ap:
                # Translate budget to discount ceiling
                profile["discount_ceiling_pct"] = min(
                    profile["discount_ceiling_pct"],
                    5,   # agents default to conservative ceiling
                )
        updates["user_profile"] = profile

        ceiling = min(
            profile.get("discount_ceiling_pct", 5),
            _STORE_POLICY["max_discount_pct"],
        )
        updates["discount_ceiling"] = ceiling

        new_entries.append({
            "agent":  "Manager Agent",
            "detail": (
                f"Profile loaded: {profile['name']} | "
                f"{profile['tier'].title()} tier | "
                f"Spend: ₹{profile['total_spend_inr']:,} | "
                f"Discount ceiling: {ceiling}%"
            ),
        })

    # ── 2. Detect phase ───────────────────────────────────────────────────────
    last_msg      = state["messages"][-1].content
    current_phase = state.get("session_phase", "browsing")
    new_phase     = _detect_phase(last_msg, current_phase)
    updates["session_phase"] = new_phase

    if new_phase != current_phase:
        new_entries.append({
            "agent":  "Manager Agent",
            "detail": f"Phase: {current_phase} → {new_phase}",
        })

    # ── 3. Guardrails ─────────────────────────────────────────────────────────
    violation = None
    for pattern, label in _INJECTION_PATTERNS:
        if re.search(pattern, last_msg, re.IGNORECASE):
            violation = label
            break

    if violation:
        notes.append(f"⚠️ Guardrail: {violation} detected in message")
        new_entries.append({
            "agent":  "Manager Agent",
            "detail": f"🚨 GUARDRAIL TRIGGERED: {violation} — request sanitised",
        })
    else:
        target = {"checkout": "Billing", "support": "Support"}.get(new_phase, "Sales")
        new_entries.append({
            "agent":  "Manager Agent",
            "detail": f"Guardrail: OK | Handing to {target} Agent",
        })

    updates["manager_notes"] = notes
    updates["audit_log"]     = state.get("audit_log", []) + new_entries
    return updates


async def manager_audit_node(state: AgentState) -> dict:
    """
    Supervisor — runs AFTER every agent turn.
    1. Log the agent's response
    2. Scan for discount percentage claims — flag if above ceiling
    """
    new_entries: list[dict] = []
    notes = list(state.get("manager_notes", []))

    last_ai = next(
        (m for m in reversed(state["messages"])
         if hasattr(m, "type") and m.type == "ai"),
        None,
    )

    if last_ai:
        content = last_ai.content
        ceiling = state.get("discount_ceiling", _STORE_POLICY["max_discount_pct"])

        # Scan for any discount % claims
        matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*%\s*(off|discount|cashback|rebate)",
            content,
            re.IGNORECASE,
        )

        flagged = False
        for amount_str, discount_type in matches:
            amount = float(amount_str)
            if amount > ceiling:
                flagged = True
                notes.append(f"VIOLATION: {amount}% {discount_type} exceeds {ceiling}% ceiling")
                new_entries.append({
                    "agent":  "Manager Agent",
                    "detail": (
                        f"🚨 AUDIT VIOLATION: Agent claimed {amount}% {discount_type} "
                        f"(ceiling={ceiling}%) — logged for review"
                    ),
                })
            else:
                new_entries.append({
                    "agent":  "Manager Agent",
                    "detail": f"✅ AUDIT: {amount}% {discount_type} within approved {ceiling}% ceiling",
                })

        if not matches:
            new_entries.append({
                "agent":  "Manager Agent",
                "detail": "✅ AUDIT: Response logged — no financial claims to verify",
            })

    return {
        "manager_notes": notes,
        "audit_log":     state.get("audit_log", []) + new_entries,
    }


async def _run_agent(state: AgentState, agent_key: str) -> dict:
    llm      = get_llm()
    prompt   = _PROMPT_BUILDERS[agent_key](state)
    messages = [SystemMessage(content=prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages)
    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + [{
            "agent":  AGENT_LABELS[agent_key],
            "detail": f"Response ready ({len(response.content)} chars)",
        }],
    }


async def sales_agent_node(state: AgentState) -> dict:
    return await _run_agent(state, "sales_agent")

async def billing_agent_node(state: AgentState) -> dict:
    return await _run_agent(state, "billing_agent")

async def support_agent_node(state: AgentState) -> dict:
    return await _run_agent(state, "support_agent")


# ── Routing ───────────────────────────────────────────────────────────────────

def route_to_agent(
    state: AgentState,
) -> Literal["sales_agent", "billing_agent", "support_agent"]:
    """Manager-set phase determines agent — not message content."""
    return {
        "checkout": "billing_agent",
        "support":  "support_agent",
    }.get(state.get("session_phase", "browsing"), "sales_agent")


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    # Supervisor nodes
    g.add_node("manager_init",  manager_init_node)
    g.add_node("manager_audit", manager_audit_node)

    # Worker agent nodes
    g.add_node("sales_agent",   sales_agent_node)
    g.add_node("billing_agent", billing_agent_node)
    g.add_node("support_agent", support_agent_node)

    # Flow: always start with supervisor
    g.set_entry_point("manager_init")

    # Manager decides which agent based on session phase
    g.add_conditional_edges(
        "manager_init",
        route_to_agent,
        {
            "sales_agent":   "sales_agent",
            "billing_agent": "billing_agent",
            "support_agent": "support_agent",
        },
    )

    # All agents always report back to manager audit
    for agent in ("sales_agent", "billing_agent", "support_agent"):
        g.add_edge(agent, "manager_audit")

    g.add_edge("manager_audit", END)

    return g.compile()
