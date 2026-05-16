import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_leads, upsert_outcomes_bulk
from utils.scoring import add_pb_bucket, land_use_label, is_likely_care_facility
from utils.filters import apply_all_filters
from utils.export import download_button, to_propstream_csv
from utils.branding import apply_branding, NAVY

st.set_page_config(page_title='Probate', page_icon='📋', layout='wide')
apply_branding()
st.title('📋 Probate Cases')

try:
    df = query_leads('probate')
except Exception as e:
    st.error(f'Could not load probate data: {e}')
    st.stop()

if df.empty:
    st.info('No probate data yet.')
    st.stop()

df = add_pb_bucket(df, 'days_since_filing')

# ── Detect care-facility addresses ───────────────────────────────────────────
# The Clerk files the decedent's LAST KNOWN MAILING ADDRESS, which is often
# an assisted living facility, nursing home, or other care facility — NOT the
# property the estate owns.  Flag those rows so Mike knows to search HCPA by
# owner name instead of relying on the address-based property lookup.
if all(c in df.columns for c in ['land_use', 'owner_raw', 'decedent_last_name']):
    df['_care_flag'] = df.apply(
        lambda r: is_likely_care_facility(
            r.get('land_use', ''),
            r.get('owner_raw', ''),
            r.get('decedent_last_name', ''),
        ), axis=1
    )
    care_cases = df[df['_care_flag'] == True]
    if not care_cases.empty:
        names = ', '.join(
            f"{r.decedent_first_name} {r.decedent_last_name}"
            for _, r in care_cases.head(5).iterrows()
            if r.get('decedent_last_name')
        )
        extra = f' + {len(care_cases) - 5} more' if len(care_cases) > 5 else ''
        st.warning(
            f"⚠️ **{len(care_cases)} decedent address(es) appear to be care facilities, "
            f"not the decedent's own property:** {names}{extra}\n\n"
            "The property data shown (beds, value, etc.) belongs to the facility building — "
            "not the estate asset. To find what the decedent actually owned, search HCPA by "
            "their name: [hcpafl.org Property Search](https://www.hcpafl.org/Property-Info/Property-Search)",
            icon="🏥"
        )

if 'land_use' in df.columns:
    df['land_use'] = df['land_use'].fillna('').apply(land_use_label)

st.sidebar.header('Filters')
# OOS filter
if 'oos' in df.columns:
    oos_only = st.sidebar.checkbox('⛺ Out-of-state only', value=False)
    if oos_only:
        df = df[df['oos'] == True]

df_f = apply_all_filters(df, date_col='filing_date', city_col='decedent_city')
st.caption(f'{len(df_f):,} of {len(df):,} leads shown')

DISPLAY = [c for c in [
    'bucket', 'days_since_filing', 'filing_date', 'case_number',
    'petitioner_first_name', 'petitioner_last_name',
    'petitioner_city', 'petitioner_state', 'oos',
    'decedent_first_name', 'decedent_last_name',
    'decedent_street', 'decedent_city', 'decedent_zip',
    'land_use', 'is_absentee', 'homestead',
    'beds', 'baths', 'heated_sqft', 'acreage',
    'just_value', 'assessed_value', 'subdivision',
    'phone_1',
    'called', 'reached', 'offer_amount', 'outcome', 'notes',
] if c in df_f.columns]

RENAME = {
    'bucket': 'Bucket', 'days_since_filing': 'Days', 'filing_date': 'Filed',
    'case_number': 'Case #',
    'petitioner_first_name': 'Pet. First', 'petitioner_last_name': 'Pet. Last',
    'petitioner_city': 'Pet. City', 'petitioner_state': 'Pet. State', 'oos': 'OOS?',
    'decedent_first_name': 'Dec. First', 'decedent_last_name': 'Dec. Last',
    'decedent_street': 'Prop. Address', 'decedent_city': 'City', 'decedent_zip': 'ZIP',
    'land_use': 'Prop Type', 'is_absentee': 'Absentee?', 'homestead': 'Homestead?',
    'beds': 'Beds', 'baths': 'Baths', 'heated_sqft': 'Sq Ft', 'acreage': 'Acres',
    'just_value': 'Mkt Value', 'assessed_value': 'Assessed',
    'subdivision': 'Subdivision',
    'phone_1': 'Phone',
    'called': 'Called?', 'reached': 'Reached?',
    'offer_amount': 'Offer $', 'outcome': 'Outcome', 'notes': 'Notes',
}

display_df = df_f[DISPLAY].rename(columns=RENAME)

OUTCOME_OPTS = ['', 'Active', 'Deal', 'Dead', 'Not Interested', 'No Property', 'Low Equity']
CALLED_OPTS  = ['', 'Yes', 'No', 'Voicemail', 'DNC']
REACHED_OPTS = ['', 'Yes', 'No', 'Voicemail']

col_config = {}
for col, opts in [('Called?', CALLED_OPTS), ('Reached?', REACHED_OPTS), ('Outcome', OUTCOME_OPTS)]:
    if col in display_df.columns:
        col_config[col] = st.column_config.SelectboxColumn(options=opts, width='medium')
if 'Offer $' in display_df.columns:
    col_config['Offer $'] = st.column_config.NumberColumn(format='$%d', width='small')
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

edited = st.data_editor(
    display_df,
    column_config=col_config,
    use_container_width=True,
    hide_index=True,
    num_rows='fixed',
    key='pb_editor',
)

if st.button('💾 Save Changes', type='primary'):
    outcome_cols = {'Called?': 'called', 'Reached?': 'reached',
                    'Offer $': 'offer_amount', 'Outcome': 'outcome', 'Notes': 'notes'}
    records = []
    for i, row in edited.iterrows():
        rec = {'case_number': df_f.loc[i, 'case_number']}
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
c1, c2 = st.columns(2)
with c1:
    download_button(df_f[DISPLAY], 'probate.csv')
with c2:
    needs_skip = df_f[
        df_f.get('phone_1', pd.Series(dtype=str)).isna() |
        (df_f.get('phone_1', pd.Series(dtype=str)) == '')
    ] if 'phone_1' in df_f.columns else pd.DataFrame()
    if not needs_skip.empty:
        st.download_button(
            '📤 Propstream Upload CSV',
            to_propstream_csv(needs_skip, 'PROBATE'),
            'propstream_upload_probate.csv',
            'text/csv',
        )
