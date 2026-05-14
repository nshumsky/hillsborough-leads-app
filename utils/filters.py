"""
Shared sidebar filter components for all lead pages.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta


def date_range_filter(df: pd.DataFrame, col: str = 'filing_date') -> pd.DataFrame:
    """Sidebar date range filter. Returns filtered df."""
    if col not in df.columns or df.empty:
        return df
    min_d = df[col].min()
    max_d = df[col].max()
    if pd.isna(min_d) or pd.isna(max_d):
        return df
    st.sidebar.subheader('📅 Date Range')
    start = st.sidebar.date_input('From', value=date.today() - timedelta(days=90),
                                   min_value=min_d.date(), max_value=max_d.date())
    end   = st.sidebar.date_input('To', value=date.today(),
                                   min_value=min_d.date(), max_value=max_d.date())
    return df[(df[col].dt.date >= start) & (df[col].dt.date <= end)]


def city_filter(df: pd.DataFrame, city_col: str) -> pd.DataFrame:
    """Sidebar city multiselect. Returns filtered df."""
    if city_col not in df.columns or df.empty:
        return df
    cities = sorted(df[city_col].dropna().unique().tolist())
    if not cities:
        return df
    selected = st.sidebar.multiselect('🏙️ City', options=cities, default=[])
    if selected:
        df = df[df[city_col].isin(selected)]
    return df


def outcome_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Sidebar outcome filter — hide closed leads option."""
    if 'outcome' not in df.columns or df.empty:
        return df
    hide_closed = st.sidebar.checkbox('Hide closed leads', value=True)
    if hide_closed:
        closed = {'Dead', 'Not Interested', 'No Property', 'Cancelled', 'Low Equity'}
        df = df[~df['outcome'].isin(closed)]
    return df


def bucket_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Sidebar bucket multiselect."""
    if 'bucket' not in df.columns or df.empty:
        return df
    buckets = df['bucket'].dropna().unique().tolist()
    # Sort by priority
    from utils.scoring import bucket_sort_key
    buckets = sorted(buckets, key=bucket_sort_key)
    selected = st.sidebar.multiselect('⏱️ Date Bucket', options=buckets, default=buckets)
    if selected:
        df = df[df['bucket'].isin(selected)]
    return df


def has_phone_filter(df: pd.DataFrame, phone_col: str = 'phone_1') -> pd.DataFrame:
    """Sidebar toggle: show only leads with a phone number."""
    if phone_col not in df.columns or df.empty:
        return df
    only_phone = st.sidebar.checkbox('📞 Has phone only', value=False)
    if only_phone:
        df = df[df[phone_col].notna() & (df[phone_col] != '')]
    return df


def apply_all_filters(df: pd.DataFrame, date_col: str = 'filing_date',
                       city_col: str | None = None) -> pd.DataFrame:
    """Apply all standard sidebar filters in order."""
    df = date_range_filter(df, date_col)
    df = outcome_filter(df)
    if city_col and city_col in df.columns:
        df = city_filter(df, city_col)
    df = bucket_filter(df)
    df = has_phone_filter(df)
    return df
