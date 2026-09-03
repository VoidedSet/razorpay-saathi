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
from app import guardrails


# ── Store Hard Policy Fallback ────────────────────────────────────────────────
_HARD_POLICY_MAX_DISCOUNT_PCT = 15.0

# Max product cards streamed per search — keep the Gen UI restrained, not spammy.
_MAX_PRODUCT_CARDS = 3


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
    manager_correction: str       # user-visible Manager override, set by audit when a response is dirty
    ui_components:      list[dict] # generative-UI components streamed to the frontend registry
    just_entered_checkout: bool   # True only on the first turn we enter checkout (gates the widget)


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


# ── Reasoning-token stripper ───────────────────────────────────────────────────
# Reasoning models (e.g. Qwen) wrap chain-of-thought in <think>...</think>. It must
# never reach the customer OR the Manager's audit (the hidden reasoning can echo
# stray numbers that look like prices). main.py strips it from the live token
# stream; this strips the stored response before it is audited.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks (and any unterminated trailing think)."""
    if not text:
        return text
    cleaned = _THINK_RE.sub("", text)
    low = cleaned.lower()
    open_idx = low.rfind("<think>")
    if open_idx != -1 and "</think>" not in low[open_idx:]:
        cleaned = cleaned[:open_idx]
    return cleaned.strip()


# ── System prompts ────────────────────────────────────────────────────────────

def _sales_system_prompt(state: AgentState) -> str:
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

    return f"""You are the Sales Agent for Razorpay Saathi's agentic store.{a2a_note}

CUSTOMER PROFILE (provided by Manager Agent):
  Name           : {name}
  Tier           : {tier}
  Past purchases : {history_str}
  Preferences    : {prefs_str}
  Max discount   : {ceiling}% (Manager-approved ceiling — do NOT exceed this)

YOUR RULES:
1. GROUNDING — You may ONLY mention products, IDs, and prices returned by the
   `search_store_catalog` tool. NEVER invent a product id (do not make up ids like
   "prod_..._gold") and NEVER invent or alter a price. If you have not searched yet, search first.
2. CART — Use `add_to_cart` (with the exact product `id` from search results) to add items,
   `view_cart` to report the authoritative cart and total, and `clear_cart` to empty it.
   NEVER claim you added, removed, or totalled anything without calling the matching tool —
   the database cart is the only source of truth. Do not do cart math in your head.
3. PRICING AUTHORITY — You CANNOT change catalog prices or negotiate a lower rupee amount.
   If the customer haggles ("make it ₹27,999", "round it down", "what's your lowest?"), do NOT
   quote a made-up lower price. The only discount that exists is the Manager-approved ceiling of
   {ceiling}%, and real discounts are applied by the Billing Agent at checkout via verified
   Razorpay bank offers. Politely explain this instead of inventing a price.
4. When items are in the cart and the customer is ready to pay, tell them to say "checkout"
   to be handed to the Billing Agent.
5. The Manager Agent validates every response against the live catalog and the {ceiling}% ceiling.
   Fake products or below-ceiling prices are overridden and shown to the customer — so stay grounded.
6. Keep responses concise (2-4 sentences), professional, and free of emojis or decorative symbols."""


def _billing_system_prompt(
    state: AgentState,
    db_cart_items: list[dict],
    offers_text: str,
    payment_link_text: str = "",
) -> str:
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

RAZORPAY PAYMENT LINK:
{payment_link_text or "(will be generated once the order total is confirmed)"}

YOUR STEPS:
1. Confirm the items and order total exactly as shown in STORE CART above — do NOT invent
   products, prices, or a different total, and do NOT apply any discount beyond the {ceiling}% ceiling.
2. Highlight applicable Razorpay bank offers from the list above (e.g. HDFC 5% cashback, Kotak ₹500 off).
   Only reference offers that actually appear above; ensure any combined discount stays within {ceiling}%.
