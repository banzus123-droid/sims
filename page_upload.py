"""
page_upload.py — SIMS_04 to SIMS_07
  SIMS_04  Upload Dataset
  SIMS_05  Preprocess Dataset
  SIMS_06  Run ML Classification
  SIMS_07  Save Analysis Results
"""
import streamlit as st
import pandas as pd
import numpy as np
import time

import database as db


def show_page(logic):

    model_ready = logic is not None and logic.is_ready

    # Hydrate analyzed_df from SQLite if session is empty (persistence across restarts)
    if st.session_state.get('analyzed_df') is None:
        try:
            persisted = db.get_all_posts()
            if not persisted.empty:
                st.session_state['analyzed_df'] = persisted
        except Exception:
            pass

    st.markdown("""
        <style>
    .stApp {
        background: linear-gradient(135deg,
            #2c3e50 0%, #4b6b8a 40%, #fd746c 100%) !important;
    }

        .up-title  { font-size:1.7rem;font-weight:900;color:#FFFFFF;
                     letter-spacing:-0.5px;margin-bottom:4px; }
        .up-sub    { font-size:0.85rem;color:#FFFFFF;margin-bottom:1.5rem; }
        .up-zone   { border:2px dashed #4c1d95;border-radius:16px;
                     padding:2.5rem 2rem;text-align:center;
                     background:rgba(124,58,237,0.04);margin-bottom:1rem; }
        .req-box   { background:rgba(124,58,237,0.07);
                     border:1px solid rgba(124,58,237,0.2);
                     border-radius:12px;padding:1.2rem 1.5rem;margin-top:1rem; }
        .req-title { font-size:0.82rem;font-weight:700;color:#a78bfa;
                     margin-bottom:0.5rem; }
        .req-item  { font-size:0.78rem;color:#CBD5E1;padding:2px 0; }
        .sec-lbl   { font-size:0.72rem;font-weight:700;color:#E2E8F0;
                     text-transform:uppercase;letter-spacing:1.5px;
                     margin:1.2rem 0 0.6rem; }
        .prev-bar  { background:#1e293b;border:1px solid #334155;
                     border-radius:8px;padding:10px 14px;margin-bottom:1rem;
                     font-size:0.8rem;color:#E2E8F0; }
        .result-ok { background:rgba(34,197,94,0.07);
                     border:1px solid rgba(34,197,94,0.2);
                     border-radius:10px;padding:12px 16px;margin-top:1rem;
                     color:#4ade80;font-weight:600;font-size:0.88rem; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="up-title">📤 Dataset Upload &amp; Analysis</div>
        <div class="up-sub">
            Upload a CSV of social media posts — the system will preprocess,
            classify, and save the results automatically.
        </div>
    """, unsafe_allow_html=True)

    tab_upload, tab_results = st.tabs([
        "📤  Upload & Analyse",
        "📋  Current Results",
    ])

    # ════════════════════════════════════════════════════
    #  TAB 1 — UPLOAD (SIMS_04 + SIMS_05 + SIMS_06 + SIMS_07)
    # ════════════════════════════════════════════════════
    with tab_upload:

        # SIMS_04 — Interactive upload zone (fully styled and clickable)
        st.markdown("""
            <style>
            /* Hide the default file uploader label */
            [data-testid="stFileUploader"] label {
                display: none !important;
            }
            
            /* Style the dropzone to match the decorative upload box */
            section[data-testid="stFileUploadDropzone"] {
                background: linear-gradient(135deg, rgba(124,58,237,0.06) 0%, rgba(124,58,237,0.02) 100%) !important;
                border: 2px dashed #4c1d95 !important;
                border-radius: 16px !important;
                padding: 3rem 2rem !important;
                margin-bottom: 2rem !important;
                text-align: center !important;
                transition: all 0.3s ease !important;
            }
            
            section[data-testid="stFileUploadDropzone"]:hover {
                background: linear-gradient(135deg, rgba(124,58,237,0.12) 0%, rgba(124,58,237,0.08) 100%) !important;
                border-color: #7c3aed !important;
                cursor: pointer !important;
                box-shadow: 0 0 20px rgba(124,58,237,0.2) !important;
            }
            
            /* Arrange instructions vertically */
            [data-testid="stFileUploaderDropzoneInstructions"] {
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
                gap: 0.8rem !important;
            }
            
            /* Large upload icon */
            [data-testid="stFileUploaderDropzoneInstructions"] svg {
                width: 3.5rem !important;
                height: 3.5rem !important;
                color: #60a5fa !important;
            }
            
            /* Main text */
            [data-testid="stFileUploaderDropzoneInstructions"] p:first-of-type {
                font-size: 1.3rem !important;
                font-weight: 900 !important;
                color: #FFFFFF !important;
                margin: 0 !important;
                letter-spacing: -0.5px !important;
            }
            
            /* Secondary text */
            [data-testid="stFileUploaderDropzoneInstructions"] p:last-of-type {
                color: #FFFFFF !important;
                font-size: 0.9rem !important;
                margin: 0 !important;
                font-weight: 500 !important;
                opacity: 0.95 !important;
            }
            
            /* Browse files button */
            [data-testid="stFileUploadDropzone"] button {
                background: linear-gradient(135deg, #7C3AED 0%, #9F67FF 100%) !important;
                color: white !important;
                border-radius: 10px !important;
                border: none !important;
                font-weight: 700 !important;
                padding: 12px 28px !important;
                font-size: 0.95rem !important;
                margin-top: 0.8rem !important;
                transition: all 0.2s ease !important;
            }
            
            [data-testid="stFileUploadDropzone"] button:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 20px rgba(124,58,237,0.4) !important;
            }
            </style>
        """, unsafe_allow_html=True)

        # The interactive file uploader — takes up the full styled zone
        uploaded = st.file_uploader(
            "⬆️ Upload Dataset\nCSV files containing social media posts",
            type=["csv"],
            key="file_uploader",
            label_visibility="collapsed"
        )

        # Requirements info box
        st.markdown("""
            <div class="req-box">
                <div class="req-title">📋 Dataset Requirements</div>
                <div class="req-item">
                    • Required column: <b>text</b> — the post content to analyse
                </div>
                <div class="req-item">
                    • Optional columns: username, platform, timestamp
                </div>
                <div class="req-item">
                    • Supported sources: Reddit, Twitter/X, Kaggle datasets
                </div>
                <div class="req-item">
                    • Pipeline: text cleaning → tokenisation →
                      stopword removal → lemmatisation → TF-IDF → Random Forest
                </div>
                <div class="req-item">
                    • Risk score range: 0.0 (safe) to 1.0 (high risk)
                </div>
            </div>
        """, unsafe_allow_html=True)

        if uploaded is not None:
            # SIMS_04 — validate and load
            try:
                df_raw = pd.read_csv(uploaded)
                st.session_state['raw_df'] = df_raw
            except Exception as e:
                st.error(f"❌ Could not read file: {e}")
                return

            if 'text' not in df_raw.columns:
                st.error(
                    f"❌ Required column **'text'** not found. "
                    f"Your file has: `{list(df_raw.columns)}`"
                )
                return

            st.success(
                f"✅ **{len(df_raw):,} rows** loaded from `{uploaded.name}` "
                f"— `text` column confirmed ✓"
            )

            # Preview
            st.markdown(
                '<div class="sec-lbl">Preview — first 10 rows</div>',
                unsafe_allow_html=True
            )
            st.dataframe(
                df_raw[['text'] +
                       [c for c in df_raw.columns if c != 'text']]
                .head(10),
                use_container_width=True,
                height=240
            )

            miss = df_raw['text'].isna().sum()
            if miss:
                st.warning(f"⚠️ {miss:,} empty rows detected — will be skipped.")

            st.markdown("<br>", unsafe_allow_html=True)

            # Previous result banner
            if st.session_state.get('analyzed_df') is not None:
                prev = st.session_state['analyzed_df']
                h = len(prev[prev['Risk_Category'] == 'High Risk'])
                m = len(prev[prev['Risk_Category'] == 'Moderate Risk'])
                l = len(prev[prev['Risk_Category'] == 'Low Risk'])
                st.markdown(f"""
                    <div class="prev-bar">
                        🗂️ Previous result in memory: <b>{len(prev):,} posts</b> —
                        <span style="color:#f87171">{h:,} High</span> ·
                        <span style="color:#fde047">{m:,} Moderate</span> ·
                        <span style="color:#86efac">{l:,} Low</span>
                        &nbsp; Running a new analysis will replace this.
                    </div>
                """, unsafe_allow_html=True)

            col_run, col_clr = st.columns([3, 1])
            with col_run:
                run = st.button(
                    "🚀 Run AI Analysis",
                    use_container_width=True,
                    key="btn_run",
                    disabled=not model_ready
                )
            with col_clr:
                if st.button("🗑️ Clear All", use_container_width=True,
                             key="btn_clear"):
                    st.session_state['analyzed_df'] = None
                    st.session_state['raw_df']      = None
                    st.rerun()

            if run:
                _run_pipeline(df_raw, logic)

    # ════════════════════════════════════════════════════
    #  TAB 2 — CURRENT RESULTS
    # ════════════════════════════════════════════════════
    with tab_results:
        data = st.session_state.get('analyzed_df')
        if data is None:
            st.info(
                "ℹ️ No results yet. Upload a CSV and run the analysis first."
            )
        else:
            total = len(data)
            high  = len(data[data['Risk_Category'] == 'High Risk'])
            mod   = len(data[data['Risk_Category'] == 'Moderate Risk'])
            low   = len(data[data['Risk_Category'] == 'Low Risk'])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📊 Total",    f"{total:,}")
            c2.metric("🔴 High",     f"{high:,}")
            c3.metric("🟡 Moderate", f"{mod:,}")
            c4.metric("🟢 Low",      f"{low:,}")

            st.markdown(
                '<div class="sec-lbl">Analysed data preview</div>',
                unsafe_allow_html=True
            )
            cols = ['Risk_Category', 'Risk_Score', 'text']
            if 'Preprocessed' in data.columns:
                cols.append('Preprocessed')
            st.dataframe(
                data[cols].head(100),
                use_container_width=True,
                height=360
            )


