#!/usr/bin/env python3
"""
test_mcp_buyer_agent.py — MCP & Agent-to-Agent (A2A) Buyer Agent Integration Test.

Demonstrates an autonomous Buyer Agent using MCP tools to search catalog criteria,
select candidate products, and initiate programmatic negotiation with Razorpay Saathi Store Manager.
"""

import pathlib
import sys
import json
import requests

# Make backend app importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "backend"))

from app.mcp_server import search_catalog, get_product

API_BASE = "http://localhost:8000"

def run_mcp_buyer_agent_flow():
    print("=" * 70)
    print("🤖 STARTING ANTIGRAVITY MCP BUYER AGENT SIMULATION")
    print("=" * 70)
    
    # Step 1: Buyer Agent uses MCP tool to search for Yeezy sneakers under ₹35,000
    print("\n🔍 [Step 1] Buyer Agent invokes MCP Tool: `search_catalog`")
    print("   Query params: query='yeezy', max_price=35000, category='sneakers'")
    
    mcp_result_json = search_catalog(
        query="yeezy",
        max_price=35000,
        category="sneakers",
        limit=4
    )
    
    products = json.loads(mcp_result_json)
    print(f"   ✓ MCP Tool returned {len(products)} matching products:")
    for p in products:
        print(f"      • [{p['id']}] {p['name']} — ₹{p['price_inr']:,}")

    if not products:
        print("❌ No products found via MCP tool.")
        return

    # Select top target product
    target_product = products[0]
    
    # Step 2: Buyer Agent uses MCP tool `get_product` for detailed specs inspection
    print(f"\n📋 [Step 2] Buyer Agent invokes MCP Tool: `get_product('{target_product['id']}')`")
    product_details_json = get_product(target_product['id'])
    product_details = json.loads(product_details_json)
    print(f"   ✓ Details retrieved: Specs={json.dumps(product_details.get('specs'))}")

    # Step 3: Buyer Agent negotiates purchase with Razorpay Saathi Store Manager via A2A
    print("\n🤝 [Step 3] Buyer Agent sends negotiation intent to `/api/a2a/negotiate`")
    buyer_intent = f"I want to purchase the {target_product['name']} (ID: {target_product['id']}) for my client. Our max budget is ₹{target_product['price_inr']}. Can you confirm availability and offer details?"
    
    a2a_payload = {
        "buyer_agent_id": "antigravity_buyer_agent_v1",
        "intent": buyer_intent,
        "budget_inr": target_product["price_inr"],
        "requested_category": target_product["category"],
        "cart": [{"id": target_product["id"], "qty": 1, "price": target_product["price_inr"]}]
    }
    
    print(f"   Payload: intent='{buyer_intent}'")
    
    try:
        response = requests.post(f"{API_BASE}/api/a2a/negotiate", json=a2a_payload, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            print("\n✨ [Step 4] A2A Negotiation Successful! Response received:")
            print("--------------------------------------------------")
            print(f"🏪 Store Agent Response:\n{res_data['response']}")
            print("--------------------------------------------------")
            
            print("\n📦 Structured Product UI/Data Payloads:")
            for item in res_data.get("data_payloads", []):
                print(f"   • Component: {item.get('component')} | Props: {item.get('props')}")
                
            print("\n🛡️ Manager Audit & Policy Notes:")
            for note in res_data.get("manager_notes", []):
                print(f"   • {note}")
        else:
            print(f"❌ A2A negotiation failed: HTTP {response.status_code} — {response.text}")
    except Exception as e:
        print(f"❌ Error communicating with backend API: {e}")

    print("\n" + "=" * 70)
    print("✅ MCP BUYER AGENT SIMULATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    run_mcp_buyer_agent_flow()
