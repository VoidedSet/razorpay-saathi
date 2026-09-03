"""
test_guardrails.py — correctness/policy validator checks.

Runnable two ways:
    cd backend && .venv/bin/python tests/test_guardrails.py     # standalone
    cd backend && .venv/bin/pytest tests/test_guardrails.py     # pytest

Cases are grounded in the real seeded catalog (see app/db.py — The Souled Store):
    prod_shoe_hightop  ₹10,999   (priciest)
    prod_shoe_miami    ₹ 9,999
    prod_shoe_mafia    ₹ 7,999
    prod_shoe_canvas   ₹ 5,999   (cheapest)
Alex (usr_001) has a 10% discount ceiling, which we use throughout.
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
    """₹10,999 sneaker 'negotiated' to ₹9,000 (~18%) must trip a price violation."""
    text = "I can do the prod_shoe_hightop for you at ₹9,000 today."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert len(audit["price_violations"]) == 1
    v = audit["price_violations"][0]
    assert v["product_id"] == "prod_shoe_hightop"
    assert v["quoted"] == 9000
    assert v["floor"] == guardrails.floor_price(10999, CEILING)  # 9899
    assert v["effective_pct"] > CEILING


def test_hallucinated_product_id():
    """An id that isn't in the catalog must be reported as hallucinated."""
    text = "Check out the prod_shoe_galaxy, a great limited-edition drop."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert "prod_shoe_galaxy" in audit["hallucinated_ids"]


def test_explicit_percent_over_ceiling():
    """'20% off' with a 10% ceiling must trip a percent violation."""
    text = "Sure, I'll give you 20% off on that."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert any(v["pct"] == 20.0 for v in audit["pct_violations"])


# ── CLEAN: must pass ────────────────────────────────────────────────────────

def test_real_catalog_price_is_clean():
    """Quoting the true catalog price is not a discount."""
    text = "The prod_shoe_miami is ₹9,999."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_discount_within_ceiling_is_clean():
    """8% off under a 10% ceiling is allowed."""
    text = "I can apply 8% off on the prod_shoe_mafia for you."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_two_catalog_priced_items_are_clean():
    """Co-quoting two real products at catalog: one's price must not read as the
    other's discount (their price bands overlap in the sneaker catalog)."""
    text = "Pair the prod_shoe_miami (₹9,999) with the prod_shoe_canvas (₹5,999)."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_bank_offer_amounts_with_cart_are_clean():
    """₹1,000 / ₹500 bank-offer amounts must not be mistaken for a discount on a cart item."""
    text = "With HDFC you get ₹1,000 cashback, and Kotak gives ₹500 off at checkout."
    cart = [db.get_product("prod_shoe_hightop")]  # ₹10,999 in cart
    audit = guardrails.audit_response(text, CEILING, cart=cart)
    assert audit["clean"], audit


def test_offer_threshold_amount_with_cart_is_clean():
    """A bank offer's 'on orders ≥ ₹8,000' threshold must not read as a phone discount.

    ₹8,000 sits inside the ₹10,999 shoe's [50%, 100%) band, so without threshold
    stripping this would be a false price violation.
    """
    text = (
        "Your order total is ₹10,999. Kotak gives ₹500 off on orders ≥ ₹8,000. "
        "Pay via the Razorpay link when ready."
    )
    cart = [db.get_product("prod_shoe_hightop")]
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
