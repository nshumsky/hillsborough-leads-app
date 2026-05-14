import streamlit as st
import pandas as pd
import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_leads
from utils.scoring import add_fc_bucket, add_pb_bucket
from utils.export import to_propstream_csv
from utils.branding import apply_branding

st.set_page_config(page_title='Skip Trace Export', page_icon='📤', layout='wide')
apply_branding()
st.title('📤 Skip Trace Export')
st.caption('Leads without phone numbers — upload to Propstream Bulk Skip Trace.')

# ── Collect leads needing phones ──────────────────────────────────────────────
needs_skip = []

for lead_type, bucket_fn in [
    ('foreclosure', add_fc_bucket),
    ('probate',     add_pb_bucket),
    ('divorce',     add_pb_bucket),
    ('eviction',    add_pb_bucket),
]:
    try:
        df = query_leads(lead_type)
        if df.empty:
            continue
        df = bucket_fn(df, 'days_since_filing')
        no_phone = df[
            df.get('phone_1', pd.Series(dtype=str)).isna() |
            (df.get('phone_1', pd.Series(dtype=str)) == '')
        ].copy() if 'phone_1' in df.columns else df.copy()
        no_phone['_lead_type'] = lead_type
        needs_skip.append(no_phone)
    except Exception as e:
        st.warning(f'{lead_type}: {e}')

if not needs_skip:
    st.info('All leads have phone numbers — nothing to export!')
    st.stop()

all_needs = pd.concat(needs_skip, ignore_index=True)

# ── Stats ─────────────────────────────────────────────────────────────────────
by_type = all_needs.groupby('_lead_type').size().reset_index(name='Count')
by_type.columns = ['Lead Type', 'Needs Phone']
c1, c2 = st.columns([1, 2])
with c1:
    st.metric('Total Needs Skip Trace', len(all_needs))
with c2:
    st.dataframe(by_type, hide_index=True, use_container_width=True)

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
st.subheader('Select leads to include in upload')

col_type = st.multiselect('Lead types', options=all_needs['_lead_type'].unique().tolist(),
                           default=all_needs['_lead_type'].unique().tolist())

filtered = all_needs[all_needs['_lead_type'].isin(col_type)]

# ── Preview ───────────────────────────────────────────────────────────────────
preview_cols = [c for c in ['_lead_type', 'case_number', 'bucket',
    'defendant_name', 'petitioner_name', 'party_1_name', 'tenant_name',
    'property_street', 'decedent_street', 'address_street',
    'property_city', 'decedent_city', 'address_city',
    'property_zip', 'decedent_zip', 'address_zip',
] if c in filtered.columns]

st.dataframe(filtered[preview_cols].head(50), use_container_width=True, hide_index=True)
if len(filtered) > 50:
    st.caption(f'(showing first 50 of {len(filtered)})')

st.divider()

# ── Generate Propstream CSV ───────────────────────────────────────────────────
st.subheader('Download Propstream Upload CSV')

# Build Propstream format manually since we have mixed lead types
def build_propstream_csv(df: pd.DataFrame) -> bytes:
    rows = []
    for _, row in df.iterrows():
        lt = row.get('_lead_type', '')
        # Get name
        for name_col in ['defendant_name', 'petitioner_name', 'party_1_name', 'tenant_name']:
            name = str(row.get(name_col, '') or '').strip()
            if name:
                break
        parts = name.split(' ', 1)
        first = parts[0] if parts else ''
        last  = parts[1] if len(parts) > 1 else ''
        # Get address
        for scol, ccol, zcol in [
            ('property_street',  'property_city',  'property_zip'),
            ('decedent_street',  'decedent_city',  'decedent_zip'),
            ('address_street',   'address_city',   'address_zip'),
        ]:
            street = str(row.get(scol, '') or '').strip()
            if street:
                city = str(row.get(ccol, '') or '').strip()
                zipcode = str(row.get(zcol, '') or '').strip()[:5]
                break
        else:
            street = city = zipcode = ''
        rows.append({
            'First Name':     first,
            'Last Name':      last,
            'Street Address': street,
            'City':           city,
            'State':          'FL',
            'Zip':            zipcode,
            'Source':         lt.upper(),
            'Case #':         str(row.get('case_number', '')),
        })
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    return buf.getvalue().encode('utf-8')

csv_bytes = build_propstream_csv(filtered)
st.download_button(
    label=f'⬇ Download Propstream CSV ({len(filtered)} rows)',
    data=csv_bytes,
    file_name='propstream_upload_latest.csv',
    mime='text/csv',
)
