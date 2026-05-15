import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_leads, upsert_outcomes_bulk
from utils.scoring import add_pb_bucket, land_use_label
from utils.filters import apply_all_filters
from utils.export import download_button
from utils.branding import apply_branding

st.set_page_config(page_title='Divorce', page_icon='💔', layout='wide')
apply_branding()
st.title('💔 Divorce — Dissolution of Marriage')
st.caption('Couples going through divorce often need to sell quickly to split assets.')

try:
    df = query_leads('divorce')
except Exception as e:
    st.error(f'Could not load divorce data: {e}')
    st.stop()

if df.empty:
    st.info('No divorce data yet. Data loads automatically each day from the Clerk daily filings.')
    st.stop()

df = add_pb_bucket(df, 'days_since_filing')
if 'land_use' in df.columns:
    df['land_use'] = df['land_use'].fillna('').apply(land_use_label)

st.sidebar.header('Filters')
df_f = apply_all_filters(df, date_col='filing_date', city_col='address_city')
st.caption(f'{len(df_f):,} of {len(df):,} leads shown')

DISPLAY = [c for c in [
    'bucket', 'days_since_filing', 'filing_date', 'case_number',
    'party_1_name', 'party_2_name', 'address_street', 'address_city', 'address_zip',
    'land_use', 'is_absentee',
    'beds', 'baths', 'heated_sqft', 'acreage',
    'just_value', 'assessed_value', 'subdivision', 'site_city', 'site_zip',
    'phone_1',
    'called', 'reached', 'offer_amount', 'outcome', 'notes',
] if c in df_f.columns]

RENAME = {
    'bucket': 'Bucket', 'days_since_filing': 'Days', 'filing_date': 'Filed',
    'case_number': 'Case #', 'party_1_name': 'Petitioner', 'party_2_name': 'Respondent',
    'address_street': 'Address', 'address_city': 'City', 'address_zip': 'ZIP',
    'land_use': 'Prop Type', 'is_absentee': 'Absentee?',
    'beds': 'Beds', 'baths': 'Baths', 'heated_sqft': 'Sq Ft', 'acreage': 'Acres',
    'just_value': 'Mkt Value', 'assessed_value': 'Assessed',
    'subdivision': 'Subdivision', 'site_city': 'HCPA City', 'site_zip': 'HCPA ZIP',
    'phone_1': 'Phone',
    'called': 'Called?', 'reached': 'Reached?',
    'offer_amount': 'Offer $', 'outcome': 'Outcome', 'notes': 'Notes',
}

display_df = df_f[DISPLAY].rename(columns=RENAME)

OUTCOME_OPTS = ['', 'Active', 'Deal', 'Dead', 'Not Interested', 'No Property']
col_config = {}
for col, opts in [('Called?', ['', 'Yes', 'No', 'Voicemail', 'DNC']),
                   ('Reached?', ['', 'Yes', 'No', 'Voicemail']),
                   ('Outcome', OUTCOME_OPTS)]:
    if col in display_df.columns:
        col_config[col] = st.column_config.SelectboxColumn(options=opts)
if 'Absentee?' in display_df.columns:
    col_config['Absentee?'] = st.column_config.CheckboxColumn(disabled=True)
for col in ['Mkt Value', 'Assessed']:
    if col in display_df.columns:
        col_config[col] = st.column_config.NumberColumn(format='$%,.0f', width='small')
for col in ['Sq Ft', 'Beds', 'Baths']:
    if col in display_df.columns:
        col_config[col] = st.column_config.NumberColumn(format='%.0f', width='small')
if 'Acres' in display_df.columns:
    col_config['Acres'] = st.column_config.NumberColumn(format='%.2f', width='small')

edited = st.data_editor(display_df, column_config=col_config,
                        use_container_width=True, hide_index=True,
                        num_rows='fixed', key='div_editor')

if st.button('💾 Save Changes', type='primary'):
    outcome_cols = {'Called?': 'called', 'Reached?': 'reached',
                    'Offer $': 'offer_amount', 'Outcome': 'outcome', 'Notes': 'notes'}
    records = []
    for i, row in edited.iterrows():
        rec = {'case_number': df_f.iloc[list(df_f.index).index(i)]['case_number']}
        for dc, db in outcome_cols.items():
            if dc in edited.columns:
                rec[db] = row.get(dc) or None
        records.append(rec)
    try:
        upsert_outcomes_bulk(records)
        st.success(f'Saved {len(records)} records.')
    except Exception as e:
        st.error(f'Save failed: {e}')

st.divider()
download_button(df_f[DISPLAY], 'divorce_leads.csv')
