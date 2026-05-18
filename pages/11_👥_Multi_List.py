"""
Multi-List Persons & Properties
================================
Shows people and addresses that appear on 2+ lead type lists simultaneously
(e.g., the same person is in both foreclosure AND probate, or a foreclosed
property is also absentee-owned).
These are the highest-priority leads — multiple distress signals on one target.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_multi_list_persons, query_multi_list_properties
from utils.export import download_button
from utils.branding import apply_branding

st.set_page_config(page_title='Multi-List Leads', page_icon='👥', layout='wide')
apply_branding()
st.title('👥 Multi-List Leads')
st.caption(
    'People and properties appearing on **2 or more** lead type lists simultaneously. '
    'Multiple distress signals = highest motivation to sell. '
    '**Absentee** = owner lives elsewhere (out-of-state or different FL address).'
)

# ── Load data ─────────────────────────────────────────────────────────────────
try:
    persons_df    = query_multi_list_persons()
    properties_df = query_multi_list_properties()
except Exception as e:
    st.error(f'Could not load multi-list data: {e}')
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric('👤 Multi-List Persons',     len(persons_df))
c2.metric('🏠 Multi-List Properties',  len(properties_df))

persons_3plus    = len(persons_df[persons_df['list_count'] >= 3])    if not persons_df.empty    else 0
properties_3plus = len(properties_df[properties_df['list_count'] >= 3]) if not properties_df.empty else 0
c3.metric('🔥 Persons on 3+ Lists',    persons_3plus)
c4.metric('🔥 Properties on 3+ Lists', properties_3plus)

st.divider()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header('Filters')
if st.sidebar.button('🔄 Refresh data'):
    st.cache_data.clear()
    st.rerun()


list_count_min = st.sidebar.slider('Minimum # of lists', min_value=2, max_value=5, value=2)

list_types = st.sidebar.multiselect(
    'Must appear on…',
    options=['foreclosure', 'probate', 'divorce', 'eviction', 'absentee'],
    default=[],
    help='Leave blank to show all multi-list leads',
)

city_filter = st.sidebar.text_input('City contains', '').strip().lower()


def _filter_df(df: pd.DataFrame, city_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    df = df[df['list_count'] >= list_count_min].copy()
    for lt in list_types:
        col = f'in_{lt}'
        if col in df.columns:
            df = df[df[col] == True]
    if city_filter and city_col in df.columns:
        df = df[df[city_col].str.lower().str.contains(city_filter, na=False)]
    return df


persons_f    = _filter_df(persons_df,    city_col='city')
properties_f = _filter_df(properties_df, city_col='city')

# Drop junk rows where street/city is "Unknown" — cases with no usable address
if not properties_f.empty and 'street' in properties_f.columns:
    properties_f = properties_f[
        ~properties_f['street'].fillna('').str.lower().isin(['unknown', '', 'nan'])
    ]


# Shared _lists builder — includes absentee
ALL_TYPES = ['foreclosure', 'probate', 'divorce', 'eviction', 'absentee']

def _lists(row):
    return ' + '.join([
        lt.title() for lt in ALL_TYPES
        if row.get(f'in_{lt}')
    ])


# ── Persons tab ───────────────────────────────────────────────────────────────
tab2, tab1 = st.tabs([
    f'🏠 Properties  ({len(properties_f)})',
    f'👤 Persons  ({len(persons_f)})',
])

with tab1:
    if persons_f.empty:
        st.info('No multi-list persons match the current filters.')
    else:
        persons_f = persons_f.copy()
        persons_f['Lists'] = persons_f.apply(_lists, axis=1)

        PCOLS = [c for c in [
            'list_count', 'Lists',
            'full_name', 'city', 'zip', 'phone_1', 'email_1',
            'foreclosure_first_date', 'probate_first_date',
            'divorce_first_date', 'eviction_first_date',
            'outcome',
        ] if c in persons_f.columns]

        PRENAME = {
            'list_count':              '# Lists',
            'full_name':               'Name',
            'city':                    'City',
            'zip':                     'ZIP',
            'phone_1':                 'Phone',
            'email_1':                 'Email',
            'foreclosure_first_date':  'FC Date',
            'probate_first_date':      'Probate Date',
            'divorce_first_date':      'Divorce Date',
            'eviction_first_date':     'Eviction Date',
            'outcome':                 'Outcome',
        }

        display_p = persons_f[PCOLS].rename(columns=PRENAME).sort_values(
            '# Lists', ascending=False
        )

        st.dataframe(display_p, use_container_width=True, hide_index=True)
        download_button(display_p, 'multi_list_persons.csv', '⬇ Download Person List')

        with st.expander('🔍 View case numbers for a specific person'):
            names = persons_f['full_name'].dropna().sort_values().unique().tolist()
            chosen = st.selectbox('Select person', options=[''] + names, key='person_sel')
            if chosen:
                row = persons_f[persons_f['full_name'] == chosen].iloc[0]
                for lt in ['foreclosure', 'probate', 'divorce', 'eviction']:
                    cases = row.get(f'{lt}_cases')
                    if cases:
                        case_list = cases if isinstance(cases, list) else str(cases).strip('{}').split(',')
                        st.write(f"**{lt.title()}:** {', '.join(case_list)}")


# ── Properties tab ────────────────────────────────────────────────────────────
with tab2:
    if properties_f.empty:
        st.info('No multi-list properties match the current filters.')
    else:
        properties_f = properties_f.copy()
        properties_f['Lists'] = properties_f.apply(_lists, axis=1)

        PRCOLS = [c for c in [
            'list_count', 'Lists',
            'street', 'city', 'zip',
            'land_use', 'assessed_value',
            'total_lien_count', 'survive_amount', 'wiped_amount',
            'lien_summary',
            'phone_1', 'email_1',
            'foreclosure_first_date', 'probate_first_date',
            'divorce_first_date', 'eviction_first_date',
        ] if c in properties_f.columns]

        PRRENAME = {
            'list_count':              '# Lists',
            'street':                  'Address',
            'city':                    'City',
            'zip':                     'ZIP',
            'land_use':                'Prop Type',
            'assessed_value':          'Assessed $',
            'total_lien_count':        'Liens',
            'survive_amount':          'Surviving $',
            'wiped_amount':            'Wiped $',
            'lien_summary':            'Lien Notes',
            'phone_1':                 'Phone',
            'email_1':                 'Email',
            'foreclosure_first_date':  'FC Date',
            'probate_first_date':      'Probate Date',
            'divorce_first_date':      'Divorce Date',
            'eviction_first_date':     'Eviction Date',
        }

        col_config = {}
        renamed_cols = properties_f.rename(columns=PRRENAME).columns
        if 'Assessed $' in renamed_cols:
            col_config['Assessed $'] = st.column_config.NumberColumn(format='$%,.0f')
        if 'Surviving $' in renamed_cols:
            col_config['Surviving $'] = st.column_config.NumberColumn(format='$%,.0f')

        display_pr = properties_f[PRCOLS].rename(columns=PRRENAME).sort_values(
            '# Lists', ascending=False
        )

        st.dataframe(
            display_pr,
            column_config=col_config,
            use_container_width=True,
            hide_index=True,
        )
        download_button(display_pr, 'multi_list_properties.csv', '⬇ Download Property List')

        with st.expander('🔍 View case numbers for a specific address'):
            addrs = properties_f['street'].dropna().sort_values().unique().tolist()
            chosen = st.selectbox('Select address', options=[''] + addrs, key='prop_sel')
            if chosen:
                row = properties_f[properties_f['street'] == chosen].iloc[0]
                for lt in ['foreclosure', 'probate', 'divorce', 'eviction']:
                    cases = row.get(f'{lt}_cases')
                    if cases:
                        case_list = cases if isinstance(cases, list) else str(cases).strip('{}').split(',')
                        st.write(f"**{lt.title()}:** {', '.join(case_list)}")
