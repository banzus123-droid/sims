"""
database.py — SIMS Database Layer
Supports Supabase (cloud) with automatic SQLite fallback (local).
"""

import os
import time
import hashlib

# ── Load .env ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Read credentials (Streamlit secrets OR environment) ──────
def _get_secret(key):
    try:
        import streamlit as st
        return st.secrets.get(key, os.environ.get(key, ""))
    except Exception:
        return os.environ.get(key, "")

_SUPABASE_URL = _get_secret("SUPABASE_URL")
_SUPABASE_KEY = _get_secret("SUPABASE_KEY")

# ── Supabase client ──────────────────────────────────────────
_SUPABASE_OK = False
_sb = None
if _SUPABASE_URL and _SUPABASE_KEY:
    try:
        from supabase import create_client
        _sb = create_client(_SUPABASE_URL, _SUPABASE_KEY)
        _SUPABASE_OK = True
        print("[DB] Connected to Supabase.")
    except Exception as e:
        print(f"[DB] Supabase connection failed: {e}")
        print("[DB] Falling back to SQLite.")
else:
    print("[DB] No Supabase credentials found. Using SQLite fallback.")

# ── SQLite fallback ──────────────────────────────────────────
if not _SUPABASE_OK:
    import sqlite3
    from pathlib import Path
    _DB_PATH = Path(__file__).parent / "sims.db"

    def _get_conn():
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

# ══════════════════════════════════════════════════════════════
#  PASSWORD HASHING  (NFR 1.1)
# ══════════════════════════════════════════════════════════════
try:
    import bcrypt as _bcrypt
    _BCRYPT = True
except ImportError:
    _BCRYPT = False

def hash_password(plain: str) -> str:
    if _BCRYPT:
        return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()
    return "sha256$" + hashlib.sha256(plain.encode()).hexdigest()

def verify_password(plain: str, stored: str) -> bool:
    if stored.startswith("sha256$"):
        return stored == "sha256$" + hashlib.sha256(plain.encode()).hexdigest()
    if _BCRYPT:
        try:
            return _bcrypt.checkpw(plain.encode(), stored.encode())
        except Exception:
            return False
    return False

# ══════════════════════════════════════════════════════════════
#  INIT — SQLite only (Supabase tables created in SQL Editor)
# ══════════════════════════════════════════════════════════════
def init_db():
    if _SUPABASE_OK:
        print("[DB] Supabase ready — tables managed via SQL Editor.")
        try:
            res = _sb.table("users").select("id").limit(1).execute()
            if not res.data:
                _sb.table("users").insert({
                    "username": "admin",
                    "email": "admin@sims.com",
                    "password_hash": hash_password("12345678"),
                    "role": "Analyst"
                }).execute()
                print("[DB] Default admin created (admin / 12345678)")
        except Exception as e:
            print(f"[DB] init check error: {e}")
        return

    conn = _get_conn()
    cur  = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'Analyst',
            created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS analysis_batches (
            batch_id    TEXT PRIMARY KEY,
            analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            analyst     TEXT DEFAULT '-',
            user_id     INTEGER,
            total_posts INTEGER DEFAULT 0,
            high        INTEGER DEFAULT 0,
            moderate    INTEGER DEFAULT 0,
            low         INTEGER DEFAULT 0,
            avg_score   REAL DEFAULT 0.0,
            max_score   REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS analyzed_posts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id       TEXT NOT NULL,
            user_id        INTEGER,
            original_text  TEXT NOT NULL,
            preprocessed   TEXT,
            risk_score     REAL NOT NULL,
            risk_category  TEXT NOT NULL,
            danger_score   REAL,
            source         TEXT,
            post_timestamp TEXT,
            analyzed_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            username   TEXT,
            details    TEXT,
            success    INTEGER NOT NULL DEFAULT 1,
            timestamp  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,?)",
            ('admin','admin@sims.com', hash_password('12345678'),'Analyst')
        )
        conn.commit()
        print("[DB] Default admin created (admin / 12345678)")
    conn.close()

