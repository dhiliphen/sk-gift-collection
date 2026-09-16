#!/usr/bin/env python3
"""Load sample data into SK Gift Collection inventory app."""
import requests, sys

BASE = "http://127.0.0.1:8000/api"

def post(path, data):
    r = requests.post(f"{BASE}{path}", json=data)
    if r.status_code not in (200, 201):
        print(f"  SKIP {path}: {r.status_code} — {r.json().get('detail', r.text)}")
        return None
    return r.json()

# ── Categories ──────────────────────────────────────────────
print("Categories...")
for name in ["Gifts", "Electronics", "Home Decor", "Stationery", "Toys"]:
    r = post("/categories", {"name": name})
    if r: print(f"  ✓ {r['name']}")

# ── Units ────────────────────────────────────────────────────
print("Units...")
for name in ["pcs", "box", "dozen", "set", "kg"]:
    r = post("/units", {"name": name})
    if r: print(f"  ✓ {r['name']}")

# ── Suppliers ────────────────────────────────────────────────
print("Suppliers...")
suppliers = [
    {"name": "Rajan Traders",       "contact_person": "Rajesh Kumar",  "phone": "9876543210", "email": "rajesh@rajantrade.com",   "address": "Coimbatore, TN"},
    {"name": "Chennai Gift House",  "contact_person": "Anbu Raj",      "phone": "9876500001", "email": "anbu@chennaigifts.com",   "address": "Chennai, TN"},
    {"name": "Delhi Wholesale Co",  "contact_person": "Suresh Gupta",  "phone": "9876500002", "email": "suresh@delhiwhole.com",   "address": "Delhi"},
]
sup_ids = {}
for s in suppliers:
    r = post("/suppliers", s)
    if r:
        sup_ids[s["name"]] = r["id"]
        print(f"  ✓ {r['name']}")

# ── Inventory Items ──────────────────────────────────────────
print("Inventory items...")
items = [
    {"name": "Ceramic Coffee Mug",       "category": "Gifts",       "supplier": "Rajan Traders",      "quantity": 80,  "unit": "pcs",   "cost_price": 120,  "wholesale_price": 180,  "dealer_price": 220,  "selling_price": 299,  "low_stock_threshold": 15},
    {"name": "LED String Lights 5m",     "category": "Home Decor",  "supplier": "Delhi Wholesale Co", "quantity": 60,  "unit": "pcs",   "cost_price": 200,  "wholesale_price": 300,  "dealer_price": 375,  "selling_price": 499,  "low_stock_threshold": 10},
    {"name": "Gift Wrap Paper Roll",     "category": "Gifts",       "supplier": "Rajan Traders",      "quantity": 200, "unit": "pcs",   "cost_price": 25,   "wholesale_price": 40,   "dealer_price": 50,   "selling_price": 69,   "low_stock_threshold": 30},
    {"name": "Scented Candle Set",       "category": "Home Decor",  "supplier": "Chennai Gift House", "quantity": 45,  "unit": "set",   "cost_price": 250,  "wholesale_price": 375,  "dealer_price": 450,  "selling_price": 599,  "low_stock_threshold": 8},
    {"name": "Bluetooth Speaker Mini",   "category": "Electronics", "supplier": "Delhi Wholesale Co", "quantity": 30,  "unit": "pcs",   "cost_price": 650,  "wholesale_price": 950,  "dealer_price": 1150, "selling_price": 1499, "low_stock_threshold": 5},
    {"name": "Greeting Card Pack",       "category": "Stationery",  "supplier": "Rajan Traders",      "quantity": 150, "unit": "box",   "cost_price": 80,   "wholesale_price": 120,  "dealer_price": 150,  "selling_price": 199,  "low_stock_threshold": 20},
    {"name": "Soft Toy - Teddy Bear",    "category": "Toys",        "supplier": "Chennai Gift House", "quantity": 7,   "unit": "pcs",   "cost_price": 350,  "wholesale_price": 520,  "dealer_price": 650,  "selling_price": 849,  "low_stock_threshold": 5},
    {"name": "Photo Frame Wooden 5x7",   "category": "Home Decor",  "supplier": "Rajan Traders",      "quantity": 55,  "unit": "pcs",   "cost_price": 180,  "wholesale_price": 270,  "dealer_price": 340,  "selling_price": 449,  "low_stock_threshold": 10},
    {"name": "USB-C Charging Cable 2m",  "category": "Electronics", "supplier": "Delhi Wholesale Co", "quantity": 90,  "unit": "pcs",   "cost_price": 85,   "wholesale_price": 130,  "dealer_price": 160,  "selling_price": 219,  "low_stock_threshold": 15},
    {"name": "Premium Gift Box (Empty)", "category": "Gifts",       "supplier": "Chennai Gift House", "quantity": 4,   "unit": "dozen", "cost_price": 300,  "wholesale_price": 450,  "dealer_price": 550,  "selling_price": 699,  "low_stock_threshold": 2},
]
item_ids = {}
for item in items:
    r = post("/items", item)
    if r:
        item_ids[item["name"]] = r["id"]
        print(f"  ✓ {r['name']} (stock: {r['quantity']})")

