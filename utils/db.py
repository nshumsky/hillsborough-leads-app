"""
Supabase connection + cached query helpers.
Credentials come from st.secrets (Streamlit Cloud) or environment vars (local).
"""
import os
import streamlit as st
from supabase import create_client, Client
import pandas as pd


@st.cache_resource
def get_client() -> Client:
    """Singleton Supabase client — cached for the session."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError):
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        st.error("⚠️ Supabase credentials not configured. Add SUPABASE_URL and SUPABASE_KEY to `.streamlit/secrets.toml`.")
        st.stop()
    return create_client(url, key)


@st.cache_data(ttl=300)  # 5-minute cache
def query_leads(lead_type: str, days_back: int = 365) -> pd.DataFrame:
    """Fetch leads from the appropriate mart view."""
    sb = get_client()
    view_map = {
        'foreclosure': 'fact_foreclosures',
        'probate':     'fact_probate',
        'divorce':     'fact_divorces',
        'eviction':    'fact_evictions',
    }
    view = view_map.get(lead_type, 'fact_all_leads')
    res = sb.schema('gold').table(view).select('*').execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    if 'filing_date' in df.columns:
        df['filing_date'] = pd.to_datetime(df['filing_date'], errors='coerce').dt.date
    if 'days_since_filing' in df.columns:
        df['days_since_filing'] = pd.to_numeric(df['days_since_filing'], errors='coerce')
    return df


@st.cache_data(ttl=300)
def query_daily_new(days: int = 7) -> pd.DataFrame:
    sb = get_client()
    res = sb.schema('gold').table('fact_daily_new').select('*').execute()
    df = pd.DataFrame(res.data or [])
    if 'filing_date' in df.columns:
        df['filing_date'] = pd.to_datetime(df['filing_date'], errors='coerce')
    return df


@st.cache_data(ttl=300)
def query_cross_matches() -> pd.DataFrame:
    sb = get_client()
    res = sb.schema('gold').table('fact_cross_matches').select('*').execute()
    return pd.DataFrame(res.data or [])


@st.cache_data(ttl=300)
def query_multi_list_persons() -> pd.DataFrame:
    """Fetch persons appearing on 2+ lead type lists."""
    sb = get_client()
    res = sb.schema('gold').table('fact_multi_list_persons').select('*').execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    for col in ['foreclosure_first_date','probate_first_date',
                'divorce_first_date','eviction_first_date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


@st.cache_data(ttl=300)
def query_multi_list_properties() -> pd.DataFrame:
    """Fetch properties (addresses) appearing on 2+ lead type lists."""
    sb = get_client()
    res = sb.schema('gold').table('fact_multi_list_properties').select('*').execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    for col in ['foreclosure_first_date','probate_first_date',
                'divorce_first_date','eviction_first_date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    if 'assessed_value' in df.columns:
        df['assessed_value'] = pd.to_numeric(df['assessed_value'], errors='coerce')
    if 'survive_amount' in df.columns:
        df['survive_amount'] = pd.to_numeric(df['survive_amount'], errors='coerce')
    return df


@st.cache_data(ttl=300)
def query_lien_detail(address: str) -> pd.DataFrame:
    """Fetch all individual lien rows for a given property address."""
    sb = get_client()
    norm = address.lower().strip()
    res = sb.schema('gold').table('fact_lien_detail').select('*').eq('address', norm).execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    if 'recorded_date' in df.columns:
        df['recorded_date'] = pd.to_datetime(df['recorded_date'], errors='coerce')
    if 'amount' in df.columns:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    return df


def upsert_outcome(case_number: str, field: str, value):
    """Update a single outcome field for a case."""
    sb = get_client()
    sb.schema('silver').table('dim_outcomes').upsert(
        {'case_number': case_number, field: value},
        on_conflict='case_number'
    ).execute()
    # Clear cache so next load picks up the change
    query_leads.clear()


def upsert_outcomes_bulk(records: list[dict]):
    """Bulk upsert outcomes (from data_editor changes)."""
    sb = get_client()
    sb.schema('silver').table('dim_outcomes').upsert(
        records, on_conflict='case_number'
    ).execute()
    query_leads.clear()


def get_kpis() -> dict:
    """Dashboard KPI counts."""
    sb = get_client()
    kpis = {}
    for lead_type in ['foreclosure', 'probate', 'divorce', 'eviction']:
        res = sb.schema('silver').table('fact_cases').select('case_number', count='exact') \
                .eq('lead_type', lead_type).execute()
        kpis[f'total_{lead_type}'] = res.count or 0

    # New today / this week
    from datetime import date, timedelta
    today_str = date.today().isoformat()
    week_str  = (date.today() - timedelta(days=7)).isoformat()
    res = sb.schema('silver').table('fact_cases').select('case_number', count='exact') \
            .gte('filing_date', today_str).execute()
    kpis['new_today'] = res.count or 0
    res = sb.schema('silver').table('fact_cases').select('case_number', count='exact') \
            .gte('filing_date', week_str).execute()
    kpis['new_this_week'] = res.count or 0
    return kpis
