import streamlit as st
import pandas as pd
import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_client

st.set_page_config(page_title='Import Propstream Results', page_icon='📥', layout='wide')
apply_branding()
st.title('📥 Import Propstream Results')
st.caption('Upload the results CSV from Propstream to save phone numbers into the database.')

st.info("""
**How to use:**
1. Run your batch skip trace in Propstream
2. Download the results CSV from Propstream
3. Upload it here — phones will be saved to all matching cases
4. Missing cases (not returned by Propstream) are flagged as **Low Equity**
""")

uploaded = st.file_uploader('Upload Propstream results CSV', type=['csv'])

if not uploaded:
    st.stop()

# ── Parse uploaded file ───────────────────────────────────────────────────────
try:
    df = pd.read_csv(uploaded, encoding='utf-8-sig')
    st.success(f'Loaded {len(df)} rows from {uploaded.name}')
except Exception as e:
    st.error(f'Could not read file: {e}')
    st.stop()

st.subheader('Preview')
st.dataframe(df.head(10), use_container_width=True, hide_index=True)

# ── Expected Propstream columns ───────────────────────────────────────────────
PHONE_COLS = [
    ('Phone 1', 'Phone 1 Type', 'Phone 1 DNC'),
    ('Phone 2', 'Phone 2 Type', 'Phone 2 DNC'),
    ('Phone 3', 'Phone 3 Type', 'Phone 3 DNC'),
    ('Phone 4', 'Phone 4 Type', 'Phone 4 DNC'),
    ('Phone 5', 'Phone 5 Type', 'Phone 5 DNC'),
]
EMAIL_COLS = ['Email 1', 'Email 2', 'Email 3', 'Email 4']
CASE_COL   = 'Case #'
ADDR_COL   = 'Street Address'

missing_cols = [c for c in [CASE_COL, ADDR_COL] if c not in df.columns]
if missing_cols:
    st.error(f'Missing expected columns: {missing_cols}. Make sure you uploaded the Propstream results file.')
    st.stop()

# ── Match and prepare records ─────────────────────────────────────────────────
if st.button('📥 Import Phones & Emails', type='primary'):
    sb = get_client()
    matched = updated = skipped = 0
    low_equity_cases = []

    # Load session map to find Low Equity (cases uploaded but not returned)
    # Try to find the most recent session file
    try:
        import json
        from pathlib import Path as P
        sessions_dir = P('/Users/jennifer/Documents/Claude/foreclosure/propstream_sessions')
        session_files = sorted(sessions_dir.glob('session_*.json'))
        session_map = {}
        if session_files:
            session_map = json.loads(session_files[-1].read_text())
    except Exception:
        session_map = {}

    returned_cases = set()

    contact_records = []
    for _, row in df.iterrows():
        case_number = str(row.get(CASE_COL, '') or '').strip()
        if not case_number:
            skipped += 1
            continue

        returned_cases.add(case_number)
        matched += 1

        phones = {}
        for i, (p_col, t_col, d_col) in enumerate(PHONE_COLS, 1):
            phone = str(row.get(p_col, '') or '').strip()
            if phone and phone.lower() not in ('', 'none', 'nan'):
                phones[f'phone_{i}']     = phone
                phones[f'phone_{i}_type'] = str(row.get(t_col, '') or '').strip()
                phones[f'phone_{i}_dnc']  = str(row.get(d_col, '') or '').strip()

        emails = {}
        for i, e_col in enumerate(EMAIL_COLS, 1):
            email = str(row.get(e_col, '') or '').strip()
            if email and email.lower() not in ('', 'none', 'nan'):
                emails[f'email_{i}'] = email

        if not phones and not emails:
            skipped += 1
            continue

        rec = {'case_number': case_number,
               'first_name': str(row.get('First Name', '') or '').strip(),
               'last_name':  str(row.get('Last Name', '') or '').strip(),
               **phones, **emails}
        contact_records.append(rec)
        updated += 1

    # Upsert contacts
    BATCH = 500
    for i in range(0, len(contact_records), BATCH):
        sb.schema('silver').table('dim_contacts').upsert(
            contact_records[i:i+BATCH], on_conflict='case_number'
        ).execute()

    # Mark Low Equity: cases in session but NOT in Propstream results
    low_equity_count = 0
    if session_map:
        for addr_norm, case_number in session_map.items():
            if case_number in returned_cases:
                continue
            # Only mark if no meaningful existing outcome
            res = sb.schema('silver').table('dim_outcomes').select('outcome') \
                    .eq('case_number', case_number).limit(1).execute()
            existing = (res.data or [{}])[0].get('outcome', '')
            if not existing or existing == 'Low Equity':
                sb.schema('silver').table('dim_outcomes').upsert(
                    {'case_number': case_number, 'outcome': 'Low Equity'},
                    on_conflict='case_number'
                ).execute()
                low_equity_count += 1

    st.success(f'✅ Done! {matched} matched, {updated} contacts saved, '
               f'{skipped} skipped, {low_equity_count} marked Low Equity')

    # Clear DB cache
    from utils.db import query_leads
from utils.branding import apply_branding
    query_leads.clear()
