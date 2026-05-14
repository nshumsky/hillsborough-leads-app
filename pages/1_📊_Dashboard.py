import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_client, query_daily_new, query_leads, get_kpis
from utils.branding import apply_branding

st.set_page_config(page_title='Dashboard', page_icon='📊', layout='wide')
apply_branding()
from utils.branding import NAVY, STEEL
st.markdown(
    f"<h2 style='color:{NAVY}; margin-bottom:0;'>Welcome, Mike! 👋</h2>",
    unsafe_allow_html=True,
)
st.caption(f'📊 Dashboard — {date.today().strftime("%A, %B %d %Y")}')

# ── KPI row ───────────────────────────────────────────────────────────────────
try:
    kpis = get_kpis()
except Exception as e:
    st.error(f'Could not load KPIs: {e}')
    st.stop()

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric('🔴 New Today',       kpis.get('new_today', 0))
col2.metric('📅 New This Week',   kpis.get('new_this_week', 0))
col3.metric('🏚 Foreclosures',    kpis.get('total_foreclosure', 0))
col4.metric('📋 Probate',         kpis.get('total_probate', 0))
col5.metric('💔 Divorce',         kpis.get('total_divorce', 0))
col6.metric('🏠 Evictions',       kpis.get('total_eviction', 0))

st.divider()

# ── Recent filings chart ──────────────────────────────────────────────────────
st.subheader('📈 New Filings — Last 30 Days')
try:
    daily = query_daily_new(days=30)
    if not daily.empty and 'filing_date' in daily.columns:
        chart = daily.groupby(['filing_date', 'lead_type']).size().reset_index(name='count')
        fig = px.bar(chart, x='filing_date', y='count', color='lead_type',
                     color_discrete_map={
                         'foreclosure': '#EF5350',
                         'probate':     '#42A5F5',
                         'divorce':     '#AB47BC',
                         'eviction':    '#FF7043',
                     },
                     barmode='stack',
                     labels={'filing_date': 'Date', 'count': 'New Cases', 'lead_type': 'Type'})
        fig.update_layout(height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info('No recent filing data available yet.')
except Exception as e:
    st.warning(f'Could not load chart: {e}')

st.divider()

# ── Lead type breakdown tables ────────────────────────────────────────────────
cols = st.columns(2)

with cols[0]:
    st.subheader('🏚 Foreclosures by Date Bucket')
    try:
        fc = query_leads('foreclosure')
        if not fc.empty and 'days_since_filing' in fc.columns:
            from utils.scoring import add_fc_bucket
            fc = add_fc_bucket(fc)
            tbl = fc.groupby('bucket').agg(
                Count=('case_number', 'count'),
                With_Phone=('phone_1', lambda x: x.notna().sum()),
            ).reset_index()
            tbl.columns = ['Bucket', 'Count', 'Has Phone']
            st.dataframe(tbl, use_container_width=True, hide_index=True)
        else:
            st.info('No foreclosure data yet.')
    except Exception as e:
        st.warning(f'{e}')

with cols[1]:
    st.subheader('📋 Probate by Date Bucket')
    try:
        pb = query_leads('probate')
        if not pb.empty and 'days_since_filing' in pb.columns:
            from utils.scoring import add_pb_bucket
            pb = add_pb_bucket(pb)
            tbl = pb.groupby('bucket').agg(
                Count=('case_number', 'count'),
                With_Phone=('phone_1', lambda x: x.notna().sum()),
                OOS=('oos', lambda x: (x == True).sum()),
            ).reset_index()
            tbl.columns = ['Bucket', 'Count', 'Has Phone', 'OOS']
            st.dataframe(tbl, use_container_width=True, hide_index=True)
        else:
            st.info('No probate data yet.')
    except Exception as e:
        st.warning(f'{e}')

# ── Cross-type matches ────────────────────────────────────────────────────────
st.divider()
st.subheader('🔁 Cross-Type Matches (same address in multiple lead types)')
st.caption('Properties appearing on 2+ lead lists simultaneously — highest priority targets. See 👥 Multi-List for full details.')
try:
    from utils.db import query_multi_list_properties
    matches = query_multi_list_properties()
    if not matches.empty:
        # Build a readable "Lists" column
        def _lists(row):
            return ' + '.join([
                lt.title() for lt in ['foreclosure', 'probate', 'divorce', 'eviction']
                if row.get(f'in_{lt}')
            ])
        matches = matches.copy()
        matches['Lists'] = matches.apply(_lists, axis=1)

        show_cols = [c for c in [
            'list_count', 'Lists', 'street', 'city', 'zip',
            'land_use', 'assessed_value', 'lien_summary',
        ] if c in matches.columns]

        col_cfg = {}
        if 'assessed_value' in matches.columns:
            col_cfg['assessed_value'] = st.column_config.NumberColumn('Assessed $', format='$%,.0f')

        st.dataframe(
            matches[show_cols].rename(columns={
                'list_count': '# Lists', 'street': 'Address',
                'city': 'City', 'zip': 'ZIP',
                'land_use': 'Prop Type', 'lien_summary': 'Liens',
            }).sort_values('# Lists', ascending=False),
            column_config=col_cfg,
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f'{len(matches)} properties — click 👥 Multi-List in the sidebar for phone numbers and case drilldown.')
    else:
        st.info('No cross-type matches found yet. These appear when the same address shows up in 2+ lead types.')
except Exception as e:
    st.warning(f'Could not load cross-type matches: {e}')
