import re
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

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

# ── Agent labels (for SSE audit events) ──────────────────────────────────────

AGENT_LABELS = {
    "manager_init":  "Manager Agent",
    "manager_audit": "Manager Agent",
    "sales_agent":   "Sales Agent",
    "billing_agent": "Billing Agent",
    "support_agent": "Support Agent",
}


# ── Generative UI: component palette ──────────────────────────────────────────

def _product_card_props(product: dict, recommended: bool = False) -> dict:
    """Grounded `product_card` props from a DB product row (all values from the DB)."""
    specs = product.get("specs") or {}
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
        "image":       product.get("image_url") or product.get("image") or "",
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
