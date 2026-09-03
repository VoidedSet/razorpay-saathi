"""
db.py — SQLite store database.

Tables:
  products      — inventory with prices, stock, specs, cross-sell links
  users         — customer profiles, tiers, purchase history
  balance_sheet — store profitability → drives Manager's discount ceiling
  carts         — session-scoped cart items

All writes go through helper functions so graph nodes never touch SQL directly.
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "store.db"

# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    brand       TEXT,
    category    TEXT,
    price_inr   INTEGER NOT NULL,
    stock       INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    specs       TEXT,     -- JSON dict of key specs
    tags        TEXT,     -- comma-separated search tags
    related     TEXT,     -- comma-separated product IDs for cross-sell
    image_url   TEXT      -- URL of product image
);

CREATE TABLE IF NOT EXISTS users (
    user_id              TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    email                TEXT,
    tier                 TEXT DEFAULT 'standard',
    purchase_history     TEXT DEFAULT '[]',  -- JSON list of product IDs
    preferences          TEXT DEFAULT '',    -- comma-separated categories
    total_spend_inr      INTEGER DEFAULT 0,
    discount_ceiling_pct INTEGER DEFAULT 5
);

CREATE TABLE IF NOT EXISTS balance_sheet (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    month                    TEXT,
    revenue_inr              INTEGER,
    cost_inr                 INTEGER,
    profit_margin_pct        REAL,
    max_discount_allowed_pct INTEGER
);

CREATE TABLE IF NOT EXISTS carts (
    session_id TEXT,
    product_id TEXT REFERENCES products(id),
    qty        INTEGER DEFAULT 1,
    PRIMARY KEY (session_id, product_id)
);
"""

# ── Seed data: The Souled Store Sneakers ───────────────────────────────────────

