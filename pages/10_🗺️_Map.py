"""
Map view — plot all geocoded leads on an interactive map.
Color-coded by lead type, with property details on hover.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_client, query_map_data, query_leads
from utils.branding import apply_branding, NAVY, STEEL

st.set_page_config(page_title='Map', page_icon='🗺️', layout='wide')
apply_branding()

st.markdown(f"<h2 style='color:{NAVY}; margin-bottom:0;'>🗺️ Property Map</h2>",
            unsafe_allow_html=True)
st.caption(f'Geocoded leads plotted in Hillsborough County — {date.today().strftime("%B %d, %Y")}')

# ── Load data ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_map_leads():
    """Join geocoded properties to all lead types for color coding."""
    sb = get_client()

    # Load geocoded dim_property
    res = sb.schema('silver').table('dim_property') \
            .select('address,folio,owner_raw,land_use,is_absentee,homestead,sale_price,lat,lon') \
            .not_.is_('lat', 'null') \
            .not_.is_('lon', 'null') \
            .execute()
    if not res.data:
        return pd.DataFrame()

    prop = pd.DataFrame(res.data)
    prop['lat'] = pd.to_numeric(prop['lat'], errors='coerce')
    prop['lon'] = pd.to_numeric(prop['lon'], errors='coerce')
    prop = prop.dropna(subset=['lat', 'lon'])
    prop['address_key'] = prop['address']   # already normalized

    # Load all leads to get lead_type for each address
    _view_map = {
        'foreclosure': 'fact_foreclosures',
        'probate':     'fact_probate',
        'divorce':     'fact_divorces',
        'eviction':    'fact_evictions',
    }
    leads_dfs = []
    for lt in ['foreclosure', 'probate', 'divorce', 'eviction']:
        try:
            res2 = sb.schema('gold').table(_view_map[lt]).select(
                'case_number,filing_date,street,city,zip,phone_1,outcome'
            ).execute()
            if res2.data:
                df2 = pd.DataFrame(res2.data)
                df2['lead_type'] = lt
                df2['address_key'] = df2['street'].str.lower().str.strip()
                leads_dfs.append(df2)
        except Exception:
            pass

    if not leads_dfs:
        # Just show properties without lead-type color
        prop['lead_type'] = 'unknown'
        prop['case_number'] = None
        return prop

    all_leads = pd.concat(leads_dfs, ignore_index=True)

    # Each address may appear in multiple lead types — keep one row per address, prefer foreclosure
    lt_order = {'foreclosure': 0, 'probate': 1, 'divorce': 2, 'eviction': 3}
    all_leads['lt_rank'] = all_leads['lead_type'].map(lt_order).fillna(99)
    agg = all_leads.sort_values('lt_rank').drop_duplicates('address_key', keep='first')

    merged = prop.merge(
        agg[['address_key', 'lead_type', 'case_number', 'filing_date', 'city', 'zip', 'phone_1', 'outcome']],
        on='address_key', how='left',
    )
    merged['lead_type'] = merged['lead_type'].fillna('enriched only')
    return merged


with st.spinner('Loading map data…'):
    df = load_map_leads()

if df.empty:
    st.info(
        "No geocoded properties yet.\n\n"
        "Run **`python3 enrich_titles.py --phase 1`** in the foreclosure repo to geocode "
        "Hillsborough County properties. Coordinates are populated automatically after "
        "HCPA lookup via the US Census Bureau geocoder."
    )
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header('🗺️ Map Filters')

lead_types = sorted(df['lead_type'].dropna().unique().tolist())
selected_types = st.sidebar.multiselect('Lead Types', lead_types, default=lead_types)

land_uses = sorted(df['land_use'].dropna().unique().tolist())
selected_land = st.sidebar.multiselect('Property Type (DOR Code)', land_uses, default=land_uses)

absentee_only = st.sidebar.checkbox('Absentee owners only (no homestead)', value=False)

# ── Filter ────────────────────────────────────────────────────────────────────
filtered = df.copy()
if selected_types:
    filtered = filtered[filtered['lead_type'].isin(selected_types)]
if selected_land:
    filtered = filtered[filtered['land_use'].isin(selected_land)]
if absentee_only:
    filtered = filtered[filtered['is_absentee'] == True]

# ── Metrics ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric('📍 Properties on Map', len(filtered))
col2.metric('🔴 Foreclosures', int((filtered['lead_type'] == 'foreclosure').sum()))
col3.metric('📋 Probate',      int((filtered['lead_type'] == 'probate').sum()))
col4.metric('🏠 Absentee',     int((filtered['is_absentee'] == True).sum()))

st.divider()

# ── Map ───────────────────────────────────────────────────────────────────────
COLOR_MAP = {
    'foreclosure':    '#EF5350',
    'probate':        '#42A5F5',
    'divorce':        '#AB47BC',
    'eviction':       '#FF7043',
    'enriched only':  '#78909C',
    'unknown':        '#90A4AE',
}

# Build hover text
filtered = filtered.copy()
filtered['hover'] = (
    filtered['address'].str.title() + '<br>'
    + filtered['lead_type'].str.title() + '<br>'
    + 'Owner: ' + filtered['owner_raw'].fillna('—') + '<br>'
    + 'Land use: ' + filtered['land_use'].fillna('—') + '<br>'
    + filtered['is_absentee'].map({True: '🔑 Absentee', False: '🏠 Homestead', None: ''}).fillna('')
)

fig = px.scatter_mapbox(
    filtered,
    lat='lat',
    lon='lon',
    color='lead_type',
    color_discrete_map=COLOR_MAP,
    hover_name='address',
    custom_data=['hover'],
    zoom=10,
    center={'lat': 27.9944, 'lon': -82.5515},  # Tampa center
    height=600,
    mapbox_style='carto-positron',
    labels={'lead_type': 'Lead Type'},
)
fig.update_traces(
    marker=dict(size=8, opacity=0.8),
    hovertemplate='%{customdata[0]}<extra></extra>',
)
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend_title_text='Lead Type')

st.plotly_chart(fig, use_container_width=True)

# ── Data table ────────────────────────────────────────────────────────────────
st.divider()
st.subheader(f'📋 {len(filtered)} Properties')

show_cols = [c for c in [
    'lead_type', 'address', 'city', 'zip', 'owner_raw',
    'land_use', 'homestead', 'is_absentee', 'sale_price',
    'lat', 'lon',
] if c in filtered.columns]

col_cfg = {}
if 'sale_price' in filtered.columns:
    col_cfg['sale_price'] = st.column_config.NumberColumn('Sale Price', format='$%,.0f')
if 'lat' in filtered.columns:
    col_cfg['lat'] = st.column_config.NumberColumn('Lat', format='%.4f')
if 'lon' in filtered.columns:
    col_cfg['lon'] = st.column_config.NumberColumn('Lon', format='%.4f')

st.dataframe(
    filtered[show_cols].rename(columns={
        'lead_type': 'Type', 'address': 'Address', 'city': 'City', 'zip': 'ZIP',
        'owner_raw': 'Owner', 'land_use': 'DOR Code',
        'homestead': 'Homestead', 'is_absentee': 'Absentee?',
    }).sort_values('Type'),
    column_config=col_cfg,
    use_container_width=True,
    hide_index=True,
)

csv = filtered[show_cols].to_csv(index=False)
st.download_button('⬇️ Download CSV', csv, 'map_properties.csv', 'text/csv')
