import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_leads, upsert_outcomes_bulk
from utils.scoring import add_pb_bucket
from utils.filters import apply_all_filters
from utils.export import download_button
from utils.branding import apply_branding

st.set_page_config(page_title='Evictions', page_icon='🏠', layout='wide')
apply_branding()
st.title('🏠 Evictions')
st.caption('Landlords filing evictions — potential motivated sellers if the property is problematic.')

try:
    df = query_leads('eviction')
except Exception as e:
    st.error(f'Could not load eviction data: {e}')
    st.stop()

if df.empty:
    st.info('No eviction data yet.')
    st.stop()

df = add_pb_bucket(df, 'days_since_filing')

st.sidebar.header('Filters')
df_f = apply_all_filters(df, date_col='filing_date', city_col='property_city')
st.caption(f'{len(df_f):,} of {len(df):,} leads shown')

DISPLAY = [c for c in [
    'bucket', 'days_since_filing', 'filing_date', 'case_number',
    'landlord_name', 'tenant_name',
    'property_street', 'property_city', 'property_zip',
    'land_use', 'phone_1',
    'called', 'reached', 'outcome', 'notes',
] if c in df_f.columns]

RENAME = {
    'bucket': 'Bucket', 'days_since_filing': 'Days', 'filing_date': 'Filed',
    'case_number': 'Case #', 'landlord_name': 'Landlord', 'tenant_name': 'Tenant',
    'property_street': 'Address', 'property_city': 'City', 'property_zip': 'ZIP',
    'land_use': 'Prop Type', 'phone_1': 'Phone',
    'called': 'Called?', 'reached': 'Reached?',
    'outcome': 'Outcome', 'notes': 'Notes',
}

display_df = df_f[DISPLAY].rename(columns=RENAME)

col_config = {}
for col, opts in [('Called?', ['', 'Yes', 'No', 'Voicemail', 'DNC']),
                   ('Reached?', ['', 'Yes', 'No', 'Voicemail']),
                   ('Outcome', ['', 'Active', 'Deal', 'Dead', 'Not Interested'])]:
    if col in display_df.columns:
        col_config[col] = st.column_config.SelectboxColumn(options=opts)

edited = st.data_editor(display_df, column_config=col_config,
                        use_container_width=True, hide_index=True,
                        num_rows='fixed', key='ev_editor')

if st.button('💾 Save Changes', type='primary'):
    records = []
    for i, row in edited.iterrows():
        rec = {'case_number': df_f.iloc[list(df_f.index).index(i)]['case_number']}
        for dc, db in [('Called?', 'called'), ('Reached?', 'reached'),
                       ('Outcome', 'outcome'), ('Notes', 'notes')]:
            if dc in edited.columns:
                rec[db] = row.get(dc) or None
        records.append(rec)
    try:
        upsert_outcomes_bulk(records)
        st.success(f'Saved {len(records)} records.')
    except Exception as e:
        st.error(f'Save failed: {e}')

st.divider()
download_button(df_f[DISPLAY], 'eviction_leads.csv')
