"""Small SQLite persistence layer for the local/demo backend."""
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


def database_path() -> Path:
    return Path(os.getenv("RIPPLE_DB_PATH", Path(__file__).resolve().parents[2] / "data" / "ripple.sqlite3"))


@contextmanager
def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS linked_accounts(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, provider TEXT NOT NULL, customer_id TEXT NOT NULL, account_id TEXT NOT NULL, linked_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, source TEXT NOT NULL, external_id TEXT NOT NULL, transaction_type TEXT NOT NULL, amount TEXT NOT NULL, date TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL, raw_json TEXT NOT NULL, UNIQUE(user_id, source, external_id));
        CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, store TEXT, date TEXT, total TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS receipt_items(id TEXT PRIMARY KEY, receipt_id TEXT NOT NULL REFERENCES receipts(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL, price TEXT NOT NULL, category TEXT NOT NULL, carbon_kg_co2e TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shopping_items(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL, price REAL NOT NULL, brand TEXT, category TEXT NOT NULL, allow_lower_quality INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, date);
        CREATE INDEX IF NOT EXISTS idx_receipts_user_date ON receipts(user_id, date);
        """)


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000).hex()


def create_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    salt = secrets.token_bytes(16)
    uid = str(uuid4())
    try:
        with connect() as c:
            c.execute("INSERT INTO users VALUES(?,?,?,?,?)", (uid, email, salt.hex(), _hash(password, salt), datetime.now(timezone.utc).isoformat()))
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.") from None
    return {"id": uid, "email": email}


def authenticate(email: str, password: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if row is None or not secrets.compare_digest(row["password_hash"], _hash(password, bytes.fromhex(row["salt"]))):
        return None
    return {"id": row["id"], "email": row["email"]}


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(36)
    expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    with connect() as c:
        c.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user_id, expiry))
    return token


def session_user(token: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT u.id,u.email,s.expires_at,s.token_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None: return None
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            c.execute("DELETE FROM sessions WHERE token_hash=?", (row["token_hash"],)); return None
        return {"id": row["id"], "email": row["email"]}


def delete_session(token: str) -> None:
    with connect() as c: c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def save_receipt(user_id: str, receipt: dict) -> dict:
    rid, now = str(uuid4()), datetime.now(timezone.utc)
    row = {"id": rid, "store": receipt.get("store"), "date": receipt.get("date"), "total": receipt.get("total"), "created_at": now, "items": []}
    with connect() as c:
        c.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?)", (rid,user_id,row["store"],str(row["date"]) if row["date"] else None,str(row["total"]) if row["total"] is not None else None,now.isoformat()))
        for line in receipt["items"]:
            item={"id":str(uuid4()),"receipt_id":rid,"name":line["name"],"price":line["price"],"category":line["category"],"carbon_kg_co2e":line["carbon_kg_co2e"]}
            c.execute("INSERT INTO receipt_items VALUES(?,?,?,?,?,?,?)",(item["id"],rid,user_id,item["name"],str(item["price"]),item["category"],str(item["carbon_kg_co2e"])))
            row["items"].append(item)
    return row


def get_receipt(user_id: str, rid: str) -> dict | None:
    with connect() as c:
        r=c.execute("SELECT * FROM receipts WHERE id=? AND user_id=?",(rid,user_id)).fetchone()
        if not r:return None
        return _receipt_row(c,r)


def _receipt_row(c,r):
    return {"id":r["id"],"store":r["store"],"date":date.fromisoformat(r["date"]) if r["date"] else None,"total":r["total"],"created_at":datetime.fromisoformat(r["created_at"]),"items":[{"id":x["id"],"receipt_id":x["receipt_id"],"name":x["name"],"price":x["price"],"category":x["category"],"carbon_kg_co2e":x["carbon_kg_co2e"]} for x in c.execute("SELECT * FROM receipt_items WHERE receipt_id=?",(r["id"],))]}


def list_receipts(user_id: str) -> list[dict]:
    with connect() as c:return [_receipt_row(c,r) for r in c.execute("SELECT * FROM receipts WHERE user_id=? ORDER BY COALESCE(date,created_at) DESC",(user_id,))]


def save_link(user_id: str, customer_id: str, account_id: str) -> None:
    with connect() as c:c.execute("INSERT INTO linked_accounts VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET provider=excluded.provider,customer_id=excluded.customer_id,account_id=excluded.account_id,linked_at=excluded.linked_at",(user_id,"nessie",customer_id,account_id,datetime.now(timezone.utc).isoformat()))


def get_link(user_id: str) -> dict | None:
    with connect() as c:
        r=c.execute("SELECT customer_id,account_id FROM linked_accounts WHERE user_id=?",(user_id,)).fetchone()
        return dict(r) if r else None


def upsert_transactions(user_id: str, rows: list[dict]) -> int:
    count=0
    with connect() as c:
        for t in rows:
            if not t.get("id"):continue
            c.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,source,external_id) DO UPDATE SET transaction_type=excluded.transaction_type,amount=excluded.amount,date=excluded.date,description=excluded.description,category=excluded.category,raw_json=excluded.raw_json",(str(uuid4()),user_id,t["source"],str(t["id"]),t["type"],str(t["amount"]),str(t["date"]),t["description"],t["category"],json.dumps(t.get("raw",{}),default=str)))
            count+=1
    return count


def transactions(user_id: str) -> list[dict]:
    with connect() as c:
        rows=c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC",(user_id,)).fetchall()
        return [{"id":r["external_id"],"type":r["transaction_type"],"date":date.fromisoformat(r["date"]),"amount":r["amount"],"description":r["description"],"category":r["category"],"source":r["source"]} for r in rows]


def ledger_entries(user_id: str) -> list[dict]:
    return [{"date":t["date"],"amount":t["amount"],"source":t["source"],"type":t["type"]} for t in transactions(user_id) if t["type"] in {"purchase","withdrawal","expense"}]


def add_shopping_item(user_id: str, item: dict) -> dict:
    row={"id":str(uuid4()),**item}
    with connect() as c:c.execute("INSERT INTO shopping_items VALUES(?,?,?,?,?,?,?)",(row["id"],user_id,row["name"],row["price"],row.get("brand"),row["category"],int(row["allow_lower_quality"])))
    return row


def list_shopping_items(user_id: str) -> list[dict]:
    with connect() as c:return [{**dict(r),"allow_lower_quality":bool(r["allow_lower_quality"])} for r in c.execute("SELECT * FROM shopping_items WHERE user_id=?",(user_id,))]


def delete_shopping_item(user_id: str, iid: str) -> bool:
    with connect() as c:cur=c.execute("DELETE FROM shopping_items WHERE id=? AND user_id=?",(iid,user_id));return cur.rowcount>0
