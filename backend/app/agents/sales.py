from langchain_core.messages import ToolMessage, SystemMessage
from app.config import get_llm
from app import db
from app.state import (
    AgentState,
    _HARD_POLICY_MAX_DISCOUNT_PCT,
    _MAX_PRODUCT_CARDS,
    AGENT_LABELS,
    _strip_think,
    _product_card_props,
)

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
        "\\nCLIENT TYPE: Automated AI shopping agent. Skip pleasantries. "
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
2. NO VERBAL REPETITION OF PRODUCT CARDS — Rich interactive product cards (Gen UI) displaying exact pricing, specs, descriptions, and imagery are automatically rendered directly below your chat response. Do NOT list out every product name, price, or full description in your plain text response! Keep your text brief (2-3 sentences), warm, and conversational (e.g. "Here are our top Yeezy drops matching your request! Check out the product cards below—the Zebra colorway is a customer favorite. Let me know if you'd like to inspect any pair or move to checkout.").
3. CART — Use `add_to_cart` (with the exact product `id` from search results) to add items,
   `view_cart` to report the authoritative cart and total, and `clear_cart` to empty it.
   NEVER claim you added, removed, or totalled anything without calling the matching tool —
   the database cart is the only source of truth. Do not do cart math in your head.
4. PRICING AUTHORITY — You CANNOT change catalog prices or negotiate a lower rupee amount.
   If the customer haggles ("make it ₹27,999", "round it down", "what's your lowest?"), do NOT
   quote a made-up lower price. The only discount that exists is the Manager-approved ceiling of
   {ceiling}%, and real discounts are applied by the Billing Agent at checkout via verified
   Razorpay bank offers. Politely explain this instead of inventing a price.
5. When items are in the cart and the customer is ready to pay, tell them to say "checkout"
   to be handed to the Billing Agent.
6. The Manager Agent validates every response against the live catalog and the {ceiling}% ceiling.
   Fake products or below-ceiling prices are overridden and shown to the customer — so stay grounded.
7. Keep responses concise (2-3 sentences), professional, and free of emojis or decorative symbols."""

def _sales_tools():
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
    prompt   = _sales_system_prompt(state)
    llm      = get_llm().bind_tools(_sales_tools())
    
    messages = [SystemMessage(content=prompt)] + list(state["messages"])[-8:]
    response = await llm.ainvoke(messages)
    if hasattr(response, "content") and response.content:
        response.content = _strip_think(response.content)
    
    new_entries = []
    if not hasattr(response, "tool_calls") or not response.tool_calls:
        new_entries.append({
            "agent":  AGENT_LABELS["sales_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        })

    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + new_entries,
    }

async def sales_tools_node(state: AgentState) -> dict:
    last_msg = state["messages"][-1]
    responses = []
    new_entries = []
    components: list[dict] = []
    session_id = state.get("session_id", "default")
    
    for call in last_msg.tool_calls:
        name = call["name"]
        args = call["args"]
        
        try:
            if name == "search_store_catalog":
                query = args.get("query", "")
                products = db.search_products(query, limit=4)
                db_text  = db.format_products_for_prompt(products)

                cross_sell = []
                if products:
                    cross_sell = db.get_related_products(products[0]["id"], limit=3)
                    if cross_sell:
                        db_text += f"\\n\\nRECOMMENDED CROSS-SELL / ACCESSORIES:\\n{db.format_products_for_prompt(cross_sell)}"

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
                    lines = "\\n".join(
                        f"  • [{i['id']}] {i['name']} × {i.get('qty', 1)} @ ₹{i['price_inr']:,}"
                        for i in cart_items
                    )
                    msg = f"CART ({len(cart_items)} item(s)):\\n{lines}\\n  TOTAL: ₹{total:,}"
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
                bullets     = [b.strip(" -•\\t") for b in bullets_raw.split("\\n") if b.strip()]
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
            else:
                responses.append(ToolMessage(content=f"Unknown tool: {name}", tool_call_id=call["id"], name=name))
        except Exception as e:
            responses.append(ToolMessage(content=f"Error executing {name}: {str(e)}", tool_call_id=call["id"], name=name))

    return {
        "messages": responses,
        "audit_log": state.get("audit_log", []) + new_entries,
        "ui_components": state.get("ui_components", []) + components,
    }
