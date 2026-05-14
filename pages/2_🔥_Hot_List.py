import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_leads
from utils.scoring import add_fc_bucket, add_pb_bucket, BUCKET_COLORS
from utils.export import download_button
from utils.branding import apply_branding

st.set_page_config(page_title='Hot List', page_icon='🔥', layout='wide')
apply_branding()
st.title('🔥 Hot List — Priority Leads')
st.caption('Foreclosures ≤ 60 days + Probate 0–90 days filed. Call these first.')

# ── Foreclosures ≤ 60 days ───────────────────────────────────────────────────
try:
    fc = query_leads('foreclosure')
    if not fc.empty:
        fc = add_fc_bucket(fc, 'days_since_filing')
        fc_hot = fc[fc['days_since_filing'] <= 60].copy()
        fc_hot = fc_hot[~fc_hot['outcome'].isin(
            {'Dead', 'Cancelled', 'Low Equity', 'Not Interested'}
        )]
    else:
        fc_hot = pd.DataFrame()
except Exception as e:
    fc_hot = pd.DataFrame()
    st.warning(f'Foreclosures: {e}')

try:
    pb = query_leads('probate')
    if not pb.empty:
        pb = add_pb_bucket(pb, 'days_since_filing')
        pb_hot = pb[pb['days_since_filing'] <= 90].copy()
        pb_hot = pb_hot[~pb_hot['outcome'].isin(
            {'Dead', 'Not Interested', 'No Property', 'Low Equity'}
        )]
    else:
        pb_hot = pd.DataFrame()
except Exception as e:
    pb_hot = pd.DataFrame()
    st.warning(f'Probate: {e}')

# ── Stats row ────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric('🏚 FC Leads',      len(fc_hot))
c2.metric('📋 Probate Leads', len(pb_hot))
c3.metric('📞 FC w/ Phone',
          int(fc_hot['phone_1'].notna().sum()) if not fc_hot.empty else 0)
c4.metric('📞 Probate w/ Phone',
          int(pb_hot['phone_1'].notna().sum()) if not pb_hot.empty else 0)

st.divider()

# ── Foreclosure hot leads table ───────────────────────────────────────────────
st.subheader(f'🏚 Foreclosures ≤ 60 Days  ({len(fc_hot)} leads)')
if not fc_hot.empty:
    show_cols_fc = [c for c in [
        'bucket', 'days_since_filing', 'case_number', 'defendant_name',
        'phone_1', 'property_street', 'property_city', 'property_zip',
        'lien_summary', 'called', 'reached', 'outcome'
    ] if c in fc_hot.columns]
    st.dataframe(
        fc_hot[show_cols_fc].rename(columns={
            'bucket': 'Bucket', 'days_since_filing': 'Days',
            'case_number': 'Case #', 'defendant_name': 'Owner',
            'phone_1': 'Phone', 'property_street': 'Address',
            'property_city': 'City', 'property_zip': 'ZIP',
            'lien_summary': 'Liens', 'called': 'Called?',
            'reached': 'Reached?', 'outcome': 'Outcome',
        }),
        use_container_width=True,
        hide_index=True,
    )
    download_button(fc_hot[show_cols_fc], 'hot_foreclosures.csv', '⬇ Download FC Hot List')
else:
    st.info('No active foreclosure leads ≤ 60 days.')

st.divider()

# ── Probate hot leads table ───────────────────────────────────────────────────
st.subheader(f'📋 Probate 0–90 Days  ({len(pb_hot)} leads)')
if not pb_hot.empty:
    show_cols_pb = [c for c in [
        'bucket', 'days_since_filing', 'case_number', 'petitioner_name',
        'phone_1', 'decedent_street', 'decedent_city', 'decedent_zip',
        'oos', 'lien_summary', 'called', 'reached', 'outcome'
    ] if c in pb_hot.columns]
    st.dataframe(
        pb_hot[show_cols_pb].rename(columns={
            'bucket': 'Bucket', 'days_since_filing': 'Days',
            'case_number': 'Case #', 'petitioner_name': 'Petitioner',
            'phone_1': 'Phone', 'decedent_street': 'Prop. Address',
            'decedent_city': 'City', 'decedent_zip': 'ZIP',
            'oos': 'OOS?', 'lien_summary': 'Liens',
            'called': 'Called?', 'reached': 'Reached?', 'outcome': 'Outcome',
        }),
        use_container_width=True,
        hide_index=True,
    )
    download_button(pb_hot[show_cols_pb], 'hot_probate.csv', '⬇ Download Probate Hot List')
else:
    st.info('No active probate leads 0–90 days.')
