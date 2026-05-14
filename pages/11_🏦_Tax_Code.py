"""
Tax Delinquent + Code Enforcement — cross-reference distressed property signals.
"""
import streamlit as st
import pandas as pd
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_client, query_tax_delinquent, query_code_violations, query_leads
from utils.branding import apply_branding, NAVY, STEEL

st.set_page_config(page_title='Tax & Code', page_icon='🏦', layout='wide')
apply_branding()

st.markdown(f"<h2 style='color:{NAVY}; margin-bottom:0;'>🏦 Tax Delinquent & Code Violations</h2>",
            unsafe_allow_html=True)
st.caption(f'Additional distress signals that may overlap with foreclosure/probate leads')

tab1, tab2, tab3 = st.tabs(['🏛️ Code Violations', '🧾 Tax Delinquent', '🔁 Overlaps'])

# ── Tab 1: Code Enforcement ────────────────────────────────────────────────────
with tab1:
    st.subheader('City of Tampa Code Enforcement Violations')

    try:
        code = query_code_violations()
    except Exception as e:
        code = pd.DataFrame()
        st.warning(f'Could not load code violations: {e}')

    if code.empty:
        st.info(
            "No code enforcement data yet.\n\n"
            "Run **`python3 fetch_code_enforcement.py`** in the foreclosure repo to load violations "
            "from the City of Tampa Open Data portal.\n\n"
            "This runs automatically each morning via GitHub Actions."
        )
    else:
        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric('Total Records', len(code))
        open_count = int((code.get('status', pd.Series(dtype=str)).str.lower() == 'open').sum()) if 'status' in code.columns else 0
        c2.metric('Open Cases', open_count)
        c3.metric('Closed Cases', len(code) - open_count)

        # Filters
        col_f1, col_f2 = st.columns(2)
        status_opts = ['All'] + sorted(code['status'].dropna().unique().tolist()) if 'status' in code.columns else ['All']
        sel_status = col_f1.selectbox('Status', status_opts)

        vtype_opts = ['All'] + sorted(code['violation_type'].dropna().unique().tolist()) if 'violation_type' in code.columns else ['All']
        sel_vtype = col_f2.selectbox('Violation Type', vtype_opts)

        filtered = code.copy()
        if sel_status != 'All' and 'status' in filtered.columns:
            filtered = filtered[filtered['status'] == sel_status]
        if sel_vtype != 'All' and 'violation_type' in filtered.columns:
            filtered = filtered[filtered['violation_type'] == sel_vtype]

        show_cols = [c for c in [
            'opened_date', 'status', 'violation_type', 'address_raw',
            'closed_date',
        ] if c in filtered.columns]

        st.dataframe(
            filtered[show_cols].rename(columns={
                'opened_date': 'Opened', 'status': 'Status',
                'violation_type': 'Type', 'address_raw': 'Address',
                'closed_date': 'Closed',
            }).sort_values('Opened', ascending=False, na_position='last')
            if 'Opened' not in filtered.columns else filtered[show_cols],
            use_container_width=True,
            hide_index=True,
        )

        csv = filtered[show_cols].to_csv(index=False) if show_cols else ''
        if csv:
            st.download_button('⬇️ Download CSV', csv, 'code_violations.csv', 'text/csv')

