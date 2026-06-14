"""
database.py — SIMS SQLite Database Layer
FIX: All history/batch/post functions now accept user_id and filter
     to only that user's data. Previously no WHERE user_id clause
     existed, so all users saw each other's history.
"""

import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

try:
    import bcrypt
    _BCRYPT = True
except ImportError:
    _BCRYPT = False

DB_PATH = Path(__file__).parent / "sims.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Password hashing (NFR 1.1) ───────────────────────────────
def hash_password(plain: str) -> str:
    if _BCRYPT:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    return "sha256$" + hashlib.sha256(plain.encode()).hexdigest()


def verify_password(plain: str, stored_hash: str) -> bool:
    if stored_hash.startswith("sha256$"):
        return stored_hash == "sha256$" + hashlib.sha256(plain.encode()).hexdigest()
    if _BCRYPT:
        try:
            return bcrypt.checkpw(plain.encode(), stored_hash.encode())
        except Exception:
            return False
    return False


# ── Schema init ──────────────────────────────────────────────
def init_db():
    conn = get_connection()
    cur  = conn.cursor()

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
    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        )
    except sqlite3.IntegrityError:
        pass

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

    # Migration: add danger_score column on old DBs
    cur.execute("PRAGMA table_info(analyzed_posts)")
    cols = {row[1] for row in cur.fetchall()}
    if 'danger_score' not in cols:
        cur.execute("ALTER TABLE analyzed_posts ADD COLUMN danger_score REAL")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_category ON analyzed_posts(risk_category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_batch    ON analyzed_posts(batch_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_date     ON analyzed_posts(analyzed_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_danger   ON analyzed_posts(danger_score)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_user     ON analyzed_posts(user_id)")

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

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
            ('admin', 'admin@sims.com', hash_password('12345678'), 'Analyst')
        )
        conn.commit()
        print("[DB] Seeded default admin (admin / 12345678)")

    conn.close()


# ── User functions ───────────────────────────────────────────
def create_user(username: str, email: str, password: str,
                role: str = "Analyst") -> tuple:
    username = username.strip().lower()
    email    = email.strip().lower()

    if not username or not email or not password:
        return False, "All fields are required."
    if " " in username:
        return False, "Username cannot contain spaces."
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."

    conn = get_connection()
    if conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
        conn.close()
        log_event('signup', username, f'Duplicate email: {email}', success=False)
        return False, "The account has been taken."
    if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        conn.close()
        log_event('signup', username, "Username taken", success=False)
        return False, "Username already taken. Please choose another."
    try:
        conn.execute(
            "INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,?)",
            (username, email, hash_password(password), role)
        )
        conn.commit()
        conn.close()
        log_event('signup', username, "Account created", success=True)
        return True, f"Account created for @{username}"
    except sqlite3.IntegrityError as e:
        conn.close()
        return False, "Username or email already taken."
    except Exception as e:
        conn.close()
        return False, f"Database error: {e}"


def authenticate(username: str, password: str) -> dict | None:
    username = username.strip().lower()
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE username=?", (username,)
    ).fetchone()
    conn.close()
    if not row:
        log_event('login', username, "User not found", success=False)
        return None
    if verify_password(password, row['password_hash']):
        log_event('login', username, "Login successful", success=True)
        return {
            'id':       row['id'],
            'username': row['username'],
            'email':    row['email'],
            'role':     row['role'],
        }
    log_event('login', username, "Wrong password", success=False)
    return None


# ── Save batch ───────────────────────────────────────────────
def save_analysis_batch(df, user_id=None) -> str:
    import uuid
    import pandas as pd
    batch_id = str(uuid.uuid4())
    conn = get_connection()
    cur  = conn.cursor()
    rows = []
    for _, r in df.iterrows():
        danger_val = None
        raw = r.get("Danger_Score")
        if raw is not None and pd.notna(raw):
            danger_val = round(float(raw), 4)
        rows.append((
            batch_id,
            int(user_id) if user_id else None,
            str(r.get('text', '')),
            str(r.get('Preprocessed', '')) if pd.notna(r.get('Preprocessed')) else None,
            round(float(r.get('Risk_Score', 0.0)), 4),
            str(r.get('Risk_Category', 'Low Risk')),
            danger_val,
            str(r.get('source', '')) if 'source' in r else None,
            str(r.get('timestamp', '')) if 'timestamp' in r else None,
        ))
    cur.executemany("""
        INSERT INTO analyzed_posts
            (batch_id, user_id, original_text, preprocessed,
             risk_score, risk_category, danger_score, source, post_timestamp)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    conn.close()
    return batch_id


# ════════════════════════════════════════════════════════════
#  HISTORY FUNCTIONS — USER-SCOPED (MAIN FIX)
#
#  ROOT CAUSE OF THE BUG:
#  The old get_batch_history() had NO WHERE clause for user_id.
#  It returned every batch from every user in the database.
#  So when peanutt logged in, they saw nizarhakim's batches too.
#
#  THE FIX:
#  All history/batch functions now take user_id as a parameter
#  and add WHERE user_id = ? to every query.
#  page_history.py passes st.session_state['current_user']['id'].
# ════════════════════════════════════════════════════════════
def get_batch_history(user_id: int | None = None):
    """
    Return a DataFrame of batch summaries.
    When user_id is provided, returns ONLY that user's batches.
    """
    import pandas as pd
    conn = get_connection()

    if user_id is not None:
        df = pd.read_sql_query("""
            SELECT
                ap.batch_id,
                MIN(ap.analyzed_at)            AS analyzed_at,
                COALESCE(u.username, '—')       AS analyst,
                COUNT(*)                         AS total_posts,
                SUM(CASE WHEN ap.risk_category='High Risk'     THEN 1 ELSE 0 END) AS high,
                SUM(CASE WHEN ap.risk_category='Moderate Risk' THEN 1 ELSE 0 END) AS moderate,
                SUM(CASE WHEN ap.risk_category='Low Risk'      THEN 1 ELSE 0 END) AS low,
                ROUND(AVG(ap.risk_score),4) AS avg_score,
                ROUND(MAX(ap.risk_score),4) AS max_score
            FROM analyzed_posts ap
            LEFT JOIN users u ON ap.user_id = u.id
            WHERE ap.user_id = ?
            GROUP BY ap.batch_id
            ORDER BY analyzed_at DESC
        """, conn, params=(user_id,))
    else:
        df = pd.read_sql_query("""
            SELECT
                ap.batch_id,
                MIN(ap.analyzed_at)            AS analyzed_at,
                COALESCE(u.username, '—')       AS analyst,
                COUNT(*)                         AS total_posts,
                SUM(CASE WHEN ap.risk_category='High Risk'     THEN 1 ELSE 0 END) AS high,
                SUM(CASE WHEN ap.risk_category='Moderate Risk' THEN 1 ELSE 0 END) AS moderate,
                SUM(CASE WHEN ap.risk_category='Low Risk'      THEN 1 ELSE 0 END) AS low,
                ROUND(AVG(ap.risk_score),4) AS avg_score,
                ROUND(MAX(ap.risk_score),4) AS max_score
            FROM analyzed_posts ap
            LEFT JOIN users u ON ap.user_id = u.id
            GROUP BY ap.batch_id
            ORDER BY analyzed_at DESC
        """, conn)

    conn.close()
    return df


def get_batch_posts(batch_id: str, user_id: int | None = None):
    """
    Return posts for a batch.
    FIX: Checks user_id ownership — users cannot load other users' batches.
    """
    import pandas as pd
    conn = get_connection()
    if user_id is not None:
        df = pd.read_sql_query("""
            SELECT id, original_text AS text, preprocessed AS Preprocessed,
                   risk_score AS Risk_Score, risk_category AS Risk_Category,
                   danger_score AS Danger_Score, source, post_timestamp, analyzed_at
            FROM analyzed_posts
            WHERE batch_id=? AND user_id=?
            ORDER BY COALESCE(danger_score,0) DESC, risk_score DESC
        """, conn, params=(batch_id, user_id))
    else:
        df = pd.read_sql_query("""
            SELECT id, original_text AS text, preprocessed AS Preprocessed,
                   risk_score AS Risk_Score, risk_category AS Risk_Category,
                   danger_score AS Danger_Score, source, post_timestamp, analyzed_at
            FROM analyzed_posts
            WHERE batch_id=?
            ORDER BY COALESCE(danger_score,0) DESC, risk_score DESC
        """, conn, params=(batch_id,))
    conn.close()
    return df


def delete_batch(batch_id: str, user_id: int | None = None):
    """
    Delete a batch.
    FIX: Only deletes if user_id matches — prevents cross-user deletion.
    """
    conn = get_connection()
    if user_id is not None:
        conn.execute(
            "DELETE FROM analyzed_posts WHERE batch_id=? AND user_id=?",
            (batch_id, user_id)
        )
    else:
        conn.execute("DELETE FROM analyzed_posts WHERE batch_id=?", (batch_id,))
    conn.commit()
    conn.close()


def get_all_posts(user_id: int | None = None, limit: int | None = None):
    """Retrieve analyzed posts, scoped to user_id when provided."""
    import pandas as pd
    conn   = get_connection()
    where  = "WHERE user_id=?" if user_id is not None else ""
    params = (user_id,)        if user_id is not None else ()
    q = f"""
        SELECT id, batch_id, original_text AS text,
               preprocessed AS Preprocessed,
               risk_score AS Risk_Score, risk_category AS Risk_Category,
               danger_score AS Danger_Score, source, post_timestamp, analyzed_at
        FROM analyzed_posts {where}
        ORDER BY analyzed_at DESC
        {'LIMIT ' + str(int(limit)) if limit else ''}
    """
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_posts_filtered(risk_category=None, min_score=0.0, keyword=None,
                       date_from=None, date_to=None, min_danger=0.0,
                       user_id: int | None = None):
    """Filter posts. Always scoped to user_id when provided."""
    import pandas as pd
    conn   = get_connection()
    where, params = [], []

    if user_id is not None:
        where.append("user_id=?")
        params.append(user_id)
    if risk_category and risk_category != "All":
        where.append("risk_category=?")
        params.append(risk_category)
    if min_score and min_score > 0:
        where.append("risk_score>=?")
        params.append(min_score)
    if min_danger and min_danger > 0:
        where.append("COALESCE(danger_score,0)>=?")
        params.append(min_danger)
    if keyword and keyword.strip():
        where.append("original_text LIKE ?")
        params.append(f"%{keyword.strip()}%")
    if date_from:
        where.append("analyzed_at>=?")
        params.append(date_from)
    if date_to:
        where.append("analyzed_at<=?")
        params.append(date_to)

    q = """
        SELECT id, batch_id, original_text AS text,
               preprocessed AS Preprocessed,
               risk_score AS Risk_Score, risk_category AS Risk_Category,
               danger_score AS Danger_Score, source, post_timestamp, analyzed_at
        FROM analyzed_posts
    """
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY analyzed_at DESC"

    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_post_stats(user_id: int | None = None) -> dict:
    """KPI counts, scoped to user_id when provided."""
    conn   = get_connection()
    cur    = conn.cursor()
    where  = "WHERE user_id=?" if user_id is not None else ""
    params = (user_id,)        if user_id is not None else ()

    cur.execute(f"SELECT COUNT(*) FROM analyzed_posts {where}", params)
    total = cur.fetchone()[0]
    cur.execute(f"SELECT risk_category, COUNT(*) FROM analyzed_posts {where} GROUP BY risk_category", params)
    by_cat = {row[0]: row[1] for row in cur.fetchall()}
    cur.execute(f"SELECT AVG(risk_score) FROM analyzed_posts {where}", params)
    avg = cur.fetchone()[0] or 0.0

    conn.close()
    return {
        'total':     total,
        'high':      by_cat.get('High Risk', 0),
        'moderate':  by_cat.get('Moderate Risk', 0),
        'low':       by_cat.get('Low Risk', 0),
        'avg_score': round(avg, 4),
    }


def clear_all_posts(user_id: int | None = None):
    """Delete posts scoped to user_id when provided."""
    conn = get_connection()
    if user_id is not None:
        conn.execute("DELETE FROM analyzed_posts WHERE user_id=?", (user_id,))
    else:
        conn.execute("DELETE FROM analyzed_posts")
    conn.commit()
    conn.close()


# ── Audit log ────────────────────────────────────────────────
def log_event(event_type: str, username: str = None,
              details: str = "", success: bool = True):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (event_type,username,details,success) VALUES (?,?,?,?)",
        (event_type, username, details, 1 if success else 0)
    )
    conn.commit()
    conn.close()


def get_audit_log(limit: int = 500):
    import pandas as pd
    conn = get_connection()
    df = pd.read_sql_query(
        f"SELECT timestamp,event_type,username,details,success FROM audit_log ORDER BY id DESC LIMIT {int(limit)}",
        conn
    )
    conn.close()
    return df