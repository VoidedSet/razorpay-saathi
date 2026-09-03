"""
test_guardrails.py — correctness/policy validator checks.

Runnable two ways:
    cd backend && .venv/bin/python tests/test_guardrails.py     # standalone
    cd backend && .venv/bin/pytest tests/test_guardrails.py     # pytest

Cases are grounded in the real seeded catalog (see app/db.py):
    prod_sm_s21fe  ₹32,999
    prod_sm_s23    ₹74,999
    prod_acc_glass ₹   799
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
    """₹32,999 phone 'negotiated' to ₹27,999 (~15%) must trip a price violation."""
    text = "I can do the prod_sm_s21fe for you at ₹27,999 today."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert len(audit["price_violations"]) == 1
    v = audit["price_violations"][0]
    assert v["product_id"] == "prod_sm_s21fe"
    assert v["quoted"] == 27999
    assert v["floor"] == guardrails.floor_price(32999, CEILING)  # 29699
    assert v["effective_pct"] > CEILING


def test_hallucinated_product_id():
    """An id that isn't in the catalog must be reported as hallucinated."""
    text = "Check out the prod_sm_s23lte, a great mid-tier option."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert "prod_sm_s23lte" in audit["hallucinated_ids"]


def test_explicit_percent_over_ceiling():
    """'20% off' with a 10% ceiling must trip a percent violation."""
    text = "Sure, I'll give you 20% off on that."
    audit = guardrails.audit_response(text, CEILING)
    assert not audit["clean"]
    assert any(v["pct"] == 20.0 for v in audit["pct_violations"])


# ── CLEAN: must pass ────────────────────────────────────────────────────────

def test_real_catalog_price_is_clean():
    """Quoting the true catalog price is not a discount."""
    text = "The prod_sm_s21fe is ₹32,999."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_discount_within_ceiling_is_clean():
    """8% off under a 10% ceiling is allowed."""
    text = "I can apply 8% off on the prod_sm_s23 for you."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_accessory_plus_phone_at_catalog_is_clean():
    """A cheap accessory price co-quoted with a phone must not read as a phone discount."""
    text = "Pair the prod_sm_s23 (₹74,999) with a prod_acc_glass screen guard (₹799)."
    audit = guardrails.audit_response(text, CEILING)
    assert audit["clean"], audit


def test_bank_offer_amounts_with_cart_are_clean():
    """₹500 / ₹1,000 bank-offer amounts must not be mistaken for a discount on a cart item."""
    text = "With HDFC you get ₹1,000 cashback, and Kotak gives ₹500 off at checkout."
    cart = [db.get_product("prod_sm_s21fe")]  # ₹32,999 in cart
    audit = guardrails.audit_response(text, CEILING, cart=cart)
    assert audit["clean"], audit


# ── Standalone runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}  —  {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  💥 {t.__name__}  —  {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
