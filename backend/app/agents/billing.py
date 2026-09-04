from langchain_core.messages import SystemMessage
from app.config import get_llm
from app import db
from app.state import (
    AgentState,
    _HARD_POLICY_MAX_DISCOUNT_PCT,
    AGENT_LABELS,
    _strip_think,
    _checkout_widget_props,
)

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
        "\\nCLIENT TYPE: Automated agent. Provide structured payment data."
        if is_agent else ""
    )

    cart_block = ""
    total = 0
    if db_cart_items:
        total = sum(i.get("price_inr", i.get("price", 0)) * i.get("qty", 1) for i in db_cart_items)
        cart_block = "\\nSTORE CART (from Database):\\n" + "\\n".join(
            f"  • {i.get('name','Item')} × {i.get('qty',1)} @ ₹{i.get('price_inr', i.get('price',0)):,}"
            for i in db_cart_items
        ) + f"\\n  ─────────────────────\\n  TOTAL  : ₹{total:,}"
    else:
        cart_block = "\\nCART: Customer is preparing to checkout (estimating based on conversation)."

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

async def billing_agent_node(state: AgentState) -> dict:
    session_id  = state.get("session_id", "default")
    new_entries = []

    # Fetch real cart items from DB
    cart_items = db.get_cart(session_id)
    
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

    # Gen UI: stream a grounded checkout widget
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
    # Keep context small
    messages = [SystemMessage(content=prompt)] + list(state["messages"])[-6:]
    response = await llm.ainvoke(messages)
    if hasattr(response, "content") and response.content:
        response.content = _strip_think(response.content)

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + new_entries + [{
            "agent":  AGENT_LABELS["billing_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        }],
        "ui_components": state.get("ui_components", []) + components,
    }
