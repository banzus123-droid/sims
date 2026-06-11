import streamlit as st
import streamlit.components.v1 as components
import os
import hashlib

import database as db


def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


def show_page():

    logo_path = r"C:\Users\konek\Documents\UUM\sem 5\fyp\dataset\Organic Spices.png"

    st.markdown("""
        <style>
        header, footer, #MainMenu { visibility: hidden; }
        .stDeployButton { display: none; }
        .stApp {
            background: linear-gradient(135deg,
                #2c3e50 0%, #4b6b8a 40%, #fd746c 100%) !important;
        }
        [data-testid="stVerticalBlock"] > div:has(.login-card-container) {
            background-color: white !important;
            padding: 20px 40px 50px 40px !important;
            border-radius: 32px !important;
            box-shadow: 0 25px 50px rgba(0,0,0,0.4) !important;
            max-width: 440px;
            margin: 0 auto;
        }
        [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"],
        [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] > div {
            background-color: transparent !important;
            box-shadow: none !important;
            border: none !important;
            background: none !important;
        }
        div[data-testid="stImage"] img {
            opacity:1.0 !important;
            filter:drop-shadow(0 4px 8px rgba(0,0,0,0.1));
            display:block; margin:0 auto;
        }
        .welcome-msg {
            font-size:44px; font-weight:900; color:#7C3AED;
            text-align:center; margin:10px 0 5px;
            line-height:1.1; letter-spacing:-1px;
        }
        .signin-small {
            font-size:13px; font-weight:700; color:#9CA3AF;
            text-align:center; margin-bottom:35px;
            text-transform:uppercase; letter-spacing:2px;
        }
        .stTextInput input {
            background-color:#F3F4F6 !important;
            border:1px solid transparent !important;
            border-radius:12px !important;
            color:#000000 !important;
            -webkit-text-fill-color:#000000 !important;
            padding:12px 15px !important;
            font-weight:500 !important;
        }
        input[type="password"] {
            color:#000000 !important;
            -webkit-text-fill-color:#000000 !important;
        }
        .stTextInput input:focus, .stTextInput input:hover {
            background-color:#E5E7EB !important;
            border:1px solid #7C3AED !important;
            color:#000000 !important;
            -webkit-text-fill-color:#000000 !important;
        }
        [data-testid="stInputInstructions"],
        div[class*="stInputInstructions"] {
            display:none !important; height:0 !important;
        }
        .stTextInput label p {
            color:#4B5563 !important;
            font-weight:700 !important; font-size:13px !important;
        }
        div.stButton > button {
            background:linear-gradient(135deg,#7C3AED 0%,#9F67FF 100%) !important;
            color:white !important; border-radius:14px !important;
            padding:14px 0 !important; font-weight:800 !important;
            font-size:18px !important; border:none !important;
            width:100% !important;
            transition:transform 0.2s, box-shadow 0.2s !important;
        }
        div.stButton > button:hover {
            transform:translateY(-2px);
            box-shadow:0 8px 20px rgba(124,58,237,0.4) !important;
        }

        /* ── Force ALL text black inside the login card ── */
        p, span, div, label,
        .stMarkdown p, .stMarkdown span, .stMarkdown div,
        [data-testid="stText"], [data-testid="stMarkdownContainer"] p,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] label,
        [data-testid="stAlert"] p,
        [data-testid="stAlert"] div {
            color: #000000 !important;
        }
        /* Warning and error boxes */
        [data-testid="stAlert"] {
            color: #000000 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)

    # ── Session state ──────────────────────────────────────
    if 'pwd_clean'    not in st.session_state: st.session_state.pwd_clean    = ""
    if 'pwd_widget'   not in st.session_state: st.session_state.pwd_widget   = ""
    if 'current_view' not in st.session_state: st.session_state.current_view = 'login'

    def _enforce_numeric():
        st.session_state.pwd_clean = "".join(
            c for c in st.session_state.pwd_widget if c.isdigit())[:8]

    # ── Card ───────────────────────────────────────────────
    with st.container():
        st.markdown('<div class="login-card-container"></div>', unsafe_allow_html=True)

        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.markdown('<div style="font-size:60px;text-align:center;">🛡️</div>',
                        unsafe_allow_html=True)

        st.markdown('<div class="welcome-msg">Welcome to the SIMS</div>',     unsafe_allow_html=True)
        st.markdown('<div class="signin-small">Sign in to your account</div>', unsafe_allow_html=True)

        username = st.text_input(
            "Username",
            placeholder="Enter your username",
            value=""
        )
        st.text_input(
            "Password (numbers only · max 8 digits)",
            type="password",
            placeholder="Insert your password",
            max_chars=8,
            key="pwd_widget",
            on_change=_enforce_numeric,
        )
        current_pwd = st.session_state.pwd_clean

        col_l, col_mid, col_r = st.columns([0.05, 0.9, 0.05])
        with col_mid:
            if st.button("Sign In", use_container_width=True, key="btn_signin"):
                if not username.strip():
                    st.warning("Please enter your username.")
                elif not current_pwd:
                    st.warning("Please enter your password.")
                else:
                    # ── SQLite-backed authentication (logs attempt to audit_log) ──
                    user = db.authenticate(username.strip(), current_pwd)
                    if user:
                        st.session_state.logged_in    = True
                        st.session_state.current_user = user
                        st.session_state.pwd_clean = ""
                        st.session_state.pop('pwd_widget', None)
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password.")

        # Hidden signup trigger
        if st.button("\u200B", key="btn_goto_signup"):
            st.session_state['current_view'] = 'signup'
            st.rerun()

        st.markdown("""
            <p style="text-align:center;margin-top:20px;font-size:14px;
                      color:#6B7280;font-family:inherit;">
                Don't have an account yet?&nbsp;<span
                    id="sims-signup-link"
                    style="color:#7C3AED;font-weight:800;cursor:pointer;"
                    onmouseover="this.style.textDecoration='underline'"
                    onmouseout="this.style.textDecoration='none'"
                >Sign up</span>
            </p>
        """, unsafe_allow_html=True)

    st.markdown(
        '<p style="text-align:center;color:white;opacity:0.7;margin-top:40px;'
        'font-size:12px;font-weight:600;letter-spacing:1px;">'
        'AUTHORIZED ANALYST PERSONNEL ONLY</p>',
        unsafe_allow_html=True
    )

    components.html("""
        <script>
        (function(){
            var doc=window.parent.document;
            function run(){
                try{
                    doc.querySelectorAll('input[type="password"]').forEach(function(inp){
                        if(inp._ng) return; inp._ng=true;
                        inp.addEventListener('keydown',function(e){
                            var ok=/^[0-9]$/.test(e.key)
                              ||['Backspace','Delete','Tab','Enter',
                                 'ArrowLeft','ArrowRight','Home','End'].includes(e.key)
                              ||((e.ctrlKey||e.metaKey)&&
                                 ['a','c','v','x'].includes(e.key.toLowerCase()));
                            if(!ok) e.preventDefault();
                        });
                        inp.addEventListener('paste',function(e){
                            e.preventDefault();
                            var d=(e.clipboardData||window.clipboardData)
                                  .getData('text').replace(/\D/g,'').slice(0,8);
                            document.execCommand('insertText',false,d);
                        });
                    });
                    var hb=null;
                    doc.querySelectorAll('button').forEach(function(b){
                        if(b.innerText==='\u200B'||b.textContent==='\u200B'){
                            hb=b;
                            var s=b.closest('[data-testid="stButton"]');
                            if(s) s.style.cssText+=';display:none!important;height:0!important;overflow:hidden!important;margin:0!important;padding:0!important';
                            var ec=b.closest('.element-container');
                            if(ec) ec.style.cssText+=';display:none!important;height:0!important;overflow:hidden!important;margin:0!important;padding:0!important';
                        }
                    });
                    var lk=doc.getElementById('sims-signup-link');
                    if(lk&&hb&&!lk._wired){lk._wired=true;lk.addEventListener('click',function(){hb.click();});}
                }catch(e){}
            }
            run(); setInterval(run,100);
        })();
        </script>
    """, height=0)


if __name__ == "__main__":
    import page_signup
    if st.session_state.get('current_view') == 'signup':
        page_signup.show_page()
    else:
        show_page()