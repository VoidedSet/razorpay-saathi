import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import get_llm
from app import db
from app.state import _strip_think

_MARKETING_SYSTEM_PROMPT = """\\
You are the **Razorpay Saathi Marketing Agent**. You have been authorised by the
Manager to run a promotional campaign for a specific product.

**Your job** (respond in strict JSON, no prose outside it):
{{
  "tweet": "<≤260 char campaign tweet with emojis, discount % and a placeholder {{LINK}} where the payment link goes>",
  "headline": "<Short snappy ad headline, ≤12 words>",
  "body": "<2-sentence ad body copy suitable for an email / push notification>"
}}

Rules:
- Mention the exact discount percentage given to you.
- Do NOT mention competitor brand names.
- Keep the tweet punchy and emoji-rich — it must feel authentic, not corporate.
- Replace {{LINK}} with the literal token {{LINK}} — main.py will substitute the real URL.
- Respond with ONLY the JSON object, nothing else.
"""

def _marketing_product_context(product: dict, discount_pct: float) -> str:
    discounted_price = int(product["price_inr"] * (1 - discount_pct / 100))
    return (
        f"Product: {product['name']} by {product.get('brand','')}\\n"
        f"Category: {product.get('category','')}\\n"
        f"Original Price: ₹{product['price_inr']:,}\\n"
        f"Campaign Price (after {discount_pct}% off): ₹{discounted_price:,}\\n"
        f"Description: {product.get('description','')}\\n"
        f"Tags: {product.get('tags','')}"
    )

async def run_marketing_campaign(
    product_id: str,
    trigger_type: str,
    approved_discount_pct: float,
    session_id: str = "",
    manager_note: str = "",
) -> dict:
    """
    Standalone async function: Manager calls this with an approved discount
    to generate campaign copy + Razorpay Payment Link.
    Returns a CampaignResult dict consumed by /api/campaign.
    """
    import json as _json

    product = db.get_product(product_id)
    if not product:
        raise ValueError(f"Product not found: {product_id}")

    discounted_price = int(product["price_inr"] * (1 - approved_discount_pct / 100))

    # Build payment link
    link_seed = f"campaign:{product_id}:{approved_discount_pct}:{session_id}"
    link = db.get_payment_link(link_seed, discounted_price, description=f"{product['name']} — {approved_discount_pct}% off (campaign)")

    # Ask LLM for tweet + copy
    ctx = _marketing_product_context(product, approved_discount_pct)
    user_msg = f"Generate campaign copy for:\\n{ctx}"
    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=_MARKETING_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ])
    raw = _strip_think(response.content or "")

    # Parse LLM JSON (robust — tolerate markdown fences)
    try:
        json_str = re.sub(r"```[a-z]*\\n?", "", raw).strip().strip("`")
        copy = _json.loads(json_str)
    except Exception:
        copy = {"tweet": raw[:260], "headline": product["name"], "body": ""}

    tweet = copy.get("tweet", "").replace("{LINK}", link["short_url"])

    # Persist
    campaign_id = db.log_campaign(
        trigger_type=trigger_type,
        product_id=product_id,
        discount_pct=approved_discount_pct,
        tweet_copy=tweet,
        payment_link=link["short_url"],
        link_id=link["id"],
        session_id=session_id,
        manager_note=manager_note,
    )

    return {
        "campaign_id":    campaign_id,
        "trigger_type":   trigger_type,
        "product": {
            "id":              product["id"],
            "name":            product["name"],
            "brand":           product.get("brand", ""),
            "category":        product.get("category", ""),
            "image":           product.get("image_url", ""),
            "original_price":  product["price_inr"],
            "campaign_price":  discounted_price,
            "currency":        "INR",
        },
        "discount_pct":   approved_discount_pct,
        "tweet":          tweet,
        "headline":       copy.get("headline", product["name"]),
        "body":           copy.get("body", ""),
        "payment_link":   link["short_url"],
        "link_id":        link["id"],
        "manager_note":   manager_note,
        "audit": [
            {"agent": "Manager",           "detail": f"Approved {approved_discount_pct}% discount campaign for {product['name']}. {manager_note}"},
            {"agent": "Marketing Agent",   "detail": f"Generated campaign copy + Razorpay Payment Link {link['id']} (₹{discounted_price:,})"},
        ],
    }
