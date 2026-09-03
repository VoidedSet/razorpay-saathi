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
    related     TEXT      -- comma-separated product IDs for cross-sell
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

# ── Seed data ─────────────────────────────────────────────────────────────────

_PRODUCTS = [
    # ── Smartphones ──────────────────────────────────────────────────────────
    {
        "id": "prod_sm_s21fe",
        "name": "Samsung Galaxy S21 FE 5G",
        "brand": "Samsung", "category": "smartphone",
        "price_inr": 32999, "stock": 47,
        "description": "Fan Edition flagship with 6.4\" AMOLED 120Hz, IP68, and triple cameras.",
        "specs": json.dumps({"display": "6.4\" AMOLED 120Hz", "chip": "Snapdragon 888",
                             "camera": "12MP+12MP+8MP | 32MP selfie", "battery": "4500mAh",
                             "storage": "128GB", "5g": True, "ip68": True}),
        "tags": "5g,amoled,samsung,mid-range,android,ip68",
        "related": "prod_acc_buds2,prod_acc_samcharger,prod_acc_s21case,prod_acc_glass",
    },
    {
        "id": "prod_sm_s23",
        "name": "Samsung Galaxy S23",
        "brand": "Samsung", "category": "smartphone",
        "price_inr": 74999, "stock": 28,
        "description": "Flagship Samsung with Snapdragon 8 Gen 2, 50MP main camera, and 3600mAh battery.",
        "specs": json.dumps({"display": "6.1\" AMOLED 120Hz", "chip": "Snapdragon 8 Gen 2",
                             "camera": "50MP+12MP+10MP | 12MP selfie", "battery": "3900mAh",
                             "storage": "128GB / 256GB", "5g": True}),
        "tags": "5g,flagship,samsung,snapdragon,android,compact",
        "related": "prod_acc_buds2,prod_acc_samcharger,prod_acc_s23case",
    },
    {
        "id": "prod_sm_s23ultra",
        "name": "Samsung Galaxy S23 Ultra",
        "brand": "Samsung", "category": "smartphone",
        "price_inr": 124999, "stock": 12,
        "description": "Ultimate Samsung flagship with built-in S Pen and 200MP quad-camera system.",
        "specs": json.dumps({"display": "6.8\" AMOLED 120Hz", "chip": "Snapdragon 8 Gen 2",
                             "camera": "200MP+12MP+10MP+10MP | 12MP selfie", "battery": "5000mAh",
                             "storage": "256GB / 512GB", "s_pen": True, "5g": True}),
        "tags": "5g,flagship,samsung,ultra,s-pen,200mp,android",
        "related": "prod_acc_buds2,prod_acc_samcharger",
    },
    {
        "id": "prod_sm_ip15",
        "name": "iPhone 15",
        "brand": "Apple", "category": "smartphone",
        "price_inr": 79900, "stock": 23,
        "description": "Apple's iPhone with Dynamic Island, USB-C, and A16 Bionic chip.",
        "specs": json.dumps({"display": "6.1\" Super Retina XDR", "chip": "A16 Bionic",
                             "camera": "48MP main | 12MP selfie", "usb_c": True, "ios": True}),
        "tags": "apple,iphone,flagship,ios,usb-c,dynamic-island",
        "related": "prod_acc_airpods,prod_acc_ip15case,prod_acc_powerbank",
    },
    {
        "id": "prod_sm_ip15pro",
        "name": "iPhone 15 Pro",
        "brand": "Apple", "category": "smartphone",
        "price_inr": 134900, "stock": 14,
        "description": "Pro titanium iPhone with A17 Pro chip, ProMotion, and Action Button.",
        "specs": json.dumps({"display": "6.1\" Super Retina XDR ProMotion 120Hz",
                             "chip": "A17 Pro", "titanium": True,
                             "camera": "48MP+12MP+12MP 3x telephoto | 12MP selfie"}),
        "tags": "apple,iphone,pro,flagship,ios,titanium,a17pro",
        "related": "prod_acc_airpods,prod_acc_ip15case",
    },
    {
        "id": "prod_sm_op12",
        "name": "OnePlus 12 5G",
        "brand": "OnePlus", "category": "smartphone",
        "price_inr": 64999, "stock": 19,
        "description": "Flagship killer with Snapdragon 8 Gen 3, Hasselblad cameras, and 100W charging.",
        "specs": json.dumps({"display": "6.82\" AMOLED 120Hz", "chip": "Snapdragon 8 Gen 3",
                             "camera": "50MP Hasselblad | 32MP selfie",
                             "battery": "5400mAh 100W", "5g": True}),
        "tags": "5g,flagship-killer,oneplus,snapdragon,android,100w,hasselblad",
        "related": "prod_acc_powerbank,prod_acc_glass",
    },
    {
        "id": "prod_sm_pixel8",
        "name": "Google Pixel 8",
        "brand": "Google", "category": "smartphone",
        "price_inr": 59999, "stock": 16,
        "description": "AI-first phone with Google Tensor G3, 7 years of OS updates, and Magic Eraser.",
        "specs": json.dumps({"display": "6.2\" OLED 120Hz", "chip": "Google Tensor G3",
                             "camera": "50MP main | 10.5MP selfie",
                             "battery": "4575mAh", "5g": True, "updates": "7 years"}),
        "tags": "5g,google,pixel,ai,android,pure,tensor,magic-eraser",
        "related": "prod_acc_powerbank,prod_acc_glass",
    },
    # ── Laptops ───────────────────────────────────────────────────────────────
    {
        "id": "prod_lt_mba_m2",
        "name": "MacBook Air M2",
        "brand": "Apple", "category": "laptop",
        "price_inr": 114900, "stock": 9,
        "description": "Ultra-thin Apple silicon laptop with fanless design and 18-hour battery.",
        "specs": json.dumps({"chip": "Apple M2 8-core", "display": "13.6\" Liquid Retina",
                             "battery": "18 hours", "ram": "8GB unified", "storage": "256GB SSD",
                             "weight": "1.24kg"}),
        "tags": "apple,laptop,macbook,m2,silicon,thin,light,macos",
        "related": "prod_acc_powerbank",
    },
    {
        "id": "prod_lt_dell_xps",
        "name": "Dell XPS 15",
        "brand": "Dell", "category": "laptop",
        "price_inr": 129999, "stock": 7,
        "description": "Premium Windows laptop with Intel i7, OLED display, and RTX 4060.",
        "specs": json.dumps({"cpu": "Intel Core i7-13700H", "gpu": "NVIDIA RTX 4060",
                             "display": "15.6\" OLED 3.5K", "ram": "16GB DDR5",
                             "storage": "512GB SSD"}),
        "tags": "dell,laptop,windows,oled,gaming,premium,rtx",
        "related": "prod_acc_powerbank",
    },
    {
        "id": "prod_lt_rog",
        "name": "ASUS ROG Strix G15",
        "brand": "ASUS", "category": "laptop",
        "price_inr": 89999, "stock": 11,
        "description": "Gaming powerhouse with AMD Ryzen 9, RTX 4070, and 165Hz display.",
        "specs": json.dumps({"cpu": "AMD Ryzen 9 7945HX", "gpu": "NVIDIA RTX 4070",
                             "display": "15.6\" IPS 165Hz", "ram": "16GB DDR5",
                             "storage": "512GB SSD"}),
        "tags": "asus,rog,gaming,laptop,windows,rtx,amd,165hz",
        "related": "prod_acc_powerbank",
    },
    # ── Accessories ───────────────────────────────────────────────────────────
    {
        "id": "prod_acc_buds2",
        "name": "Samsung Galaxy Buds2 Pro",
        "brand": "Samsung", "category": "earbuds",
        "price_inr": 14999, "stock": 58,
        "description": "Premium TWS earbuds with 360 Audio, ANC, and IPX7 water resistance.",
        "specs": json.dumps({"anc": True, "battery": "8hrs + 21hrs (case)",
                             "audio": "360 Audio", "ipx7": True}),
        "tags": "samsung,earbuds,tws,anc,wireless,audio,360audio",
        "related": "prod_sm_s23,prod_sm_s21fe,prod_sm_s23ultra",
    },
    {
        "id": "prod_acc_airpods",
        "name": "Apple AirPods Pro (2nd Gen)",
        "brand": "Apple", "category": "earbuds",
        "price_inr": 24900, "stock": 38,
        "description": "Apple's best earbuds with Adaptive Audio, Transparency mode, and USB-C case.",
        "specs": json.dumps({"anc": True, "battery": "6hrs + 30hrs (case)",
                             "chip": "H2", "usb_c": True, "adaptive_audio": True}),
        "tags": "apple,airpods,pro,earbuds,tws,anc,ios,h2,usb-c",
        "related": "prod_sm_ip15,prod_sm_ip15pro",
    },
    {
        "id": "prod_acc_samcharger",
        "name": "Samsung 45W Super Fast Charger",
        "brand": "Samsung", "category": "charger",
        "price_inr": 2499, "stock": 95,
        "description": "USB-C Power Delivery charger compatible with all Samsung and USB-C devices.",
        "specs": json.dumps({"wattage": 45, "usb_c": True, "pd": True, "cable_included": True}),
        "tags": "samsung,charger,45w,fast-charge,usb-c,accessory,cable",
        "related": "prod_sm_s23,prod_sm_s21fe,prod_sm_s23ultra,prod_sm_op12",
    },
    {
        "id": "prod_acc_powerbank",
        "name": "Anker 20000mAh PowerCore",
        "brand": "Anker", "category": "powerbank",
        "price_inr": 3999, "stock": 67,
        "description": "High-capacity power bank with dual USB-C 65W output for phones and laptops.",
        "specs": json.dumps({"capacity": "20000mAh", "output": "65W USB-C",
                             "ports": "2× USB-C + 1× USB-A", "passthrough": True}),
        "tags": "anker,powerbank,portable,65w,usb-c,charging,accessory,laptop",
        "related": "prod_sm_op12,prod_sm_pixel8,prod_lt_mba_m2,prod_lt_dell_xps",
    },
    {
        "id": "prod_acc_s23case",
        "name": "Spigen Tough Armor (Galaxy S23)",
        "brand": "Spigen", "category": "case",
        "price_inr": 1299, "stock": 74,
        "description": "MIL-STD-810G drop protection with air-cushion technology.",
        "specs": json.dumps({"compatibility": "Samsung Galaxy S23",
                             "protection": "MIL-STD-810G", "material": "TPU+PC"}),
        "tags": "samsung,case,s23,spigen,protection,drop,accessory",
        "related": "prod_sm_s23,prod_sm_s23ultra",
    },
    {
        "id": "prod_acc_s21case",
        "name": "Samsung Leather Cover (Galaxy S21 FE)",
        "brand": "Samsung", "category": "case",
        "price_inr": 1799, "stock": 31,
        "description": "Official Samsung genuine leather cover with card slot for Galaxy S21 FE.",
        "specs": json.dumps({"compatibility": "Samsung Galaxy S21 FE",
                             "material": "genuine leather", "card_slot": True}),
        "tags": "samsung,case,leather,s21fe,official,card-slot,accessory",
        "related": "prod_sm_s21fe",
    },
    {
        "id": "prod_acc_ip15case",
        "name": "Apple iPhone 15 Silicone Case",
        "brand": "Apple", "category": "case",
        "price_inr": 4900, "stock": 46,
        "description": "Official Apple silicone case with MagSafe and microfiber lining.",
        "specs": json.dumps({"compatibility": "iPhone 15",
                             "material": "silicone", "magsafe": True, "microfiber": True}),
        "tags": "apple,case,iphone15,magsafe,silicone,official,accessory",
        "related": "prod_sm_ip15,prod_sm_ip15pro",
    },
    {
        "id": "prod_acc_glass",
        "name": "Belkin ScreenForce Tempered Glass",
        "brand": "Belkin", "category": "screen-protector",
        "price_inr": 799, "stock": 180,
        "description": "9H hardness tempered glass with easy installation tray.",
        "specs": json.dumps({"hardness": "9H", "thickness": "0.33mm",
                             "installation": "easy-tray", "anti_scratch": True}),
        "tags": "screen-protector,tempered-glass,belkin,9h,accessory,universal",
        "related": "prod_sm_op12,prod_sm_pixel8,prod_sm_s21fe,prod_sm_s23",
    },
]

