import streamlit as st
import streamlit.components.v1 as components
import os
import hashlib

import database as db


def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


def show_page():


    st.markdown("""
        <style>
        header, footer, #MainMenu { visibility: hidden; }
        .stDeployButton { display: none; }
        .stApp {
            background: linear-gradient(135deg,
                #2c3e50 0%, #4b6b8a 40%, #fd746c 100%) !important;
        }
        [data-testid="stVerticalBlock"] > div:has(.signup-card-container) {
            background-color: white !important;
            padding: 20px 40px 40px 40px !important;
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
            opacity: 1.0 !important;
            filter: drop-shadow(0 4px 8px rgba(0,0,0,0.1));
            display: block; margin: 0 auto;
        }
        .welcome-msg {
            font-size: 38px; font-weight: 900; color: #7C3AED;
            text-align: center; margin: 10px 0 5px;
            line-height: 1.1; letter-spacing: -1px;
        }
        .signin-small {
            font-size: 13px; font-weight: 700; color: #9CA3AF;
            text-align: center; margin-bottom: 28px;
            text-transform: uppercase; letter-spacing: 2px;
        }
        .stTextInput input {
            background-color: #F3F4F6 !important;
            border: 1px solid transparent !important;
            border-radius: 12px !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            padding: 12px 15px !important;
            font-weight: 500 !important;
        }
        input[type="password"] {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
        }
        .stTextInput input:focus, .stTextInput input:hover {
            background-color: #E5E7EB !important;
            border: 1px solid #7C3AED !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
        }
        [data-testid="stInputInstructions"],
        div[class*="stInputInstructions"] {
            display: none !important; height: 0 !important;
        }
        .stTextInput label p {
            color: #4B5563 !important;
            font-weight: 700 !important; font-size: 13px !important;
        }
        div.stButton > button {
            background: linear-gradient(135deg, #7C3AED 0%, #9F67FF 100%) !important;
            color: white !important; border-radius: 14px !important;
            padding: 14px 0 !important; font-weight: 800 !important;
            font-size: 18px !important; border: none !important;
            width: 100% !important;
            transition: transform 0.2s, box-shadow 0.2s !important;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(124,58,237,0.4) !important;
        }

        /* ── Force ALL text black inside the signup card ── */
        *, *::before, *::after,
        p, span, div, li, a,
        h1, h2, h3, h4, h5, h6,
        label, small, strong, em, b, i,
        .stMarkdown, .stMarkdown *,
        [data-testid="stText"],
        [data-testid="stCaption"],
        [data-testid="stMarkdownContainer"] *,
        [data-testid="stWidgetLabel"] *,
        [data-testid="stAlert"] *,
        [data-testid="stInfo"] *,
        [data-testid="stWarning"] *,
        [data-testid="stSuccess"] *,
        [data-testid="stError"] * {
            color: #000000 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)

    # ── Session state ──────────────────────────────────────
    for k, v in {
        'su_pwd_widget': '', 'su_pwd_clean': '',
        'su_cpwd_widget': '', 'su_cpwd_clean': '',
        'current_view': 'login',
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Callbacks — only update shadow key, never write back to widget key
    def _clean_pwd():
        st.session_state.su_pwd_clean = "".join(
            c for c in st.session_state.su_pwd_widget if c.isdigit())[:8]

    def _clean_cpwd():
        st.session_state.su_cpwd_clean = "".join(
            c for c in st.session_state.su_cpwd_widget if c.isdigit())[:8]

    # ── Card ───────────────────────────────────────────────
    with st.container():
        st.markdown('<div class="signup-card-container"></div>', unsafe_allow_html=True)

        logo_path = r"C:\Users\konek\Documents\UUM\sem 5\fyp\dataset\Organic Spices.png"
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.image(r"C:\Users\konek\Documents\UUM\sem 5\fyp\dataset\Organic_Spices.png", use_container_width=True)

        st.markdown('<div class="welcome-msg">Create Account</div>',          unsafe_allow_html=True)
        st.markdown('<div class="signin-small">Register as an Analyst</div>', unsafe_allow_html=True)

        # Fields
        username = st.text_input("Username",      placeholder="e.g. nizar_hakim")
        email    = st.text_input("Email Address", placeholder="e.g. nizar@gmail.com")

        st.text_input(
            "Password (numbers only · max 8 digits)",
            type="password",
            placeholder="Enter 8-digit numeric password",
            max_chars=8,
            key="su_pwd_widget",
            on_change=_clean_pwd,
        )
        st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Re-enter your numeric password",
            max_chars=8,
            key="su_cpwd_widget",
            on_change=_clean_cpwd,
        )

        col_l, col_mid, col_r = st.columns([0.05, 0.9, 0.05])
        with col_mid:
            if st.button("Create Account", use_container_width=True,
                         key="btn_create"):
                pwd   = st.session_state.su_pwd_clean
                cpwd  = st.session_state.su_cpwd_clean
                uname = username.strip().lower()

                # Validation
                if not uname:
                    st.error("❌ Please enter a username.")
                elif " " in uname:
                    st.error("❌ Username cannot contain spaces.")
                elif not email.strip() or "@" not in email:
                    st.error("❌ Please enter a valid email address.")
                elif len(pwd) < 6:
                    st.error("❌ Password must be at least 6 digits.")
                elif pwd != cpwd:
                    st.error("❌ Passwords do not match.")
                else:
                    # ── SQLite-backed account creation ──
                    ok, msg = db.create_user(uname, email.strip(), pwd)
                    if not ok:
                        st.error(f"❌ {msg}")
                    else:
                        st.success(
                            f"✅ Account created for **@{uname}**! "
                            "Redirecting to sign in…"
                        )

                        import time; time.sleep(1.5)

                        # Delete widget keys — safe way to clear password fields
                        for k in ('su_pwd_widget', 'su_pwd_clean',
                                  'su_cpwd_widget', 'su_cpwd_clean'):
                            st.session_state.pop(k, None)

                        st.session_state['current_view'] = 'login'
                        st.rerun()

        # Hidden back-to-login trigger
        if st.button("\u200B", key="btn_back_login"):
            st.session_state['current_view'] = 'login'
            st.rerun()

        st.markdown("""
            <p style="text-align:center;margin-top:20px;font-size:14px;
                      color:#6B7280;font-family:inherit;">
                Already have an account?&nbsp;<span
                    id="sims-signin-link"
                    style="color:#7C3AED;font-weight:800;cursor:pointer;"
                    onmouseover="this.style.textDecoration='underline'"
                    onmouseout="this.style.textDecoration='none'"
                >Sign in</span>
            </p>
        """, unsafe_allow_html=True)

    st.markdown(
        '<p style="text-align:center;color:white;opacity:0.7;margin-top:40px;'
        'font-size:12px;font-weight:600;letter-spacing:1px;">'
        'AUTHORIZED ANALYST PERSONNEL ONLY</p>',
        unsafe_allow_html=True
    )

    # ── JavaScript ─────────────────────────────────────────
    components.html("""
        <script>
        (function(){
            var doc=window.parent.document;
            function run(){
                try{
                    /* Numeric guard on password fields */
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
                    /* Hide hidden back-to-login button */
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
                    /* Wire Sign in span */
                    var lk=doc.getElementById('sims-signin-link');
                    if(lk&&hb&&!lk._wired){
                        lk._wired=true;
                        lk.addEventListener('click',function(){ hb.click(); });
                    }
                }catch(e){}
            }
            run(); setInterval(run,100);
        })();
        </script>
    """, height=0)


if __name__ == "__main__":
    show_page()