"""
sims.py — SIMS Entry Point
Run with: streamlit run sims.py

Proposal mapping:
  SIMS_01  Sign Up        → page_signup.show_page()
  SIMS_02  Login          → page_login.show_page()
  SIMS_03  Dashboard      → page_dashboard.show_page()
  SIMS_04-07 Upload/ML   → page_upload.show_page(logic)
  SIMS_08-09 Filter/CSV  → page_analysis.show_page()
  FR 2.3   Trends        → page_trends.show_page()
  SIMS_10  Logout         → sidebar button
  NFR 1.1  Hashed pwds   → database.py (bcrypt)
  NFR 1.2  Audit log     → database.py (audit_log table)
"""

# ══════════════════════════════════════════════════════════
#  STEP 0 — STARTUP SAFETY CHECKS
#  Must run BEFORE importing streamlit or any other module.
#  Streamlit Cloud, Colab, and fresh installs all need
#  NLTK corpora downloaded at startup explicitly.
#  Other packages are checked here so the app shows a clear
#  human-readable error instead of a cryptic import crash.
# ══════════════════════════════════════════════════════════
import os
import sys

# ── Load .env file (for local development and Colab) ───────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — env vars set manually

# ── NLTK corpora download ───────────────────────────────────
# Must happen before logic.py is imported because logic.py
# imports nltk at module level. If corpora are missing, the
# SIMSLogic class will crash on instantiation.
#
# Corpora used (with academic citations):
#   stopwords  — Bird, Klein & Loper (2009). NLTK Book. O'Reilly.
#   wordnet    — Miller (1995). WordNet. Comms ACM 38(11).
#   punkt      — Kiss & Strunk (2006). Comp. Linguistics 32(4).
#   omw-1.4    — Bond & Foster (2013). ACL 2013.
try:
    import nltk as _nltk_startup
    _nltk_dir = os.path.expanduser("~/nltk_data")
    os.makedirs(_nltk_dir, exist_ok=True)

    _CORPORA = {
        "stopwords": "corpora",
        "wordnet":   "corpora",
        "omw-1.4":   "corpora",
        "punkt":     "tokenizers",
        "punkt_tab": "tokenizers",
    }
    for _corpus, _category in _CORPORA.items():
        try:
            _nltk_startup.data.find(f"{_category}/{_corpus}")
        except LookupError:
            print(f"[SIMS startup] Downloading NLTK corpus: {_corpus}")
            _nltk_startup.download(
                _corpus, quiet=True, download_dir=_nltk_dir
            )
    print("[SIMS startup] NLTK corpora ready.")
except ImportError:
    print("[SIMS startup] NLTK not installed — keyword fallback will be used.")
except Exception as _e:
    print(f"[SIMS startup] NLTK warning: {_e}")

# ── Check all required packages are installed ───────────────
_REQUIRED = {
    "streamlit":  "streamlit",
    "pandas":     "pandas",
    "numpy":      "numpy",
    "sklearn":    "scikit-learn",
    "nltk":       "nltk",
    "joblib":     "joblib",
    "altair":     "altair",
    "bcrypt":     "bcrypt",
}
_MISSING = []
for _mod, _pkg in _REQUIRED.items():
    try:
        __import__(_mod)
    except ImportError:
        _MISSING.append(_pkg)

# ── Optional packages (warn but do not stop) ───────────────
_OPTIONAL_MISSING = []
for _mod, _pkg in {"wordcloud": "wordcloud",
                    "supabase":  "supabase",
                    "gdown":     "gdown"}.items():
    try:
        __import__(_mod)
    except ImportError:
        _OPTIONAL_MISSING.append(_pkg)