# ── Tab 2: Tax Delinquent ─────────────────────────────────────────────────────
with tab2:
    st.subheader('Hillsborough County — Delinquent Tax Certificates')

    try:
        tax = query_tax_delinquent()
    except Exception as e:
        tax = pd.DataFrame()
        st.warning(f'Could not load tax certificates: {e}')

    if tax.empty:
        st.info(
            "No tax delinquent data yet.\n\n"
            "**How to load:**\n"
            "1. Download the certificate list from "
            "[hillstax.org/tax-certificates](https://www.hillstax.org/tax-certificates/)\n"
            "2. Run: `python3 fetch_tax_delinquent.py --file /path/to/downloaded.csv`\n\n"
            "The annual certificate sale is held each May. The list is published shortly after."
        )
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric('Certificate Records', len(tax))
        if 'amount_due' in tax.columns:
            total = tax['amount_due'].sum()
            c2.metric('Total Amount Due', f'${total:,.0f}')
        if 'year' in tax.columns:
            years = sorted(tax['year'].dropna().unique())
            c3.metric('Years', f"{min(years)}–{max(years)}" if len(years) > 1 else str(years[0]))

        show_cols = [c for c in [
            'year', 'folio', 'cert_number', 'amount_due', 'owner_raw',
            'address_raw', 'file_date',
        ] if c in tax.columns]

        col_cfg = {}
        if 'amount_due' in tax.columns:
            col_cfg['amount_due'] = st.column_config.NumberColumn('Amount Due', format='$%,.0f')

        st.dataframe(
            tax[show_cols].sort_values('amount_due', ascending=False) if 'amount_due' in tax.columns else tax[show_cols],
            column_config=col_cfg,
            use_container_width=True,
            hide_index=True,
        )

        csv = tax[show_cols].to_csv(index=False)
        st.download_button('⬇️ Download CSV', csv, 'tax_delinquent.csv', 'text/csv')

# ── Tab 3: Overlaps ───────────────────────────────────────────────────────────
with tab3:
    st.subheader('🔁 Addresses Appearing in Multiple Distress Signals')
    st.caption(
        'Properties that appear on a lead list (foreclosure / probate / divorce / eviction) '
        'AND have a code violation or tax delinquent certificate — the highest-distress targets.'
    )

    # Build a set of lead addresses
    lead_addresses: set[str] = set()
    _view_map = {'foreclosure': 'fact_foreclosures', 'probate': 'fact_probate',
                 'divorce': 'fact_divorces', 'eviction': 'fact_evictions'}
    for lt in ['foreclosure', 'probate', 'divorce', 'eviction']:
        try:
            view = _view_map[lt]
            res = get_client().schema('gold').table(view).select('street,lead_type').execute()
            for row in (res.data or []):
                s = str(row.get('street') or '').lower().strip()
                if s:
                    lead_addresses.add(s)
        except Exception:
            pass

    overlaps = []

    # Code violation overlaps
    if not code.empty and 'address' in code.columns:
        code_hits = code[code['address'].isin(lead_addresses)].copy()
        if not code_hits.empty:
            code_hits['signal'] = '🚨 Code Violation'
            overlaps.append(code_hits[['address', 'signal', 'violation_type', 'opened_date', 'status']].rename(
                columns={'violation_type': 'detail', 'opened_date': 'date', 'status': 'status'}
            ) if all(c in code_hits.columns for c in ['violation_type', 'opened_date', 'status']) else code_hits[['address']].assign(signal='🚨 Code Violation'))

    # Tax delinquent overlaps
    if not tax.empty and 'address' in tax.columns:
        tax_hits = tax[tax['address'].isin(lead_addresses)].copy()
        if not tax_hits.empty:
            tax_hits['signal'] = '🏛️ Tax Delinquent'
            overlaps.append(tax_hits[['address', 'signal', 'year', 'amount_due']].rename(
                columns={'year': 'detail', 'amount_due': 'status'}
            ) if all(c in tax_hits.columns for c in ['year', 'amount_due']) else tax_hits[['address']].assign(signal='🏛️ Tax Delinquent'))

    if overlaps:
        combined = pd.concat(overlaps, ignore_index=True)
        st.metric('Overlap Addresses', combined['address'].nunique())
        st.dataframe(
            combined.sort_values('address'),
            use_container_width=True,
            hide_index=True,
        )
        csv_overlap = combined.to_csv(index=False)
        st.download_button('⬇️ Download Overlaps', csv_overlap, 'distress_overlaps.csv', 'text/csv')
    else:
        if lead_addresses:
            st.info(
                "No overlaps found yet. Once code enforcement and/or tax delinquent data is loaded, "
                "matches against your leads will appear here automatically."
            )
        else:
            st.info("No lead data available to compare.")
