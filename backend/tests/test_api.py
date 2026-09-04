"""
test_api.py — Integration tests for FastAPI endpoints in app/main.py.
"""

import pathlib
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_config" in data

def test_stagnant_inventory_endpoints():
    # Mark prod_01 stagnant
    res_mark = client.post("/api/mark_stagnant/prod_01?stock=2")
    assert res_mark.status_code == 200
    assert res_mark.json()["success"] is True

    # Check stagnant list
    res_list = client.get("/api/stagnant")
    assert res_list.status_code == 200
    prods = res_list.json()["products"]
    assert any(p["id"] == "prod_01" for p in prods)

def test_campaigns_history_endpoint():
    response = client.get("/api/campaigns")
    assert response.status_code == 200
    data = response.json()
    assert "campaigns" in data
    assert isinstance(data["campaigns"], list)

def test_a2a_negotiate_endpoint():
    payload = {
        "buyer_agent_id": "test_agent_001",
        "intent": "Looking for black sneakers under 15000 INR",
        "budget_inr": 15000,
        "requested_category": "sneakers",
        "cart": []
    }
    response = client.post("/api/a2a/negotiate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "response" in data
    assert isinstance(data["data_payloads"], list)
    assert isinstance(data["manager_notes"], list)

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
