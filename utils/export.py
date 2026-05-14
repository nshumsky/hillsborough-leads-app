"""
CSV export helpers — Propstream format and generic CSV download.
"""
import io
import pandas as pd
import streamlit as st


PROPSTREAM_COLS = [
    'First Name', 'Last Name', 'Street Address', 'City', 'State', 'Zip',
    'Source', 'Case #'
]


def to_propstream_csv(df: pd.DataFrame, lead_type: str) -> bytes:
    """
    Convert a leads DataFrame into the Propstream bulk skip-trace upload format.
    Returns CSV bytes.
    """
    name_parts = _split_name_col(df)
    out = pd.DataFrame({
        'First Name':     name_parts['first'],
        'Last Name':      name_parts['last'],
        'Street Address': df.get('property_street', df.get('decedent_street',
                          df.get('address_street', df.get('street', '')))),
        'City':           df.get('property_city', df.get('decedent_city',
                          df.get('address_city', df.get('city', '')))),
        'State':          'FL',
        'Zip':            df.get('property_zip', df.get('decedent_zip',
                          df.get('address_zip', df.get('zip', '')))),
        'Source':         lead_type.upper(),
        'Case #':         df.get('case_number', ''),
    })
    buf = io.StringIO()
    out.to_csv(buf, index=False)
    return buf.getvalue().encode('utf-8')


def _split_name_col(df: pd.DataFrame) -> dict:
    """Best-effort split of defendant_name / petitioner_name into first/last."""
    name_col = None
    for col in ['defendant_name', 'petitioner_name', 'party_1_name',
                'tenant_name', 'primary_name']:
        if col in df.columns:
            name_col = col
            break

    if name_col is None:
        return {'first': pd.Series([''] * len(df)), 'last': pd.Series([''] * len(df))}

    def split(name):
        parts = str(name or '').strip().split(' ', 1)
        return parts[0], parts[1] if len(parts) > 1 else ''

    pairs = df[name_col].apply(split)
    return {
        'first': pairs.apply(lambda x: x[0]),
        'last':  pairs.apply(lambda x: x[1]),
    }


def download_button(df: pd.DataFrame, filename: str, label: str = '⬇ Download CSV'):
    """Render a Streamlit download button for a DataFrame."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    st.download_button(label, buf.getvalue().encode(), filename, 'text/csv')
