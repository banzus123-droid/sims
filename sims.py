"""
app.py — SIMS Entry Point
Run with: streamlit run app.py

Proposal mapping:
  SIMS_01  Sign Up        → page_signup.show_page()
  SIMS_02  Login          → page_login.show_page()
  SIMS_03  Dashboard      → page_dashboard.show_page()
  SIMS_04–07 Upload/ML   → page_upload.show_page(logic)
  SIMS_08–09 Filter/CSV  → page_analysis.show_page()
  FR 2.3   Trends        → page_trends.show_page()
  SIMS_10  Logout         → sidebar button
  NFR 1.1  Hashed pwds   → logic handled in page_login / page_signup
  NFR 1.2  Audit log     → session_state['audit_log']
"""

import streamlit as st
import hashlib
import time
import os

# ── Page modules ──────────────────────────────────────────
import page_login
import page_signup
import page_dashboard
import page_upload
import page_analysis
import page_trends
import page_history

# ── Database layer (SQLite) ───────────────────────────────
import database as db


# ── ML backend ────────────────────────────────────────────
try:
    from logic import SIMSLogic
except Exception as e:
    st.error(f"❌ Could not import SIMSLogic: {e}")
    st.stop()

# ══════════════════════════════════════════════════════════
#  PAGE CONFIG  (must be the very first Streamlit call)
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SIMS | Suicidal Ideation Monitoring System",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════
#  DATABASE INIT — creates sims.db on first run, seeds admin
# ══════════════════════════════════════════════════════════
if 'db_initialized' not in st.session_state:
    db.init_db()
    st.session_state['db_initialized'] = True

