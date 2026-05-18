"""
Code Enforcement Violations — City of Tampa distressed property signals.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_client, query_code_violations
from utils.branding import apply_branding, NAVY

st.set_page_config(page_title='Code Enforcement', page_icon='🚨', layout='wide')
apply_branding()
st.title('🚨 Code Enforcement')
st.caption('City of Tampa code enforcement violations — active cases signal distressed or abandoned properties.')

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
    st.stop()

# ── Metrics ────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric('Total Records', len(code))
open_count = int((code.get('status', pd.Series(dtype=str)).str.lower() == 'open').sum()) if 'status' in code.columns else 0
c2.metric('Open Cases', open_count)
c3.metric('Closed Cases', len(code) - open_count)

st.divider()

# ── Filters ────────────────────────────────────────────────────────────────────
st.sidebar.header('Filters')

if 'status' in code.columns:
    status_opts = sorted(code['status'].dropna().unique().tolist())
    sel_status = st.sidebar.multiselect('Status', status_opts, default=[s for s in status_opts if 'open' in s.lower()])
    if sel_status:
        code = code[code['status'].isin(sel_status)]

if 'violation_type' in code.columns:
    vtype_opts = sorted(code['violation_type'].dropna().unique().tolist())
    sel_vtype = st.sidebar.multiselect('Violation Type', vtype_opts)
    if sel_vtype:
        code = code[code['violation_type'].isin(sel_vtype)]

st.caption(f'{len(code):,} violations shown')

# ── Table ──────────────────────────────────────────────────────────────────────
show_cols = [c for c in [
    'opened_date', 'status', 'violation_type', 'address_raw', 'closed_date',
] if c in code.columns]

display_code = code[show_cols].rename(columns={
    'opened_date': 'Opened', 'status': 'Status',
    'violation_type': 'Type', 'address_raw': 'Address',
    'closed_date': 'Closed',
})
if 'Opened' in display_code.columns:
    display_code = display_code.sort_values('Opened', ascending=False, na_position='last')

st.dataframe(display_code, use_container_width=True, hide_index=True)

csv = code[show_cols].to_csv(index=False) if show_cols else ''
if csv:
    st.download_button('⬇️ Download CSV', csv, 'code_violations.csv', 'text/csv')

st.divider()

# ── Overlaps with active leads ─────────────────────────────────────────────────
st.subheader('🔁 Overlaps with Active Leads')
st.caption('Properties with a code violation that also appear in foreclosure, probate, divorce, or eviction leads.')

lead_addresses: set[str] = set()
_addr_col_map = {
    'foreclosure': ('fact_foreclosures', 'property_street'),
    'probate':     ('fact_probate',      'decedent_street'),
    'divorce':     ('fact_divorces',     'address_street'),
    'eviction':    ('fact_evictions',    'property_street'),
}
for lt, (view, addr_col) in _addr_col_map.items():
    try:
        res = get_client().schema('gold').table(view).select(addr_col).execute()
        for row in (res.data or []):
            s = str(row.get(addr_col) or '').lower().strip()
            if s:
                lead_addresses.add(s)
    except Exception:
        pass

if lead_addresses and not code.empty:
    addr_col = 'address' if 'address' in code.columns else 'address_raw'
    if addr_col in code.columns:
        hits = code[code[addr_col].str.lower().str.strip().isin(lead_addresses)].copy()
        if not hits.empty:
            st.metric('Overlap Properties', hits[addr_col].nunique())
            overlap_cols = [c for c in [addr_col, 'status', 'violation_type', 'opened_date'] if c in hits.columns]
            st.dataframe(hits[overlap_cols].sort_values(addr_col), use_container_width=True, hide_index=True)
            st.download_button('⬇️ Download Overlaps', hits[overlap_cols].to_csv(index=False),
                               'code_overlaps.csv', 'text/csv')
        else:
            st.info('No overlaps found yet between code violations and current leads.')
    else:
        st.info('Address column not available for overlap matching.')
else:
    st.info('Load lead and code enforcement data to see overlaps.')
