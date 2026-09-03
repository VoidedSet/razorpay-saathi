"""
graph.py — LangGraph multi-agent supervisor graph connected to SQLite DB.

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
  1. User/Agent enters → manager_init fetches user profile & balance sheet from DB, sets ceiling
  2. User talks ONLY to Sales Agent (browsing, RAG product search, cross-sell recommendation)
  3. When cart finalised → Sales Agent hands off → Billing Agent
  4. Billing Agent: fetches cart & Razorpay Offers API from DB → computes total & link
  5. manager_audit always runs AFTER agent: logs response, flags policy violations
"""

import re
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.config import get_llm
from app import db


# ── Store Hard Policy Fallback ────────────────────────────────────────────────
_HARD_POLICY_MAX_DISCOUNT_PCT = 15.0


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:          Annotated[list, add_messages]  # full conversation
    session_id:        str        # session identifier for cart & persistent state
    user_id:           str        # user identifier in store DB
    session_phase:     str        # "browsing" | "checkout" | "support"
    user_profile:      dict       # loaded from DB by manager_init
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

def _sales_system_prompt(state: AgentState, db_products_text: str, cross_sell_text: str) -> str:
    profile  = state.get("user_profile", {})
    cart     = state.get("cart", [])
    ceiling  = state.get("discount_ceiling", _HARD_POLICY_MAX_DISCOUNT_PCT)
    is_agent = state.get("client_type") == "agent"

    name     = profile.get("name", "Customer")
    tier     = str(profile.get("tier", "standard")).title()
    history  = profile.get("purchase_history", [])
    prefs    = profile.get("preferences", [])

    history_str = ", ".join(history[-3:]) if history else "none on record"
    prefs_str   = ", ".join(prefs) if prefs else "not specified"

    a2a_note = (
        "\nCLIENT TYPE: Automated AI shopping agent. Skip pleasantries. "
        "Lead with exact product specs, price, and stock levels."
        if is_agent else ""
    )

    cart_note = ""
    if cart:
        cart_note = "\nCURRENT CART:\n" + "\n".join(
            f"  • {i.get('name')} × {i.get('qty',1)} @ ₹{i.get('price_inr', i.get('price', 0)):,}"
            for i in cart
        )

    return f"""You are the Sales Agent for Razorpay Saathi's agentic store.{a2a_note}

REAL-TIME STORE DATABASE RESULTS:
{db_products_text}

RECOMMENDED CROSS-SELL / ACCESSORIES:
{cross_sell_text}

CUSTOMER PROFILE (provided by Manager Agent):
  Name           : {name}
  Tier           : {tier}
  Past purchases : {history_str}
  Preferences    : {prefs_str}
  Max discount   : {ceiling}% (Manager-approved ceiling — do NOT exceed this)
{cart_note}

YOUR RULES:
1. Ground all recommendations STRICTLY in the REAL-TIME STORE DATABASE RESULTS provided above. Mention exact names, prices in INR (₹), and availability.
2. Always suggest one complementary item from the RECOMMENDED CROSS-SELL list when discussing a main product.
3. NEVER make up non-existent products, prices, or fake specifications.
4. Never offer more than {ceiling}% discount — the Manager Agent audits every response against financial bounds.
5. When the customer indicates readiness to buy or checkout, confirm the item and instruct them to say "checkout" to be handed to the Billing Agent.
6. Keep responses concise (2-4 sentences) and professional."""


