"""
Tax Delinquent Certificates — Hillsborough County distressed property signals.
"""
import streamlit as st
import pandas as pd
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import query_tax_delinquent
from utils.branding import apply_branding

st.set_page_config(page_title='Tax Delinquent', page_icon='🧾', layout='wide')
apply_branding()
st.title('🧾 Tax Delinquent')
st.caption('Hillsborough County properties with delinquent tax certificates — strong signal of financial distress.')

try:
    tax = query_tax_delinquent()
except Exception as e:
    tax = pd.DataFrame()
    st.warning(f'Could not load tax certificates: {e}')

# ── Manual upload ──────────────────────────────────────────────────────────────
with st.expander('📤 Upload tax certificate CSV', expanded=tax.empty):
    st.markdown(
        "The Hillsborough Tax Collector publishes the delinquent list each year "
        "around **late May / early June** after the annual certificate sale.\n\n"
        "**How to get the file:**\n"
        "1. Go to **[lienhub.com/county/hillsborough/certsale/main](https://lienhub.com/county/hillsborough/certsale/main)** "
        "→ *Advertised List* (available ~2 weeks before the sale)\n"
        "2. Or go to **[hillsborough.county-taxes.com/public/reports/real_estate](https://hillsborough.county-taxes.com/public/reports/real_estate)** "
        "→ *Tax Sale Downloads* (available after the sale)\n"
        "3. Download the CSV, then upload it here."
    )
    uploaded = st.file_uploader('Choose CSV file', type=['csv'], key='tax_upload')
    if uploaded:
        try:
            upload_df = pd.read_csv(uploaded, dtype=str)
            st.success(f'Loaded {len(upload_df):,} rows — previewing first 5:')
            st.dataframe(upload_df.head(), use_container_width=True)

            year_input = st.number_input('Tax year', min_value=2018,
                                         max_value=2030, value=2025, step=1)
            if st.button('💾 Load into database', type='primary'):
                tmp = Path('/tmp/tax_cert_upload.csv')
                upload_df.to_csv(tmp, index=False)
                result = subprocess.run(
                    [sys.executable,
                     str(Path(__file__).parent.parent.parent /
                         'foreclosure' / 'fetch_tax_delinquent.py'),
                     '--file', str(tmp), '--year', str(year_input)],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    st.success(result.stdout or 'Loaded successfully.')
                    query_tax_delinquent.clear()
                    st.rerun()
                else:
                    st.error(result.stderr or result.stdout or 'Load failed.')
        except Exception as e:
            st.error(f'Could not parse file: {e}')

if tax.empty:
    st.info(
        "No tax delinquent data yet. "
        "Use the upload panel above once the annual certificate list is published "
        "(typically late May / early June each year)."
    )
    st.stop()

# ── Metrics ────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric('Certificate Records', len(tax))
if 'amount_due' in tax.columns:
    c2.metric('Total Amount Due', f"${tax['amount_due'].sum():,.0f}")
if 'year' in tax.columns:
    years = sorted(tax['year'].dropna().unique())
    c3.metric('Years', f"{min(years)}–{max(years)}" if len(years) > 1 else str(years[0]))

st.divider()

# ── Filters ────────────────────────────────────────────────────────────────────
st.sidebar.header('Filters')
if 'year' in tax.columns:
    year_opts = sorted(tax['year'].dropna().unique().tolist(), reverse=True)
    sel_years = st.sidebar.multiselect('Tax Year', year_opts, default=year_opts)
    if sel_years:
        tax = tax[tax['year'].isin(sel_years)]

st.caption(f'{len(tax):,} certificates shown')

# ── Table ──────────────────────────────────────────────────────────────────────
show_cols = [c for c in [
    'year', 'folio', 'cert_number', 'amount_due', 'owner_raw',
    'address_raw', 'file_date',
] if c in tax.columns]

col_cfg = {}
if 'amount_due' in tax.columns:
    col_cfg['amount_due'] = st.column_config.NumberColumn('Amount Due', format='$%,.0f')

st.dataframe(
    tax[show_cols].sort_values('amount_due', ascending=False) if 'amount_due' in tax.columns else tax[show_cols],
    column_config=col_cfg,
    use_container_width=True,
    hide_index=True,
)

st.download_button('⬇️ Download CSV', tax[show_cols].to_csv(index=False), 'tax_delinquent.csv', 'text/csv')
