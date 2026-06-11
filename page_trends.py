"""
page_trends.py — FR 2.3
  Trend visualisations: daily/weekly risk score averages,
  category distribution, high-risk proportion bar.
"""
import streamlit as st
import pandas as pd
import altair as alt

import database as db


def show_page():

    # Auto-hydration removed — analyzed_df is cleared on login (sims.py).
    # Use History page to explicitly load a previous batch.

    st.markdown("""
        <style>
    .stApp {
        background: linear-gradient(135deg,
            #2c3e50 0%, #4b6b8a 40%, #fd746c 100%) !important;
    }

        .tr-title { font-size:1.7rem;font-weight:900;color:#FFFFFF;
                    letter-spacing:-0.5px;margin-bottom:4px; }
        .tr-sub   { font-size:0.85rem;color:#FFFFFF;margin-bottom:1.5rem; }
        .sec-lbl  { font-size:0.72rem;font-weight:700;color:#E2E8F0;
                    text-transform:uppercase;letter-spacing:1.5px;
                    margin:1.2rem 0 0.6rem; }
        .stat-card {
            background:#1e293b;border:1px solid #334155;
            border-radius:12px;padding:1rem 1.2rem;margin-bottom:0;
        }
        .stat-label { font-size:0.7rem;font-weight:700;color:#CBD5E1;
                      text-transform:uppercase;letter-spacing:1px;
                      margin-bottom:4px; }
        .stat-value { font-size:1.6rem;font-weight:900;color:#FFFFFF; }
        .prop-track {
            background:#1e293b;border-radius:99px;
            height:12px;overflow:hidden;margin-top:0.6rem;
        }
        .prop-fill {
            height:100%;border-radius:99px;
            background:linear-gradient(90deg,#ef4444,#7c3aed);
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="tr-title">📈 Trend Analytics</div>
        <div class="tr-sub">
            Risk score trends, category distributions,
            and statistical summaries (FR 2.3).
        </div>
    """, unsafe_allow_html=True)

    data = st.session_state.get('analyzed_df')

    if data is None:
        st.info(
            "ℹ️ No data to visualise. Go to **Upload** and run the "
            "analysis pipeline first."
        )
        return

    total = len(data)
    high  = len(data[data['Risk_Category'] == 'High Risk'])
    mod   = len(data[data['Risk_Category'] == 'Moderate Risk'])
    low   = len(data[data['Risk_Category'] == 'Low Risk'])
    pct   = (high / total * 100) if total else 0

    # ── Row 1: bar chart + stats ───────────────────────────
    row1_l, row1_r = st.columns([1.6, 1])

    with row1_l:
        st.markdown(
            '<div class="sec-lbl">Risk Category Volume (FR 2.3)</div>',
            unsafe_allow_html=True
        )
        counts = data['Risk_Category'].value_counts().reset_index()
        counts.columns = ['Category', 'Count']
        # Order: High Risk, Moderate Risk, Low Risk
        counts['Category'] = pd.Categorical(
            counts['Category'],
            categories=['High Risk', 'Moderate Risk', 'Low Risk'],
            ordered=True
        )
        counts = counts.sort_values('Category')
        
        # Color mapping: Red for High, Orange for Moderate, Green for Low
        color_scale = alt.Scale(
            domain=['High Risk', 'Moderate Risk', 'Low Risk'],
            range=['#ef4444', '#f97316', '#22c55e']
        )
        
        chart = alt.Chart(counts).mark_bar().encode(
            x=alt.X('Category:N', axis=alt.Axis(title=None, labelAngle=45)),
            y=alt.Y('Count:Q', axis=alt.Axis(title=None)),
            color=alt.Color('Category:N', scale=color_scale, legend=None)
        ).properties(
            width=280,
            height=280
        ).configure_axis(
            labelFontSize=11,
            titleFontSize=12
        ).configure_mark(
            opacity=0.9
        )
        
        st.altair_chart(chart, use_container_width=True)

    with row1_r:
        st.markdown(
            '<div class="sec-lbl">Statistical Summary</div>',
            unsafe_allow_html=True
        )
        for label, val in [
            ("Mean Score",   f"{data['Risk_Score'].mean():.4f}"),
            ("Median Score", f"{data['Risk_Score'].median():.4f}"),
            ("Max Score",    f"{data['Risk_Score'].max():.4f}"),
            ("Std Dev",      f"{data['Risk_Score'].std():.4f}"),
        ]:
            st.markdown(f"""
                <div class="stat-card" style="margin-bottom:8px;">
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{val}</div>
                </div>
            """, unsafe_allow_html=True)

    # ── Row 2: score volatility ────────────────────────────
    st.markdown(
        '<div class="sec-lbl">Risk Score Volatility — All Posts</div>',
        unsafe_allow_html=True
    )
    st.line_chart(
        data['Risk_Score'].reset_index(drop=True),
        color="#7c3aed",
        height=220
    )

    # ── Row 3: histogram + high-risk proportion ────────────
    row2_l, row2_r = st.columns(2)

    with row2_l:
        st.markdown(
            '<div class="sec-lbl">Score Distribution Histogram</div>',
            unsafe_allow_html=True
        )
        bins = pd.cut(
            data['Risk_Score'],
            bins=[0, .2, .4, .6, .8, 1.0],
            labels=['0–0.2','0.2–0.4','0.4–0.6','0.6–0.8','0.8–1.0']
        )
        st.bar_chart(
            bins.value_counts().sort_index(),
            color="#4f46e5",
            height=220
        )

    with row2_r:
        st.markdown(
            '<div class="sec-lbl">High-Risk Proportion</div>',
            unsafe_allow_html=True
        )
        st.metric(
            "High-Risk Posts",
            f"{high:,} / {total:,}",
            delta=f"{pct:.1f}% of dataset"
        )
        st.markdown(f"""
            <div class="prop-track">
                <div class="prop-fill"
                     style="width:{min(pct,100):.1f}%;">
                </div>
            </div>
            <p style="font-size:0.75rem;color:#FFFFFF;margin-top:4px;">
                {pct:.1f}% flagged as High Risk
            </p>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.metric("Moderate Risk", f"{mod:,}")
        st.metric("Low Risk",      f"{low:,}")