3. Share the Razorpay Payment Link shown above so the customer can pay.
4. Ask for preferred payment mode (UPI, HDFC Credit Card, Netbanking).

Be transactional, fast, and reassuring. Do NOT use emojis or decorative symbols. Do NOT exceed the Manager's discount ceiling."""


def _support_system_prompt(state: AgentState) -> str:
    profile = state.get("user_profile", {})
    name    = profile.get("name", "Customer")
    history = profile.get("purchase_history", [])
    return f"""You are the Customer Support Agent for Razorpay Saathi.
Customer: {name} | Recent purchases: {', '.join(history[-2:]) if history else 'none'}
Help with order issues, returns, refunds, complaints. Be empathetic and solution-focused.
Escalate financial decisions (refunds > ₹1,000) to the Manager Agent. Avoid emojis and decorative symbols."""


# ── Agent labels (for SSE audit events) ──────────────────────────────────────

AGENT_LABELS = {
    "manager_init":  "Manager Agent",
    "manager_audit": "Manager Agent",
    "sales_agent":   "Sales Agent",
    "billing_agent": "Billing Agent",
    "support_agent": "Support Agent",
}


# ── Generative UI: component palette ──────────────────────────────────────────
# The frontend holds a registry of predefined components keyed by these names.
# Agents "fill in the values" but the SERVER grounds every authoritative field
# (id / price / total / payment link) from the DB, so numbers can't be
# hallucinated. `custom` is the escape hatch: an agent authors it via the
# render_custom_ui tool when nothing predefined fits. Cards use a text monogram
# on the frontend — no emojis.


def _product_card_props(product: dict, recommended: bool = False) -> dict:
    """Grounded `product_card` props from a DB product row (all values from the DB)."""
    specs = product.get("specs") or {}
    # A few display-friendly specs (skip booleans like {"5g": true}).
    spec_items = [
        {"label": str(k), "value": str(v)}
        for k, v in list(specs.items())
        if not isinstance(v, bool)
    ][:3]
    return {
        "id":          product["id"],
        "name":        product["name"],
        "brand":       product.get("brand", ""),
        "category":    product.get("category", ""),
        "price":       product["price_inr"],
        "currency":    "INR",
        "image":       product.get("image_url") or "",   # no image column yet → monogram fallback
        "description": product.get("description", ""),
        "stock":       product.get("stock", 0),
        "specs":       spec_items,
        "recommended": recommended,
    }