# ══════════════════════════════════════════════════════════
#  GLOBAL CSS — dark theme shared across dashboard pages
# ══════════════════════════════════════════════════════════
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], p, label, .stMarkdown,
    h1, h2, h3, h4 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    /* Background is set per-page */

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
        color: #a78bfa !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }

    /* Buttons — purple */
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

    /* Tabs */
    div[data-testid="stTabs"] button {
        color: #ffffff !important;
        font-weight: 600 !important;
        background: transparent !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #ffffff !important;
        border-bottom-color: #7c3aed !important;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] { border-radius: 10px !important; }

    /* Alerts */
    [data-testid="stAlert"] { border-radius: 10px !important; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0F172A; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

    /* ── White text for dark pages ONLY (not login/signup) ── */
    /* Triggered by the dark app background set on dashboard/upload/analysis/trends */
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
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stTextInput label,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stSelectbox label,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stMultiSelect label,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stRadio label,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stCheckbox label,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stFileUploader label {
        color: #F1F5F9 !important;
    }
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) [data-baseweb="select"] [data-baseweb="value"],
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stRadio div label p,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .stCheckbox div label p,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) .streamlit-expanderHeader,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h1,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h2,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h3,
    [data-testid="stAppViewContainer"]:not(:has(.login-card-container)):not(:has(.signup-card-container)) h4 {
        color: #F1F5F9 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  SESSION STATE — initialise all keys once at startup
# ══════════════════════════════════════════════════════════
_DEFAULTS = {
    # Auth
    'logged_in':      False,
    'current_user':   None,
    'current_view':   'login',      # 'login' | 'signup'
    # Navigation
    'active_page':    'Dashboard',
    # Data
    'raw_df':         None,
    'analyzed_df':    None,
    # Tracks which batch is currently loaded in analyzed_df.
    # Set when user loads a batch from History, or after a new upload.
    # Cleared to None when that batch is deleted.
    'active_batch_id': None,
    # Audit log (NFR 1.2) — kept for legacy in-session display only;
    # the authoritative audit log is in SQLite (see database.py)
    'audit_log':      [],
    '_login_logged':  False,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════
#  BACKEND — load once, cache for the session
# ══════════════════════════════════════════════════════════
@st.cache_resource(show_spinner="Loading SIMS AI engine…")
def _load_logic():
    for path in ['models/sims_pipeline.pkl', 'sims_pipeline.pkl']:
        if os.path.exists(path):
            return SIMSLogic()
    # Returns with pipeline=None — pages handle gracefully
    return SIMSLogic()

try:
    logic = _load_logic()
except Exception as e:
    st.warning(f"⚠️ AI engine error: {e}. Some features may be unavailable.")
    logic = None

# ══════════════════════════════════════════════════════════
#  SIDEBAR  (shown only when logged in)
# ══════════════════════════════════════════════════════════
NAV_PAGES = [
    ("Dashboard",   "📊"),
    ("Upload",      "📤"),
    ("Analysis",    "🔍"),
    ("Trends",      "📈"),
    ("History",     "🕒"),
]

def _render_sidebar():
    with st.sidebar:
        # Brand — plain text
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
        user = st.session_state['current_user'] or {}
        st.markdown(f"""
            <div style='background:#1e293b;border:1px solid #334155;
                        border-radius:10px;padding:10px 12px;margin-bottom:1rem;'>
                <div style='font-size:0.65rem;color:#7c3aed;font-weight:700;
                            text-transform:uppercase;letter-spacing:1px;'>
                    {user.get('role','Analyst')}
                </div>
                <div style='font-weight:800;color:#f1f5f9;font-size:0.88rem;
                            margin-top:2px;'>
                    @{user.get('username','—')}
                </div>
                <div style='font-size:0.7rem;color:#475569;margin-top:1px;'>
                    {user.get('email','—')}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Navigation — active state via CSS only, no wrapper divs
        st.markdown(
            "<div style='font-size:0.65rem;color:#475569;font-weight:700;"
            "text-transform:uppercase;letter-spacing:1.5px;"
            "margin-bottom:0.5rem;'>Navigation</div>",
            unsafe_allow_html=True
        )

        active_page = st.session_state['active_page']

        # Inject one CSS block — base style for all nav buttons,
        # plus active override for the current page's button key.
        # Streamlit renders each st.button with a wrapping element
        # that carries data-testid="stBaseButton-{key}", which lets
        # us target the active button without any wrapper divs.
        active_key = f"nav_{active_page}"
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
                st.session_state['active_page'] = page_name
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
        has_data = st.session_state.get('analyzed_df') is not None
        d_colour = "#22c55e" if has_data else "#64748b"
        d_label  = f"{len(st.session_state['analyzed_df']):,} posts analysed" \
                   if has_data else "No dataset loaded"
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
            # Log to SQLite (NFR 1.2)
            db.log_event(
                'logout',
                user.get('username', '—'),
                'User logged out',
                success=True
            )
            # Keep legacy in-session log for backward compatibility
            st.session_state['audit_log'].append({
                'event': 'logout',
                'user':  user.get('username', '—'),
                'time':  time.strftime('%Y-%m-%d %H:%M:%S')
            })
            for k in ('logged_in','current_user','raw_df',
                      'analyzed_df','active_batch_id','_login_logged'):
                st.session_state[k] = (
                    False if k == 'logged_in' else None
                )
            st.session_state['current_view'] = 'login'
            st.rerun()

# ══════════════════════════════════════════════════════════
#  MAIN ROUTER
# ══════════════════════════════════════════════════════════
if not st.session_state['logged_in']:
    # ── Auth flow ─────────────────────────────────────────
    if st.session_state['current_view'] == 'signup':
        page_signup.show_page()          # SIMS_01
    else:
        page_login.show_page()           # SIMS_02

else:
    # ── Audit: log first login per session (NFR 1.2) ──────
    if not st.session_state['_login_logged']:
        st.session_state['audit_log'].append({
            'event': 'login',
            'user':  st.session_state['current_user'].get('username','—'),
            'time':  time.strftime('%Y-%m-%d %H:%M:%S')
        })
        st.session_state['_login_logged'] = True

        # ── Clear any stale dataset from a previous session ──
        # The hydration blocks in page_upload / page_analysis /
        # page_trends restore data from SQLite whenever analyzed_df
        # is None — so clearing here means the user always starts
        # with a clean slate and must explicitly load or upload a
        # batch before any data appears on the dashboard.
        st.session_state['analyzed_df']    = None
        st.session_state['active_batch_id'] = None

    _render_sidebar()

    # ── Route to active page ──────────────────────────────
    page = st.session_state['active_page']

    if page == 'Dashboard':
        page_dashboard.show_page()       # SIMS_03

    elif page == 'Upload':
        page_upload.show_page(logic)     # SIMS_04 → SIMS_07

    elif page == 'Analysis':
        page_analysis.show_page()        # SIMS_08 + SIMS_09

    elif page == 'Trends':
        page_trends.show_page()          # FR 2.3

    elif page == 'History':
        page_history.show_page()         # Past analysis batches