_PRODUCTS = [
    {
        "id": "prod_shoe_miami",
        "name": "Souled: Miami",
        "brand": "The Souled Store",
        "category": "vintage",
        "price_inr": 9999,
        "stock": 35,
        "description": "A vibrant, retro-inspired sneaker for the Miami soul. Lightweight and comfortable, perfect for a walk by the beach.",
        "specs": json.dumps({"style": "Retro Runner", "upper": "Breathable Mesh & Suede", "sole": "Wave Foam Cushioning"}),
        "tags": "vintage,retro,miami,souled,sneaker,beach,lifestyle",
        "related": "prod_shoe_mafia,prod_shoe_yoda,prod_shoe_ghost",
        "image_url": "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1743521912_7639983.jpg?w=480&dpr=2",
    },
    {
        "id": "prod_shoe_mafia",
        "name": "UBZ 0.5: Mafia Mules",
        "brand": "The Souled Store",
        "category": "court",
        "price_inr": 7999,
        "stock": 22,
        "description": "Bold and stylish, these mules make a statement. Inspired by classic cinema, they are the epitome of cool.",
        "specs": json.dumps({"style": "Slip-on Mule", "upper": "Genuine Leather", "sole": "High-Rebound Comfort Sole"}),
        "tags": "court,mules,mafia,slipon,cinema,stylish",
        "related": "prod_shoe_miami,prod_shoe_yoda",
        "image_url": "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1761894000_9908200.jpg?w=1080&dpr=2",
    },
    {
        "id": "prod_shoe_yoda",
        "name": "Yoda",
        "brand": "The Souled Store",
        "category": "classics",
        "price_inr": 8999,
        "stock": 18,
        "description": "Wisdom in every step. These classic green-themed sneakers are a must-have for any fan of the galaxy.",
        "specs": json.dumps({"style": "High Top Classic", "upper": "Canvas & Leather", "sole": "Gum Rubber Outsole"}),
        "tags": "classics,yoda,green,galaxy,hightop,iconic",
        "related": "prod_shoe_ghost,prod_shoe_miami",
        "image_url": "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1759387261_3013866.jpg?w=1080&dpr=2",
    },
    {
        "id": "prod_shoe_ghost",
        "name": "Hydros: Ghost",
        "brand": "The Souled Store",
        "category": "running",
        "price_inr": 6999,
        "stock": 40,
        "description": "Sleek, minimalist, and fast. The Ghost runners are designed for urban exploration, day or night.",
        "specs": json.dumps({"style": "Foam Runner", "upper": "Ergonomic Cutouts", "sole": "Ultra-light EVA"}),
        "tags": "running,ghost,hydros,white,minimalist,urban",
        "related": "prod_shoe_cyber,prod_shoe_miami",
        "image_url": "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1754742095_6028923.jpg?w=1080&dpr=2",
    },
    {
        "id": "prod_shoe_hightop",
        "name": "TSS Originals: Urban High-Tops",
        "brand": "The Souled Store",
        "category": "court",
        "price_inr": 10999,
        "stock": 25,
        "description": "High-top silhouette engineered for urban court performance and retro street aesthetics.",
        "specs": json.dumps({"style": "Retro High-Top", "upper": "Full Grain Leather", "sole": "Traction Rubber"}),
        "tags": "court,hightop,urban,originals,basketball,streetwear",
        "related": "prod_shoe_mafia,prod_shoe_stealth",
        "image_url": "https://images.unsplash.com/photo-1512374382149-233c42b6a83b?w=600&auto=format&fit=crop",
    },
    {
        "id": "prod_shoe_cyber",
        "name": "Supersonic: Cyber Neon",
        "brand": "The Souled Store",
        "category": "running",
        "price_inr": 8499,
        "stock": 30,
        "description": "Dynamic cushioned running sneakers with vibrant neon accents and responsive foam midsoles.",
        "specs": json.dumps({"style": "Performance Runner", "upper": "Engineered Knit", "sole": "Responsive Foam Midsoles"}),
        "tags": "running,cyber,neon,supersonic,sport,cushion",
        "related": "prod_shoe_ghost,prod_shoe_miami",
        "image_url": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=600&auto=format&fit=crop",
    },
    {
        "id": "prod_shoe_canvas",
        "name": "Vintage 77: Classic Canvas",
        "brand": "The Souled Store",
        "category": "classics",
        "price_inr": 5999,
        "stock": 50,
        "description": "Timeless low-profile canvas sneakers crafted for everyday effortless style and comfort.",
        "specs": json.dumps({"style": "Low-Top Canvas", "upper": "Unbleached Canvas", "sole": "Vulcanized Rubber Trim"}),
        "tags": "classics,canvas,vintage77,everyday,lowtop,casual",
        "related": "prod_shoe_yoda,prod_shoe_ghost",
        "image_url": "https://images.unsplash.com/photo-1607522370275-f14206abe5d3?w=600&auto=format&fit=crop",
    },
    {
        "id": "prod_shoe_stealth",
        "name": "Apex: Stealth Black",
        "brand": "The Souled Store",
        "category": "vintage",
        "price_inr": 9299,
        "stock": 15,
        "description": "Matte black stealth finish with genuine suede overlays and high-traction rubber outsole.",
        "specs": json.dumps({"style": "Stealth Trainer", "upper": "Matte Suede & Synthetic", "sole": "High-Traction Rubber"}),
        "tags": "vintage,stealth,black,apex,suede,matte",
        "related": "prod_shoe_miami,prod_shoe_hightop",
        "image_url": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=600&auto=format&fit=crop",
    },
]

_USERS = [
    {
        "user_id": "usr_001",
        "name": "Alex",
        "email": "alex@example.com",
        "tier": "gold",
        "purchase_history": json.dumps(["prod_shoe_miami", "prod_shoe_yoda"]),
        "preferences": "vintage,sneakers,classics,souled",
        "total_spend_inr": 18998,
        "discount_ceiling_pct": 10,
    },
    {
        "user_id": "usr_002",
        "name": "Priya",
        "email": "priya@example.com",
        "tier": "standard",
        "purchase_history": json.dumps(["prod_shoe_ghost"]),
        "preferences": "running,minimalist",
        "total_spend_inr": 6999,
        "discount_ceiling_pct": 5,
    },
    {
        "user_id": "usr_003",
        "name": "Ravi",
        "email": "ravi@example.com",
        "tier": "platinum",
        "purchase_history": json.dumps(["prod_shoe_hightop", "prod_shoe_miami", "prod_shoe_stealth"]),
        "preferences": "court,vintage,premium",
        "total_spend_inr": 30297,
        "discount_ceiling_pct": 12,
    },
    {
        "user_id": "agt_001",
        "name": "ShopBot v1",
        "email": "bot@autobuyer.ai",
        "tier": "enterprise",
        "purchase_history": json.dumps([]),
        "preferences": "sneakers,vintage",
        "total_spend_inr": 0,
        "discount_ceiling_pct": 5,
    },
]

_BALANCE_SHEET = [
    {
        "month": "2026-09",
        "revenue_inr": 25_000_000,
        "cost_inr": 21_000_000,
        "profit_margin_pct": 16.0,
        "max_discount_allowed_pct": 12,
    }
]


