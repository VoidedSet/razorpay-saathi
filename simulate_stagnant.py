#!/usr/bin/env python3
"""
simulate_stagnant.py — Live demo script for Hackathon Pitch.

Triggers a stagnant inventory campaign for Apex: Stealth Black (or specified product),
simulating inventory overstock → Manager approval → Marketing Agent tweet & payment link generation.
"""

import sys
import json
import urllib.request
import urllib.parse

API_BASE = "http://localhost:8000"

def main():
    product_id = sys.argv[1] if len(sys.argv) > 1 else "prod_shoe_stealth"
    discount_requested = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0

    print(f"🚀 [1/3] Marking stock low (stagnant inventory) for product '{product_id}'...")
    req = urllib.request.Request(
        f"{API_BASE}/api/mark_stagnant/{product_id}?stock=3",
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print(f"   Response: {res}")

    print(f"\n🎯 [2/3] Triggering Marketing Campaign ({discount_requested}% requested)...")
    payload = json.dumps({
        "product_id": product_id,
        "trigger_type": "stagnant_inventory",
        "discount_pct": discount_requested
    }).encode("utf-8")

    campaign_req = urllib.request.Request(
        f"{API_BASE}/api/campaign",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(campaign_req) as resp:
        result = json.loads(resp.read().decode())

    print("\n✨ [3/3] Campaign Result Generated Successfully!")
    print(f"  • Product: {result['product']['name']} (₹{result['product']['original_price']:,} → ₹{result['product']['campaign_price']:,})")
    print(f"  • Approved Discount: {result['discount_pct']}%")
    print(f"  • Manager Note: {result['manager_note']}")
    print(f"  • Razorpay Link: {result['payment_link']} (id: {result['link_id']})")
    print("\n📢 Generated Tweet Copy:")
    print("--------------------------------------------------")
    print(result['tweet'])
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