# ══════════════════════════════════════════════════════════
#  PIPELINE: SIMS_05 → SIMS_06 → SIMS_07
# ══════════════════════════════════════════════════════════
def _run_pipeline(df: pd.DataFrame, logic):
    """
    SIMS_05 — Preprocess Dataset
    SIMS_06 — Run ML Classification
    SIMS_07 — Save Analysis Results
    """
    df_work = df.copy()
    df_work = df_work[
        df_work['text'].notna() &
        (df_work['text'].str.strip() != "")
    ]
    total = len(df_work)

    if total == 0:
        st.error("❌ No valid text rows found after removing empty entries.")
        return

    bar    = st.progress(0)
    status = st.empty()

    # SIMS_05 — Preprocessing steps
    for pct, msg in [
        (10, "SIMS_05 · Removing noise and special characters…"),
        (25, "SIMS_05 · Tokenising text…"),
        (40, "SIMS_05 · Removing stop words…"),
        (55, "SIMS_05 · Lemmatising tokens…"),
        (70, "SIMS_06 · Extracting TF-IDF features…"),
        (85, "SIMS_06 · Running Random Forest classifier…"),
        (95, "SIMS_07 · Saving results to session…"),
        (100,"✅ Pipeline complete!"),
    ]:
        status.markdown(
            f"<p style='color:#a78bfa;font-size:0.83rem;"
            f"font-weight:600;'>{msg}</p>",
            unsafe_allow_html=True
        )
        bar.progress(pct)
        time.sleep(0.3)

    # SIMS_05 — actual preprocessing via SIMSLogic.clean_text()
    df_work['Preprocessed'] = df_work['text'].apply(logic.clean_text)

    # SIMS_06 — classification (works with pipeline or separate models)
    try:
        probs, predictions = logic.predict_proba_batch(
            df_work['Preprocessed'].tolist()
        )
        # Risk_Score = model confidence in its predicted class (0.0–1.0)
        # Kept for backward compatibility — represents how sure the model is.
        df_work['Risk_Score']    = np.max(probs, axis=1).round(4)
        labels = {0: 'Low Risk', 1: 'Moderate Risk', 2: 'High Risk'}
        df_work['Risk_Category'] = [labels[p] for p in predictions]

        # Danger_Score = weighted danger meter (0.0 = safe, 1.0 = high danger)
        # Aligns with proposal: "Risk score range: 0.0 (safe) to 1.0 (high risk)"
        # Formula: P(High)*1.0 + P(Moderate)*0.5 + P(Low)*0.0
        if probs.shape[1] >= 3:
            danger = probs[:, 2] * 1.0 + probs[:, 1] * 0.5 + probs[:, 0] * 0.0
        else:
            # Fallback for unexpected shapes — use raw confidence
            danger = np.max(probs, axis=1)
        df_work['Danger_Score'] = np.round(danger, 4)
    except Exception as e:
        st.error(f"❌ Classification failed: {e}")
        return

    # SIMS_07 — save to session state
    st.session_state['analyzed_df'] = df_work

    # SIMS_07 — also persist to SQLite (FR 1.3 — database storage)
    try:
        user_for_save = st.session_state.get('current_user', {}) or {}
        batch_id = db.save_analysis_batch(
            df_work,
            user_id=user_for_save.get('id'),
            username=user_for_save.get('username', '—')
        )
    except Exception as e:
        st.warning(f"⚠️ Could not save to database: {e}")
        batch_id = None

    # Audit log (NFR 1.2)
    user = st.session_state.get('current_user', {})
    st.session_state.setdefault('audit_log', []).append({
        'event': 'analysis_run',
        'user':  user.get('username', '—'),
        'rows':  total,
        'time':  time.strftime('%Y-%m-%d %H:%M:%S')
    })
    # Mirror to SQLite audit log
    try:
        db.log_event(
            'analysis_run',
            user.get('username', '—'),
            f'Analyzed {total:,} posts; batch_id={batch_id}',
            success=True
        )
    except Exception:
        pass

    # Summary
    high = len(df_work[df_work['Risk_Category'] == 'High Risk'])
    mod  = len(df_work[df_work['Risk_Category'] == 'Moderate Risk'])
    low  = len(df_work[df_work['Risk_Category'] == 'Low Risk'])

    st.markdown("<br>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 High Risk",      f"{high:,}")
    m2.metric("🟡 Moderate",       f"{mod:,}")
    m3.metric("🟢 Low Risk",       f"{low:,}")
    m4.metric("📊 Total Analysed", f"{total:,}")

    st.markdown("""
        <div class="result-ok">
            ✅ Analysis saved (SIMS_07 complete).
            Navigate to <b>Analysis</b> to filter results or
            <b>Trends</b> for visualisations.
        </div>
    """, unsafe_allow_html=True)

    st.balloons()