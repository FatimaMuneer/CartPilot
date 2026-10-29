import json, os, sqlite3, datetime
from .policy import Rules


def _path():
    return os.environ.get("DB_PATH", "cartpilot.db")


def _conn():
    c = sqlite3.connect(_path())
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT, title TEXT, amount REAL, category TEXT,
            decision TEXT, reason TEXT, status TEXT,
            paypal_order_id TEXT, created_at TEXT, paid_at TEXT);
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event TEXT, detail TEXT);
        """)


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def get_rules() -> Rules:
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key='rules'").fetchone()
    return Rules.from_dict(json.loads(row["value"])) if row else Rules()


def set_rules(rules: Rules):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES ('rules', ?)", (json.dumps(rules.to_dict()),))
    log("rules_updated", rules.to_dict())


def log(event, detail=None):
    with _conn() as c:
        c.execute("INSERT INTO audit (ts, event, detail) VALUES (?,?,?)",
                  (now(), event, json.dumps(detail) if detail is not None else ""))


def audit_log(limit=50):
    with _conn() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def add_request(product, decision, reason):
    status = {"block": "blocked", "needs_approval": "awaiting_approval", "allow": "approved"}[decision]
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO requests (product_id,title,amount,category,decision,reason,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (product["id"], product["title"], product["price"], product["category"],
             decision, reason, status, now()))
        rid = cur.lastrowid
    log("purchase_requested", {"request_id": rid, "title": product["title"], "amount": product["price"],
                               "decision": decision, "reason": reason})
    return get_request(rid)


def get_request(rid):
    with _conn() as c:
        r = c.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    return dict(r) if r else None


def set_status(rid, status, **extra):
    sets, vals = ["status=?"], [status]
    for k, v in extra.items():
        sets.append(f"{k}=?"); vals.append(v)
    vals.append(rid)
    with _conn() as c:
        c.execute(f"UPDATE requests SET {', '.join(sets)} WHERE id=?", vals)
    log(f"request_{status}", {"request_id": rid, **extra})


def list_requests(limit=30):
    with _conn() as c:
        rows = c.execute("SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def spent_this_month() -> float:
    month = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    with _conn() as c:
        row = c.execute("SELECT COALESCE(SUM(amount),0) s FROM requests WHERE status='paid' AND paid_at LIKE ?",
                        (month + "%",)).fetchone()
    return round(row["s"], 2)
