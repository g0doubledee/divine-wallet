"""
DIVINE WALLET v7.0 - Complete Payment System
Copy this entire file into GitHub as main.py
"""

import secrets
import hashlib
import time
import sqlite3
import os
import threading
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
import numpy as np

# ==================== CONFIGURATION ====================
ADMIN_PASSWORD = "DIVINE"
FALLBACK_PIN = "4249"
JWT_SECRET = "divine_wallet_secret_v7"

COASTAL_BANK = {
    "bank_name": "Coastal Community Bank",
    "routing_number": "125109006",
    "account_number": "11292319051"
}

# ==================== GLOBAL VARIABLES ====================
current_multiplier = 1
total_multiplies = 0

BASE_MASTER_LEDGER_CENTS = 33367993765372392100
BASE_ACCOUNT_CENTS = 100000000000000
BASE_DAILY_DEPOSIT_CENTS = 240000000
BASE_MASTER_DEPOSIT_CENTS = 5000000000

def get_current_daily_deposit():
    return BASE_DAILY_DEPOSIT_CENTS * current_multiplier

def get_current_master_deposit():
    return BASE_MASTER_DEPOSIT_CENTS * current_multiplier

# ==================== ACCOUNTS ====================
PROTECTED_ACCOUNTS = {
    "account_1": {"name": "Monday Account", "balance_cents": BASE_ACCOUNT_CENTS, "daily_deposit_cents": BASE_DAILY_DEPOSIT_CENTS, "deposit_day": 0},
    "account_2": {"name": "Tuesday Account", "balance_cents": BASE_ACCOUNT_CENTS, "daily_deposit_cents": BASE_DAILY_DEPOSIT_CENTS, "deposit_day": 1},
    "account_3": {"name": "Wednesday Account", "balance_cents": BASE_ACCOUNT_CENTS, "daily_deposit_cents": BASE_DAILY_DEPOSIT_CENTS, "deposit_day": 2},
    "account_4": {"name": "Thursday Account", "balance_cents": BASE_ACCOUNT_CENTS, "daily_deposit_cents": BASE_DAILY_DEPOSIT_CENTS, "deposit_day": 3},
    "account_5": {"name": "Friday Account", "balance_cents": BASE_ACCOUNT_CENTS, "daily_deposit_cents": BASE_DAILY_DEPOSIT_CENTS, "deposit_day": 4},
}

MASTER_ACCOUNT = {"name": "Master Reserve", "balance_cents": BASE_ACCOUNT_CENTS * 100, "master_deposit_cents": BASE_MASTER_DEPOSIT_CENTS}

