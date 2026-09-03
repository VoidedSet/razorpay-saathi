import requests
import json

def test_a2a_negotiate():
    url = "http://localhost:8000/api/a2a/negotiate"
    payload = {
        "buyer_agent_id": "agent_sneakerhead_007",
        "intent": "I am looking for a pair of black sneakers under 15000 INR for my client. Show me the best options with stealth styling.",
        "budget_inr": 15000,
        "requested_category": "sneakers",
        "cart": []
    }
    
    print(f"🤖 Buyer Agent Intent: {payload['intent']}")
    print(f"💰 Buyer Budget: ₹{payload['budget_inr']}")
    print("-" * 50)
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print("\n🏪 Store Agent Response:")
        print(data["response"])
        
        print("\n📊 Structured Data Returned (instead of UI):")
        for comp in data["data_payloads"]:
            print(f"  → Component Type: {comp['component']}")
            if comp['component'] == 'product_card':
                print(f"      Product: {comp['props'].get('name')}")
                print(f"      Price: ₹{comp['props'].get('price')}")
                
        print("\n🛡️ Manager Notes (Guardrails):")
        for note in data["manager_notes"]:
            print(f"  → {note}")
    else:
        print(f"Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_a2a_negotiate()
