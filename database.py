"""
database.py — SIMS Cloud Database Layer (Supabase)
Replaces the local SQLite file with a cloud PostgreSQL database
hosted on Supabase (https://supabase.com).

All function signatures are IDENTICAL to the old SQLite version
so no other file in the project needs to change.

Tables required in Supabase (create via SQL Editor):
    users, analyzed_posts, audit_log
See README_DEPLOYMENT.md for the full CREATE TABLE SQL.

Environment variables required (put in .env file):
    SUPABASE_URL = https://your-project-id.supabase.co
    SUPABASE_KEY = your-anon-public-key

Security (NFR 1.1):
    Passwords are hashed with bcrypt before storage.
    The anon key only allows row-level operations — it cannot
    drop tables or access other projects.
"""

import os
import time
import hashlib
from datetime import datetime

# ── Load .env file if present (works locally and on Colab) ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

# ── Supabase client ──────────────────────────────────────────
try:
    from supabase import create_client, Client
    _SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    _SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY environment variables are not set.\n"
            "Create a .env file in your project folder with:\n"
            "  SUPABASE_URL=https://your-project.supabase.co\n"
            "  SUPABASE_KEY=your-anon-key"
        )
    _sb: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    _SUPABASE_OK = True
    print("[DB] Connected to Supabase cloud database.")
except Exception as e:
    _SUPABASE_OK = False
    print(f"[DB] WARNING: Supabase not available — {e}")
    print("[DB] Falling back to local SQLite (sims.db).")


# ════════════════════════════════════════════════════════════
#  SQLITE FALLBACK
#  If Supabase is not configured, fall back to local SQLite
#  so the app still works on localhost without internet.
# ════════════════════════════════════════════════════════════
if not _SUPABASE_OK:
    import sqlite3
    from pathlib import Path

    _DB_PATH = Path(__file__).parent / "sims.db"

    def _get_conn():
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


# ════════════════════════════════════════════════════════════
#  PASSWORD HASHING  (NFR 1.1)
# ════════════════════════════════════════════════════════════
try:
    import bcrypt as _bcrypt
    _BCRYPT = True
except ImportError:
    _BCRYPT = False


def hash_password(plain: str) -> str:
    if _BCRYPT:
        return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()
    return "sha256$" + hashlib.sha256(plain.encode()).hexdigest()


def verify_password(plain: str, stored_hash: str) -> bool:
    if stored_hash.startswith("sha256$"):
        return stored_hash == "sha256$" + hashlib.sha256(plain.encode()).hexdigest()
    if _BCRYPT:
        try:
            return _bcrypt.checkpw(plain.encode(), stored_hash.encode())
        except Exception:
            return False
    return False


