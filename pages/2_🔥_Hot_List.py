"""
Hot List — Priority leads across all types, with filters + PropStream export.
"""
import io
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_leads, query_liens_by_address
from utils.scoring import (
    add_fc_bucket, add_pb_bucket, bucket_sort_key,
    land_use_label, BUCKET_COLORS,
)
from utils.export import to_propstream_csv, download_button
from utils.branding import apply_branding, NAVY

st.set_page_config(page_title='Hot List', page_icon='🔥', layout='wide')
apply_branding()

st.markdown(f"<h2 style='color:{NAVY}; margin-bottom:0;'>🔥 Hot List</h2>",
            unsafe_allow_html=True)
st.caption('Priority leads across all types. Filter, review, then export to PropStream.')

# ── Load all lead types ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_all_leads():
    frames = []
    for lt in ['foreclosure', 'probate', 'divorce', 'eviction']:
        try:
            df = query_leads(lt)
            if df.empty:
                continue
            df['lead_type'] = lt
            # Normalise address columns to common names
            if 'property_street' in df.columns:
                df['street']  = df['property_street']
                df['city']    = df.get('property_city',  df.get('city', ''))
                df['zip']     = df.get('property_zip',   df.get('zip', ''))
            elif 'decedent_street' in df.columns:
                df['street']  = df['decedent_street']
                df['city']    = df.get('decedent_city',  df.get('city', ''))
                df['zip']     = df.get('decedent_zip',   df.get('zip', ''))
            # Normalise owner name
            for col in ['defendant_name', 'petitioner_name', 'party_1_name',
                        'tenant_name', 'primary_name']:
                if col in df.columns:
                    df['owner_name'] = df[col]
                    break
            # Add buckets
            if 'days_since_filing' in df.columns:
                if lt == 'foreclosure':
                    df = add_fc_bucket(df)
                else:
                    df = add_pb_bucket(df)
            frames.append(df)
        except Exception as e:
            st.warning(f'Could not load {lt}: {e}')
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    if 'land_use' in combined.columns:
        combined['prop_type'] = combined['land_use'].apply(land_use_label)
    return combined

with st.spinner('Loading leads…'):
    all_leads = load_all_leads()
    lien_map = query_liens_by_address()   # address → lien detail dict

if all_leads.empty:
    st.info('No leads found.')
    st.stop()

# ── Join lien data by address ─────────────────────────────────────────────────
if lien_map and 'street' in all_leads.columns:
    addr_key = all_leads['street'].str.lower().str.strip()
    all_leads['lien_detail']     = addr_key.map(lambda a: lien_map.get(a, {}).get('detail', ''))
    all_leads['survive_total']   = addr_key.map(lambda a: lien_map.get(a, {}).get('survive_total', 0))
    all_leads['wiped_total']     = addr_key.map(lambda a: lien_map.get(a, {}).get('wiped_total', 0))
    all_leads['survive_count']   = addr_key.map(lambda a: lien_map.get(a, {}).get('survive_count', 0))
    all_leads['wiped_count']     = addr_key.map(lambda a: lien_map.get(a, {}).get('wiped_count', 0))
else:
    for col in ['lien_detail', 'survive_total', 'wiped_total', 'survive_count', 'wiped_count']:
        all_leads[col] = None

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header('🔥 Hot List Filters')

# Lead type
all_types = sorted(all_leads['lead_type'].unique().tolist())
sel_types = st.sidebar.multiselect(
    'Lead Type', all_types,
    default=all_types,
    format_func=lambda x: {
        'foreclosure': '🏚 Foreclosure',
        'probate':     '📋 Probate',
        'divorce':     '💔 Divorce',
        'eviction':    '🏠 Eviction',
    }.get(x, x.title()),
)

# Date bucket
all_buckets = sorted(
    all_leads['bucket'].dropna().unique().tolist(),
    key=bucket_sort_key,
) if 'bucket' in all_leads.columns else []
sel_buckets = st.sidebar.multiselect('Date Bucket', all_buckets, default=all_buckets)

# Phone filter
phone_filter = st.sidebar.radio(
    'Phone', ['All', 'Has phone only', 'No phone yet'],
    horizontal=True,
)

# Property type
if 'prop_type' in all_leads.columns:
    prop_types = sorted([p for p in all_leads['prop_type'].dropna().unique() if p])
    sel_prop = st.sidebar.multiselect('Property Type', prop_types, default=prop_types)
else:
    sel_prop = []

# City
if 'city' in all_leads.columns:
    cities = sorted([c for c in all_leads['city'].dropna().unique() if c])
    sel_cities = st.sidebar.multiselect('City', cities)
else:
    sel_cities = []

# ZIP
if 'zip' in all_leads.columns:
    zips = sorted([z for z in all_leads['zip'].dropna().unique() if z])
    sel_zips = st.sidebar.multiselect('ZIP', zips)
else:
    sel_zips = []

# Absentee
absentee_only = st.sidebar.checkbox('Absentee owners only', value=False)

# Outcome exclusions
st.sidebar.markdown('**Exclude outcomes:**')
excl_dead      = st.sidebar.checkbox('Dead / Cancelled', value=True)
excl_no_int    = st.sidebar.checkbox('Not Interested',   value=True)
excl_low_eq    = st.sidebar.checkbox('Low Equity',       value=False)
excl_contacted = st.sidebar.checkbox('Already Reached',  value=False)

# ── Apply filters ─────────────────────────────────────────────────────────────
df = all_leads.copy()

if sel_types:
    df = df[df['lead_type'].isin(sel_types)]
if sel_buckets and 'bucket' in df.columns:
    df = df[df['bucket'].isin(sel_buckets)]
