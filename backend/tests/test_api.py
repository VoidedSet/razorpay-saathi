"""
test_api.py — Integration tests for FastAPI endpoints in app/main.py.
"""

import pathlib
import sys
from fastapi.testclient import TestClient
from unittest.mock import patch

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

@patch("app.main._graph.ainvoke")
def test_a2a_negotiate_endpoint(mock_ainvoke):
    import asyncio
    
    mock_final_state = {
        "messages": [
            type("AIMessage", (), {"content": "Sure, here are some black sneakers under 15000 INR."})()
        ],
        "cart": [],
        "manager_notes": ["Mock note"],
        "audit_log": [{"agent": "Manager", "detail": "Mock detail"}],
    }
    
    # We need to return a coroutine
    async def mock_coro(*args, **kwargs):
        return mock_final_state
    mock_ainvoke.side_effect = mock_coro

    payload = {
        "buyer_agent_id": "test_agent_001",
        "intent": "Looking for black sneakers under 15000 INR",
        "budget_inr": 15000,
        "requested_category": "sneakers",
        "cart": []
    }
    response = client.post(
        "/api/a2a/negotiate",
        json=payload,
        headers={"x-kya-proof": "mocked-valid-proof"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "response" in data
    assert isinstance(data["cart_state"], list)
    assert isinstance(data["manager_notes"], list)

def test_a2a_negotiate_rejects_bad_key():
    payload = {
        "buyer_agent_id": "test_agent_001",
        "intent": "Looking for sneakers",
        "budget_inr": 15000,
    }
    response = client.post(
        "/api/a2a/negotiate",
        json=payload,
        headers={"x-kya-proof": ""},
    )
    assert response.status_code == 401

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