# ── Customers ────────────────────────────────────────────────
print("Customers...")
customers = [
    {"name": "Star Gift World",      "customer_type": "wholesaler", "phone": "9500011111", "email": "buy@stargifts.com",   "address": "Erode, TN"},
    {"name": "Fancy Gifts Depot",    "customer_type": "dealer",     "phone": "9500022222", "email": "info@fancydepot.com", "address": "Salem, TN"},
    {"name": "Priya Gift Corner",    "customer_type": "retailer",   "phone": "9500033333", "email": "priya@gifts.com",     "address": "Trichy, TN"},
    {"name": "Kumar Novelties",      "customer_type": "wholesaler", "phone": "9500044444", "email": "kumar@novelties.com", "address": "Madurai, TN"},
    {"name": "Shanthi Enterprises",  "customer_type": "dealer",     "phone": "9500055555", "email": "shanthi@ent.com",     "address": "Tirunelveli, TN"},
]
for c in customers:
    r = post("/customers", c)
    if r: print(f"  ✓ {r['name']} ({r['customer_type']})")

# ── Purchase Bill ────────────────────────────────────────────
print("Purchase bill...")
if item_ids:
    pur = post("/purchases", {
        "supplier_name":    "Rajan Traders",
        "supplier_invoice": "RAJ-2026-0042",
        "items": [
            {"item_id": item_ids["Ceramic Coffee Mug"],       "quantity": 50, "unit_cost": 120},
            {"item_id": item_ids["Gift Wrap Paper Roll"],     "quantity": 100,"unit_cost": 25},
            {"item_id": item_ids["Premium Gift Box (Empty)"], "quantity": 10, "unit_cost": 300},
        ]
    })
    if pur: print(f"  ✓ {pur['purchase_number']} — ₹{pur['total_amount']:,.2f}")

# ── Sales Bill ───────────────────────────────────────────────
print("Sales bill...")
if item_ids:
    bill = post("/bills", {
        "customer_name":  "Star Gift World",
        "customer_phone": "9500011111",
        "customer_type":  "wholesaler",
        "items": [
            {"item_id": item_ids["Ceramic Coffee Mug"],     "quantity": 12, "unit_price": 180},
            {"item_id": item_ids["LED String Lights 5m"],   "quantity": 6,  "unit_price": 300},
            {"item_id": item_ids["Scented Candle Set"],     "quantity": 5,  "unit_price": 375},
            {"item_id": item_ids["Greeting Card Pack"],     "quantity": 10, "unit_price": 120},
        ]
    })
    if bill: print(f"  ✓ {bill['invoice_number']} — ₹{bill['total_amount']:,.2f}")

print("\n✅ Sample data loaded.")
