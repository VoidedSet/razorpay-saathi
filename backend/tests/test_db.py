"""
test_db.py — Unit tests for SQLite database operations in app/db.py.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

def setup_module():
    db.init_db()

def test_get_product_success():
    prod = db.get_product("prod_01")
    assert prod is not None
    assert prod["id"] == "prod_01"
    assert "Yeezy" in prod["name"]
    assert isinstance(prod["specs"], dict)

def test_get_product_not_found():
    prod = db.get_product("prod_non_existent_999")
    assert prod is None

def test_search_products_by_query():
    results = db.search_products(query="zebra", limit=5)
    assert len(results) > 0
    assert any("Zebra" in p["name"] or "zebra" in p["tags"] for p in results)

def test_search_products_by_price_range():
    results = db.search_products(min_price=10000, max_price=20000)
    assert len(results) > 0
    for p in results:
        assert 10000 <= p["price_inr"] <= 20000

def test_search_products_by_specs():
    results = db.search_products(specs_filter={"material": "Primeknit"})
    assert isinstance(results, list)
    for p in results:
        assert p["specs"].get("material") == "Primeknit"

def test_get_user_profile():
    user = db.get_user_profile("usr_001")
    assert user is not None
    assert user["name"] == "Alex"
    assert user["discount_ceiling_pct"] == 10

def test_cart_operations():
    session_id = "test_sess_123"
    db.clear_cart(session_id)
    
    db.add_to_cart(session_id, "prod_01", qty=2)
    cart = db.get_cart(session_id)
    assert len(cart) == 1
    assert cart[0]["id"] == "prod_01"
    assert cart[0]["qty"] == 2
    
    db.clear_cart(session_id)
    assert len(db.get_cart(session_id)) == 0

def test_mark_stagnant_inventory():
    prod = db.get_product("prod_03")
    assert prod is not None
    res = db.mark_stagnant("prod_03", stock=2)
    assert res is True
    updated = db.get_product("prod_03")
    assert updated["stock"] == 2

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__} — {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
