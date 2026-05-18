"""
Absentee Owners — properties where the HCPA owner doesn't live at the property.
Out-of-state absentee owners on distress lists are the highest-motivation sellers.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_absentee_leads
from utils.scoring import land_use_label
from utils.branding import apply_branding

st.set_page_config(page_title='Absentee Owners', page_icon='🏠', layout='wide')
apply_branding()
st.title('🏠 Absentee Owners')
st.caption(
    'Properties where the HCPA owner\'s mailing address differs from the property address — '
    'landlords, investors, and out-of-state heirs who may be motivated to sell.'
)

try:
    df = query_absentee_leads()
except Exception as e:
    st.error(f'Could not load absentee leads: {e}')
    st.stop()

if df.empty:
    st.info('No absentee owner data yet.')
    st.stop()

if 'land_use' in df.columns:
    df['land_use'] = df['land_use'].fillna('').apply(land_use_label)

# ── Sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.header('Filters')

oos_only = st.sidebar.checkbox('Out-of-state owners only', value=False)
if oos_only and 'is_out_of_state' in df.columns:
    df = df[df['is_out_of_state'] == True]

if 'lead_type' in df.columns:
    type_opts = sorted(df['lead_type'].dropna().unique().tolist())
    sel_types = st.sidebar.multiselect('Lead Type', type_opts, default=type_opts)
    if sel_types:
        df = df[df['lead_type'].isin(sel_types)]

if 'property_city' in df.columns:
    city_opts = sorted(df['property_city'].dropna().unique().tolist())
    sel_cities = st.sidebar.multiselect('City', city_opts)
    if sel_cities:
        df = df[df['property_city'].isin(sel_cities)]

if 'owner_mailing_state' in df.columns:
    state_opts = sorted(df['owner_mailing_state'].dropna().unique().tolist())
    sel_states = st.sidebar.multiselect('Owner\'s State', state_opts)
    if sel_states:
        df = df[df['owner_mailing_state'].isin(sel_states)]

# ── Metrics ────────────────────────────────────────────────────────────────────
total = len(df)
oos = int(df['is_out_of_state'].sum()) if 'is_out_of_state' in df.columns else 0
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric('Total', total)
c2.metric('Out-of-State', oos)
for i, lt in enumerate(['foreclosure', 'eviction', 'probate']):
    n = int((df['lead_type'] == lt).sum()) if 'lead_type' in df.columns else 0
    [c3, c4, c5][i].metric(lt.title(), n)

st.caption(f'{total:,} absentee leads shown')
st.divider()

# ── Table ──────────────────────────────────────────────────────────────────────
DISPLAY = [c for c in [
    'lead_type', 'filing_date', 'defendant_name',
    'property_street', 'property_city', 'property_zip',
    'owner_mailing_street', 'owner_mailing_city', 'owner_mailing_state',
    'is_out_of_state',
    'land_use', 'beds', 'baths', 'heated_sqft',
    'assessed_value', 'just_value',
    'survive_count', 'survive_amount',
    'homestead',
] if c in df.columns]

RENAME = {
    'lead_type': 'Type', 'filing_date': 'Filed',
    'defendant_name': 'Defendant',
    'property_street': 'Property Address', 'property_city': 'City',
    'property_zip': 'ZIP',
    'owner_mailing_street': 'Owner Mailing', 'owner_mailing_city': 'Owner City',
    'owner_mailing_state': 'Owner State',
    'is_out_of_state': 'Out of State?',
    'land_use': 'Prop Type',
    'beds': 'Beds', 'baths': 'Baths', 'heated_sqft': 'Sq Ft',
    'assessed_value': 'Assessed', 'just_value': 'Mkt Value',
    'survive_count': '# Survive', 'survive_amount': 'Survive $',
    'homestead': 'Homestead',
}

display_df = df[DISPLAY].rename(columns=RENAME)

# Sort: out-of-state first, then by assessed value descending
if 'Out of State?' in display_df.columns and 'Assessed' in display_df.columns:
    display_df = display_df.sort_values(
        ['Out of State?', 'Assessed'], ascending=[False, False]
    )

col_config = {
    'Out of State?': st.column_config.CheckboxColumn(disabled=True),
    'Homestead':     st.column_config.TextColumn(),
}
for col in ['Assessed', 'Mkt Value', 'Survive $']:
    if col in display_df.columns:
        col_config[col] = st.column_config.NumberColumn(format='$%,.0f')
for col in ['Beds', 'Baths', '# Survive']:
    if col in display_df.columns:
        col_config[col] = st.column_config.NumberColumn(format='%.0f', width='small')
if 'Sq Ft' in display_df.columns:
    col_config['Sq Ft'] = st.column_config.NumberColumn(format='%,.0f', width='small')

# HCPA link column
if 'hcpa_url' in df.columns:
    display_df.insert(1, 'HCPA', df['hcpa_url'].values)
    col_config['HCPA'] = st.column_config.LinkColumn('HCPA', display_text='🏠')

st.dataframe(display_df, column_config=col_config, use_container_width=True, hide_index=True)

# ── Download ───────────────────────────────────────────────────────────────────
st.download_button(
    '⬇️ Download CSV',
    df[DISPLAY].to_csv(index=False),
    'absentee_owners.csv',
    'text/csv',
)