# ══════════════════════════════════════════════════════════════
#  USER FUNCTIONS
# ══════════════════════════════════════════════════════════════
def create_user(username, email, password, role="Analyst"):
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
            if _sb.table("users").select("id").eq("email", email).execute().data:
                return False, "This email is already registered."
            if _sb.table("users").select("id").eq("username", username).execute().data:
                return False, "Username already taken."
            _sb.table("users").insert({
                "username":      username,
                "email":         email,
                "password_hash": hash_password(password),
                "role":          role
            }).execute()
            log_event("signup", username, f"Account created: {email}", True)
            return True, f"Account created for @{username}"
        except Exception as e:
            return False, f"Database error: {e}"

    conn = _get_conn()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            return False, "This email is already registered."
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return False, "Username already taken."
        conn.execute(
            "INSERT INTO users (username,email,password_hash,role) VALUES (?,?,?,?)",
            (username, email, hash_password(password), role)
        )
        conn.commit()
        log_event("signup", username, f"Account created: {email}", True)
        return True, f"Account created for @{username}"
    except Exception as e:
        return False, f"Database error: {e}"
    finally:
        conn.close()

def get_user(username):
    username = username.strip().lower()
    if _SUPABASE_OK:
        try:
            res = _sb.table("users").select("*").eq("username", username).execute()
            return res.data[0] if res.data else None
        except Exception:
            return None
    conn = _get_conn()
    row  = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def authenticate(username, password):
    username = username.strip().lower()
    user = get_user(username)
    if user:
        stored = user.get("password_hash", "")
        if verify_password(password, stored):
            log_event("login", username, "Successful login", True)
            user.pop("password_hash", None)
            return user
    log_event("login", username, "Invalid credentials", False)
    return None

# ══════════════════════════════════════════════════════════════
#  SAVE ANALYSIS BATCH  (SIMS_07)
# ══════════════════════════════════════════════════════════════
def save_analysis_batch(df, user_id=None, username=None) -> str:
    """
    Save analyzed posts + batch summary.
    The summary row in analysis_batches is what History reads.
    It persists in Supabase permanently across logout/login.
    """
    batch_id = f"batch_{int(time.time())}"
    analyst  = username or "-"

    total = len(df)
    high  = int((df["Risk_Category"] == "High Risk").sum())
    mod   = int((df["Risk_Category"] == "Moderate Risk").sum())
    low   = int((df["Risk_Category"] == "Low Risk").sum())
    avg   = round(float(df["Risk_Score"].mean()), 4) if total else 0.0
    mx    = round(float(df["Risk_Score"].max()),  4) if total else 0.0

    rows = []
    for _, r in df.iterrows():
        danger = r.get("Danger_Score", None)
        try:
            danger = float(danger) if danger is not None else None
        except (ValueError, TypeError):
            danger = None
        rows.append({
            "batch_id":       batch_id,
            "user_id":        user_id,
            "original_text":  str(r.get("text", "")),
            "preprocessed":   str(r.get("Preprocessed", "")),
            "risk_score":     float(r.get("Risk_Score", 0.0)),
            "risk_category":  str(r.get("Risk_Category", "Low Risk")),
            "danger_score":   danger,
            "source":         str(r["source"]) if "source" in r else None,
            "post_timestamp": str(r["timestamp"]) if "timestamp" in r else None,
        })

    if _SUPABASE_OK:
        # 1. Save batch summary first — this is what History reads
        try:
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
            print(f"[DB] Batch summary saved: {batch_id} ({total} posts)")
        except Exception as e:
            print(f"[DB] ERROR saving batch summary: {e}")

        # 2. Save posts in chunks
        try:
            chunk = 500
            for i in range(0, len(rows), chunk):
                _sb.table("analyzed_posts").insert(rows[i:i+chunk]).execute()
            print(f"[DB] Posts saved: {total}")
        except Exception as e:
            print(f"[DB] ERROR saving posts: {e}")

        return batch_id

    # SQLite fallback
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO analysis_batches
              (batch_id,analyst,total_posts,high,moderate,low,avg_score,max_score)
            VALUES (?,?,?,?,?,?,?,?)
        """, (batch_id, analyst, total, high, mod, low, avg, mx))
        conn.executemany("""
            INSERT INTO analyzed_posts
              (batch_id,user_id,original_text,preprocessed,
               risk_score,risk_category,danger_score,source,post_timestamp)
            VALUES
              (:batch_id,:user_id,:original_text,:preprocessed,
               :risk_score,:risk_category,:danger_score,:source,:post_timestamp)
        """, rows)
        conn.commit()
        print(f"[DB] SQLite: saved {total} posts for {batch_id}")
    except Exception as e:
        print(f"[DB] SQLite error: {e}")
        conn.rollback()
    finally:
        conn.close()
    return batch_id

# ══════════════════════════════════════════════════════════════
#  BATCH HISTORY  (History page)
# ══════════════════════════════════════════════════════════════
def get_batch_history(username: str = None):
    """
    Return analysis batches for a specific user only.
    If username is provided, filter by analyst name so each
    user sees only their own history — not other users batches.
    """
    import pandas as pd
    _cols = ["batch_id","analyzed_at","analyst",
             "total_posts","high","moderate","low",
             "avg_score","max_score"]
    if _SUPABASE_OK:
        try:
            q = _sb.table("analysis_batches").select(
                "batch_id,analyzed_at,analyst,"
                "total_posts,high,moderate,low,avg_score,max_score"
            )
            if username:
                q = q.eq("analyst", username)
            q = q.order("analyzed_at", desc=True)
            res = q.execute()
            if not res.data:
                return pd.DataFrame(columns=_cols)
            return pd.DataFrame(res.data)
        except Exception as e:
            print(f"[DB] get_batch_history error: {e}")
            return pd.DataFrame(columns=_cols)

    conn = _get_conn()
    if username:
        df = pd.read_sql_query("""
            SELECT batch_id,analyzed_at,analyst,
                   total_posts,high,moderate,low,avg_score,max_score
            FROM analysis_batches WHERE analyst=?
            ORDER BY analyzed_at DESC
        """, conn, params=(username,))
    else:
        df = pd.read_sql_query("""
            SELECT batch_id,analyzed_at,analyst,
                   total_posts,high,moderate,low,avg_score,max_score
            FROM analysis_batches ORDER BY analyzed_at DESC
        """, conn)
    conn.close()
    return df

def get_batch_posts(batch_id: str):
    import pandas as pd
    if _SUPABASE_OK:
        try:
            res = _sb.table("analyzed_posts").select(
                "id,original_text,preprocessed,"
                "risk_score,risk_category,danger_score,"
                "source,post_timestamp,analyzed_at"
            ).eq("batch_id", batch_id).execute()
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
               original_text AS text,
               preprocessed  AS Preprocessed,
               risk_score    AS Risk_Score,
               risk_category AS Risk_Category,
               danger_score  AS Danger_Score,
               source, post_timestamp, analyzed_at
        FROM analyzed_posts WHERE batch_id=?
        ORDER BY COALESCE(danger_score,0) DESC
    """, conn, params=(batch_id,))
    conn.close()
    return df

