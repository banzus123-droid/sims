"""
page_analysis.py — SIMS_08 + SIMS_09
  SIMS_08  Filter Dashboard Results
  SIMS_09  Export CSV
  Word clouds per risk category (High / Moderate / Low)
"""
import streamlit as st
import pandas as pd
import numpy as np
import io

import database as db

# WordCloud — graceful import so the page still works if not installed
try:
    from wordcloud import WordCloud, STOPWORDS
    _WC_AVAILABLE = True
except ImportError:
    _WC_AVAILABLE = False


def _make_wordcloud(text: str, colormap: str) -> bytes | None:
    """
    Generate a word cloud PNG from a string of space-separated tokens.
    Returns PNG bytes or None on failure.

    Uses WordCloud library (Mueller, 2012 — github.com/amueller/word_cloud).
    Stopwords sourced from NLTK English stopwords corpus (Bird et al., 2009).
    """
    if not _WC_AVAILABLE or not text.strip():
        return None
    try:
        wc = WordCloud(
            width=600,
            height=300,
            background_color='#0f172a',
            colormap=colormap,
            stopwords=STOPWORDS,
            max_words=80,
            min_font_size=9,
            prefer_horizontal=0.85,
            collocations=False,   # avoid repeated bigrams
        ).generate(text)
        buf = io.BytesIO()
        wc.to_image().save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        return None


