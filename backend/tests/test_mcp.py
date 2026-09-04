"""
test_mcp.py — Unit tests for MCP server tools in app/mcp_server.py.
"""

import pathlib
import sys
import json

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.mcp_server import search_catalog, get_product  # noqa: E402
from app import db  # noqa: E402

def setup_module():
    db.init_db()

def test_mcp_search_catalog_query():
    res_str = search_catalog(query="yeezy", limit=5)
    assert not res_str.startswith("Error")
    assert not res_str.startswith("No products found")
    data = json.loads(res_str)
    assert isinstance(data, list)
    assert len(data) > 0

def test_mcp_search_catalog_specs():
    specs_str = json.dumps({"material": "Primeknit"})
    res_str = search_catalog(specs_filter=specs_str, limit=5)
    assert not res_str.startswith("Error")
    data = json.loads(res_str)
    assert isinstance(data, list)

def test_mcp_get_product_success():
    res_str = get_product("prod_01")
    assert not res_str.startswith("Error")
    data = json.loads(res_str)
    assert data["id"] == "prod_01"

def test_mcp_get_product_invalid():
    res_str = get_product("invalid_id_9999")
    assert res_str.startswith("Error")

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