# ── Google Drive model download ─────────────────────────────
# Set these in Streamlit Cloud Secrets or your .env file:
#   GDRIVE_PIPELINE_ID    = file ID of sims_pipeline.pkl
#   GDRIVE_VECTORIZER_ID  = file ID of sims_tfidf_vectorizer.pkl
#   GDRIVE_CLASSIFIER_ID  = file ID of sims_classifier.pkl
#
# How to get a file ID:
#   1. Upload the .pkl file to Google Drive
#   2. Right-click -> Share -> Anyone with the link -> Copy link
#   3. The ID is the string between /d/ and /view in the link
#      e.g. https://drive.google.com/file/d/1BxiMVs0XRA5nFM.../view
#                                             ^^^^^^^^^^^^^^^^ this part
def _get_env(key):
    """Read from environment variables (covers both .env and Streamlit secrets)."""
    return os.environ.get(key, "")

os.makedirs("models", exist_ok=True)

_MODEL_FILES = {
    "models/sims_pipeline.pkl":         _get_env("GDRIVE_PIPELINE_ID"),
    "models/sims_tfidf_vectorizer.pkl":  _get_env("GDRIVE_VECTORIZER_ID"),
    "models/sims_classifier.pkl":        _get_env("GDRIVE_CLASSIFIER_ID"),
}

if any(_MODEL_FILES.values()):
    try:
        import gdown as _gdown
        for _dest, _fid in _MODEL_FILES.items():
            if _fid and not os.path.exists(_dest):
                print(f"[SIMS startup] Downloading {os.path.basename(_dest)}...")
                _gdown.download(
                    f"https://drive.google.com/uc?id={_fid}",
                    _dest,
                    quiet=False
                )
                print(f"[SIMS startup] Done: {_dest}")
    except ImportError:
        print("[SIMS startup] gdown not installed - add it to requirements.txt")
    except Exception as _e:
        print(f"[SIMS startup] Model download error: {_e}")

# ══════════════════════════════════════════════════════════
#  NOW import streamlit — must be after all startup checks
# ══════════════════════════════════════════════════════════
import streamlit as st
import time

# ── Show missing package error immediately after st loads ──
if _MISSING:
    st.set_page_config(page_title="SIMS — Setup Required", layout="centered")
    st.error(
        f"❌ **Missing required packages:** `{', '.join(_MISSING)}`\n\n"
        "Run this command in your terminal then restart the app:\n\n"
        f"```\npip install {' '.join(_MISSING)}\n```"
    )
    st.stop()

if _OPTIONAL_MISSING:
    # Don't stop — just warn in the terminal
    print(f"[SIMS startup] Optional packages not installed: "
          f"{', '.join(_OPTIONAL_MISSING)}")
    print(f"[SIMS startup] Install with: pip install "
          f"{' '.join(_OPTIONAL_MISSING)}")

# ══════════════════════════════════════════════════════════
#  PAGE CONFIG — must be first Streamlit call after import
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SIMS | Suicidal Ideation Monitoring System",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Page modules ────────────────────────────────────────────
import page_login
import page_signup
import page_dashboard
import page_upload
import page_analysis
import page_trends
import page_history
import database as db

# ── ML backend ──────────────────────────────────────────────
try:
    from logic import SIMSLogic
except Exception as _e:
    st.error(
        f"❌ Could not import SIMSLogic: {_e}\n\n"
        "Make sure `logic.py` is in your project folder and all "
        "packages in `requirements.txt` are installed."
    )
    st.stop()

# ══════════════════════════════════════════════════════════
#  DATABASE INIT
# ══════════════════════════════════════════════════════════
if "db_initialized" not in st.session_state:
    db.init_db()
    st.session_state["db_initialized"] = True