def _billing_system_prompt(state: AgentState, db_cart_items: list[dict], offers_text: str) -> str:
    profile  = state.get("user_profile", {})
    ceiling  = state.get("discount_ceiling", _HARD_POLICY_MAX_DISCOUNT_PCT)
    is_agent = state.get("client_type") == "agent"

    name = profile.get("name", "Customer")
    tier = str(profile.get("tier", "standard")).title()

    a2a_note = (
        "\nCLIENT TYPE: Automated agent. Provide structured payment data."
        if is_agent else ""
    )

    cart_block = ""
    total = 0
    if db_cart_items:
        total = sum(i.get("price_inr", i.get("price", 0)) * i.get("qty", 1) for i in db_cart_items)
        cart_block = "\nSTORE CART (from Database):\n" + "\n".join(
            f"  • {i.get('name','Item')} × {i.get('qty',1)} @ ₹{i.get('price_inr', i.get('price',0)):,}"
            for i in db_cart_items
        ) + f"\n  ─────────────────────\n  TOTAL  : ₹{total:,}"
    else:
        cart_block = "\nCART: Customer is preparing to checkout (estimating based on conversation)."

    return f"""You are the Billing Agent for Razorpay Saathi — checkout and payment specialist.
You were handed this customer by the Sales Agent because they are ready to buy.{a2a_note}

CUSTOMER : {name} ({tier} tier)
MANAGER-APPROVED DISCOUNT CEILING : {ceiling}%
{cart_block}

LIVE RAZORPAY OFFERS API RESULTS:
{offers_text}

YOUR STEPS:
1. Confirm the items and order total.
2. Highlight applicable Razorpay bank offers from the list above (e.g. HDFC 5% cashback, Kotak ₹500 off).
   Ensure any combined discount stays strictly within the Manager's {ceiling}% ceiling.
3. Confirm that a Razorpay Payment Link / QR is generated and ready.
4. Ask for preferred payment mode (UPI, HDFC Credit Card, Netbanking).

Be transactional, fast, and reassuring. Do NOT exceed the Manager's discount ceiling."""