if phone_filter == 'Has phone only':
    df = df[df['phone_1'].notna()] if 'phone_1' in df.columns else df
elif phone_filter == 'No phone yet':
    df = df[df['phone_1'].isna()] if 'phone_1' in df.columns else df
if sel_prop and 'prop_type' in df.columns:
    df = df[df['prop_type'].isin(sel_prop)]
if sel_cities and 'city' in df.columns:
    df = df[df['city'].isin(sel_cities)]
if sel_zips and 'zip' in df.columns:
    df = df[df['zip'].isin(sel_zips)]
if absentee_only and 'is_absentee' in df.columns:
    df = df[df['is_absentee'] == True]

# Outcome exclusions
if 'outcome' in df.columns:
    excl = set()
    if excl_dead:    excl |= {'Dead', 'Cancelled'}
    if excl_no_int:  excl |= {'Not Interested', 'No Property'}
    if excl_low_eq:  excl |= {'Low Equity'}
    if excl_contacted: excl |= {'Reached', 'In Negotiation', 'Under Contract'}
    if excl:
        df = df[~df['outcome'].isin(excl)]

# Sort by urgency (bucket_sort) then type
if 'bucket_sort' in df.columns:
    df = df.sort_values(['bucket_sort', 'lead_type'])

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric('Total',         len(df))
c2.metric('🏚 FC',         int((df['lead_type'] == 'foreclosure').sum()))
c3.metric('📋 Probate',    int((df['lead_type'] == 'probate').sum()))
c4.metric('📞 Has Phone',  int(df['phone_1'].notna().sum()) if 'phone_1' in df.columns else 0)
c5.metric('🔑 Absentee',   int((df['is_absentee'] == True).sum()) if 'is_absentee' in df.columns else 0)

st.divider()

# ── Table ─────────────────────────────────────────────────────────────────────
show_cols = [c for c in [
    'bucket', 'lead_type', 'days_since_filing', 'case_number',
    'owner_name', 'phone_1', 'street', 'city', 'zip',
    'prop_type', 'is_absentee',
    'beds', 'baths', 'heated_sqft', 'acreage',
    'just_value', 'assessed_value', 'subdivision',
    'survive_count', 'survive_total', 'wiped_count', 'wiped_total',
    'lien_detail',
    'called', 'reached', 'outcome',
] if c in df.columns]

col_cfg = {
    'lead_type':        st.column_config.TextColumn('Type'),
    'bucket':           st.column_config.TextColumn('Bucket'),
    'days_since_filing':st.column_config.NumberColumn('Days', format='%d'),
    'case_number':      st.column_config.TextColumn('Case #'),
    'owner_name':       st.column_config.TextColumn('Owner'),
    'phone_1':          st.column_config.TextColumn('Phone'),
    'street':           st.column_config.TextColumn('Address'),
    'city':             st.column_config.TextColumn('City'),
    'zip':              st.column_config.TextColumn('ZIP'),
    'prop_type':        st.column_config.TextColumn('Prop Type'),
    'is_absentee':      st.column_config.CheckboxColumn('Absentee?'),
    'beds':             st.column_config.NumberColumn('Beds',     format='%.0f', width='small'),
    'baths':            st.column_config.NumberColumn('Baths',    format='%.0f', width='small'),
    'heated_sqft':      st.column_config.NumberColumn('Sq Ft',    format='%.0f', width='small'),
    'acreage':          st.column_config.NumberColumn('Acres',    format='%.2f', width='small'),
    'just_value':       st.column_config.NumberColumn('Mkt Value',format='$%,.0f', width='small'),
    'assessed_value':   st.column_config.NumberColumn('Assessed', format='$%,.0f', width='small'),
    'subdivision':      st.column_config.TextColumn('Subdivision'),
    'survive_count':    st.column_config.NumberColumn('# Survive', format='%d'),
    'survive_total':    st.column_config.NumberColumn('Survive $', format='$%,.0f'),
    'wiped_count':      st.column_config.NumberColumn('# Wiped',   format='%d'),
    'wiped_total':      st.column_config.NumberColumn('Wiped $',   format='$%,.0f'),
    'lien_detail':      st.column_config.TextColumn('Lien Detail', width='large'),
    'called':           st.column_config.CheckboxColumn('Called?'),
    'reached':          st.column_config.CheckboxColumn('Reached?'),
    'outcome':          st.column_config.TextColumn('Outcome'),
}

st.dataframe(
    df[show_cols],
    column_config=col_cfg,
    use_container_width=True,
    hide_index=True,
    height=500,
)

# ── PropStream export ─────────────────────────────────────────────────────────
st.divider()
st.subheader('📤 Export to PropStream')

no_phone = df[df['phone_1'].isna()].copy() if 'phone_1' in df.columns else df.copy()
has_phone = df[df['phone_1'].notna()].copy() if 'phone_1' in df.columns else pd.DataFrame()

col_a, col_b = st.columns(2)

with col_a:
    st.markdown(f"**No phone yet** — {len(no_phone)} leads  \n_Send these to PropStream for skip tracing_")
    if not no_phone.empty:
        st.download_button(
            f'⬇️ PropStream Upload ({len(no_phone)} rows)',
            to_propstream_csv(no_phone, 'HOTLIST'),
            'propstream_upload_hotlist.csv',
            'text/csv',
            type='primary',
        )

with col_b:
    st.markdown(f"**All filtered leads** — {len(df)} leads  \n_Download full filtered list as CSV_")
    if not df.empty:
        buf2 = io.StringIO()
        df[show_cols].to_csv(buf2, index=False)
        st.download_button(
            f'⬇️ Full Hot List CSV ({len(df)} rows)',
            buf2.getvalue().encode(),
            'hot_list_filtered.csv',
            'text/csv',
        )
