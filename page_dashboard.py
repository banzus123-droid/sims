"""
page_dashboard.py — SIMS_03: View Dashboard
Proposal FR 2.1 — display posts with risk category, source, text snippet
Proposal FR 2.2 — filter by risk level
Proposal FR 2.3 — interactive trend visualisations
NFR 1.2          — audit log display
"""
import streamlit as st
import pandas as pd
import altair as alt
import time

import database as db


# ══════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════
_CSS = """
<style>
/* ── Dusk gradient background ── */
.stApp {
    background: linear-gradient(135deg,
        #2c3e50 0%, #4b6b8a 40%, #fd746c 100%) !important;
}

/* ── Header ── */
.db-greeting {
    font-size: 1.1rem;
    color: #CBD5E1;
    font-weight: 500;
    margin-bottom: 2px;
}
.db-title {
    font-size: 2rem;
    font-weight: 900;
    color: #f1f5f9;
    letter-spacing: -0.8px;
    margin-bottom: 4px;
    line-height: 1.1;
}
.db-subtitle {
    font-size: 0.85rem;
    color: #FFFFFF;
    margin-bottom: 1.8rem;
}

/* ── KPI cards ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
    margin-bottom: 1.6rem;
}
.kpi-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 14px 14px 0 0;
}
.kpi-card.total::before  { background: #7c3aed; }
.kpi-card.high::before   { background: #ef4444; }
.kpi-card.mod::before    { background: #eab308; }
.kpi-card.low::before    { background: #22c55e; }
.kpi-card.avg::before    { background: #3b82f6; }

.kpi-icon {
    font-size: 1.4rem;
    margin-bottom: 6px;
    display: block;
}
.kpi-label {
    font-size: 0.68rem;
    font-weight: 700;
    color: #CBD5E1;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 1.9rem;
    font-weight: 900;
    line-height: 1;
    margin-bottom: 4px;
}
.kpi-value.c-purple { color: #a78bfa; }
.kpi-value.c-red    { color: #f87171; }
.kpi-value.c-yellow { color: #fde047; }
.kpi-value.c-green  { color: #86efac; }
.kpi-value.c-blue   { color: #93c5fd; }
.kpi-sub {
    font-size: 0.72rem;
    color: #FFFFFF;
}

/* ── Section label ── */
.sec-lbl {
    font-size: 0.7rem;
    font-weight: 700;
    color: #7c3aed;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 1.4rem 0 0.7rem;
}

/* ── Chart card ── */
.chart-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1.2rem;
}
.chart-title {
    font-size: 0.82rem;
    font-weight: 700;
    color: #E2E8F0;
    margin-bottom: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

/* ── Post row ── */
.post-row {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 7px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
}
.post-badge {
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.68rem;
    font-weight: 700;
    white-space: nowrap;
    flex-shrink: 0;
    margin-top: 1px;
}
.badge-high { background: rgba(239,68,68,0.15);  color: #f87171; }
.badge-mod  { background: rgba(234,179,8,0.15);  color: #fde047; }
.badge-low  { background: rgba(34,197,94,0.15);  color: #86efac; }
.post-score {
    font-size: 0.72rem;
    font-weight: 800;
    color: #a78bfa;
    white-space: nowrap;
    flex-shrink: 0;
    margin-top: 3px;
    min-width: 44px;
}
.post-text {
    font-size: 0.8rem;
    color: #E2E8F0;
    line-height: 1.45;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}

/* ── Progress bar ── */
.prog-track {
    background: #0f172a;
    border-radius: 99px;
    height: 8px;
    overflow: hidden;
    margin-top: 6px;
}
.prog-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, #ef4444, #7c3aed);
}

/* ── Stat mini card ── */
.stat-mini {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.stat-mini-label { font-size: 0.75rem; color: #CBD5E1; }
.stat-mini-value { font-size: 0.88rem; font-weight: 800; color: #a78bfa; }

/* ── Empty state ── */
.empty-state {
    background: #1e293b;
    border: 2px dashed #334155;
    border-radius: 16px;
    padding: 4rem 2rem;
    text-align: center;
    margin: 1rem 0;
}
.empty-icon  { font-size: 3rem; margin-bottom: 1rem; }
.empty-title {
    font-size: 1.1rem;
    font-weight: 800;
    color: #CBD5E1;
    margin-bottom: 6px;
}
.empty-sub {
    font-size: 0.85rem;
    color: #FFFFFF;
    margin-bottom: 1.5rem;
    line-height: 1.6;
}

/* ── Quick nav cards ── */
.nav-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s;
}
.nav-card:hover { border-color: #7c3aed; }
.nav-card-icon  { font-size: 1.6rem; margin-bottom: 6px; }
.nav-card-title {
    font-size: 0.82rem;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 2px;
}
.nav-card-sub { font-size: 0.72rem; color: #FFFFFF; }

/* ── Audit row ── */
.audit-row {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 6px;
    font-size: 0.78rem;
    color: #E2E8F0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
</style>
"""