def delete_batch(batch_id: str):
    if _SUPABASE_OK:
        try:
            _sb.table("analyzed_posts").delete().eq("batch_id", batch_id).execute()
            _sb.table("analysis_batches").delete().eq("batch_id", batch_id).execute()
        except Exception as e:
            print(f"[DB] delete_batch error: {e}")
        return
    conn = _get_conn()
    conn.execute("DELETE FROM analyzed_posts WHERE batch_id=?",    (batch_id,))
    conn.execute("DELETE FROM analysis_batches WHERE batch_id=?", (batch_id,))
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════════════
#  GET POSTS
# ══════════════════════════════════════════════════════════════
def get_all_posts(limit=None):
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
            df = pd.DataFrame(q.execute().data)
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

    conn = _get_conn()
    df = pd.read_sql_query("""
        SELECT id,batch_id,
               original_text AS text,
               preprocessed  AS Preprocessed,
               risk_score    AS Risk_Score,
               risk_category AS Risk_Category,
               danger_score  AS Danger_Score,
               source,post_timestamp,analyzed_at
        FROM analyzed_posts ORDER BY analyzed_at DESC
    """ + (f" LIMIT {int(limit)}" if limit else ""), conn)
    conn.close()
    return df

def get_posts_filtered(risk_category=None, min_score=0.0,
                       keyword=None, date_from=None,
                       date_to=None, min_danger=0.0):
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
            df = pd.DataFrame(q.execute().data)
            if df.empty:
                return df
            df = df.rename(columns={
                "original_text": "text",
                "preprocessed":  "Preprocessed",
                "risk_score":    "Risk_Score",
                "risk_category": "Risk_Category",
                "danger_score":  "Danger_Score",
            })
            if keyword and keyword.strip():
                df = df[df["text"].str.contains(
                    keyword.strip(), case=False, na=False)]
            return df
        except Exception as e:
            print(f"[DB] get_posts_filtered error: {e}")
            return pd.DataFrame()

    conn = _get_conn()
    where, params = [], []
    if risk_category and risk_category != "All":
        where.append("risk_category=?"); params.append(risk_category)
    if min_score > 0:
        where.append("risk_score>=?"); params.append(min_score)
    if min_danger > 0:
        where.append("COALESCE(danger_score,0)>=?"); params.append(min_danger)
    if keyword and keyword.strip():
        where.append("original_text LIKE ?")
        params.append(f"%{keyword.strip()}%")
    if date_from:
        where.append("analyzed_at>=?"); params.append(date_from)
    if date_to:
        where.append("analyzed_at<=?"); params.append(date_to)
    q = """SELECT id,batch_id,
                  original_text AS text,
                  preprocessed  AS Preprocessed,
                  risk_score    AS Risk_Score,
                  risk_category AS Risk_Category,
                  danger_score  AS Danger_Score,
                  source,post_timestamp,analyzed_at
           FROM analyzed_posts"""
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY analyzed_at DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df

