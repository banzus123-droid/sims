"""
page_history.py — Analysis History
  View all past analysis batches, drill into any batch's results,
  and re-load a batch as the active dataset for filtering / trends.
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import time

import database as db


def show_page():

    st.markdown("""
        <style>
    .stApp {
        background: linear-gradient(135deg,
            #2c3e50 0%, #4b6b8a 40%, #fd746c 100%) !important;
    }

        .hi-title { font-size:1.7rem;font-weight:900;color:#FFFFFF;
                    letter-spacing:-0.5px;margin-bottom:4px; }
        .hi-sub   { font-size:0.85rem;color:#FFFFFF;margin-bottom:1.5rem; }
        .sec-lbl  { font-size:0.72rem;font-weight:700;color:#E2E8F0;
                    text-transform:uppercase;letter-spacing:1.5px;
                    margin:1.2rem 0 0.6rem; }
        .batch-card {
            background:#0f172a;border:1px solid #1e293b;
            border-radius:12px;padding:1.2rem 1.4rem;margin-top:0.8rem;
        }
        .stat-card {
            background:#1e293b;border:1px solid #334155;
            border-radius:12px;padding:1rem 1.2rem;margin-bottom:0;
        }
        .stat-label { font-size:0.7rem;font-weight:700;color:#CBD5E1;
                      text-transform:uppercase;letter-spacing:1px;
                      margin-bottom:4px; }
        .stat-value { font-size:1.6rem;font-weight:900;color:#FFFFFF; }
        .empty-box {
            background:rgba(124,58,237,0.07);
            border:1px solid rgba(124,58,237,0.2);
            border-radius:12px;padding:2rem 1.5rem;
            text-align:center;color:#CBD5E1;
        }
        /* ── Centered delete confirmation modal ── */
        .modal-overlay {
            position:fixed;top:0;left:0;width:100vw;height:100vh;
            background:rgba(0,0,0,0.65);z-index:9999;
            display:flex;align-items:center;justify-content:center;
        }
        .modal-box {
            background:#0f172a;border:1px solid #334155;
            border-radius:16px;padding:2rem 2.4rem;
            max-width:460px;width:90%;text-align:center;
            box-shadow:0 24px 60px rgba(0,0,0,0.6);
        }
        .modal-icon { font-size:2.4rem;margin-bottom:0.8rem; }
        .modal-title {
            font-size:1.1rem;font-weight:800;color:#FFFFFF;
            margin-bottom:0.5rem;
        }
        .modal-body {
            font-size:0.85rem;color:#CBD5E1;margin-bottom:1.6rem;
            line-height:1.55;
        }
        .modal-batch {
            font-family:monospace;color:#FFFFFF;
            background:#1e293b;padding:2px 8px;border-radius:4px;
        }
        /* Modal button row */
        .modal-btn-row {
            display:flex;gap:12px;justify-content:center;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="hi-title">🕒 Analysis History</div>
        <div class="hi-sub">
            Every batch you've ever analysed is saved here.
            Drill into any past run, re-load it as the active dataset, or remove it.
        </div>
    """, unsafe_allow_html=True)

    # ── Load batch history from SQLite ─────────────────────
    batches = db.get_batch_history()

    if batches.empty:
        st.markdown("""
            <div class="empty-box">
                <div style="font-size:2rem;margin-bottom:0.5rem;">📭</div>
                <div style="font-size:1rem;font-weight:700;color:#FFFFFF;
                            margin-bottom:4px;">No past analyses yet</div>
                <div style="font-size:0.82rem;">
                    Go to <b>Upload</b> and run your first AI analysis —
                    every batch gets saved here automatically.
                </div>
            </div>
        """, unsafe_allow_html=True)
        return

    # ── Summary metrics ────────────────────────────────────
    total_batches = len(batches)
    total_posts   = int(batches['total_posts'].sum())
    total_high    = int(batches['high'].sum())
    avg_score     = float(batches['avg_score'].mean())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Batches",  f"{total_batches:,}")
    c2.metric("📊 Total Posts",    f"{total_posts:,}")
    c3.metric("🔴 Total High Risk", f"{total_high:,}")
    c4.metric("⚖️ Avg Score",       f"{avg_score:.3f}")

    st.divider()

    # ── Batch list ─────────────────────────────────────────
    st.markdown(
        '<div class="sec-lbl">Past Analysis Batches</div>',
        unsafe_allow_html=True
    )

    # Format datetime for display
    display_df = batches.copy()
    display_df['analyzed_at'] = pd.to_datetime(display_df['analyzed_at'])\
                                 .dt.strftime('%Y-%m-%d %H:%M:%S')
    display_df = display_df.rename(columns={
        'batch_id':    'Batch ID',
        'analyzed_at': 'Date / Time',
        'analyst':     'Analyst',
        'total_posts': 'Posts',
        'high':        'High',
        'moderate':    'Moderate',
        'low':         'Low',
        'avg_score':   'Avg Score',
        'max_score':   'Max Score',
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        height=300,
        hide_index=True
    )

    st.markdown(
        '<div class="sec-lbl">Inspect a Batch</div>',
        unsafe_allow_html=True
    )
    st.caption(
        "Select a batch below to view its posts, "
        "load it as the active dataset, or remove it from history."
    )

    # ── Batch picker ───────────────────────────────────────
    batch_options = []
    for _, r in batches.iterrows():
        ts = pd.to_datetime(r['analyzed_at']).strftime('%Y-%m-%d %H:%M')
        label = (f"{r['batch_id']}  •  {ts}  •  "
                 f"{int(r['total_posts'])} posts  •  "
                 f"{int(r['high'])} high")
        batch_options.append((label, r['batch_id']))

    label_map = {label: bid for label, bid in batch_options}
    selected_label = st.selectbox(
        "Select a batch",
        options=[label for label, _ in batch_options],
        key="hist_batch_picker"
    )
    selected_batch_id = label_map[selected_label]

    # ── Action buttons ─────────────────────────────────────
    bc1, bc2, bc3 = st.columns([2, 2, 2])

    with bc1:
        if st.button("🔄 Load as Active Dataset",
                     use_container_width=True,
                     key="hist_load_active"):
            posts = db.get_batch_posts(selected_batch_id)
            st.session_state['analyzed_df']    = posts
            st.session_state['active_batch_id'] = selected_batch_id
            user = st.session_state.get('current_user', {}) or {}
            db.log_event(
                'load_batch',
                user.get('username', '—'),
                f'Loaded batch {selected_batch_id} as active dataset',
                success=True
            )
            st.success(
                f"✅ Loaded {len(posts):,} posts from `{selected_batch_id}`. "
                "Go to **Analysis** or **Trends** to explore."
            )

    with bc2:
        # Build CSV bytes for download
        csv_posts = db.get_batch_posts(selected_batch_id)
        csv_bytes = csv_posts.to_csv(index=False).encode('utf-8')
        if st.download_button(
            "📥 Download Batch CSV",
            data=csv_bytes,
            file_name=f"SIMS_{selected_batch_id}.csv",
            mime="text/csv",
            key="hist_download",
            use_container_width=True,
            help="Export this batch's posts as CSV"
        ):
            user = st.session_state.get('current_user', {}) or {}
            db.log_event(
                'export_csv',
                user.get('username', '—'),
                f'Exported batch {selected_batch_id} from history',
                success=True
            )

    with bc3:
        if st.button("🗑️ Delete Batch",
                     use_container_width=True,
                     key="hist_delete"):
            st.session_state['hist_confirm_delete'] = selected_batch_id

    # ── Centered modal delete confirmation ─────────────────
    # Strategy: render hidden Streamlit buttons for the actual
    # click handlers, then render the visible modal HTML with
    # real <button> elements wired via JS to click the hidden ones.
    # Same pattern used in page_login.py for the signup link.
    if st.session_state.get('hist_confirm_delete') == selected_batch_id:

        # Hidden functional buttons (invisible, below the overlay)
        _hcol1, _hcol2, _hgap = st.columns([1, 1, 8])
        with _hcol1:
            _do_delete = st.button("\u200B",   key="hist_confirm_yes")
        with _hcol2:
            _do_cancel = st.button("\u200B\u200B", key="hist_confirm_no")

        if _do_delete:
            db.delete_batch(selected_batch_id)
            user = st.session_state.get('current_user', {}) or {}
            db.log_event(
                'delete_batch',
                user.get('username', '—'),
                f'Deleted batch {selected_batch_id}',
                success=True
            )
            # If the deleted batch is currently loaded in the dashboard,
            # clear it so Dashboard, Analysis and Trends show no data.
            if st.session_state.get('active_batch_id') == selected_batch_id:
                st.session_state['analyzed_df']    = None
                st.session_state['active_batch_id'] = None
            st.session_state.pop('hist_confirm_delete', None)
            st.success(f"✅ Batch `{selected_batch_id}` deleted.")
            time.sleep(1)
            st.rerun()

        if _do_cancel:
            st.session_state.pop('hist_confirm_delete', None)
            st.rerun()

        # Visible modal overlay — buttons inside call JS to click hidden ones
        st.markdown(f"""
            <div class="modal-overlay" id="sims-delete-modal">
                <div class="modal-box">
                    <div class="modal-icon">🗑️</div>
                    <div class="modal-title">Delete Batch?</div>
                    <div class="modal-body">
                        You are about to permanently delete<br>
                        <span class="modal-batch">{selected_batch_id}</span><br><br>
                        and all its posts.&nbsp;
                        <strong style="color:#f87171;">This cannot be undone.</strong>
                    </div>
                    <div class="modal-btn-row">
                        <button
                            id="sims-modal-yes"
                            style="background:linear-gradient(135deg,#dc2626,#b91c1c);
                                   color:#fff;border:none;border-radius:10px;
                                   padding:11px 28px;font-size:0.9rem;font-weight:700;
                                   cursor:pointer;transition:opacity 0.15s;"
                            onmouseover="this.style.opacity='0.85'"
                            onmouseout="this.style.opacity='1'"
                        >✓ Yes, delete</button>
                        <button
                            id="sims-modal-cancel"
                            style="background:#1e293b;color:#cbd5e1;
                                   border:1px solid #334155;border-radius:10px;
                                   padding:11px 28px;font-size:0.9rem;font-weight:700;
                                   cursor:pointer;transition:opacity 0.15s;"
                            onmouseover="this.style.opacity='0.75'"
                            onmouseout="this.style.opacity='1'"
                        >✕ Cancel</button>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # JS: wire the visible modal buttons to the hidden Streamlit buttons
        import streamlit.components.v1 as components
        components.html("""
            <script>
            (function() {
                var doc = window.parent.document;
                function wire() {
                    try {
                        // Find hidden yes/cancel buttons by their zero-width-space text
                        var allBtns = Array.from(doc.querySelectorAll('button'));
                        var hiddenYes    = allBtns.find(b =>
                            b.innerText === '\u200B' || b.textContent === '\u200B');
                        var hiddenCancel = allBtns.find(b =>
                            b.innerText === '\u200B\u200B' || b.textContent === '\u200B\u200B');

                        // Hide the Streamlit button containers
                        [hiddenYes, hiddenCancel].forEach(function(b) {
                            if (!b) return;
                            var wrap = b.closest('[data-testid="stButton"]')
                                    || b.closest('.element-container');
                            if (wrap) wrap.style.cssText +=
                                ';display:none!important;height:0!important;' +
                                'overflow:hidden!important;margin:0!important;padding:0!important;';
                        });

                        // Wire modal Yes button
                        var visYes = doc.getElementById('sims-modal-yes');
                        if (visYes && hiddenYes && !visYes._wired) {
                            visYes._wired = true;
                            visYes.addEventListener('click', function() {
                                hiddenYes.click();
                            });
                        }

                        // Wire modal Cancel button
                        var visCancel = doc.getElementById('sims-modal-cancel');
                        if (visCancel && hiddenCancel && !visCancel._wired) {
                            visCancel._wired = true;
                            visCancel.addEventListener('click', function() {
                                hiddenCancel.click();
                            });
                        }
                    } catch(e) {}
                }
                wire();
                setInterval(wire, 100);
            })();
            </script>
        """, height=0)

    # ── Batch details preview ──────────────────────────────
    st.markdown(
        '<div class="sec-lbl">Batch Preview</div>',
        unsafe_allow_html=True
    )

    posts = db.get_batch_posts(selected_batch_id)

    # Per-batch summary card
    sel = batches[batches['batch_id'] == selected_batch_id].iloc[0]
    sel_ts = pd.to_datetime(sel['analyzed_at']).strftime('%Y-%m-%d %H:%M:%S')

    st.markdown(f"""
        <div class="batch-card" style="border-left:4px solid #7c3aed;">
            <p style="margin:0 0 0.5rem;font-size:0.82rem;color:#CBD5E1;">
                Batch:&nbsp;<strong style="color:#FFFFFF;">{sel['batch_id']}</strong>
                &nbsp;|&nbsp; Date:&nbsp;<strong style="color:#FFFFFF;">{sel_ts}</strong>
                &nbsp;|&nbsp; Analyst:&nbsp;<strong style="color:#FFFFFF;">@{sel['analyst']}</strong>
            </p>
            <p style="margin:0;font-size:0.8rem;color:#FFFFFF;">
                Total: <b>{int(sel['total_posts']):,}</b> posts &nbsp;·&nbsp;
                <span style="color:#f87171;">High: {int(sel['high']):,}</span> &nbsp;·&nbsp;
                <span style="color:#fde047;">Moderate: {int(sel['moderate']):,}</span> &nbsp;·&nbsp;
                <span style="color:#86efac;">Low: {int(sel['low']):,}</span>
                &nbsp;·&nbsp; Avg: <b>{sel['avg_score']:.3f}</b>
                &nbsp;·&nbsp; Max: <b>{sel['max_score']:.3f}</b>
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Posts table for this batch
    disp_cols = ['Risk_Category', 'Risk_Score', 'text']
    if 'Preprocessed' in posts.columns:
        disp_cols.append('Preprocessed')
    st.dataframe(
        posts[disp_cols].head(200),
        use_container_width=True,
        height=340
    )

    # ── Security Audit Log (NFR 1.2) ───────────────────────
    # Placed here in History — it naturally belongs alongside
    # the record of past analyses, not in Trends visualisations.
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="sec-lbl">🔒 Security Audit Log (NFR 1.2)</div>',
        unsafe_allow_html=True
    )
    try:
        audit_df = db.get_audit_log(limit=500)
    except Exception:
        audit_df = pd.DataFrame()

    with st.expander(
        f"View audit log — {len(audit_df)} events",
        expanded=False
    ):
        if not audit_df.empty:
            st.dataframe(audit_df, use_container_width=True)
        else:
            st.info("No audit events logged yet.")