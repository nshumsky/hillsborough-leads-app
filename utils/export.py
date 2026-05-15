"""
CSV export helpers — Propstream format and generic CSV download.
"""
import io
import pandas as pd
import streamlit as st


# Exact PropStream bulk skip-trace upload column order
PROPSTREAM_COLS = [
    'First Name', 'Last Name', 'Email', 'Phone', 'Mobile Phone', 'Landline',
    'Street Address', 'City', 'State', 'Zip',
    'Mail Street Address', 'Mail City', 'Mail State', 'Mail Zip',
    'Mail Address Same', 'Type', 'Status',
]


def to_propstream_csv(df: pd.DataFrame, lead_type: str) -> bytes:
    """
    Convert a leads DataFrame into the exact PropStream bulk skip-trace
    upload format (matches the Excel export template).
    Returns CSV bytes.
    """
    name_parts = _split_name_col(df)

    street = _coalesce(df, ['property_street', 'decedent_street', 'address_street', 'street'])
    city   = _coalesce(df, ['property_city',   'decedent_city',   'address_city',   'city'])
    zip_   = _coalesce(df, ['property_zip',    'decedent_zip',    'address_zip',    'zip'])

    out = pd.DataFrame({
        'First Name':        name_parts['first'],
        'Last Name':         name_parts['last'],
        'Email':             '',
        'Phone':             df.get('phone_1', pd.Series([''] * len(df), index=df.index)),
        'Mobile Phone':      '',
        'Landline':          '',
        'Street Address':    street,
        'City':              city,
        'State':             'FL',
        'Zip':               zip_,
        'Mail Street Address': '',
        'Mail City':         '',
        'Mail State':        '',
        'Mail Zip':          '',
        'Mail Address Same': 'Yes',
        'Type':              'Owner',
        'Status':            'New',
    })

    buf = io.StringIO()
    out.to_csv(buf, index=False)
    return buf.getvalue().encode('utf-8')


def _coalesce(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Return first non-empty series found among col names."""
    for col in cols:
        if col in df.columns:
            return df[col].fillna('')
    return pd.Series([''] * len(df), index=df.index)


def _split_name_col(df: pd.DataFrame) -> dict:
    """Best-effort split of owner name into first/last."""
    for col in ['defendant_name', 'petitioner_name', 'party_1_name',
                'tenant_name', 'owner_name', 'primary_name']:
        if col in df.columns:
            def split(name):
                parts = str(name or '').strip().split(' ', 1)
                return parts[0], parts[1] if len(parts) > 1 else ''
            pairs = df[col].apply(split)
            return {
                'first': pairs.apply(lambda x: x[0]),
                'last':  pairs.apply(lambda x: x[1]),
            }
    return {
        'first': pd.Series([''] * len(df), index=df.index),
        'last':  pd.Series([''] * len(df), index=df.index),
    }


def download_button(df: pd.DataFrame, filename: str, label: str = '⬇ Download CSV'):
    """Render a Streamlit download button for a DataFrame."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    st.download_button(label, buf.getvalue().encode(), filename, 'text/csv')