def get_post_stats(username: str = None) -> dict:
    """
    Return summary KPIs for the dashboard.
    Filtered by username so each user sees only their own data.
    """
    import pandas as pd
    _empty = {"total":0,"high":0,"moderate":0,"low":0,"avg_score":0.0}
    if _SUPABASE_OK:
        try:
            q = _sb.table("analysis_batches").select(
                "total_posts,high,moderate,low,avg_score"
            )
            if username:
                q = q.eq("analyst", username)
            df = pd.DataFrame(q.execute().data)
            if df.empty:
                return _empty
            return {
                "total":     int(df["total_posts"].sum()),
                "high":      int(df["high"].sum()),
                "moderate":  int(df["moderate"].sum()),
                "low":       int(df["low"].sum()),
                "avg_score": round(float(df["avg_score"].mean()), 4),
            }
        except Exception as e:
            print(f"[DB] get_post_stats error: {e}")
            return _empty

    conn = _get_conn()
    if username:
        total = conn.execute(
            "SELECT COALESCE(SUM(total_posts),0) FROM analysis_batches WHERE analyst=?",
            (username,)).fetchone()[0]
        rows = conn.execute(
            """SELECT SUM(high),SUM(moderate),SUM(low),AVG(avg_score)
               FROM analysis_batches WHERE analyst=?""",
            (username,)).fetchone()
    else:
        total = conn.execute(
            "SELECT COUNT(*) FROM analyzed_posts").fetchone()[0]
        rows = conn.execute(
            """SELECT
                SUM(CASE WHEN risk_category='High Risk' THEN 1 ELSE 0 END),
                SUM(CASE WHEN risk_category='Moderate Risk' THEN 1 ELSE 0 END),
                SUM(CASE WHEN risk_category='Low Risk' THEN 1 ELSE 0 END),
                AVG(risk_score)
               FROM analyzed_posts""").fetchone()
    conn.close()
    return {
        "total":    int(total or 0),
        "high":     int(rows[0] or 0),
        "moderate": int(rows[1] or 0),
        "low":      int(rows[2] or 0),
        "avg_score":round(float(rows[3] or 0.0), 4),
    }

    if _SUPABASE_OK:
        try:
            _sb.table("analyzed_posts").delete().neq("id", 0).execute()
            _sb.table("analysis_batches").delete().neq("batch_id","").execute()
        except Exception as e:
            print(f"[DB] clear_all_posts error: {e}")
        return
    conn = _get_conn()
    conn.execute("DELETE FROM analyzed_posts")
    conn.execute("DELETE FROM analysis_batches")
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════════════
#  AUDIT LOG  (NFR 1.2)
# ══════════════════════════════════════════════════════════════
def log_event(event_type: str, username: str = None,
              details: str = "", success: bool = True):
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
        "INSERT INTO audit_log (event_type,username,details,success) VALUES (?,?,?,?)",
        (event_type, username, details, 1 if success else 0)
    )
    conn.commit()
    conn.close()

def get_audit_log(limit: int = 500):
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