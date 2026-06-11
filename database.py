"""
database.py — SIMS SQLite Database Layer
Provides persistent storage for:
  • users          (SIMS_01 Sign Up, SIMS_02 Login)
  • analyzed_posts (SIMS_07 Save Analysis Results)
  • audit_log      (NFR 1.2 Security audit trail)

All functions use bcrypt for password hashing (NFR 1.1).
"""

import sqlite3
import os
import json
import time
from datetime import datetime
from pathlib import Path

try:
    import bcrypt
    _BCRYPT = True
except ImportError:
    _BCRYPT = False
    import hashlib  # Fallback if bcrypt not installed

# ════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════
DB_PATH = Path(__file__).parent / "sims.db"


# ════════════════════════════════════════════════════════════
#  CONNECTION HELPER
# ════════════════════════════════════════════════════════════
def get_connection():
    """Return a SQLite connection with foreign keys ON and row factory set."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ════════════════════════════════════════════════════════════
#  PASSWORD HASHING (NFR 1.1)
# ════════════════════════════════════════════════════════════
def hash_password(plain: str) -> str:
    """Hash a password using bcrypt (fallback: SHA-256 if bcrypt unavailable)."""
    if _BCRYPT:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    # Fallback — not production-grade but keeps the app runnable
    return "sha256$" + hashlib.sha256(plain.encode()).hexdigest()


def verify_password(plain: str, stored_hash: str) -> bool:
    """Verify a plain password against a stored bcrypt (or SHA-256 fallback) hash."""
    if stored_hash.startswith("sha256$"):
        # Legacy / fallback hash
        import hashlib
        return stored_hash == "sha256$" + hashlib.sha256(plain.encode()).hexdigest()
    if _BCRYPT:
        try:
            return bcrypt.checkpw(plain.encode(), stored_hash.encode())
        except Exception:
            return False
    return False


# ════════════════════════════════════════════════════════════
#  SCHEMA INITIALIZATION
# ════════════════════════════════════════════════════════════
def init_db():
    """
    Create all tables if they don't already exist.
    Safe to call on every app startup.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # ── users table (SIMS_01, SIMS_02) ──────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            role          TEXT    NOT NULL DEFAULT 'Analyst',
            created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration safety: ensure email uniqueness is enforced even on
    # existing databases that were created before this constraint was added.
    # CREATE INDEX IF NOT EXISTS is safe to run repeatedly.
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
    except sqlite3.IntegrityError:
        # Existing rows already violate uniqueness — surface a clear message in the log.
        # The app continues; the next create_user() will still hit the UNIQUE check.
        print("[DB] Warning: existing users share emails; unique index could not be applied. "
              "Consider cleaning up duplicate emails.")

    # ── analyzed_posts table (SIMS_07) ──────────────────────
    # FR 1.3: store post, risk score, risk category, timestamp
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analyzed_posts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id       TEXT    NOT NULL,
            user_id        INTEGER,
            original_text  TEXT    NOT NULL,
            preprocessed   TEXT,
            risk_score     REAL    NOT NULL,
            risk_category  TEXT    NOT NULL,
            danger_score   REAL,
            source         TEXT,
            post_timestamp TEXT,
            analyzed_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    # Migration safety: if an older DB is missing danger_score, add it.
    cur.execute("PRAGMA table_info(analyzed_posts)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if 'danger_score' not in existing_cols:
        cur.execute("ALTER TABLE analyzed_posts ADD COLUMN danger_score REAL")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_category ON analyzed_posts(risk_category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_batch    ON analyzed_posts(batch_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_date     ON analyzed_posts(analyzed_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_danger   ON analyzed_posts(danger_score)")

    # ── audit_log table (NFR 1.2) ───────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            username   TEXT,
            details    TEXT,
            success    INTEGER NOT NULL DEFAULT 1,
            timestamp  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(username)")

    conn.commit()

    # ── Seed default admin account if no users exist ───────
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (
            'admin',
            'admin@sims.com',
            hash_password('12345678'),
            'Analyst'
        ))
        conn.commit()
        print("[DB] Seeded default admin account (admin / 12345678)")

    conn.close()


# ════════════════════════════════════════════════════════════
#  USER FUNCTIONS (SIMS_01, SIMS_02)
# ════════════════════════════════════════════════════════════
def create_user(username: str, email: str, password: str, role: str = "Analyst") -> tuple:
    """
    Create a new user account (SIMS_01).
    Each email address can only be registered ONCE.
    Returns (success: bool, message: str).
    """
    username = username.strip().lower()
    email    = email.strip().lower()

    if not username or not email or not password:
        return False, "All fields are required."
    if " " in username:
        return False, "Username cannot contain spaces."
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."

    # ── Pre-check: email already registered? ────────────────
    # We check email FIRST because that's the new constraint.
    # This also gives users a clearer error than a generic IntegrityError.
    conn = get_connection()
    existing_email = conn.execute(
        "SELECT username FROM users WHERE email = ?", (email,)
    ).fetchone()
    if existing_email:
        conn.close()
        msg = "The account has been taken."
        log_event('signup', username, f'Duplicate email: {email}', success=False)
        return False, msg

    # ── Pre-check: username taken? ──────────────────────────
    existing_user = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing_user:
        conn.close()
        msg = "Username already taken. Please choose another."
        log_event('signup', username, msg, success=False)
        return False, msg

    # ── Insert new account ──────────────────────────────────
    success = False
    msg = ""
    try:
        conn.execute("""
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (username, email, hash_password(password), role))
        conn.commit()
        success = True
        msg = f"Account created for @{username}"
    except sqlite3.IntegrityError as e:
        # Race-condition fallback (someone else inserted between our checks)
        err_str = str(e).lower()
        if 'email' in err_str:
            msg = "The account has been taken."
        elif 'username' in err_str:
            msg = "Username already taken. Please choose another."
        else:
            msg = f"Account could not be created: {e}"
    except Exception as e:
        msg = f"Database error: {e}"
    finally:
        conn.close()

    # Log AFTER closing the connection (prevents lock)
    if success:
        log_event('signup', username, f'New account created: {email}', success=True)
    else:
        log_event('signup', username, msg, success=False)
    return success, msg
    return success, msg


def get_user(username: str) -> dict | None:
    """Fetch a user by username. Returns dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.strip().lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def authenticate(username: str, password: str) -> dict | None:
    """
    Authenticate user (SIMS_02).
    Returns user dict on success, None on failure.
    Logs every attempt (NFR 1.2).
    """
    username = username.strip().lower()
    user = get_user(username)

    if user and verify_password(password, user['password_hash']):
        log_event('login', username, 'Successful login', success=True)
        # Don't return the hash
        user.pop('password_hash', None)
        return user

    log_event('login', username, 'Invalid credentials', success=False)
    return None


# ════════════════════════════════════════════════════════════
#  ANALYZED POSTS FUNCTIONS (SIMS_07, SIMS_08, SIMS_09)
# ════════════════════════════════════════════════════════════
def save_analysis_batch(df, user_id: int | None = None) -> str:
    """
    SIMS_07 — Save a batch of analyzed posts.
    Expects df with columns: text, Preprocessed, Risk_Score, Risk_Category
    Optional: source, timestamp
    Returns the batch_id used.
    """
    batch_id = f"batch_{int(time.time())}"
    conn = get_connection()
    cur  = conn.cursor()

    rows = []
    for _, r in df.iterrows():
        # Danger_Score is optional — if missing, default to None (column is nullable)
        danger_val = r.get('Danger_Score', None)
        try:
            danger_val = float(danger_val) if danger_val is not None else None
        except (ValueError, TypeError):
            danger_val = None

        rows.append((
            batch_id,
            user_id,
            str(r.get('text', '')),
            str(r.get('Preprocessed', '')),
            float(r.get('Risk_Score', 0.0)),
            str(r.get('Risk_Category', 'Low Risk')),
            danger_val,
            str(r.get('source', '')) if 'source' in r else None,
            str(r.get('timestamp', '')) if 'timestamp' in r else None,
        ))

    cur.executemany("""
        INSERT INTO analyzed_posts (
            batch_id, user_id, original_text, preprocessed,
            risk_score, risk_category, danger_score, source, post_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    conn.close()
    return batch_id


def get_all_posts(limit: int | None = None):
    """
    SIMS_08 — Retrieve all analyzed posts as a pandas DataFrame.
    """
    import pandas as pd
    conn = get_connection()
    q = """
        SELECT id, batch_id, original_text AS text,
               preprocessed AS Preprocessed,
               risk_score   AS Risk_Score,
               risk_category AS Risk_Category,
               danger_score AS Danger_Score,
               source, post_timestamp, analyzed_at
        FROM analyzed_posts
        ORDER BY analyzed_at DESC
    """
    if limit:
        q += f" LIMIT {int(limit)}"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def get_posts_filtered(risk_category: str = None,
                       min_score: float = 0.0,
                       keyword: str = None,
                       date_from: str = None,
                       date_to: str = None,
                       min_danger: float = 0.0):
    """
    SIMS_08 — Filter analyzed posts by criteria.
    Returns a pandas DataFrame.

    min_danger filters by the weighted danger score (0.0 safe → 1.0 high risk).
    min_score filters by the model's confidence in its own prediction.
    """
    import pandas as pd
    conn = get_connection()
    where, params = [], []

    if risk_category and risk_category != "All":
        where.append("risk_category = ?")
        params.append(risk_category)
    if min_score and min_score > 0:
        where.append("risk_score >= ?")
        params.append(min_score)
    if min_danger and min_danger > 0:
        # Treat NULL danger_score as 0 so legacy rows (pre-migration) aren't
        # accidentally surfaced when the user wants high-danger posts only.
        where.append("COALESCE(danger_score, 0) >= ?")
        params.append(min_danger)
    if keyword and keyword.strip():
        where.append("original_text LIKE ?")
        params.append(f"%{keyword.strip()}%")
    if date_from:
        where.append("analyzed_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("analyzed_at <= ?")
        params.append(date_to)

    q = """
        SELECT id, batch_id, original_text AS text,
               preprocessed AS Preprocessed,
               risk_score   AS Risk_Score,
               risk_category AS Risk_Category,
               danger_score AS Danger_Score,
               source, post_timestamp, analyzed_at
        FROM analyzed_posts
    """
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY analyzed_at DESC"

    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_post_stats() -> dict:
    """Return summary counts for the dashboard KPIs."""
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM analyzed_posts")
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT risk_category, COUNT(*)
        FROM analyzed_posts
        GROUP BY risk_category
    """)
    by_cat = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("SELECT AVG(risk_score) FROM analyzed_posts")
    avg = cur.fetchone()[0] or 0.0

    conn.close()
    return {
        'total':    total,
        'high':     by_cat.get('High Risk', 0),
        'moderate': by_cat.get('Moderate Risk', 0),
        'low':      by_cat.get('Low Risk', 0),
        'avg_score': round(avg, 4),
    }


def clear_all_posts():
    """Delete all analyzed posts (for Clear All button)."""
    conn = get_connection()
    conn.execute("DELETE FROM analyzed_posts")
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
#  HISTORY FUNCTIONS — group analyzed posts by batch
# ════════════════════════════════════════════════════════════
def get_batch_history():
    """
    Return a DataFrame summarising each saved analysis batch.
    One row per batch: batch_id, when it ran, who ran it, totals per category.
    """
    import pandas as pd
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            ap.batch_id,
            MIN(ap.analyzed_at) AS analyzed_at,
            COALESCE(u.username, '—') AS analyst,
            COUNT(*) AS total_posts,
            SUM(CASE WHEN ap.risk_category = 'High Risk' THEN 1 ELSE 0 END)     AS high,
            SUM(CASE WHEN ap.risk_category = 'Moderate Risk' THEN 1 ELSE 0 END) AS moderate,
            SUM(CASE WHEN ap.risk_category = 'Low Risk' THEN 1 ELSE 0 END)      AS low,
            ROUND(AVG(ap.risk_score), 4) AS avg_score,
            ROUND(MAX(ap.risk_score), 4) AS max_score
        FROM analyzed_posts ap
        LEFT JOIN users u ON ap.user_id = u.id
        GROUP BY ap.batch_id
        ORDER BY analyzed_at DESC
    """, conn)
    conn.close()
    return df


def get_batch_posts(batch_id: str):
    """Return all posts belonging to a single batch."""
    import pandas as pd
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT id,
               original_text  AS text,
               preprocessed   AS Preprocessed,
               risk_score     AS Risk_Score,
               risk_category  AS Risk_Category,
               danger_score   AS Danger_Score,
               source, post_timestamp, analyzed_at
        FROM analyzed_posts
        WHERE batch_id = ?
        ORDER BY COALESCE(danger_score, 0) DESC, risk_score DESC
    """, conn, params=(batch_id,))
    conn.close()
    return df


def delete_batch(batch_id: str):
    """Delete a single batch from history."""
    conn = get_connection()
    conn.execute("DELETE FROM analyzed_posts WHERE batch_id = ?", (batch_id,))
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
#  AUDIT LOG FUNCTIONS (NFR 1.2)
# ════════════════════════════════════════════════════════════
def log_event(event_type: str, username: str = None,
              details: str = "", success: bool = True):
    """Append an event to the audit log."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO audit_log (event_type, username, details, success)
        VALUES (?, ?, ?, ?)
    """, (event_type, username, details, 1 if success else 0))
    conn.commit()
    conn.close()


def get_audit_log(limit: int = 500):
    """Fetch the audit log as a pandas DataFrame."""
    import pandas as pd
    conn = get_connection()
    df = pd.read_sql_query(f"""
        SELECT timestamp, event_type, username, details, success
        FROM audit_log
        ORDER BY id DESC
        LIMIT {int(limit)}
    """, conn)
    conn.close()
    return df