def show_page():

    # Auto-hydration removed — analyzed_df is cleared on login (sims.py).
    # Use History page to explicitly load a previous batch.

    st.markdown("""
        <style>
    .stApp {
        background: linear-gradient(135deg,
            #2c3e50 0%, #4b6b8a 40%, #fd746c 100%) !important;
    }

        .an-title { font-size:1.7rem;font-weight:900;color:#FFFFFF;
                    letter-spacing:-0.5px;margin-bottom:4px; }
        .an-sub   { font-size:0.85rem;color:#FFFFFF;margin-bottom:1.5rem; }
        .sec-lbl  { font-size:0.72rem;font-weight:700;color:#E2E8F0;
                    text-transform:uppercase;letter-spacing:1.5px;
                    margin:1.2rem 0 0.6rem; }
        .detail-card {
            background:#0f172a;border:1px solid #1e293b;
            border-radius:12px;padding:1.2rem 1.4rem;margin-top:0.8rem;
        }
        .wc-card {
            background:#0f172a;border:1px solid #1e293b;
            border-radius:12px;padding:1rem 1.2rem;
        }
        .wc-title {
            font-size:0.78rem;font-weight:700;letter-spacing:1.2px;
            text-transform:uppercase;margin-bottom:0.6rem;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="an-title">🔍 Risk Analysis</div>
        <div class="an-sub">
            Filter, search, export, and explore word patterns per risk category.
        </div>
    """, unsafe_allow_html=True)

    data = st.session_state.get('analyzed_df')

    if data is None:
        st.info(
            "ℹ️ No data available. Go to **Upload** and run the "
            "AI analysis pipeline first."
        )
        return

    total = len(data)

    # ── Summary metrics ────────────────────────────────────
    high = len(data[data['Risk_Category'] == 'High Risk'])
    mod  = len(data[data['Risk_Category'] == 'Moderate Risk'])
    low  = len(data[data['Risk_Category'] == 'Low Risk'])
    avg  = data['Risk_Score'].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📊 Total Posts",   f"{total:,}")
    c2.metric("🔴 High Risk",     f"{high:,}")
    c3.metric("🟡 Moderate Risk", f"{mod:,}")
    c4.metric("🟢 Low Risk",      f"{low:,}")
    c5.metric("⚖️ Avg Score",     f"{avg:.3f}")

    st.divider()

    # ══════════════════════════════════════════════════════
    #  WORD CLOUDS PER RISK CATEGORY
    #  Source: WordCloud library (Mueller, A., 2012).
    #  Word frequencies derived from preprocessed post tokens
    #  after NLTK stopword removal (Bird et al., 2009).
    #  Visualises the most discriminative terms per risk level.
    # ══════════════════════════════════════════════════════
    st.markdown(
        '<div class="sec-lbl">🌐 Word Clouds — Most Frequent Terms per Risk Category</div>',
        unsafe_allow_html=True
    )

    # Decide which text column to use — prefer 'Preprocessed' (already
    # tokenised and lemmatised by SIMS_05), fall back to raw 'text'
    text_col = 'Preprocessed' if 'Preprocessed' in data.columns else 'text'

    if not _WC_AVAILABLE:
        st.warning(
            "⚠️ `wordcloud` package not installed. "
            "Run `pip install wordcloud` then restart the app."
        )
    else:
        wc_configs = [
            ('High Risk',     '#f87171', 'Reds',    '🔴'),
            ('Moderate Risk', '#fde047', 'YlOrBr',  '🟡'),
            ('Low Risk',      '#86efac', 'Greens',  '🟢'),
        ]

        wc_cols = st.columns(3)

        for col_ui, (category, colour, cmap, icon) in zip(wc_cols, wc_configs):
            subset = data[data['Risk_Category'] == category][text_col].dropna()

            with col_ui:
                st.markdown(
                    f'<div class="wc-card">'
                    f'<div class="wc-title" style="color:{colour};">'
                    f'{icon} {category} '
                    f'<span style="color:#475569;font-weight:400;">({len(subset):,} posts)</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                if subset.empty:
                    st.caption("No posts in this category.")
                    st.markdown('</div>', unsafe_allow_html=True)
                    continue

                combined_text = " ".join(subset.astype(str).tolist())
                png = _make_wordcloud(combined_text, cmap)

                if png:
                    st.image(png, use_container_width=True)
                else:
                    st.caption("Could not generate word cloud.")

                st.markdown('</div>', unsafe_allow_html=True)

        st.caption(
            "Word clouds show the most frequent terms after NLP preprocessing "
            "(stopword removal, lemmatisation). Larger words appear more often "
            "in posts of that risk category. "
            "Source: Mueller (2012); NLTK stopwords corpus — Bird et al. (2009)."
        )

    st.divider()

    # ── SIMS_08 — Filters ──────────────────────────────────
    st.markdown(
        '<div class="sec-lbl">SIMS_08 — Filter Results</div>',
        unsafe_allow_html=True
    )

    f1, f2 = st.columns([2, 2])
    with f1:
        risk_filter = st.selectbox(
            "Risk Level",
            ["All", "High Risk", "Moderate Risk", "Low Risk"],
            key="an_risk"
        )
    with f2:
        keyword = st.text_input(
            "Keyword Search",
            placeholder="Search post text…",
            key="an_kw"
        )

    # Apply filters
    filtered = data.copy()
    if risk_filter != "All":
        filtered = filtered[filtered['Risk_Category'] == risk_filter]
    if keyword.strip():
        filtered = filtered[
            filtered['text'].str.contains(
                keyword.strip(), case=False, na=False
            )
        ]

    st.markdown(
        f"<p style='color:#FFFFFF;font-size:0.8rem;'>"
        f"Showing <b style='color:#a78bfa'>{len(filtered):,}</b> "
        f"of {total:,} posts</p>",
        unsafe_allow_html=True
    )

    # ── SIMS_09 — Export CSV ───────────────────────────────
    exp1, exp2 = st.columns([5, 1])
    with exp2:
        if st.download_button(
            "📥 Export CSV",
            data=filtered.to_csv(index=False).encode('utf-8'),
            file_name=(
                f"SIMS_Export_{risk_filter.replace(' ','_')}.csv"
            ),
            mime="text/csv",
            key="an_export",
            help="SIMS_09 — Export filtered results as CSV"
        ):
            try:
                user = st.session_state.get('current_user', {}) or {}
                db.log_event(
                    'export_csv',
                    user.get('username', '—'),
                    f'Exported {len(filtered)} rows; filter={risk_filter}',
                    success=True
                )
            except Exception:
                pass

    # ── Post list (FR 2.1 — paginated view) ───────────────
    disp_cols = ['Risk_Category', 'Risk_Score']
    if 'Danger_Score' in filtered.columns:
        disp_cols.append('Danger_Score')
    disp_cols.append('text')
    if 'Preprocessed' in filtered.columns:
        disp_cols.append('Preprocessed')

    st.dataframe(
        filtered[disp_cols].head(200),
        use_container_width=True,
        height=340
    )

    # ── Details-on-Demand (FR scope) ──────────────────────
    st.markdown(
        '<div class="sec-lbl">Details on Demand</div>',
        unsafe_allow_html=True
    )
    st.caption(
        "Select any post index to see its full text, "
        "risk score, and preprocessed form."
    )

    if filtered.empty:
        st.info("No posts match the current filters.")
        return

    idx = st.selectbox(
        "Select post index",
        options=filtered.index.tolist()[:100],
        key="an_detail_idx"
    )

    case = filtered.loc[idx]
    cat  = case['Risk_Category']
    sc   = case['Risk_Score']
    dgr  = case.get('Danger_Score', None)

    colour_map = {
        'High Risk':     '#f87171',
        'Moderate Risk': '#fde047',
        'Low Risk':      '#86efac'
    }
    clr = colour_map.get(cat, '#a78bfa')

    prep = case.get('Preprocessed', '—')

    danger_html = ""
    if dgr is not None and pd.notna(dgr):
        danger_html = (
            f"&nbsp;|&nbsp; Danger Score:&nbsp;"
            f"<strong style=\"color:{clr};\">{float(dgr):.4f}</strong>"
        )

    st.markdown(f"""
        <div class="detail-card"
             style="border-left:4px solid {clr};">
            <p style="margin:0 0 0.6rem;font-size:0.82rem;color:#CBD5E1;">
                Category:&nbsp;
                <strong style="color:{clr};font-size:0.95rem;">{cat}</strong>
                &nbsp;|&nbsp; Confidence:&nbsp;
                <strong style="color:{clr};">{sc:.4f}</strong>
                {danger_html}
                &nbsp;|&nbsp; Index:&nbsp;{idx}
            </p>
            <p style="background:#1e293b;padding:1rem;border-radius:8px;
                      border:1px solid #334155;color:#FFFFFF;
                      font-style:italic;line-height:1.65;margin-bottom:0.6rem;">
                "{case['text']}"
            </p>
            <p style="font-size:0.75rem;color:#FFFFFF;margin:0;">
                <b>Preprocessed:</b> {prep}
            </p>
        </div>
    """, unsafe_allow_html=True)