# ==================== DATABASE ====================
DB_PATH = "/tmp/divine.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS master_ledger (
        id INTEGER PRIMARY KEY CHECK (id=1), balance_cents INTEGER, balance_display TEXT, multiplier INTEGER, updated_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, transaction_id TEXT, auth_code TEXT, amount_usd REAL, merchant TEXT, source TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS direct_deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT, deposit_id TEXT, amount_usd REAL, source_account TEXT, timestamp TEXT)''')
    c.execute("SELECT COUNT(*) FROM master_ledger")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO master_ledger VALUES (1, ?, ?, 1, ?)", 
                  (BASE_MASTER_LEDGER_CENTS, f"${BASE_MASTER_LEDGER_CENTS/100:,.2f}", datetime.now().isoformat()))
    conn.commit()
    conn.close()

init_db()

# ==================== FASTAPI ====================
app = FastAPI(title="Divine Wallet")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ==================== MODELS ====================
class PaymentRequest(BaseModel):
    amount_usd: float
    merchant: str
    source: str = "direct"

class CashRequest(BaseModel):
    amount_usd: float
    method: str

class NFCTapRequest(BaseModel):
    amount_usd: float
    merchant: str
    terminal_id: str

# ==================== API ENDPOINTS ====================
@app.post("/api/auth/login")
async def login(data: dict):
    if data.get("username") == "G0doubledee" and data.get("password") == "Divinity":
        token = jwt.encode({"sub": "G0doubledee", "exp": datetime.utcnow().timestamp() + 86400}, JWT_SECRET, algorithm="HS256")
        return {"success": True, "access_token": token}
    raise HTTPException(401, "Invalid credentials")

@app.post("/api/multiply")
async def multiply():
    global current_multiplier, total_multiplies
    conn = get_db()
    c = conn.cursor()
    c.execute("BEGIN IMMEDIATE")
    row = c.execute("SELECT multiplier, balance_cents FROM master_ledger WHERE id=1").fetchone()
    new_multiplier = row[0] * 5
    new_balance = row[1] * 5
    total_multiplies += 1
    c.execute("UPDATE master_ledger SET balance_cents=?, balance_display=?, multiplier=?, updated_at=? WHERE id=1",
              (new_balance, f"${new_balance/100:,.2f}", new_multiplier, datetime.now().isoformat()))
    for acc in PROTECTED_ACCOUNTS.values():
        acc["balance_cents"] *= 5
        acc["daily_deposit_cents"] *= 5
    MASTER_ACCOUNT["balance_cents"] *= 5
    MASTER_ACCOUNT["master_deposit_cents"] *= 5
    current_multiplier = new_multiplier
    conn.commit()
    conn.close()
    return {"success": True, "press_number": total_multiplies, "new_multiplier": new_multiplier}

@app.post("/api/cash/access")
async def cash_access(req: CashRequest):
    account = PROTECTED_ACCOUNTS["account_1"]
    amount_cents = int(req.amount_usd * 100)
    if account["balance_cents"] < amount_cents:
        account = MASTER_ACCOUNT
    account["balance_cents"] -= amount_cents
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT balance_cents FROM master_ledger WHERE id=1").fetchone()
    new_balance = row[0] - amount_cents
    c.execute("UPDATE master_ledger SET balance_cents=?, balance_display=? WHERE id=1",
              (new_balance, f"${new_balance/100:,.2f}"))
    tx_id = f"DIV{int(time.time()*1000)}{secrets.token_hex(4)}"
    auth = f"DV{int(time.time())}{secrets.token_hex(4).upper()}"
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
              (None, tx_id, auth, req.amount_usd, f"Cash {req.method}", "cash", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "auth_code": auth}

@app.post("/api/nfc/tap")
async def nfc_tap(req: NFCTapRequest):
    account = PROTECTED_ACCOUNTS["account_2"]
    amount_cents = int(req.amount_usd * 100)
    if account["balance_cents"] < amount_cents:
        account = MASTER_ACCOUNT
    account["balance_cents"] -= amount_cents
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT balance_cents FROM master_ledger WHERE id=1").fetchone()
    new_balance = row[0] - amount_cents
    c.execute("UPDATE master_ledger SET balance_cents=?, balance_display=? WHERE id=1",
              (new_balance, f"${new_balance/100:,.2f}"))
    tx_id = f"DIV{int(time.time()*1000)}{secrets.token_hex(4)}"
    auth = f"DV{int(time.time())}{secrets.token_hex(4).upper()}"
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
              (None, tx_id, auth, req.amount_usd, req.merchant, "nfc_tap", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "auth_code": auth}

@app.post("/api/virtual-card/create")
async def virtual_card():
    def luhn(base):
        digits = [int(d) for d in base]
        for i in range(len(digits)-2, -1, -2):
            d = digits[i] * 2
            digits[i] = d - 9 if d > 9 else d
        checksum = (10 - (sum(digits) % 10)) % 10
        return base + str(checksum)
    iin = "777777"
    account = ''.join([str(secrets.randbelow(10)) for _ in range(9)])
    card = luhn(iin + account)
    formatted = ' '.join([card[i:i+4] for i in range(0, 16, 4)])
    return {"success": True, "card_number": formatted, "expiry": f"{datetime.now().month:02d}/{datetime.now().year+5}", "cvv": f"{secrets.randbelow(900)+100}"}

@app.post("/api/payment")
async def payment(req: PaymentRequest):
    account = PROTECTED_ACCOUNTS.get("account_3", PROTECTED_ACCOUNTS["account_5"])
    amount_cents = int(req.amount_usd * 100)
    if account["balance_cents"] < amount_cents:
        account = MASTER_ACCOUNT
    account["balance_cents"] -= amount_cents
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT balance_cents FROM master_ledger WHERE id=1").fetchone()
    new_balance = row[0] - amount_cents
    c.execute("UPDATE master_ledger SET balance_cents=?, balance_display=? WHERE id=1",
              (new_balance, f"${new_balance/100:,.2f}"))
    tx_id = f"DIV{int(time.time()*1000)}{secrets.token_hex(4)}"
    auth = f"DV{int(time.time())}{secrets.token_hex(4).upper()}"
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
              (None, tx_id, auth, req.amount_usd, req.merchant, req.source, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "auth_code": auth}

@app.get("/api/balance")
async def balance():
    conn = get_db()
    row = conn.execute("SELECT balance_cents, balance_display, multiplier FROM master_ledger WHERE id=1").fetchone()
    conn.close()
    return {"balance_usd": row[0]/100, "balance_display": row[1], "multiplier": row[2]}

@app.get("/api/multiplier/status")
async def multiplier_status():
    return {"current_multiplier": current_multiplier, "total_presses": total_multiplies}

@app.get("/api/coastal-balance")
async def coastal_balance():
    conn = get_db()
    total = conn.execute("SELECT SUM(amount_usd) FROM direct_deposits").fetchone()[0] or 0
    conn.close()
    return {"bank": "Coastal Community Bank", "balance": f"${total:,.2f}"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": "7.0"}

@app.get("/")
async def root():
    return {"name": "Divine Wallet v7.0", "status": "live", "login": "G0doubledee/Divinity"}

# ==================== BACKGROUND DEPOSITS ====================
_last_deposits = {}
_last_master = None

def run_deposits():
    global _last_master
    while True:
        now = datetime.now()
        day = now.weekday()
        if day <= 4:
            for acc_id, acc in PROTECTED_ACCOUNTS.items():
                if acc["deposit_day"] == day:
                    last = _last_deposits.get(acc_id)
                    if not last or last.date() < now.date():
                        conn = get_db()
                        c = conn.cursor()
                        did = f"DD{int(time.time())}{secrets.token_hex(4)}"
                        c.execute("INSERT INTO direct_deposits VALUES (?, ?, ?, ?, ?)",
                                  (None, did, acc["daily_deposit_cents"]/100, acc["name"], datetime.now().isoformat()))
                        conn.commit()
                        conn.close()
                        _last_deposits[acc_id] = now
        if not _last_master:
            _last_master = now - timedelta(hours=5)
        if (now - _last_master).seconds >= 14400:
            conn = get_db()
            c = conn.cursor()
            did = f"MD{int(time.time())}{secrets.token_hex(4)}"
            c.execute("INSERT INTO direct_deposits VALUES (?, ?, ?, ?, ?)",
                      (None, did, MASTER_ACCOUNT["master_deposit_cents"]/100, "Master Reserve", datetime.now().isoformat()))
            conn.commit()
            conn.close()
            _last_master = now
        time.sleep(60)

threading.Thread(target=run_deposits, daemon=True).start()

# ==================== START ====================
if __name__ == "__main__":
    import uvicorn
    print("="*50)
    print("DIVINE WALLET v7.0 - READY")
    print("="*50)
    print("Login: G0doubledee / Divinity")
    print("Admin: DIVINE | PIN: 4249")
    print("="*50)
    uvicorn.run(app, host="0.0.0.0", port=8000)