_USERS = [
    {
        "user_id": "usr_001",
        "name": "Alex",
        "email": "alex@example.com",
        "tier": "gold",
        "purchase_history": json.dumps(["prod_sm_s23", "prod_acc_airpods", "prod_acc_powerbank"]),
        "preferences": "electronics,samsung,premium",
        "total_spend_inr": 145000,
        "discount_ceiling_pct": 10,
    },
    {
        "user_id": "usr_002",
        "name": "Priya",
        "email": "priya@example.com",
        "tier": "standard",
        "purchase_history": json.dumps(["prod_sm_ip15"]),
        "preferences": "apple,ios",
        "total_spend_inr": 79900,
        "discount_ceiling_pct": 5,
    },
    {
        "user_id": "usr_003",
        "name": "Ravi",
        "email": "ravi@example.com",
        "tier": "platinum",
        "purchase_history": json.dumps(["prod_lt_mba_m2", "prod_sm_ip15pro", "prod_acc_airpods"]),
        "preferences": "apple,laptop,premium",
        "total_spend_inr": 310000,
        "discount_ceiling_pct": 12,
    },
    {
        "user_id": "agt_001",
        "name": "ShopBot v1",
        "email": "bot@autobuyer.ai",
        "tier": "enterprise",
        "purchase_history": json.dumps([]),
        "preferences": "electronics",
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

def init_db() -> None:
    """Create tables and seed with mock data if empty."""
    with _conn() as db:
        db.executescript(_SCHEMA)
        if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            _seed(db)
    print(f"✅ DB initialised at {DB_PATH}")


def _seed(db: sqlite3.Connection) -> None:
    db.executemany(
        "INSERT OR IGNORE INTO products VALUES (:id,:name,:brand,:category,"
        ":price_inr,:stock,:description,:specs,:tags,:related)",
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
    """Get a single product by ID."""
    with _conn() as db:
        row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _parse_product(dict(row)) if row else None


def get_related_products(product_id: str, limit: int = 3) -> list[dict]:
    """Get cross-sell products linked to a given product."""
    product = get_product(product_id)
    if not product or not product.get("related"):
        return []
    related_ids = product["related"][:limit + 2]   # fetch a few extra in case some are OOS
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
    """
    Mock Razorpay Offers API response.
    In production this would be a live API call:
      GET https://api.razorpay.com/v1/offers?amount={amount}
    """
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
    if amount_inr >= 10_000:
        offers.append({
            "bank": "Kotak Mahindra",
            "type": "instant_discount",
            "discount_flat_inr": 500,
            "min_order_inr": 10_000,
            "payment_method": "Kotak Debit Card",
            "offer_code": "KOTAK500",
        })
    if amount_inr >= 20_000:
        offers.append({
            "bank": "ICICI Bank",
            "type": "emi_cashback",
            "discount_pct": 3,
            "max_discount_inr": 1_500,
            "min_order_inr": 20_000,
            "payment_method": "ICICI Credit Card (3-month EMI)",
            "offer_code": "ICICIEMI3",
        })
    return offers


def format_products_for_prompt(products: list[dict]) -> str:
    """Format a product list into a concise LLM-readable block."""
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
    """Format Razorpay offers into a concise LLM-readable block."""
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