def show_page():

    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Greeting header ────────────────────────────────────
    user = st.session_state.get('current_user', {})
    uname = user.get('username', 'Analyst')
    role  = user.get('role', 'Analyst')
    now   = time.strftime('%A, %d %B %Y')

    st.markdown(f"""
        <div class="db-greeting">{_greeting()}, <b style="color:#a78bfa">@{uname}</b></div>
        <div class="db-title">SIMS Dashboard</div>
        <div class="db-subtitle">
            {role} &nbsp;·&nbsp; {now} &nbsp;·&nbsp;
            Suicidal Ideation Monitoring System
        </div>
    """, unsafe_allow_html=True)

    data = st.session_state.get('analyzed_df')

    # ══════════════════════════════════════════════════════
    #  STATE A — Data available
    # ══════════════════════════════════════════════════════
    if data is not None and len(data) > 0:
        total    = len(data)
        high     = len(data[data['Risk_Category'] == 'High Risk'])
        mod      = len(data[data['Risk_Category'] == 'Moderate Risk'])
        low      = len(data[data['Risk_Category'] == 'Low Risk'])
        avg      = data['Risk_Score'].mean()
        high_pct = (high / total * 100) if total else 0

        # ── KPI cards ─────────────────────────────────────
        st.markdown(f"""
            <div class="kpi-grid">
                <div class="kpi-card total">
                    <span class="kpi-icon">📊</span>
                    <div class="kpi-label">Total Posts</div>
                    <div class="kpi-value c-purple">{total:,}</div>
                    <div class="kpi-sub">Dataset analysed</div>
                </div>
                <div class="kpi-card high">
                    <span class="kpi-icon">🔴</span>
                    <div class="kpi-label">High Risk</div>
                    <div class="kpi-value c-red">{high:,}</div>
                    <div class="kpi-sub">{high_pct:.1f}% of total</div>
                </div>
                <div class="kpi-card mod">
                    <span class="kpi-icon">🟡</span>
                    <div class="kpi-label">Moderate Risk</div>
                    <div class="kpi-value c-yellow">{mod:,}</div>
                    <div class="kpi-sub">{(mod/total*100):.1f}% of total</div>
                </div>
                <div class="kpi-card low">
                    <span class="kpi-icon">🟢</span>
                    <div class="kpi-label">Low Risk</div>
                    <div class="kpi-value c-green">{low:,}</div>
                    <div class="kpi-sub">{(low/total*100):.1f}% of total</div>
                </div>
                <div class="kpi-card avg">
                    <span class="kpi-icon">⚖️</span>
                    <div class="kpi-label">Avg Risk Score</div>
                    <div class="kpi-value c-blue">{avg:.3f}</div>
                    <div class="kpi-sub">Scale 0.0 – 1.0</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # ── Row 1: Charts ──────────────────────────────────
        col_chart, col_stats = st.columns([2.2, 1])

        with col_chart:
            st.markdown(
                '<div class="chart-card">'
                '<div class="chart-title">Risk Category Distribution</div>',
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
                height=230
            ).configure_axis(
                labelFontSize=11,
                titleFontSize=12
            ).configure_mark(
                opacity=0.9
            )
            
            st.altair_chart(chart, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_stats:
            st.markdown(
                '<div class="chart-card">',
                unsafe_allow_html=True
            )
            st.markdown(
                '<div class="chart-title">Statistical Summary</div>',
                unsafe_allow_html=True
            )
            for label, val in [
                ("Mean Score",   f"{data['Risk_Score'].mean():.4f}"),
                ("Median Score", f"{data['Risk_Score'].median():.4f}"),
                ("Max Score",    f"{data['Risk_Score'].max():.4f}"),
                ("Min Score",    f"{data['Risk_Score'].min():.4f}"),
                ("Std Dev",      f"{data['Risk_Score'].std():.4f}"),
            ]:
                st.markdown(f"""
                    <div class="stat-mini">
                        <span class="stat-mini-label">{label}</span>
                        <span class="stat-mini-value">{val}</span>
                    </div>
                """, unsafe_allow_html=True)

            # High-risk proportion bar
            st.markdown(f"""
                <div style="margin-top:10px;">
                    <div style="display:flex;justify-content:space-between;
                                font-size:0.7rem;color:#CBD5E1;margin-bottom:4px;">
                        <span>High-Risk Proportion</span>
                        <span style="color:#f87171;font-weight:700;">
                            {high_pct:.1f}%
                        </span>
                    </div>
                    <div class="prog-track">
                        <div class="prog-fill"
                             style="width:{min(high_pct,100):.1f}%;">
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Row 2: Score trend line ────────────────────────
        st.markdown(
            '<div class="chart-card">'
            '<div class="chart-title">Risk Score Trend — All Posts</div>',
            unsafe_allow_html=True
        )
        st.line_chart(
            data['Risk_Score'].reset_index(drop=True),
            color="#a78bfa",
            height=200
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Row 3: Top high-risk posts + quick stats ───────
        col_posts, col_quick = st.columns([1.6, 1])

        with col_posts:
            st.markdown(
                '<div class="sec-lbl">🚨 Top 10 Highest Risk Posts</div>',
                unsafe_allow_html=True
            )
            top = data.nlargest(10, 'Risk_Score').reset_index(drop=True)
            for _, row in top.iterrows():
                cat   = row['Risk_Category']
                score = row['Risk_Score']
                text  = str(row['text'])[:120] + ('…' if len(str(row['text'])) > 120 else '')
                badge_cls = {
                    'High Risk':     'badge-high',
                    'Moderate Risk': 'badge-mod',
                    'Low Risk':      'badge-low'
                }.get(cat, 'badge-high')
                st.markdown(f"""
                    <div class="post-row">
                        <span class="post-badge {badge_cls}">{cat}</span>
                        <span class="post-score">{score:.4f}</span>
                        <span class="post-text">{text}</span>
                    </div>
                """, unsafe_allow_html=True)

        with col_quick:
            st.markdown(
                '<div class="sec-lbl">📌 Quick Navigation</div>',
                unsafe_allow_html=True
            )
            # Quick nav cards with buttons
            for page, icon, desc in [
                ("Upload",   "📤", "Upload & analyse CSV"),
                ("Analysis", "🔍", "Filter & export posts"),
                ("Trends",   "📈", "Trend visualisations"),
            ]:
                st.markdown(f"""
                    <div class="nav-card">
                        <div class="nav-card-icon">{icon}</div>
                        <div class="nav-card-title">{page}</div>
                        <div class="nav-card-sub">{desc}</div>
                    </div>
                """, unsafe_allow_html=True)
                if st.button(
                    f"Go to {page} →",
                    key=f"dash_nav_{page}",
                    use_container_width=True
                ):
                    st.session_state['active_page'] = page
                    st.rerun()

    # ══════════════════════════════════════════════════════
    #  STATE B — No data yet
    # ══════════════════════════════════════════════════════
    else:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">📂</div>
                <div class="empty-title">No dataset analysed yet</div>
                <div class="empty-sub">
                    Upload a CSV containing social media posts and run the
                    AI analysis pipeline to see your risk dashboard.
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Still show nav cards so user knows where to go
        c1, c2, c3 = st.columns(3)
        for col, (page, icon, title, desc) in zip(
            [c1, c2, c3],
            [
                ("Upload",   "📤", "Upload Dataset",
                 "Upload a CSV and run the AI pipeline"),
                ("Analysis", "🔍", "Risk Analysis",
                 "Filter and explore classified posts"),
                ("Trends",   "📈", "Trend Analytics",
                 "View risk score trends over time"),
            ]
        ):
            with col:
                st.markdown(f"""
                    <div class="nav-card" style="margin-bottom:8px;">
                        <div class="nav-card-icon">{icon}</div>
                        <div class="nav-card-title">{title}</div>
                        <div class="nav-card-sub">{desc}</div>
                    </div>
                """, unsafe_allow_html=True)
                if st.button(
                    f"Go to {page} →",
                    key=f"empty_nav_{page}",
                    use_container_width=True
                ):
                    st.session_state['active_page'] = page
                    st.rerun()

    # ══════════════════════════════════════════════════════
    #  AUDIT LOG  (NFR 1.2 — always visible at bottom)
    # ══════════════════════════════════════════════════════
    log = st.session_state.get('audit_log', [])
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander(
        f"🔒 Security Audit Log  —  {len(log)} event(s)  (NFR 1.2)",
        expanded=False
    ):
        if log:
            for entry in reversed(log[-20:]):
                event = entry.get('event', '—').replace('_', ' ').title()
                user_ = entry.get('user', '—')
                ts    = entry.get('time', '—')
                rows  = (f" · {entry['rows']:,} rows"
                         if 'rows' in entry else "")
                dot_color = {
                    'Login':        '#22c55e',
                    'Logout':       '#ef4444',
                    'Analysis Run': '#a78bfa',
                }.get(event, '#64748b')
                st.markdown(f"""
                    <div class="audit-row">
                        <span>
                            <span style="display:inline-block;width:7px;
                                         height:7px;border-radius:50%;
                                         background:{dot_color};
                                         margin-right:8px;
                                         vertical-align:middle;">
                            </span>
                            <b style="color:#FFFFFF;">{event}</b>
                            <span style="color:#CBD5E1;">{rows}</span>
                        </span>
                        <span style="color:#FFFFFF;">
                            @{user_} &nbsp;·&nbsp; {ts}
                        </span>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No events logged yet.")


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════
def _greeting() -> str:
    h = int(time.strftime('%H'))
    if h < 12:  return "Good morning"
    if h < 17:  return "Good afternoon"
    return "Good evening"