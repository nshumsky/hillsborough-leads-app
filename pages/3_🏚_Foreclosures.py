import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_leads, upsert_outcomes_bulk
from utils.scoring import add_fc_bucket
from utils.filters import apply_all_filters
from utils.export import download_button, to_propstream_csv
from utils.branding import apply_branding

st.set_page_config(page_title='Foreclosures', page_icon='🏚', layout='wide')
apply_branding()
st.title('🏚 Foreclosures')

# ── Load + bucket ─────────────────────────────────────────────────────────────
try:
    df = query_leads('foreclosure')
except Exception as e:
    st.error(f'Could not load foreclosure data: {e}')
    st.stop()

if df.empty:
    st.info('No foreclosure data yet. Run `fetch_clerk_daily.py` to load data.')
    st.stop()

df = add_fc_bucket(df, 'days_since_filing')

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header('Filters')
df_f = apply_all_filters(df, date_col='filing_date', city_col='property_city')

st.caption(f'{len(df_f):,} of {len(df):,} leads shown')

# ── Display columns ────────────────────────────────────────────────────────────
DISPLAY = [c for c in [
    'bucket', 'days_since_filing', 'filing_date', 'case_number',
    'defendant_name', 'phone_1', 'property_street', 'property_city', 'property_zip',
    'land_use', 'is_absentee', 'lien_summary', 'survive_amount',
    'called', 'reached', 'offer_amount', 'outcome', 'notes',
] if c in df_f.columns]

RENAME = {
    'bucket': 'Bucket', 'days_since_filing': 'Days', 'filing_date': 'Filed',
    'case_number': 'Case #', 'defendant_name': 'Defendant',
    'phone_1': 'Phone', 'property_street': 'Address',
    'property_city': 'City', 'property_zip': 'ZIP',
    'land_use': 'Prop Type', 'is_absentee': 'Absentee?',
    'lien_summary': 'Liens', 'survive_amount': 'Survive $',
    'called': 'Called?', 'reached': 'Reached?', 'offer_amount': 'Offer $',
    'outcome': 'Outcome', 'notes': 'Notes',
}

display_df = df_f[DISPLAY].rename(columns=RENAME)

# ── Editable outcome columns ──────────────────────────────────────────────────
OUTCOME_OPTS  = ['', 'Active', 'Deal', 'Dead', 'On MLS', 'Cancelled', 'Low Equity']
CALLED_OPTS   = ['', 'Yes', 'No', 'Voicemail', 'DNC']
REACHED_OPTS  = ['', 'Yes', 'No', 'Voicemail']

col_config = {}
if 'Called?' in display_df.columns:
    col_config['Called?']  = st.column_config.SelectboxColumn(options=CALLED_OPTS, width='small')
if 'Reached?' in display_df.columns:
    col_config['Reached?'] = st.column_config.SelectboxColumn(options=REACHED_OPTS, width='small')
if 'Outcome' in display_df.columns:
    col_config['Outcome']  = st.column_config.SelectboxColumn(options=OUTCOME_OPTS, width='medium')
if 'Offer $' in display_df.columns:
    col_config['Offer $']  = st.column_config.NumberColumn(format='$%d', width='small')
if 'Survive $' in display_df.columns:
    col_config['Survive $'] = st.column_config.NumberColumn(format='$%d', width='small')
if 'Absentee?' in display_df.columns:
    col_config['Absentee?'] = st.column_config.CheckboxColumn(disabled=True)

edited = st.data_editor(
    display_df,
    column_config=col_config,
    use_container_width=True,
    hide_index=True,
    num_rows='fixed',
    key='fc_editor',
)

# ── Save edits ────────────────────────────────────────────────────────────────
if st.button('💾 Save Changes', type='primary'):
    outcome_cols = {'Called?': 'called', 'Reached?': 'reached',
                    'Offer $': 'offer_amount', 'Outcome': 'outcome', 'Notes': 'notes'}
    inv_rename = {v: k for k, v in RENAME.items()}
    records = []
    for i, row in edited.iterrows():
        orig = display_df.iloc[list(display_df.index).index(i)] if i in display_df.index else None
        rec = {'case_number': df_f.iloc[list(df_f.index).index(i)]['case_number']}
        for display_col, db_col in outcome_cols.items():
            if display_col in edited.columns:
                rec[db_col] = row.get(display_col) or None
        records.append(rec)
    try:
        upsert_outcomes_bulk(records)
        st.success(f'Saved {len(records)} records.')
    except Exception as e:
        st.error(f'Save failed: {e}')

st.divider()

# ── Exports ───────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    download_button(df_f[DISPLAY], 'foreclosures.csv')
with c2:
    needs_skip = df_f[df_f.get('phone_1', pd.Series(dtype=str)).isna() |
                      (df_f.get('phone_1', pd.Series(dtype=str)) == '')]
    if not needs_skip.empty:
        st.download_button(
            '📤 Propstream Upload CSV',
            to_propstream_csv(needs_skip, 'FORECLOSURE'),
            'propstream_upload_foreclosures.csv',
            'text/csv',
        )