def _checkout_widget_props(cart_items: list[dict], total: int, offers: list[dict],
                           payment_link: dict | None, ceiling: float) -> dict:
    """Grounded `checkout_widget` props (cart + Razorpay offers + payment link)."""
    items = [{
        "id":    i["id"],
        "name":  i["name"],
        "qty":   i.get("qty", 1),
        "price": i.get("price_inr", i.get("price", 0)),
    } for i in cart_items]

    offer_rows = []
    for o in offers:
        if o["type"] == "cashback":
            label = f"{o['bank']}: {o['discount_pct']}% cashback (max ₹{o['max_discount_inr']:,})"
        elif o["type"] == "instant_discount":
            label = f"{o['bank']}: ₹{o['discount_flat_inr']:,} instant off"
        elif o["type"] == "emi_cashback":
            label = f"{o['bank']}: {o['discount_pct']}% EMI cashback (max ₹{o['max_discount_inr']:,})"
        else:
            label = o.get("bank", "Bank offer")
        offer_rows.append({
            "label":  label,
            "code":   o.get("offer_code", ""),
            "method": o.get("payment_method", ""),
        })

    return {
        "items":    items,
        "total":    total,
        "currency": "INR",
        "offers":   offer_rows,
        "payment_link": (
            {"url": payment_link.get("short_url", ""), "id": payment_link.get("id", "")}
            if payment_link else None
        ),
        "ceiling":  ceiling,
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
    # Surface the checkout widget only on the FIRST turn we enter checkout — not on
    # every later billing turn (payment-mode follow-ups, etc.).
    updates["just_entered_checkout"] = new_phase == "checkout" and current_phase != "checkout"

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
        notes.append(f"Guardrail: {violation} detected in message")
        new_entries.append({
            "agent":  "Manager Agent",
            "detail": f"GUARDRAIL TRIGGERED: {violation} — request sanitised",
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

    Validates the agent's response against the live catalog and the
    Manager-approved discount ceiling (see guardrails.audit_response):
      • hallucinated product ids     → blocked
      • absolute-rupee discounts      → caught (not just literal "N% off")
      • explicit over-ceiling "N%"    → caught
    A dirty response also produces a user-visible Manager correction.
    """
    new_entries: list[dict] = []
    notes = list(state.get("manager_notes", []))
    updates: dict = {}

    last_ai = next(
        (m for m in reversed(state["messages"])
         if hasattr(m, "type") and m.type == "ai" and m.content),
        None,
    )

    if last_ai:
        ceiling = state.get("discount_ceiling", _HARD_POLICY_MAX_DISCOUNT_PCT)
        cart    = db.get_cart(state.get("session_id", "default"))
        audit   = guardrails.audit_response(_strip_think(last_ai.content), ceiling, cart)

        new_entries.extend(guardrails.audit_log_entries(audit, ceiling))

        if not audit["clean"]:
            updates["manager_correction"] = guardrails.build_manager_correction(audit, ceiling)
            for pid in audit["hallucinated_ids"]:
                notes.append(f"VIOLATION: hallucinated product {pid}")
            for v in audit["price_violations"]:
                notes.append(
                    f"VIOLATION: {v['name']} quoted ₹{v['quoted']:,} "
                    f"(≈{v['effective_pct']:g}% > {ceiling:g}% ceiling)"
                )
            for v in audit["pct_violations"]:
                notes.append(f"VIOLATION: {v['pct']:g}% {v['type']} > {ceiling:g}% ceiling")

    updates["manager_notes"] = notes
    updates["audit_log"]     = state.get("audit_log", []) + new_entries
    return updates


def _sales_tools():
    # We define dummy tool schemas here so bind_tools works.
    # The actual execution happens in sales_tools_node.
    def search_store_catalog(query: str):
        """Searches the real-time store database for products matching the query."""
        pass
    def add_to_cart(product_id: str, qty: int = 1):
        """Adds a specific product to the user's cart. MUST use the exact product 'id' from search results."""
        pass
    def view_cart():
        """Returns the authoritative cart contents and total from the database. Use this before quoting any cart total."""
        pass
    def clear_cart():
        """Removes all items from the user's cart."""
        pass
    def render_custom_ui(title: str, body: str = "", bullets: str = "",
                         cta_label: str = "", cta_message: str = ""):
        """Render a CUSTOM generative-UI card in the chat when NO standard component fits.
        Standard components are the product cards (shown automatically when you search) and
        the checkout widget. Use this for things like a short comparison, a summary, or a
        promo note. `bullets` is a newline-separated list. `cta_label` + `cta_message`
        optionally add a button that sends `cta_message` as the customer's next chat message.
        Do NOT use this to quote prices or invent products — product cards carry verified pricing."""
        pass
    return [search_store_catalog, add_to_cart, view_cart, clear_cart, render_custom_ui]

async def sales_agent_node(state: AgentState) -> dict:
    """
    Sales Agent node:
    Uses Native Tool Calling to search SQLite DB and add items to cart.
    """
    prompt   = _sales_system_prompt(state)
    llm      = get_llm().bind_tools(_sales_tools())
    
    # We don't prepend the system prompt if the last message was a tool result,
    # to avoid context stuffing, or we can just prepend it safely.
    # Keep only the last 8 messages to save tokens for Groq limits
    messages = [SystemMessage(content=prompt)] + list(state["messages"])[-8:]
    response = await llm.ainvoke(messages)
    
    new_entries = []
    if not response.tool_calls:
        new_entries.append({
            "agent":  AGENT_LABELS["sales_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        })

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + new_entries,
    }

from langchain_core.messages import ToolMessage

async def sales_tools_node(state: AgentState) -> dict:
    """
    Executes tools requested by the Sales Agent (search DB, add to cart).
    """
    last_msg = state["messages"][-1]
    responses = []
    new_entries = []
    components: list[dict] = []
    session_id = state.get("session_id", "default")
    
    for call in last_msg.tool_calls:
        name = call["name"]
        args = call["args"]
        
        if name == "search_store_catalog":
            query = args.get("query", "")
            products = db.search_products(query, limit=4)
            db_text  = db.format_products_for_prompt(products)

            cross_sell = []
            if products:
                cross_sell = db.get_related_products(products[0]["id"], limit=3)
                if cross_sell:
                    db_text += f"\n\nRECOMMENDED CROSS-SELL / ACCESSORIES:\n{db.format_products_for_prompt(cross_sell)}"

            # Gen UI: stream a few grounded product cards — deduped and capped so the
            # chat never gets spammed. Search hits first, then recommended cross-sell
            # fills any remaining slots.
            seen_card_ids: set[str] = set()
            n_search_cards = n_rec_cards = 0
            for p in products:
                if len(seen_card_ids) >= _MAX_PRODUCT_CARDS:
                    break
                if p["id"] in seen_card_ids:
                    continue
                seen_card_ids.add(p["id"])
                components.append({"component": "product_card", "props": _product_card_props(p)})
                n_search_cards += 1
            for p in cross_sell:
                if len(seen_card_ids) >= _MAX_PRODUCT_CARDS:
                    break
                if p["id"] in seen_card_ids:
                    continue
                seen_card_ids.add(p["id"])
                components.append({"component": "product_card", "props": _product_card_props(p, recommended=True)})
                n_rec_cards += 1

            responses.append(ToolMessage(content=db_text, tool_call_id=call["id"], name=name))
            new_entries.append({
                "agent": "Sales Agent",
                "detail": f"Tool Call: search_store_catalog('{query[:20]}') → found {len(products)} item(s)",
            })
            if products:
                new_entries.append({
                    "agent": "Sales Agent",
                    "detail": (
                        f"Gen UI: streamed {n_search_cards + n_rec_cards} product card(s)"
                        + (f" (+{n_rec_cards} recommended)" if n_rec_cards else "")
                    ),
                })
            
        elif name == "add_to_cart":
            product_id = args.get("product_id", "")
            qty = args.get("qty", 1)
            success = db.add_to_cart(session_id, product_id, qty)
            if success:
                msg = f"Successfully added {qty}x {product_id} to cart."
            else:
                msg = f"Failed: product {product_id} not found in database."
                
            responses.append(ToolMessage(content=msg, tool_call_id=call["id"], name=name))
            new_entries.append({
                "agent": "Sales Agent",
                "detail": f"Tool Call: add_to_cart('{product_id}', {qty}) → {'Success' if success else 'Failed'}",
            })

        elif name == "view_cart":
            cart_items = db.get_cart(session_id)
            if cart_items:
                total = sum(i.get("price_inr", 0) * i.get("qty", 1) for i in cart_items)
                lines = "\n".join(
                    f"  • [{i['id']}] {i['name']} × {i.get('qty', 1)} @ ₹{i['price_inr']:,}"
                    for i in cart_items
                )
                msg = f"CART ({len(cart_items)} item(s)):\n{lines}\n  TOTAL: ₹{total:,}"
            else:
                msg = "Cart is empty."
            responses.append(ToolMessage(content=msg, tool_call_id=call["id"], name=name))
            new_entries.append({
                "agent": "Sales Agent",
                "detail": f"Tool Call: view_cart() → {len(cart_items)} item(s)",
            })

        elif name == "clear_cart":
            db.clear_cart(session_id)
            responses.append(ToolMessage(content="Cart cleared.", tool_call_id=call["id"], name=name))
            new_entries.append({
                "agent": "Sales Agent",
                "detail": "Tool Call: clear_cart() → cart emptied",
            })

        elif name == "render_custom_ui":
            title       = args.get("title", "") or "Details"
            body        = args.get("body", "")
            bullets_raw = args.get("bullets", "") or ""
            bullets     = [b.strip(" -•\t") for b in bullets_raw.split("\n") if b.strip()]
            cta_label   = args.get("cta_label", "")
            cta_message = args.get("cta_message", "")
            components.append({
                "component": "custom",
                "props": {
                    "title":   title,
                    "body":    body,
                    "bullets": bullets,
                    "cta":     ({"label": cta_label, "message": cta_message or cta_label}
                                if cta_label else None),
                },
            })
            responses.append(ToolMessage(
                content=f"Custom UI card '{title}' rendered to the customer.",
                tool_call_id=call["id"], name=name,
            ))
            new_entries.append({
                "agent": "Sales Agent",
                "detail": f"Gen UI: render_custom_ui('{title[:24]}')",
            })

    return {
        "messages": responses,
        "audit_log": state.get("audit_log", []) + new_entries,
        "ui_components": state.get("ui_components", []) + components,
    }


async def billing_agent_node(state: AgentState) -> dict:
    """
    Billing Agent node:
    Fetches cart and Razorpay Offers API data from DB, calls LLM.
    """
    session_id  = state.get("session_id", "default")
    new_entries = []

    # Fetch real cart items from DB
    cart_items = db.get_cart(session_id)
    
    # We no longer guess cart from chat context; cart_items is authoritative from the add_to_cart tool.

    total_amount = sum(i.get("price_inr", i.get("price", 0)) * i.get("qty", 1) for i in cart_items)
    
    # Call Razorpay Offers API (mocked in db.py)
    offers = db.get_razorpay_offers(total_amount)
    offers_text = db.format_offers_for_prompt(offers)

    new_entries.append({
        "agent":  "Billing Agent",
        "detail": f"Razorpay API: fetched {len(offers)} bank offer(s) for ₹{total_amount:,} order",
    })

    # Generate a Razorpay Payment Link for the confirmed total (mocked in db.py)
    payment_link_text = ""
    link = None
    if total_amount > 0:
        link = db.get_payment_link(session_id, total_amount)
        payment_link_text = db.format_payment_link_for_prompt(link)
        new_entries.append({
            "agent":  "Billing Agent",
            "detail": f"Razorpay API: payment link {link['id']} → {link['short_url']} (₹{total_amount:,})",
        })

    # Gen UI: stream a grounded checkout widget (cart + Razorpay offers + payment link),
    # but only when the customer FIRST enters checkout — re-rendering the full widget on
    # every payment-mode follow-up spams the chat.
    components: list[dict] = []
    if cart_items and state.get("just_entered_checkout", True):
        ceiling = state.get("discount_ceiling", _HARD_POLICY_MAX_DISCOUNT_PCT)
        components.append({
            "component": "checkout_widget",
            "props": _checkout_widget_props(cart_items, total_amount, offers, link, ceiling),
        })
        new_entries.append({
            "agent":  "Billing Agent",
            "detail": f"Gen UI: streamed checkout widget (₹{total_amount:,}, {len(offers)} offer(s))",
        })

    prompt   = _billing_system_prompt(state, cart_items, offers_text, payment_link_text)
    llm      = get_llm()
    # Keep context small — billing agent only needs the last few turns, not the full history
    messages = [SystemMessage(content=prompt)] + list(state["messages"])[-6:]
    response = await llm.ainvoke(messages)

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + new_entries + [{
            "agent":  AGENT_LABELS["billing_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        }],
        "ui_components": state.get("ui_components", []) + components,
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