# ══════════════════════════════════════════════════════════
#  GLOBAL CSS — dark theme shared across all dashboard pages
# ══════════════════════════════════════════════════════════
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], p, label, .stMarkdown,
    h1, h2, h3, h4 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(10,12,28,0.98) !important;
        border-right: 1px solid #1E293B;
        width: 270px !important;
    }

    /* Global metric cards */
    div[data-testid="metric-container"] {
        background: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }

    /* Buttons */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(135deg,#7c3aed 0%,#6d28d9 100%) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(124,58,237,0.4) !important;
    }

    /* Inputs */
    input, textarea, [data-baseweb="input"] input {
        background: #0F172A !important;
        color: #F1F5F9 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] { border-radius: 10px !important; }

    /* Alerts */
    [data-testid="stAlert"] { border-radius: 10px !important; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0F172A; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

    /* White text for dark pages */
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) p,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) span,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) li,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stMarkdown p,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) [data-testid="stText"],
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) [data-testid="stCaption"] {
        color: #F1F5F9 !important;
    }
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) label,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) [data-testid="stWidgetLabel"] p,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h1,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h2,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h3,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h4 {
        color: #F1F5F9 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════
_DEFAULTS = {
    "logged_in":       False,
    "current_user":    None,
    "current_view":    "login",
    "active_page":     "Dashboard",
    "raw_df":          None,
    "analyzed_df":     None,
    "active_batch_id": None,
    "audit_log":       [],
    "_login_logged":   False,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════
#  LOAD ML BACKEND — cached for the whole session
# ══════════════════════════════════════════════════════════
@st.cache_resource(show_spinner="Loading SIMS AI engine…")
def _load_logic():
    return SIMSLogic()

try:
    logic = _load_logic()
except Exception as _e:
    st.warning(
        f"⚠️ AI engine could not load: {_e}\n\n"
        "The keyword fallback classifier will be used instead. "
        "Upload your `.pkl` model files to the `models/` folder "
        "to enable full ML classification."
    )
    logic = None

# ══════════════════════════════════════════════════════════
#  NAV PAGES
# ══════════════════════════════════════════════════════════
NAV_PAGES = [
    ("Dashboard", "📊"),
    ("Upload",    "📤"),
    ("Analysis",  "🔍"),
    ("Trends",    "📈"),
    ("History",   "🕒"),
]

# ══════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════
def _render_sidebar():
    with st.sidebar:
        st.markdown("""
            <div style='text-align:center;padding:1rem 0 0.5rem;'>
                <div style='font-size:0.65rem;color:#ffffff;font-weight:700;
                            text-transform:uppercase;letter-spacing:2px;'>
                    SIMS<br>Suicidal Ideation Monitoring System
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.divider()

        # User badge
        user = st.session_state["current_user"] or {}
        st.markdown(f"""
            <div style='background:#1e293b;border:1px solid #334155;
                        border-radius:10px;padding:10px 12px;margin-bottom:1rem;'>
                <div style='font-size:0.65rem;color:#94a3b8;font-weight:700;
                            text-transform:uppercase;letter-spacing:1px;'>
                    {user.get("role","Analyst")}
                </div>
                <div style='font-weight:800;color:#f1f5f9;font-size:0.88rem;
                            margin-top:2px;'>
                    @{user.get("username","—")}
                </div>
                <div style='font-size:0.7rem;color:#475569;margin-top:1px;'>
                    {user.get("email","—")}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Navigation
        st.markdown(
            "<div style='font-size:0.65rem;color:#475569;font-weight:700;"
            "text-transform:uppercase;letter-spacing:1.5px;"
            "margin-bottom:0.5rem;'>Navigation</div>",
            unsafe_allow_html=True
        )

        active_key = f"nav_{st.session_state['active_page']}"
        st.markdown(f"""
            <style>
            div[data-testid="stSidebar"] button[kind="secondary"] {{
                background: transparent !important;
                border: 1px solid transparent !important;
                color: #94a3b8 !important;
                transition: background 0.15s, color 0.15s !important;
            }}
            div[data-testid="stSidebar"] button[kind="secondary"]:hover {{
                background: rgba(124,58,237,0.08) !important;
                border: 1px solid rgba(124,58,237,0.2) !important;
                color: #e2e8f0 !important;
            }}
            div[data-testid="stSidebar"] [data-testid="stBaseButton-{active_key}"] button,
            div[data-testid="stSidebar"] [data-testid="stBaseButton-{active_key}"] button:hover {{
                background: rgba(124,58,237,0.18) !important;
                border: 1px solid rgba(124,58,237,0.45) !important;
                color: #ffffff !important;
            }}
            </style>
        """, unsafe_allow_html=True)

        for page_name, icon in NAV_PAGES:
            if st.button(
                f"{icon}  {page_name}",
                key=f"nav_{page_name}",
                use_container_width=True
            ):
                st.session_state["active_page"] = page_name
                st.rerun()

        st.divider()

        # AI engine status
        ok     = logic is not None and logic.is_ready
        colour = "#22c55e" if ok else "#ef4444"
        label  = "AI Engine Ready" if ok else "Model Not Loaded"
        st.markdown(f"""
            <div style='background:#0f172a;border:1px solid {colour}33;
                        border-radius:8px;padding:8px 10px;
                        display:flex;align-items:center;gap:8px;
                        margin-bottom:0.8rem;'>
                <div style='width:7px;height:7px;border-radius:50%;
                            background:{colour};flex-shrink:0;'></div>
                <span style='font-size:0.72rem;color:{colour};font-weight:600;'>
                    {label}
                </span>
            </div>
        """, unsafe_allow_html=True)

        # Dataset status
        has_data = st.session_state.get("analyzed_df") is not None
        d_colour = "#22c55e" if has_data else "#64748b"
        d_label  = (
            f"{len(st.session_state['analyzed_df']):,} posts loaded"
            if has_data else "No dataset loaded"
        )
        st.markdown(f"""
            <div style='background:#0f172a;border:1px solid {d_colour}33;
                        border-radius:8px;padding:8px 10px;
                        display:flex;align-items:center;gap:8px;
                        margin-bottom:1rem;'>
                <div style='width:7px;height:7px;border-radius:50%;
                            background:{d_colour};flex-shrink:0;'></div>
                <span style='font-size:0.72rem;color:{d_colour};font-weight:600;'>
                    {d_label}
                </span>
            </div>
        """, unsafe_allow_html=True)

        # Logout — SIMS_10
        if st.button("🚪 Logout", use_container_width=True, key="btn_logout"):
            db.log_event(
                "logout",
                user.get("username", "—"),
                "User logged out",
                success=True
            )
            st.session_state["audit_log"].append({
                "event": "logout",
                "user":  user.get("username", "—"),
                "time":  time.strftime("%Y-%m-%d %H:%M:%S")
            })
            for k in ("logged_in", "current_user", "raw_df",
                      "analyzed_df", "active_batch_id", "_login_logged"):
                st.session_state[k] = (
                    False if k == "logged_in" else None
                )
            st.session_state["current_view"] = "login"
            st.rerun()

# ══════════════════════════════════════════════════════════
#  MAIN ROUTER
# ══════════════════════════════════════════════════════════
if not st.session_state["logged_in"]:
    if st.session_state["current_view"] == "signup":
        page_signup.show_page()      # SIMS_01
    else:
        page_login.show_page()       # SIMS_02

else:
    # On first entry after login — clear any stale dataset
    if not st.session_state["_login_logged"]:
        st.session_state["audit_log"].append({
            "event": "login",
            "user":  st.session_state["current_user"].get("username", "—"),
            "time":  time.strftime("%Y-%m-%d %H:%M:%S")
        })
        st.session_state["_login_logged"]  = True
        st.session_state["analyzed_df"]    = None
        st.session_state["active_batch_id"] = None

    _render_sidebar()

    page = st.session_state["active_page"]

    if   page == "Dashboard": page_dashboard.show_page()
    elif page == "Upload":    page_upload.show_page(logic)
    elif page == "Analysis":  page_analysis.show_page()
    elif page == "Trends":    page_trends.show_page()
    elif page == "History":   page_history.show_page()