# ── Connection ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ── Init + seed ───────────────────────────────────────────────────────────────

def init_db(force_reseed: bool = True) -> None:
    """Create tables and seed with mock data."""
    with _conn() as db:
        db.executescript(_SCHEMA)
        if force_reseed or db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            db.execute("DELETE FROM products")
            db.execute("DELETE FROM users")
            db.execute("DELETE FROM balance_sheet")
            _seed(db)
    print(f"✅ DB initialised at {DB_PATH}")


def _seed(db: sqlite3.Connection) -> None:
    db.executemany(
        "INSERT OR IGNORE INTO products VALUES (:id,:name,:brand,:category,"
        ":price_inr,:stock,:description,:specs,:tags,:related,:image_url)",
        _PRODUCTS,
    )
    db.executemany(
        "INSERT OR IGNORE INTO users VALUES (:user_id,:name,:email,:tier,"
        ":purchase_history,:preferences,:total_spend_inr,:discount_ceiling_pct)",
        _USERS,
    )
    db.executemany(
        "INSERT OR IGNORE INTO balance_sheet "
        "(month,revenue_inr,cost_inr,profit_margin_pct,max_discount_allowed_pct) "
        "VALUES (:month,:revenue_inr,:cost_inr,:profit_margin_pct,:max_discount_allowed_pct)",
        _BALANCE_SHEET,
    )
    print(f"  ↳ Seeded {len(_PRODUCTS)} products, {len(_USERS)} users, {len(_BALANCE_SHEET)} balance sheet rows")


# ── Read helpers ──────────────────────────────────────────────────────────────

def _parse_product(row: dict) -> dict:
    """Decode JSON fields in a product row."""
    if isinstance(row.get("specs"), str):
        try:
            row["specs"] = json.loads(row["specs"])
        except Exception:
            row["specs"] = {}
    if isinstance(row.get("related"), str):
        row["related"] = [x.strip() for x in row["related"].split(",") if x.strip()]
    return row


def search_products(query: str, limit: int = 6) -> list[dict]:
    """
    Keyword search across name, brand, category, tags.
    Scores each product by number of query-word matches and returns top results.
    """
    words = [w.lower() for w in query.split() if len(w) > 1]
    with _conn() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM products WHERE stock > 0").fetchall()]

    if not words:
        return [_parse_product(r) for r in rows[:limit]]

    scored: list[tuple[int, dict]] = []
    for row in rows:
        searchable = f"{row['name']} {row['brand']} {row['category']} {row.get('tags', '')}".lower()
        score = sum(1 for w in words if w in searchable)
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: -x[0])
    return [_parse_product(p) for _, p in scored[:limit]]


def get_product(product_id: str) -> Optional[dict]:
    """Get a single product by ID or numerical index alias."""
    alias_map = {
        "1": "prod_shoe_miami",
        "2": "prod_shoe_mafia",
        "3": "prod_shoe_yoda",
        "4": "prod_shoe_ghost",
        "5": "prod_shoe_hightop",
        "6": "prod_shoe_cyber",
        "7": "prod_shoe_canvas",
        "8": "prod_shoe_stealth",
    }
    real_id = alias_map.get(str(product_id), product_id)
    with _conn() as db:
        row = db.execute("SELECT * FROM products WHERE id = ?", (real_id,)).fetchone()
    return _parse_product(dict(row)) if row else None


def get_related_products(product_id: str, limit: int = 3) -> list[dict]:
    """Get cross-sell products linked to a given product."""
    product = get_product(product_id)
    if not product or not product.get("related"):
        return []
    related_ids = product["related"][:limit + 2]
    with _conn() as db:
        placeholders = ",".join("?" * len(related_ids))
        rows = db.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders}) AND stock > 0",
            related_ids,
        ).fetchall()
    return [_parse_product(dict(r)) for r in rows[:limit]]


def get_user_profile(user_id: str) -> Optional[dict]:
    """Get user profile with decoded JSON fields."""
    with _conn() as db:
        row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    p = dict(row)
    p["purchase_history"] = json.loads(p.get("purchase_history") or "[]")
    p["preferences"]      = [x.strip() for x in (p.get("preferences") or "").split(",") if x.strip()]
    return p


