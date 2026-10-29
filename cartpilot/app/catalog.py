"""Product source. Demo catalog by default; plug Channel3 into search_channel3() for live data."""
import os, re

CATALOG = [
    {"id": "p01", "title": "Single-Origin Coffee Beans 1kg", "price": 24.00, "category": "food", "emoji": "☕", "description": "Medium roast whole beans, notes of chocolate and citrus. Great gift for coffee lovers."},
    {"id": "p02", "title": "Pour-Over Coffee Set", "price": 38.50, "category": "home", "emoji": "🫖", "description": "Glass dripper, carafe and reusable filter for slow coffee at home."},
    {"id": "p03", "title": "Insulated Travel Mug", "price": 19.99, "category": "home", "emoji": "🥤", "description": "Keeps coffee hot for 8 hours. Leak-proof lid."},
    {"id": "p04", "title": "Manual Coffee Grinder", "price": 45.00, "category": "home", "emoji": "⚙️", "description": "Ceramic burr hand grinder, adjustable coarseness, for coffee beans."},
    {"id": "p05", "title": "Gourmet Coffee & Chocolate Gift Box", "price": 32.00, "category": "gifts", "emoji": "🎁", "description": "Curated coffee sampler with dark chocolate. Ready to gift."},
    {"id": "p06", "title": "Bluetooth Earbuds", "price": 59.00, "category": "tech", "emoji": "🎧", "description": "Wireless earbuds with noise reduction and 24h battery."},
    {"id": "p07", "title": "Mechanical Keyboard", "price": 89.00, "category": "tech", "emoji": "⌨️", "description": "Compact 75% hot-swappable keyboard with tactile switches."},
    {"id": "p08", "title": "Noise-Cancelling Headphones", "price": 299.00, "category": "tech", "emoji": "🎧", "description": "Premium over-ear headphones with active noise cancelling."},
    {"id": "p09", "title": "Paperback: Atomic Habits", "price": 14.50, "category": "books", "emoji": "📘", "description": "Bestselling book on building good habits. Great gift for self-improvement fans."},
    {"id": "p10", "title": "Cookbook: Salt Fat Acid Heat", "price": 28.00, "category": "books", "emoji": "📗", "description": "Illustrated cooking book that teaches how to cook anything."},
    {"id": "p11", "title": "Yoga Mat Premium", "price": 34.00, "category": "fitness", "emoji": "🧘", "description": "Non-slip 6mm mat with carrying strap."},
    {"id": "p12", "title": "Adjustable Dumbbell Set", "price": 149.00, "category": "fitness", "emoji": "🏋️", "description": "Adjustable weights 2-20kg for home workouts."},
    {"id": "p13", "title": "Wool Scarf", "price": 26.00, "category": "fashion", "emoji": "🧣", "description": "Soft warm winter scarf. Nice gift for dad or mom."},
    {"id": "p14", "title": "Leather Wallet", "price": 42.00, "category": "fashion", "emoji": "👛", "description": "Slim bifold leather wallet with RFID protection. Classic gift for dad."},
    {"id": "p15", "title": "Building Blocks Set 500pcs", "price": 29.00, "category": "toys", "emoji": "🧱", "description": "Creative building blocks for kids age 6+."},
    {"id": "p16", "title": "Scented Candle Trio", "price": 21.00, "category": "gifts", "emoji": "🕯️", "description": "Three soy candles: vanilla, cedar, citrus. Cozy gift."},
]
_BY_ID = {p["id"]: p for p in CATALOG}
_STOP = {"a", "an", "the", "for", "my", "me", "i", "to", "of", "and", "under", "below", "with", "he", "she",
         "his", "her", "loves", "love", "likes", "like", "gift", "buy", "need", "want", "find", "something",
         "is", "who", "dad", "mom", "birthday"}


def get(pid):
    return _BY_ID.get(pid)


def search_channel3(query, max_price=None):
    """TODO: call the Channel3 product search API here (see Channel3 docs / partner credits)
    and map each result to {id, title, price, category, emoji, description}."""
    raise NotImplementedError


def search(query, max_price=None, limit=5):
    if os.environ.get("CHANNEL3_API_KEY"):
        try:
            return search_channel3(query, max_price)[:limit]
        except NotImplementedError:
            pass  # fall back to demo catalog
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in _STOP]
    scored = []
    for p in CATALOG:
        if max_price is not None and p["price"] > max_price:
            continue
        hay = f"{p['title']} {p['description']} {p['category']}".lower()
        score = sum(2 if w in p["title"].lower() else 1 for w in words if w in hay)
        if score:
            scored.append((score, -p["price"], p))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [p for _, _, p in scored[:limit]]
