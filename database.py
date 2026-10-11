
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).with_name("coin_rush.db")


def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                coins INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referred_id INTEGER PRIMARY KEY,
                referrer_id INTEGER NOT NULL,
                rewarded INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referred_id) REFERENCES users(user_id),
                FOREIGN KEY (referrer_id) REFERENCES users(user_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_rewards (
                user_id INTEGER PRIMARY KEY,
                claimed_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                coins INTEGER NOT NULL,
                upi_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)


def register_user(user_id, username=None):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        conn.execute(
            """
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET username = excluded.username
            """,
            (user_id, username),
        )

        return existing is None


def get_balance(user_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT coins FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    return row["coins"] if row else 0


def add_coins(user_id, amount):
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("Coin amount must be a positive integer")

    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE users SET coins = coins + ? WHERE user_id = ?",
            (amount, user_id),
        )

        if cursor.rowcount == 0:
            raise ValueError("User is not registered")

def claim_daily_reward(user_id, amount=100):
    import time
    now = int(time.time())

    with get_db() as conn:
        row = conn.execute(
            "SELECT claimed_at FROM daily_rewards WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row and now - row["claimed_at"] < 86400:
            return False

        conn.execute(
            "INSERT INTO daily_rewards (user_id, claimed_at) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET claimed_at = excluded.claimed_at",
            (user_id, now),
        )
        conn.execute(
            "UPDATE users SET coins = coins + ? WHERE user_id = ?",
            (amount, user_id),
        )
        return True
def create_withdrawal(user_id, coins, upi_id):
    if not isinstance(coins, int) or coins <= 0:
        raise ValueError("Invalid coin amount")

    conn = sqlite3.connect(DB_FILE, timeout=30)
    try:
        conn.execute("BEGIN IMMEDIATE")

        cur = conn.execute(
            "UPDATE users SET coins = coins - ? "
            "WHERE user_id = ? AND coins >= ?",
            (coins, user_id, coins),
        )

        if cur.rowcount != 1:
            conn.rollback()
            return None

        cur = conn.execute(
            "INSERT INTO withdrawals (user_id, coins, upi_id) "
            "VALUES (?, ?, ?)",
            (user_id, coins, upi_id),
        )

        withdrawal_id = cur.lastrowid
        conn.commit()
        return withdrawal_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_pending_withdrawal(user_id):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, coins, upi_id FROM withdrawals "
            "WHERE user_id = ? AND status = 'PENDING' "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def confirm_withdrawal(withdrawal_id):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    try:
        cur = conn.cursor()
        cur.execute(
             "UPDATE withdrawals SET status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND status = 'PENDING'",
            (withdrawal_id,),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()

def reject_withdrawal(withdrawal_id):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "SELECT user_id, coins FROM withdrawals "
            "WHERE id = ? AND status = 'PENDING'",
            (withdrawal_id,),
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return None

        user_id, coins = row
        conn.execute(
            "UPDATE withdrawals SET status = 'REJECTED' "
            "WHERE id = ? AND status = 'PENDING'",
            (withdrawal_id,),
        )
        conn.execute(
            "UPDATE users SET coins = coins + ? WHERE user_id = ?",
            (coins, user_id),
        )
        conn.commit()
        return user_id, coins
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_withdrawal_by_id(withdrawal_id):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    try:
        cur = conn.execute(
            "SELECT id, user_id, coins, upi_id, status "
            "FROM withdrawals WHERE id = ?",
            (withdrawal_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("DATABASE READY")



def process_referral(referred_id, referrer_id, bonus=500):
    if referred_id == referrer_id:
        return False

    with get_db() as conn:
        referrer = conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (referrer_id,),
        ).fetchone()

        if referrer is None:
            return False

        existing = conn.execute(
            "SELECT 1 FROM referrals WHERE referred_id = ?",
            (referred_id,),
        ).fetchone()

        if existing is not None:
            return False

        conn.execute(
            """
            INSERT INTO referrals (referred_id, referrer_id, rewarded)
            VALUES (?, ?, 1)
            """,
            (referred_id, referrer_id),
        )

        conn.execute(
            "UPDATE users SET coins = coins + ? WHERE user_id = ?",
            (bonus, referrer_id),
        )

        return True
def get_daily_reward_remaining(user_id):
    import time

    with get_db() as conn:
        row = conn.execute(
            "SELECT claimed_at FROM daily_rewards WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    if row is None:
        return 0

    elapsed = int(time.time()) - row["claimed_at"]
    remaining = 86400 - elapsed

    return max(0, remaining)
