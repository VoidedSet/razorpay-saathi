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

CREATE TABLE IF NOT EXISTS campaigns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    DEFAULT (datetime('now')),
    trigger_type TEXT    NOT NULL,     -- 'stagnant_inventory' | 'cart_abandonment'
    product_id   TEXT    NOT NULL,
    discount_pct REAL    NOT NULL,
    tweet_copy   TEXT,
    payment_link TEXT,                 -- short_url from Razorpay
    link_id      TEXT,                 -- plink_... id
    session_id   TEXT,                 -- set for cart-abandonment campaigns
    manager_note TEXT                  -- why Manager approved this discount
);
"""

# ── Seed data: The Souled Store Sneakers ───────────────────────────────────────

CATALOG_PATH = Path(__file__).parent.parent / "catalog.json"
try:
    with open(CATALOG_PATH, "r") as f:
        _PRODUCTS = json.load(f)
        for p in _PRODUCTS:
            if isinstance(p.get("specs"), dict):
                p["specs"] = json.dumps(p["specs"])
except FileNotFoundError:
    _PRODUCTS = []

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
        if force_reseed:
            db.execute("DROP TABLE IF EXISTS products")
            db.execute("DROP TABLE IF EXISTS users")
            db.execute("DROP TABLE IF EXISTS balance_sheet")
            db.execute("DROP TABLE IF EXISTS carts")
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


def search_products(
    query: str = "", 
    limit: int = 6,
    category: str = None,
    min_price: int = None,
    max_price: int = None,
    specs_filter: dict = None
) -> list[dict]:
    """
    Keyword and exact-spec search across name, brand, category, tags, and JSON specs.
    """
    words = [w.lower() for w in query.split() if len(w) > 1]
    with _conn() as db:
        sql = "SELECT * FROM products WHERE stock > 0"
        params = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if min_price is not None:
            sql += " AND price_inr >= ?"
            params.append(min_price)
        if max_price is not None:
            sql += " AND price_inr <= ?"
            params.append(max_price)
            
        rows = [dict(r) for r in db.execute(sql, params).fetchall()]

    if not words and not specs_filter:
        return [_parse_product(r) for r in rows[:limit]]

    scored: list[tuple[int, dict]] = []
    for row in rows:
        parsed_row = _parse_product(row)
        
        if specs_filter:
            row_specs = parsed_row.get("specs", {})
            match = True
            for k, v in specs_filter.items():
                row_val = row_specs.get(k)
                if isinstance(v, str) and isinstance(row_val, str):
                    if v.lower() != row_val.lower():
                        match = False; break
                elif row_val != v:
                    match = False; break
            if not match:
                continue

        score = 1
        if words:
            searchable = f"{parsed_row['name']} {parsed_row['brand']} {parsed_row['category']} {parsed_row.get('tags', '')}".lower()
            score = sum(1 for w in words if w in searchable)
            
        if score > 0:
            scored.append((score, parsed_row))

    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]


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


# ── Marketing / Campaign helpers ──────────────────────────────────────────────

def mark_stagnant(product_id: str, stock: int = 3) -> bool:
    """
    Simulate stagnant inventory by dropping a product's stock count to a low
    number. The Manager monitors products with stock < 5 to trigger campaigns.
    """
    with _conn() as db:
        rows_affected = db.execute(
            "UPDATE products SET stock = ? WHERE id = ?", (stock, product_id)
        ).rowcount
    return rows_affected > 0


def get_stagnant_products(threshold: int = 5) -> list[dict]:
    """Return products whose stock is below the stagnant threshold."""
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM products WHERE stock > 0 AND stock <= ? ORDER BY stock ASC",
            (threshold,),
        ).fetchall()
    return [_parse_product(dict(r)) for r in rows]


def log_campaign(
    trigger_type: str,
    product_id: str,
    discount_pct: float,
    tweet_copy: str,
    payment_link: str,
    link_id: str,
    session_id: str = "",
    manager_note: str = "",
) -> int:
    """Persist a campaign execution to the campaigns table. Returns new row id."""
    with _conn() as db:
        cur = db.execute(
            """INSERT INTO campaigns
               (trigger_type, product_id, discount_pct, tweet_copy, payment_link, link_id, session_id, manager_note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (trigger_type, product_id, discount_pct, tweet_copy, payment_link, link_id, session_id, manager_note),
        )
        return cur.lastrowid


def get_campaigns(limit: int = 20) -> list[dict]:
    """Return the most recent campaigns, newest first."""
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM campaigns ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