def get_balance_sheet() -> dict:
    """Get the most recent balance sheet entry."""
    with _conn() as db:
        row = db.execute("SELECT * FROM balance_sheet ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else {"profit_margin_pct": 0.0, "max_discount_allowed_pct": 15}


# ── Cart helpers ──────────────────────────────────────────────────────────────

def get_cart(session_id: str) -> list[dict]:
    """Get cart items with full product details."""
    with _conn() as db:
        rows = db.execute(
            """
            SELECT p.*, c.qty FROM carts c
            JOIN products p ON p.id = c.product_id
            WHERE c.session_id = ?
            """,
            (session_id,),
        ).fetchall()
    return [_parse_product(dict(r)) for r in rows]


def add_to_cart(session_id: str, product_id: str, qty: int = 1) -> bool:
    """Add / update a product in the session cart. Returns True on success."""
    if not get_product(product_id):
        return False
    with _conn() as db:
        db.execute(
            "INSERT INTO carts (session_id, product_id, qty) VALUES (?,?,?) "
            "ON CONFLICT (session_id, product_id) DO UPDATE SET qty = qty + ?",
            (session_id, product_id, qty, qty),
        )
    return True


def clear_cart(session_id: str) -> None:
    with _conn() as db:
        db.execute("DELETE FROM carts WHERE session_id = ?", (session_id,))


# ── Razorpay Offers (mock) ────────────────────────────────────────────────────

def get_razorpay_offers(amount_inr: int) -> list[dict]:
    offers = []
    if amount_inr >= 5_000:
        offers.append({
            "bank": "HDFC Bank",
            "type": "cashback",
            "discount_pct": 5,
            "max_discount_inr": 1_000,
            "min_order_inr": 5_000,
            "payment_method": "HDFC Credit Card",
            "offer_code": "HDFC5OFF",
        })
    if amount_inr >= 8_000:
        offers.append({
            "bank": "Kotak Mahindra",
            "type": "instant_discount",
            "discount_flat_inr": 500,
            "min_order_inr": 8_000,
            "payment_method": "Kotak Debit Card",
            "offer_code": "KOTAK500",
        })
    if amount_inr >= 12_000:
        offers.append({
            "bank": "ICICI Bank",
            "type": "emi_cashback",
            "discount_pct": 5,
            "max_discount_inr": 1_500,
            "min_order_inr": 12_000,
            "payment_method": "ICICI Credit Card (3-month EMI)",
            "offer_code": "ICICIEMI3",
        })
    return offers


# ── Razorpay Payment Links (mock) ──────────────────────────────────────────────

def get_payment_link(
    session_id: str,
    amount_inr: int,
    description: str = "Razorpay Saathi order",
) -> dict:
    token = hashlib.sha1(f"{session_id}:{amount_inr}".encode()).hexdigest()[:10]
    return {
        "id":           f"plink_{token}",
        "short_url":    f"https://rzp.io/i/{token}",
        "amount":       amount_inr,
        "amount_paise": amount_inr * 100,
        "currency":     "INR",
        "status":       "created",
        "description":  description,
        "mock":         True,
    }


def format_payment_link_for_prompt(link: dict) -> str:
    return (
        f"Razorpay Payment Link generated → {link['short_url']} "
        f"(id: {link['id']}, amount: ₹{link['amount']:,}, status: {link['status']})"
    )


def format_products_for_prompt(products: list[dict]) -> str:
    if not products:
        return "No products found."
    lines = []
    for p in products:
        stock_note = f"{p['stock']} in stock" if p["stock"] < 10 else "In stock"
        lines.append(
            f"• [{p['id']}] {p['name']} — ₹{p['price_inr']:,} | {stock_note}\n"
            f"  {p['description']}"
        )
    return "\n".join(lines)


def format_offers_for_prompt(offers: list[dict]) -> str:
    if not offers:
        return "No bank offers currently available."
    lines = []
    for o in offers:
        if o["type"] == "cashback":
            lines.append(
                f"• {o['bank']} ({o['payment_method']}): "
                f"{o['discount_pct']}% cashback up to ₹{o['max_discount_inr']:,} "
                f"on orders ≥ ₹{o['min_order_inr']:,} [Code: {o['offer_code']}]"
            )
        elif o["type"] == "instant_discount":
            lines.append(
                f"• {o['bank']} ({o['payment_method']}): "
                f"₹{o['discount_flat_inr']:,} off on orders ≥ ₹{o['min_order_inr']:,} "
                f"[Code: {o['offer_code']}]"
            )
        elif o["type"] == "emi_cashback":
            lines.append(
                f"• {o['bank']} ({o['payment_method']}): "
                f"{o['discount_pct']}% cashback up to ₹{o['max_discount_inr']:,} "
                f"on orders ≥ ₹{o['min_order_inr']:,} [Code: {o['offer_code']}]"
            )
    return "\n".join(lines)
