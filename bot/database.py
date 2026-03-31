"""Модуль работы с базой данных SQLite."""

import aiosqlite
import json
from datetime import datetime, timedelta
from config import DB_PATH, DEFAULT_SUBSCRIPTION_PRICE, DEFAULT_EXTRA_ACCOUNT_PRICE, DEFAULT_REFERRAL_BONUS_DAYS, TRIAL_DAYS


async def init_db():
    """Инициализация базы данных."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_end TEXT,
                max_accounts INTEGER DEFAULT 1,
                referrer_id INTEGER,
                is_banned INTEGER DEFAULT 0,
                created_at TEXT,
                trial_given INTEGER DEFAULT 0,
                today_sent INTEGER DEFAULT 0,
                today_date TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone TEXT,
                api_id TEXT,
                api_hash TEXT,
                session_string TEXT,
                added_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                text TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipient_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                usernames TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mailings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_id INTEGER,
                phone TEXT,
                text TEXT,
                total INTEGER,
                sent INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                failed_usernames TEXT DEFAULT '[]',
                started_at TEXT,
                finished_at TEXT,
                status TEXT DEFAULT 'running',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                currency TEXT DEFAULT 'USD',
                invoice_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_mailings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_id INTEGER,
                text TEXT,
                usernames TEXT,
                delay INTEGER,
                break_after INTEGER,
                break_duration INTEGER,
                scheduled_time TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        # Инициализация настроек по умолчанию
        for key, val in [
            ("subscription_price", str(DEFAULT_SUBSCRIPTION_PRICE)),
            ("extra_account_price", str(DEFAULT_EXTRA_ACCOUNT_PRICE)),
            ("referral_bonus_days", str(DEFAULT_REFERRAL_BONUS_DAYS)),
        ]:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, val)
            )
        await db.commit()


# ==================== USERS ====================

async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_user(user_id: int, username: str, first_name: str, referrer_id: int = None):
    now = datetime.utcnow().isoformat()
    sub_end = (datetime.utcnow() + timedelta(days=TRIAL_DAYS)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users 
            (user_id, username, first_name, subscription_end, referrer_id, created_at, trial_given, today_date)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (user_id, username, first_name, sub_end, referrer_id, now, now[:10])
        )
        await db.commit()


async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", vals)
        await db.commit()


async def is_subscribed(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    if user["subscription_end"] == "forever":
        return True
    try:
        end = datetime.fromisoformat(user["subscription_end"])
        return datetime.utcnow() < end
    except (TypeError, ValueError):
        return False


async def get_today_sent(user_id: int) -> int:
    user = await get_user(user_id)
    if not user:
        return 0
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if user.get("today_date") != today:
        await update_user(user_id, today_sent=0, today_date=today)
        return 0
    return user.get("today_sent", 0)


async def increment_today_sent(user_id: int, count: int = 1):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    user = await get_user(user_id)
    if user.get("today_date") != today:
        await update_user(user_id, today_sent=count, today_date=today)
    else:
        await update_user(user_id, today_sent=(user.get("today_sent", 0) + count))


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def get_user_by_username(username: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            (username.lstrip('@'),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== ACCOUNTS ====================

async def get_accounts(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM accounts WHERE user_id = ?", (user_id,))
        return [dict(r) for r in await cursor.fetchall()]


async def get_account(account_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def add_account(user_id: int, phone: str, api_id: str, api_hash: str, session_string: str) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO accounts (user_id, phone, api_id, api_hash, session_string, added_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, phone, api_id, api_hash, session_string, now)
        )
        await db.commit()
        return cursor.lastrowid


async def delete_account(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()


# ==================== TEMPLATES ====================

async def get_templates(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM templates WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return [dict(r) for r in await cursor.fetchall()]


async def add_template(user_id: int, name: str, text: str) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO templates (user_id, name, text, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, text, now)
        )
        await db.commit()
        return cursor.lastrowid


async def delete_template(template_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        await db.commit()


async def get_template(template_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== RECIPIENT LISTS ====================

async def get_recipient_lists(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM recipient_lists WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return [dict(r) for r in await cursor.fetchall()]


async def add_recipient_list(user_id: int, name: str, usernames: list[str]) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO recipient_lists (user_id, name, usernames, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, json.dumps(usernames), now)
        )
        await db.commit()
        return cursor.lastrowid


async def delete_recipient_list(list_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM recipient_lists WHERE id = ?", (list_id,))
        await db.commit()


async def get_recipient_list(list_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM recipient_lists WHERE id = ?", (list_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== MAILINGS ====================

async def create_mailing(user_id: int, account_id: int, phone: str, text: str, total: int) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO mailings (user_id, account_id, phone, text, total, started_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, account_id, phone, text, total, now)
        )
        await db.commit()
        return cursor.lastrowid


async def update_mailing(mailing_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [mailing_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE mailings SET {sets} WHERE id = ?", vals)
        await db.commit()


async def get_mailing(mailing_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM mailings WHERE id = ?", (mailing_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_mailings(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM mailings WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
            (user_id, limit)
        )
        return [dict(r) for r in await cursor.fetchall()]


# ==================== PAYMENTS ====================

async def create_payment(user_id: int, pay_type: str, amount: float, invoice_id: str) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO payments (user_id, type, amount, invoice_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, pay_type, amount, invoice_id, now)
        )
        await db.commit()
        return cursor.lastrowid


async def update_payment_status(invoice_id: str, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payments SET status = ? WHERE invoice_id = ?", (status, invoice_id))
        await db.commit()


async def get_payment_by_invoice(invoice_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_payments_stats(days: int = None) -> dict:
    """Статистика платежей за период."""
    async with aiosqlite.connect(DB_PATH) as db:
        if days is not None:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'paid' AND created_at >= ?",
                (since,)
            )
        else:
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'paid'"
            )
        row = await cursor.fetchone()
        return {"count": row[0], "total": row[1]}


# ==================== SETTINGS ====================

async def get_setting(key: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


async def get_subscription_price() -> float:
    val = await get_setting("subscription_price")
    return float(val) if val else DEFAULT_SUBSCRIPTION_PRICE


async def get_extra_account_price() -> float:
    val = await get_setting("extra_account_price")
    return float(val) if val else DEFAULT_EXTRA_ACCOUNT_PRICE


async def get_referral_bonus_days() -> int:
    val = await get_setting("referral_bonus_days")
    return int(val) if val else DEFAULT_REFERRAL_BONUS_DAYS


# ==================== SCHEDULED ====================

async def add_scheduled_mailing(user_id: int, account_id: int, text: str, usernames: list[str],
                                 delay: int, break_after: int, break_duration: int,
                                 scheduled_time: str) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO scheduled_mailings 
            (user_id, account_id, text, usernames, delay, break_after, break_duration, scheduled_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, account_id, text, json.dumps(usernames), delay, break_after, break_duration, scheduled_time, now)
        )
        await db.commit()
        return cursor.lastrowid


async def get_scheduled_mailings(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM scheduled_mailings WHERE user_id = ? AND status = 'pending' ORDER BY scheduled_time",
            (user_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def cancel_scheduled_mailing(sched_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE scheduled_mailings SET status = 'cancelled' WHERE id = ?", (sched_id,))
        await db.commit()


async def get_scheduled_mailing(sched_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM scheduled_mailings WHERE id = ?", (sched_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_scheduled_status(sched_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE scheduled_mailings SET status = ? WHERE id = ?", (status, sched_id))
        await db.commit()
