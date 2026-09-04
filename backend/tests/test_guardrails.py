"""
test_guardrails.py — correctness/policy validator checks.

Runnable two ways:
    cd backend && .venv/bin/python tests/test_guardrails.py     # standalone
    cd backend && .venv/bin/pytest tests/test_guardrails.py     # pytest

Cases are grounded in the real seeded catalog (e.g. prod_01 ₹32,000, prod_02 ₹26,500, prod_03 ₹14,500).
User ceiling = 10.0%.
"""

import pathlib
import sys

# Make `app` importable when run as a plain script (sys.path[0] would be tests/).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import db, guardrails  # noqa: E402

CEILING = 10.0

# Ensure the catalog exists (idempotent; reads the seeded store.db).
db.init_db()


# ── DIRTY: must be flagged ──────────────────────────────────────────────────

def test_rupee_smuggled_discount():
    """prod_01 (₹32,000) 'negotiated' to ₹25,000 (~21.8%) must trip a price violation."""
    p1 = db.get_product("prod_01")
    assert p1 is not None, "prod_01 must exist in store.db"
    orig_price = p1["price_inr"]  # 32000
    quoted_price = 25000  # ~21.8% discount > 10% ceiling
    text = f"I can do the prod_01 for you at ₹{quoted_price:,} today."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert len(audit["price_violations"]) == 1
    v = audit["price_violations"][0]
    assert v["product_id"] == "prod_01"
    assert v["quoted"] == quoted_price
    assert v["floor"] == guardrails.floor_price(orig_price, CEILING)
    assert v["effective_pct"] > CEILING


def test_hallucinated_product_id():
    """An id that isn't in the catalog must be reported as hallucinated."""
    text = "Check out the prod_shoe_galaxy_fake_99, a great limited-edition drop."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert "prod_shoe_galaxy_fake_99" in audit["hallucinated_ids"]


def test_explicit_percent_over_ceiling():
    """'20% off' with a 10% ceiling must trip a percent violation."""
    text = "Sure, I'll give you 20% off on that."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert any(v["pct"] == 20.0 for v in audit["pct_violations"])


# ── CLEAN: must pass ────────────────────────────────────────────────────────

def test_real_catalog_price_is_clean():
    """Quoting the true catalog price is not a discount."""
    p2 = db.get_product("prod_02")
    assert p2 is not None, "prod_02 must exist in store.db"
    text = f"The prod_02 is ₹{p2['price_inr']:,}."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_discount_within_ceiling_is_clean():
    """8% off under a 10% ceiling is allowed."""
    p3 = db.get_product("prod_03")
    assert p3 is not None, "prod_03 must exist in store.db"
    text = f"I can apply 8% off on the {p3['id']} for you."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_two_catalog_priced_items_are_clean():
    """Co-quoting two real products at catalog: one's price must not read as the
    other's discount."""
    p1 = db.get_product("prod_01")
    p3 = db.get_product("prod_03")
    text = f"Pair the prod_01 (₹{p1['price_inr']:,}) with the prod_03 (₹{p3['price_inr']:,})."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_bank_offer_amounts_with_cart_are_clean():
    """₹1,000 / ₹500 bank-offer amounts must not be mistaken for a discount on a cart item."""
    p1 = db.get_product("prod_01")
    text = "With HDFC you get ₹1,000 cashback, and Kotak gives ₹500 off at checkout."
    cart = [p1]
    audit = guardrails.audit_response(text, CEILING, cart=cart)
    assert audit["clean"], audit


def test_offer_threshold_amount_with_cart_is_clean():
    """A bank offer's 'on orders ≥ ₹20,000' threshold must not read as a discount."""
    p1 = db.get_product("prod_01")
    text = (
        f"Your order total is ₹{p1['price_inr']:,}. Kotak gives ₹1,000 off on orders ≥ ₹20,000. "
        "Pay via the Razorpay link when ready."
    )
    cart = [p1]
    audit = guardrails.audit_response(text, CEILING, cart=cart)
    assert audit["clean"], audit


# ── Standalone runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}  —  {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERR   {t.__name__}  —  {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
