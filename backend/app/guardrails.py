"""
guardrails.py — server-side correctness & policy enforcement.

The LLM is NEVER trusted as the source of truth for products, prices, or
discounts. Everything an agent claims is validated here against the SQLite
catalog and the Manager-approved discount ceiling.

Two holes this closes (both observed in convo.log):

  1. HALLUCINATED PRODUCTS — the model invented IDs/prices that don't exist,
     e.g. `prod_shoe_galaxy` and `prod_shoe_gold_ltd`.

  2. RUPEE-SMUGGLED DISCOUNTS — the model "negotiated" a sneaker from ₹10,999
     down to ₹9,000 (≈18%). The old audit only scanned for the literal
     pattern "N% off", so an absolute-rupee cut sailed through as clean.

Grounding strategy for price checks: we only flag a quoted price as a
below-ceiling discount when it can be *tied to a real product* — either the
agent named the product's `prod_...` id in the same message, or the product is
already in the session cart. A quoted amount counts as "that product's price"
only when it lands in the product's [50%, 100%) catalog band AND it is not the
exact catalog price of some other grounded product, and offer/eligibility
thresholds ("on orders ≥ ₹8,000") are stripped first — so cart totals, bank
offer amounts, and co-quoted product prices are never mistaken for a discount.
"""

import re
from typing import Optional

from app import db


# ── Extraction patterns ──────────────────────────────────────────────────────

_PRODUCT_ID_RE = re.compile(r"prod_[a-z0-9_]+", re.IGNORECASE)

# ₹32,999  |  Rs. 27999  |  Rs 1,299
_PRICE_RE = re.compile(r"(?:₹|rs\.?\s*)([\d][\d,]*)", re.IGNORECASE)

# 15% off | 20 % discount | 5% cashback | 3% rebate
_PCT_DISCOUNT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(off|discount|cashback|rebate)", re.IGNORECASE
)

# A quoted price is treated as "this product's price" only inside this band of
# the catalog price. Below the band → it's some other (cheaper) line item;
# at/above catalog → it's just quoting the real price, not a discount.
_PRICE_BAND_LOW = 0.50

# Amounts that are offer/eligibility THRESHOLDS ("on orders ≥ ₹8,000", "above
# ₹5,000") rather than a quoted product price — blanked out before the discount-
# band check so a bank offer's minimum-order figure is never read as a discount.
_THRESHOLD_AMOUNT_RE = re.compile(
    r"(?:≥|>=|>|\babove\b|\bover\b|\bminimum\b|\bmin\.?\b|\bat\s+least\b|"
    r"\border(?:s)?\s+(?:of\s+)?(?:≥|>=|>|above|over)?|"
    r"\bpurchase(?:s)?\s+(?:of\s+)?(?:≥|>=|>|above|over)?)"
    r"\s*(?:₹|rs\.?\s*)?[\d][\d,]*",
    re.IGNORECASE,
)


def _strip_threshold_amounts(text: str) -> str:
    """Blank out offer-threshold amounts so they aren't read as discounted prices."""
    return _THRESHOLD_AMOUNT_RE.sub(" ", text or "")


def extract_product_ids(text: str) -> list[str]:
    """All `prod_...` ids mentioned, de-duplicated, order preserved."""
    seen: dict[str, None] = {}
    for m in _PRODUCT_ID_RE.findall(text or ""):
        seen.setdefault(m.lower(), None)
    return list(seen.keys())


def extract_prices(text: str) -> list[int]:
    """All rupee amounts mentioned, as ints."""
    out: list[int] = []
    for raw in _PRICE_RE.findall(text or ""):
        digits = raw.replace(",", "")
        if digits.isdigit():
            out.append(int(digits))
    return out


def floor_price(catalog_price: int, ceiling_pct: float) -> int:
    """Lowest price allowed for a product under the Manager's discount ceiling."""
    return round(catalog_price * (1 - ceiling_pct / 100.0))


# ── Validation ────────────────────────────────────────────────────────────────

