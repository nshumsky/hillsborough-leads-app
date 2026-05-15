"""
Auctions tab — properties scheduled for courthouse sale on realforeclose.com.
Lien/title info is shown here because it directly affects the max bid calculation.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_auctions
from utils.scoring import land_use_label
from utils.branding import apply_branding

st.set_page_config(page_title='Auctions', page_icon='🏛', layout='wide')
apply_branding()
st.title('🏛 Auctions')
st.caption('Properties scheduled for courthouse sale on realforeclose.com — sorted by urgency.')

try:
    df = query_auctions()
except Exception as e:
    st.error(f'Could not load auction data: {e}')
    st.stop()

if df.empty:
    st.info('No auction data yet. Run `load_auctions_to_db.py` to load from the scraper CSV.')
    st.stop()

if 'land_use' in df.columns:
    df['land_use'] = df['land_use'].fillna('').apply(land_use_label)

# ── Sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.header('Filters')

# Status filter
if 'status' in df.columns:
    all_statuses = sorted(df['status'].dropna().unique().tolist())
    # Default: exclude Sold and Cancelled
    default_statuses = [s for s in all_statuses if s not in ('Sold', 'Cancelled', 'sold', 'cancelled')]
    sel_status = st.sidebar.multiselect('Status', all_statuses, default=default_statuses)
    if sel_status:
        df = df[df['status'].isin(sel_status)]

# Urgency filter
if 'urgency' in df.columns:
    urgency_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    all_urgencies = [u for u in urgency_order if u in df['urgency'].unique()]
    sel_urgency = st.sidebar.multiselect('Urgency', all_urgencies, default=all_urgencies)
    if sel_urgency:
        df = df[df['urgency'].isin(sel_urgency)]

# Property type exclusion
excl_mobile_apt = st.sidebar.checkbox('Exclude Mobile Homes & Apartments', value=True)
if excl_mobile_apt and 'land_use' in df.columns:
    EXCL = {'Mobile Home', 'Multi-Family'}
    df = df[~df['land_use'].isin(EXCL)]

# City filter
if 'property_city' in df.columns:
    cities = sorted(df['property_city'].dropna().unique().tolist())
    sel_cities = st.sidebar.multiselect('City', cities)
    if sel_cities:
        df = df[df['property_city'].isin(sel_cities)]

# Sort by urgency then days_to_sale
urgency_rank = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
if 'urgency' in df.columns:
    df['_urgency_rank'] = df['urgency'].map(urgency_rank).fillna(9)
    df = df.sort_values(['_urgency_rank', 'days_to_sale'])

st.caption(f'{len(df):,} auctions shown')

# ── Metrics ────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric('Total', len(df))
c2.metric('🚨 Critical',  int((df['urgency'] == 'CRITICAL').sum()) if 'urgency' in df.columns else 0)
c3.metric('📅 This Week', int((df['days_to_sale'].fillna(999) <= 7).sum()) if 'days_to_sale' in df.columns else 0)
c4.metric('⚖️ Avg Judgment', f"${df['judgment'].mean():,.0f}" if 'judgment' in df.columns and df['judgment'].notna().any() else '—')

st.divider()

# ── Display columns ────────────────────────────────────────────────────────────
DISPLAY = [c for c in [
    'urgency', 'days_to_sale', 'sale_date', 'case_number',
    'defendant_name', 'property_street', 'property_city', 'property_zip',
    'judgment', 'land_use', 'is_absentee',
    'beds', 'baths', 'heated_sqft', 'acreage',
    'just_value', 'assessed_value', 'subdivision',
    'survive_count', 'survive_amount', 'wiped_count', 'wiped_amount',
    'lien_detail', 'lien_url',
] if c in df.columns]

RENAME = {
    'urgency': 'Urgency', 'days_to_sale': 'Days', 'sale_date': 'Sale Date',
    'case_number': 'Case #', 'defendant_name': 'Defendant',
    'property_street': 'Address', 'property_city': 'City', 'property_zip': 'ZIP',
    'judgment': 'Judgment $', 'land_use': 'Prop Type', 'is_absentee': 'Absentee?',
    'beds': 'Beds', 'baths': 'Baths', 'heated_sqft': 'Sq Ft', 'acreage': 'Acres',
    'just_value': 'Mkt Value', 'assessed_value': 'Assessed',
    'subdivision': 'Subdivision',
    'survive_count': '# Survive', 'survive_amount': 'Survive $',
    'wiped_count': '# Wiped', 'wiped_amount': 'Wiped $',
    'lien_detail': 'Lien Detail', 'lien_url': 'Lien URL',
}

display_df = df[DISPLAY].rename(columns=RENAME)

col_config = {}
if 'Absentee?' in display_df.columns:
    col_config['Absentee?'] = st.column_config.CheckboxColumn(disabled=True)
if 'Case #' in display_df.columns and 'auction_url' in df.columns:
    # Build clickable link column from aid
    pass  # handled below via link_column if available
for col in ['Judgment $', 'Mkt Value', 'Assessed', 'Survive $', 'Wiped $']:
    if col in display_df.columns:
        col_config[col] = st.column_config.NumberColumn(format='$%,.0f')
for col in ['Sq Ft', 'Beds', 'Baths']:
    if col in display_df.columns:
        col_config[col] = st.column_config.NumberColumn(format='%.0f', width='small')
if 'Acres' in display_df.columns:
    col_config['Acres'] = st.column_config.NumberColumn(format='%.2f', width='small')
if 'Lien URL' in display_df.columns:
    col_config['Lien URL'] = st.column_config.LinkColumn('Lien URL', display_text='🔗 View')
if 'Days' in display_df.columns:
    col_config['Days'] = st.column_config.NumberColumn('Days', format='%d')

# Add auction URL as link column if we have it
if 'auction_url' in df.columns:
    display_df.insert(1, 'Auction Link', df['auction_url'].values)
    col_config['Auction Link'] = st.column_config.LinkColumn('Auction Link', display_text='🏛 View')

st.dataframe(
    display_df,
    column_config=col_config,
    use_container_width=True,
    hide_index=True,
)

st.divider()
from utils.export import download_button
download_button(df[DISPLAY] if set(DISPLAY).issubset(df.columns) else df, 'auctions.csv')