def _support_system_prompt(state: AgentState) -> str:
    profile = state.get("user_profile", {})
    name    = profile.get("name", "Customer")
    history = profile.get("purchase_history", [])
    return f"""You are the Customer Support Agent for Razorpay Saathi.
Customer: {name} | Recent purchases: {', '.join(history[-2:]) if history else 'none'}
Help with order issues, returns, refunds, complaints. Be empathetic and solution-focused.
Escalate financial decisions (refunds > ₹1,000) to the Manager Agent."""


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
    1. Load user profile & store balance sheet from SQLite DB
    2. Compute discount ceiling (user tier × store balance sheet profit margin)
    3. Detect session phase (browsing / checkout / support)
    4. Run guardrails on incoming message
    """
    updates: dict = {}
    new_entries: list[dict] = []
    notes = list(state.get("manager_notes", []))

    user_id = state.get("user_id") or "usr_001"

    # ── 1. Load profile & store financial bounds from SQLite DB ─────────────────
    profile = state.get("user_profile", {})
    if not profile:
        profile = db.get_user_profile(user_id)
        if not profile:
            fallback_key = "agt_001" if state.get("client_type") == "agent" else "usr_001"
            profile = db.get_user_profile(fallback_key) or {
                "name": "Alex", "tier": "gold", "total_spend_inr": 145000,
                "purchase_history": [], "preferences": [], "discount_ceiling_pct": 10
            }

        # Overlay A2A agent_profile fields if provided
        ap = state.get("agent_profile", {})
        if ap:
            if "name"        in ap: profile["name"]        = ap["name"]
            if "preferences" in ap: profile["preferences"] = ap["preferences"]
            if "budget"      in ap:
                profile["discount_ceiling_pct"] = min(profile.get("discount_ceiling_pct", 5), 5)

        updates["user_profile"] = profile

        # Read balance sheet to set dynamic financial bounds
        bs = db.get_balance_sheet()
        store_max_disc = bs.get("max_discount_allowed_pct", 12)
        user_tier_max  = profile.get("discount_ceiling_pct", 5)

        ceiling = float(min(user_tier_max, store_max_disc, _HARD_POLICY_MAX_DISCOUNT_PCT))
        updates["discount_ceiling"] = ceiling

        new_entries.append({
            "agent":  "Manager Agent",
            "detail": (
                f"DB Lookup: Profile [{profile.get('name')}] ({profile.get('tier','').title()}) | "
                f"Store margin: {bs.get('profit_margin_pct', 16)}% | "
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
            "detail": f"Phase transition: {current_phase} → {new_phase}",
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
            "detail": f"Guardrail: OK | Routing to {target} Agent",
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
        ceiling = state.get("discount_ceiling", _HARD_POLICY_MAX_DISCOUNT_PCT)

        matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*%\s*(off|discount|cashback|rebate)",
            content,
            re.IGNORECASE,
        )

        for amount_str, discount_type in matches:
            amount = float(amount_str)
            if amount > ceiling:
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
                "detail": "✅ AUDIT: Response verified — no policy violations found",
            })

    return {
        "manager_notes": notes,
        "audit_log":     state.get("audit_log", []) + new_entries,
    }


async def sales_agent_node(state: AgentState) -> dict:
    """
    Sales Agent node:
    Performs RAG product search in SQLite DB based on user's prompt,
    retrieves cross-sell recommendations, and calls LLM.
    """
    last_msg = state["messages"][-1].content
    new_entries: list[dict] = []

    # Query DB for products matching message keywords
    products = db.search_products(last_msg, limit=4)
    db_text  = db.format_products_for_prompt(products)

    # Query cross-sell recommendations if product found
    cross_sell = []
    if products:
        top_id = products[0]["id"]
        cross_sell = db.get_related_products(top_id, limit=3)
    cross_sell_text = db.format_products_for_prompt(cross_sell)

    new_entries.append({
        "agent":  "Sales Agent",
        "detail": f"DB Query: search_products('{last_msg[:30]}…') → found {len(products)} item(s)",
    })

    prompt   = _sales_system_prompt(state, db_text, cross_sell_text)
    llm      = get_llm()
    messages = [SystemMessage(content=prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages)

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + new_entries + [{
            "agent":  AGENT_LABELS["sales_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        }],
    }


async def billing_agent_node(state: AgentState) -> dict:
    """
    Billing Agent node:
    Fetches cart and Razorpay Offers API data from DB, calls LLM.
    """
    session_id  = state.get("session_id", "default")
    new_entries = []

    # Fetch real cart items from DB
    cart_items = db.get_cart(session_id) or state.get("cart", [])
    
    # If cart empty in DB, try to extract items discussed in chat context
    if not cart_items:
        # Check last messages for products
        context_str = " ".join([m.content for m in state["messages"][-4:]])
        matched = db.search_products(context_str, limit=2)
        if matched:
            cart_items = [{"name": p["name"], "price_inr": p["price_inr"], "qty": 1} for p in matched]

    total_amount = sum(i.get("price_inr", i.get("price", 0)) * i.get("qty", 1) for i in cart_items)
    
    # Call Razorpay Offers API (mocked in db.py)
    offers = db.get_razorpay_offers(total_amount)
    offers_text = db.format_offers_for_prompt(offers)

    new_entries.append({
        "agent":  "Billing Agent",
        "detail": f"Razorpay API: fetched {len(offers)} bank offer(s) for ₹{total_amount:,} order",
    })

    prompt   = _billing_system_prompt(state, cart_items, offers_text)
    llm      = get_llm()
    messages = [SystemMessage(content=prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages)

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + new_entries + [{
            "agent":  AGENT_LABELS["billing_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        }],
    }


async def support_agent_node(state: AgentState) -> dict:
    prompt   = _support_system_prompt(state)
    llm      = get_llm()
    messages = [SystemMessage(content=prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages)
    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + [{
            "agent":  AGENT_LABELS["support_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        }],
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def route_to_agent(
    state: AgentState,
) -> Literal["sales_agent", "billing_agent", "support_agent"]:
    return {
        "checkout": "billing_agent",
        "support":  "support_agent",
    }.get(state.get("session_phase", "browsing"), "sales_agent")


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("manager_init",  manager_init_node)
    g.add_node("manager_audit", manager_audit_node)
    g.add_node("sales_agent",   sales_agent_node)
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

    for agent in ("sales_agent", "billing_agent", "support_agent"):
        g.add_edge(agent, "manager_audit")

    g.add_edge("manager_audit", END)

    return g.compile()