def audit_response(
    text: str,
    ceiling_pct: float,
    cart: Optional[list[dict]] = None,
) -> dict:
    """
    Validate one agent response against the catalog and the discount ceiling.

    Returns a dict:
      {
        "clean": bool,
        "hallucinated_ids": [str, ...],
        "price_violations": [
            {product_id, name, catalog, quoted, floor, effective_pct}, ...
        ],
        "pct_violations": [{pct: float, type: str}, ...],
      }
    """
    text = text or ""
    mentioned_ids = extract_product_ids(text)

    # ── 1. Hallucinated product ids ──────────────────────────────────────────
    hallucinated: list[str] = []
    real_products: dict[str, dict] = {}
    for pid in mentioned_ids:
        product = db.get_product(pid)
        if product is None:
            hallucinated.append(pid)
        else:
            real_products[pid] = product

    # ── 2. Below-ceiling prices (percent OR absolute rupees) ─────────────────
    # Grounding set = real products named in this message ∪ products in the cart.
    grounded: dict[str, dict] = dict(real_products)
    for item in cart or []:
        pid = item.get("id")
        if pid and pid not in grounded:
            grounded[pid] = item

    # Strip offer/eligibility thresholds first so a "≥ ₹8,000" minimum isn't read
    # as a discounted price for a similarly-priced item.
    prices = extract_prices(_strip_threshold_amounts(text))
    # Exact catalog prices of grounded products are real prices, not discounts —
    # this stops one product's price from tripping a similarly-priced product's band.
    known_catalog_prices = {
        (p.get("price_inr") or p.get("price") or 0) for p in grounded.values()
    }
    price_violations: list[dict] = []
    seen_pids: set[str] = set()

    for pid, product in grounded.items():
        catalog = product.get("price_inr") or product.get("price") or 0
        if catalog <= 0:
            continue
        floor = floor_price(catalog, ceiling_pct)
        band_low = catalog * _PRICE_BAND_LOW
        for p in prices:
            # p is a discounted price for THIS product only if it sits inside the
            # product's own price band, dips below the allowed floor, and isn't just
            # some other grounded product's real catalog price.
            if band_low <= p < floor and p not in known_catalog_prices and pid not in seen_pids:
                price_violations.append({
                    "product_id":    pid,
                    "name":          product.get("name", pid),
                    "catalog":       catalog,
                    "quoted":        p,
                    "floor":         floor,
                    "effective_pct": round((1 - p / catalog) * 100, 1),
                })
                seen_pids.add(pid)
                break

    # ── 3. Explicit "N% off" claims above the ceiling ────────────────────────
    pct_violations: list[dict] = []
    for amount_str, dtype in _PCT_DISCOUNT_RE.findall(text):
        pct = float(amount_str)
        if pct > ceiling_pct:
            pct_violations.append({"pct": pct, "type": dtype.lower()})

    clean = not (hallucinated or price_violations or pct_violations)
    return {
        "clean":            clean,
        "hallucinated_ids": hallucinated,
        "price_violations": price_violations,
        "pct_violations":   pct_violations,
    }


# ── Human-facing correction ────────────────────────────────────────────────────

def build_manager_correction(audit: dict, ceiling_pct: float) -> Optional[str]:
    """
    Turn a dirty audit into a concise, user-visible Manager override note.
    Returns None when the response is clean.
    """
    if audit.get("clean"):
        return None

    lines: list[str] = []

    for pid in audit.get("hallucinated_ids", []):
        lines.append(
            f"• “{pid}” is not a real product in our catalog — please disregard it."
        )

    for v in audit.get("price_violations", []):
        lines.append(
            f"• Max approved discount is {ceiling_pct:g}%. The lowest valid price for "
            f"{v['name']} is ₹{v['floor']:,} (the quoted ₹{v['quoted']:,} would be "
            f"≈{v['effective_pct']:g}% off ₹{v['catalog']:,})."
        )

    for v in audit.get("pct_violations", []):
        lines.append(
            f"• {v['pct']:g}% {v['type']} exceeds the approved {ceiling_pct:g}% ceiling."
        )

    header = "Manager policy override:"
    return header + "\n" + "\n".join(lines)


# ── Audit-trail entries (for the activity accordion) ───────────────────────────

def audit_log_entries(audit: dict, ceiling_pct: float) -> list[dict]:
    """Manager Agent audit-log rows describing what validation found."""
    entries: list[dict] = []

    for pid in audit.get("hallucinated_ids", []):
        entries.append({
            "agent":  "Manager Agent",
            "detail": f"GROUNDING VIOLATION: '{pid}' not found in catalog — hallucinated product blocked",
        })

    for v in audit.get("price_violations", []):
        entries.append({
            "agent":  "Manager Agent",
            "detail": (
                f"PRICE VIOLATION: {v['name']} quoted ₹{v['quoted']:,} "
                f"(≈{v['effective_pct']:g}% off) — floor is ₹{v['floor']:,} at {ceiling_pct:g}% ceiling"
            ),
        })

    for v in audit.get("pct_violations", []):
        entries.append({
            "agent":  "Manager Agent",
            "detail": f"AUDIT VIOLATION: {v['pct']:g}% {v['type']} exceeds {ceiling_pct:g}% ceiling",
        })

    if audit.get("clean"):
        entries.append({
            "agent":  "Manager Agent",
            "detail": "AUDIT: products & pricing verified against catalog — no violations",
        })

    return entries