# ════════════════════════════════════════════════════════════
#  SCHEMA INIT — only needed for the SQLite fallback path.
#  Supabase tables are created manually in the SQL Editor.
# ════════════════════════════════════════════════════════════
def init_db():
    """
    Initialise the database.
    - Supabase: prints a confirmation (tables already created in dashboard).
    - SQLite fallback: creates tables if they don't exist.
    """
    if _SUPABASE_OK:
        print("[DB] Supabase — tables managed via Supabase SQL Editor.")
        # Seed default admin if no users exist
        try:
            res = _sb.table("users").select("id").limit(1).execute()
            if not res.data:
                _sb.table("users").insert({
                    "username": "admin",
                    "email": "admin@sims.com",
                    "password_hash": hash_password("12345678"),
                    "role": "Analyst"
                }).execute()
                print("[DB] Seeded default admin account (admin / 12345678)")
        except Exception as e:
            print(f"[DB] Could not check/seed admin: {e}")
        return

    # ── SQLite fallback schema ──────────────────────────────
    conn = _get_conn()
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
            analyzed_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration safety — add danger_score column if missing
    cur.execute("PRAGMA table_info(analyzed_posts)")
    if 'danger_score' not in {r[1] for r in cur.fetchall()}:
        cur.execute("ALTER TABLE analyzed_posts ADD COLUMN danger_score REAL")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analysis_batches (
            batch_id     TEXT PRIMARY KEY,
            analyzed_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            analyst      TEXT DEFAULT '—',
            user_id      INTEGER,
            total_posts  INTEGER DEFAULT 0,
            high         INTEGER DEFAULT 0,
            moderate     INTEGER DEFAULT 0,
            low          INTEGER DEFAULT 0,
            avg_score    REAL    DEFAULT 0.0,
            max_score    REAL    DEFAULT 0.0
        )
    """)
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
    conn.commit()
    # Seed admin
    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,?)",
            ('admin', 'admin@sims.com', hash_password('12345678'), 'Analyst')
        )
        conn.commit()
        print("[DB] Seeded default admin account (admin / 12345678)")
    conn.close()


# ════════════════════════════════════════════════════════════
#  USER FUNCTIONS  (SIMS_01 Sign Up, SIMS_02 Login)
# ════════════════════════════════════════════════════════════
def create_user(username: str, email: str,
                password: str, role: str = "Analyst") -> tuple:
    """
    SIMS_01 — Create a new analyst account.
    Returns (success: bool, message: str).
    """
    username = username.strip().lower()
    email    = email.strip().lower()

    if not username or not email or not password:
        return False, "All fields are required."
    if " " in username:
        return False, "Username cannot contain spaces."
    if "@" not in email:
        return False, "Please enter a valid email address."

    if _SUPABASE_OK:
        try:
            # Check email duplicate
            res = _sb.table("users").select("username") \
                     .eq("email", email).execute()
            if res.data:
                log_event('signup', username,
                          f'Duplicate email: {email}', success=False)
                return False, "This email is already registered."

            # Check username duplicate
            res = _sb.table("users").select("id") \
                     .eq("username", username).execute()
            if res.data:
                log_event('signup', username,
                          'Username taken', success=False)
                return False, "Username already taken. Please choose another."

            # Insert new user
            _sb.table("users").insert({
                "username":      username,
                "email":         email,
                "password_hash": hash_password(password),
                "role":          role
            }).execute()

            log_event('signup', username,
                      f'New account created: {email}', success=True)
            return True, f"Account created for @{username}"

        except Exception as e:
            return False, f"Database error: {e}"

    # ── SQLite fallback ─────────────────────────────────────
    conn = _get_conn()
    try:
        if conn.execute(
                "SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            log_event('signup', username,
                      f'Duplicate email: {email}', success=False)
            return False, "This email is already registered."
        if conn.execute(
                "SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            log_event('signup', username,
                      'Username taken', success=False)
            return False, "Username already taken. Please choose another."
        conn.execute(
            "INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,?)",
            (username, email, hash_password(password), role)
        )
        conn.commit()
        log_event('signup', username,
                  f'New account: {email}', success=True)
        return True, f"Account created for @{username}"
    except Exception as e:
        return False, f"Database error: {e}"
    finally:
        conn.close()


def get_user(username: str) -> dict | None:
    """Fetch a user record by username. Returns dict or None."""
    username = username.strip().lower()
    if _SUPABASE_OK:
        try:
            res = _sb.table("users").select("*") \
                     .eq("username", username).execute()
            return res.data[0] if res.data else None
        except Exception:
            return None

    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username=?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def authenticate(username: str, password: str) -> dict | None:
    """
    SIMS_02 — Authenticate a user.
    Returns user dict (without password hash) on success, None on failure.
    Logs every attempt (NFR 1.2).
    """
    username = username.strip().lower()
    user = get_user(username)

    if user:
        # Supabase stores 'password_hash'; SQLite also stores 'password_hash'
        stored = user.get('password_hash', '')
        if verify_password(password, stored):
            log_event('login', username, 'Successful login', success=True)
            user.pop('password_hash', None)
            return user

    log_event('login', username, 'Invalid credentials', success=False)
    return None


# ════════════════════════════════════════════════════════════
#  ANALYZED POSTS FUNCTIONS  (SIMS_07, SIMS_08, SIMS_09)
# ════════════════════════════════════════════════════════════
def save_analysis_batch(df, user_id=None, username=None) -> str:
    """
    SIMS_07 — Save a batch of analyzed posts to the database.
    Also writes a summary record to analysis_batches so that
    History page can retrieve it after logout/login.
    Returns the batch_id string.
    """
    import pandas as pd
    batch_id  = f"batch_{int(time.time())}"
    analyst   = username or "—"

    # ── Build summary stats ─────────────────────────────────
    total = len(df)
    high  = int((df['Risk_Category'] == 'High Risk').sum())
    mod   = int((df['Risk_Category'] == 'Moderate Risk').sum())
    low   = int((df['Risk_Category'] == 'Low Risk').sum())
    avg   = round(float(df['Risk_Score'].mean()), 4) if total else 0.0
    mx    = round(float(df['Risk_Score'].max()),  4) if total else 0.0

    # ── Build rows for analyzed_posts ───────────────────────
    rows = []
    for _, r in df.iterrows():
        danger = r.get('Danger_Score', None)
        try:
            danger = float(danger) if danger is not None else None
        except (ValueError, TypeError):
            danger = None

        rows.append({
            "batch_id":      batch_id,
            "user_id":       user_id,
            "original_text": str(r.get('text', '')),
            "preprocessed":  str(r.get('Preprocessed', '')),
            "risk_score":    float(r.get('Risk_Score', 0.0)),
            "risk_category": str(r.get('Risk_Category', 'Low Risk')),
            "danger_score":  danger,
            "source":        str(r.get('source', '')) if 'source' in r else None,
            "post_timestamp":str(r.get('timestamp', '')) if 'timestamp' in r else None,
        })

    if _SUPABASE_OK:
        try:
            # ── Insert posts in chunks of 500 ───────────────
            chunk_size = 500
            for i in range(0, len(rows), chunk_size):
                _sb.table("analyzed_posts") \
                   .insert(rows[i:i+chunk_size]).execute()

            # ── Insert batch summary ─────────────────────────
            _sb.table("analysis_batches").insert({
                "batch_id":    batch_id,
                "analyst":     analyst,
                "user_id":     user_id,
                "total_posts": total,
                "high":        high,
                "moderate":    mod,
                "low":         low,
                "avg_score":   avg,
                "max_score":   mx,
            }).execute()

        except Exception as e:
            print(f"[DB] save_analysis_batch error: {e}")
        return batch_id

    # ── SQLite fallback ─────────────────────────────────────
    conn = _get_conn()
    conn.executemany("""
        INSERT INTO analyzed_posts
          (batch_id, user_id, original_text, preprocessed,
           risk_score, risk_category, danger_score, source, post_timestamp)
        VALUES
          (:batch_id,:user_id,:original_text,:preprocessed,
           :risk_score,:risk_category,:danger_score,:source,:post_timestamp)
    """, rows)
    # Insert batch summary for SQLite too
    conn.execute("""
        INSERT OR REPLACE INTO analysis_batches
          (batch_id, analyst, total_posts, high, moderate,
           low, avg_score, max_score)
        VALUES (?,?,?,?,?,?,?,?)
    """, (batch_id, analyst, total, high, mod, low, avg, mx))
    conn.commit()
    conn.close()
    return batch_id


def get_all_posts(limit=None):
    """SIMS_08 — Retrieve all analyzed posts as a pandas DataFrame."""
    import pandas as pd

    if _SUPABASE_OK:
        try:
            q = _sb.table("analyzed_posts").select(
                "id,batch_id,original_text,preprocessed,"
                "risk_score,risk_category,danger_score,"
                "source,post_timestamp,analyzed_at"
            ).order("analyzed_at", desc=True)
            if limit:
                q = q.limit(int(limit))
            res = q.execute()
            df = pd.DataFrame(res.data)
            if df.empty:
                return df
            return df.rename(columns={
                "original_text": "text",
                "preprocessed":  "Preprocessed",
                "risk_score":    "Risk_Score",
                "risk_category": "Risk_Category",
                "danger_score":  "Danger_Score",
            })
        except Exception as e:
            print(f"[DB] get_all_posts error: {e}")
            return pd.DataFrame()

    # SQLite fallback
    conn = _get_conn()
    df = pd.read_sql_query("""
        SELECT id, batch_id, original_text AS text,
               preprocessed AS Preprocessed,
               risk_score AS Risk_Score,
               risk_category AS Risk_Category,
               danger_score AS Danger_Score,
               source, post_timestamp, analyzed_at
        FROM analyzed_posts ORDER BY analyzed_at DESC
    """ + (f" LIMIT {int(limit)}" if limit else ""), conn)
    conn.close()
    return df


def get_posts_filtered(risk_category=None, min_score=0.0,
                       keyword=None, date_from=None,
                       date_to=None, min_danger=0.0):
    """SIMS_08 — Filter analyzed posts."""
    import pandas as pd

    if _SUPABASE_OK:
        try:
            q = _sb.table("analyzed_posts").select(
                "id,batch_id,original_text,preprocessed,"
                "risk_score,risk_category,danger_score,"
                "source,post_timestamp,analyzed_at"
            )
            if risk_category and risk_category != "All":
                q = q.eq("risk_category", risk_category)
            if min_score and min_score > 0:
                q = q.gte("risk_score", min_score)
            if min_danger and min_danger > 0:
                q = q.gte("danger_score", min_danger)
            if date_from:
                q = q.gte("analyzed_at", date_from)
            if date_to:
                q = q.lte("analyzed_at", date_to)
            q = q.order("analyzed_at", desc=True)
            res = q.execute()
            df = pd.DataFrame(res.data)
            if df.empty:
                return df
            df = df.rename(columns={
                "original_text": "text",
                "preprocessed":  "Preprocessed",
                "risk_score":    "Risk_Score",
                "risk_category": "Risk_Category",
                "danger_score":  "Danger_Score",
            })
            # Keyword filter in Python (Supabase free tier has limited ILIKE)
            if keyword and keyword.strip():
                df = df[df['text'].str.contains(
                    keyword.strip(), case=False, na=False)]
            return df
        except Exception as e:
            print(f"[DB] get_posts_filtered error: {e}")
            return pd.DataFrame()

    # SQLite fallback
    conn = _get_conn()
    where, params = [], []
    if risk_category and risk_category != "All":
        where.append("risk_category=?"); params.append(risk_category)
    if min_score > 0:
        where.append("risk_score>=?");   params.append(min_score)
    if min_danger > 0:
        where.append("COALESCE(danger_score,0)>=?"); params.append(min_danger)
    if keyword and keyword.strip():
        where.append("original_text LIKE ?")
        params.append(f"%{keyword.strip()}%")
    if date_from:
        where.append("analyzed_at>=?"); params.append(date_from)
    if date_to:
        where.append("analyzed_at<=?"); params.append(date_to)
    q = """SELECT id,batch_id,original_text AS text,
                  preprocessed AS Preprocessed,
                  risk_score AS Risk_Score,
                  risk_category AS Risk_Category,
                  danger_score AS Danger_Score,
                  source,post_timestamp,analyzed_at
           FROM analyzed_posts"""
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY analyzed_at DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_post_stats() -> dict:
    """Return summary counts for the dashboard KPIs."""
    if _SUPABASE_OK:
        try:
            res = _sb.table("analyzed_posts").select(
                "risk_category,risk_score"
            ).execute()
            import pandas as pd
            df = pd.DataFrame(res.data)
            if df.empty:
                return {'total':0,'high':0,'moderate':0,'low':0,'avg_score':0.0}
            vc = df['risk_category'].value_counts().to_dict()
            return {
                'total':    len(df),
                'high':     vc.get('High Risk', 0),
                'moderate': vc.get('Moderate Risk', 0),
                'low':      vc.get('Low Risk', 0),
                'avg_score': round(df['risk_score'].mean(), 4),
            }
        except Exception as e:
            print(f"[DB] get_post_stats error: {e}")
            return {'total':0,'high':0,'moderate':0,'low':0,'avg_score':0.0}

    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM analyzed_posts").fetchone()[0]
    by_cat = {r[0]:r[1] for r in conn.execute(
        "SELECT risk_category,COUNT(*) FROM analyzed_posts GROUP BY risk_category"
    ).fetchall()}
    avg = conn.execute(
        "SELECT AVG(risk_score) FROM analyzed_posts").fetchone()[0] or 0.0
    conn.close()
    return {
        'total':total,
        'high':by_cat.get('High Risk',0),
        'moderate':by_cat.get('Moderate Risk',0),
        'low':by_cat.get('Low Risk',0),
        'avg_score':round(avg,4),
    }


def clear_all_posts():
    """Delete all analyzed posts."""
    if _SUPABASE_OK:
        try:
            _sb.table("analyzed_posts").delete().neq("id", 0).execute()
        except Exception as e:
            print(f"[DB] clear_all_posts error: {e}")
        return
    conn = _get_conn()
    conn.execute("DELETE FROM analyzed_posts")
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
#  BATCH HISTORY FUNCTIONS
# ════════════════════════════════════════════════════════════
def get_batch_history():
    """
    Return a DataFrame summarising each saved analysis batch.
    Reads from the analysis_batches summary table which is
    written by save_analysis_batch() — persists across logout/login.
    """
    import pandas as pd

    if _SUPABASE_OK:
        try:
            res = _sb.table("analysis_batches").select(
                "batch_id,analyzed_at,analyst,"
                "total_posts,high,moderate,low,"
                "avg_score,max_score"
            ).order("analyzed_at", desc=True).execute()

            if not res.data:
                return pd.DataFrame(columns=[
                    'batch_id','analyzed_at','analyst',
                    'total_posts','high','moderate','low',
                    'avg_score','max_score'
                ])
            return pd.DataFrame(res.data)

        except Exception as e:
            print(f"[DB] get_batch_history error: {e}")
            return pd.DataFrame()

    # ── SQLite fallback ─────────────────────────────────────
    import pandas as pd
    conn = _get_conn()
    df = pd.read_sql_query("""
        SELECT batch_id, analyzed_at, analyst,
               total_posts, high, moderate, low,
               avg_score, max_score
        FROM analysis_batches
        ORDER BY analyzed_at DESC
    """, conn)
    conn.close()
    return df


def get_batch_posts(batch_id: str):
    """Return all posts belonging to a single batch as a DataFrame."""
    import pandas as pd

    if _SUPABASE_OK:
        try:
            res = _sb.table("analyzed_posts").select(
                "id,original_text,preprocessed,"
                "risk_score,risk_category,danger_score,"
                "source,post_timestamp,analyzed_at"
            ).eq("batch_id", batch_id) \
             .order("danger_score", desc=True).execute()
            df = pd.DataFrame(res.data)
            if df.empty:
                return df
            return df.rename(columns={
                "original_text": "text",
                "preprocessed":  "Preprocessed",
                "risk_score":    "Risk_Score",
                "risk_category": "Risk_Category",
                "danger_score":  "Danger_Score",
            })
        except Exception as e:
            print(f"[DB] get_batch_posts error: {e}")
            return pd.DataFrame()

    conn = _get_conn()
    df = pd.read_sql_query("""
        SELECT id,
               original_text AS text, preprocessed AS Preprocessed,
               risk_score AS Risk_Score, risk_category AS Risk_Category,
               danger_score AS Danger_Score,
               source, post_timestamp, analyzed_at
        FROM analyzed_posts WHERE batch_id=?
        ORDER BY COALESCE(danger_score,0) DESC, risk_score DESC
    """, conn, params=(batch_id,))
    conn.close()
    return df


def delete_batch(batch_id: str):
    """Delete all posts belonging to a batch."""
    if _SUPABASE_OK:
        try:
            _sb.table("analyzed_posts") \
               .delete().eq("batch_id", batch_id).execute()
        except Exception as e:
            print(f"[DB] delete_batch error: {e}")
        return
    conn = _get_conn()
    conn.execute("DELETE FROM analyzed_posts WHERE batch_id=?", (batch_id,))
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
#  AUDIT LOG FUNCTIONS  (NFR 1.2)
# ════════════════════════════════════════════════════════════
def log_event(event_type: str, username: str = None,
              details: str = "", success: bool = True):
    """Append a security event to the audit log."""
    if _SUPABASE_OK:
        try:
            _sb.table("audit_log").insert({
                "event_type": event_type,
                "username":   username,
                "details":    details,
                "success":    success,
            }).execute()
        except Exception as e:
            print(f"[DB] log_event error: {e}")
        return
    conn = _get_conn()
    conn.execute(
        "INSERT INTO audit_log (event_type,username,details,success) "
        "VALUES (?,?,?,?)",
        (event_type, username, details, 1 if success else 0)
    )
    conn.commit()
    conn.close()


def get_audit_log(limit: int = 500):
    """Fetch the audit log as a pandas DataFrame."""
    import pandas as pd

    if _SUPABASE_OK:
        try:
            res = _sb.table("audit_log").select(
                "timestamp,event_type,username,details,success"
            ).order("id", desc=True).limit(int(limit)).execute()
            return pd.DataFrame(res.data)
        except Exception as e:
            print(f"[DB] get_audit_log error: {e}")
            return pd.DataFrame()

    conn = _get_conn()
    df = pd.read_sql_query(f"""
        SELECT timestamp,event_type,username,details,success
        FROM audit_log ORDER BY id DESC LIMIT {int(limit)}
    """, conn)
    conn.close()
    return df