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
def query_auctions() -> pd.DataFrame:
    """Fetch auctions from gold.fact_auctions."""
    sb = get_client()
    res = sb.schema('gold').table('fact_auctions').select('*').execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    for col in ['sale_date', 'hcpa_sale_date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
    for col in ['days_to_sale', 'judgment', 'assessed', 'just_value',
                'assessed_value', 'beds', 'baths', 'heated_sqft']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


@st.cache_data(ttl=300)
def query_daily_new(days: int = 7) -> pd.DataFrame:
    sb = get_client()
    res = sb.schema('gold').table('fact_daily_new').select('*').execute()
    df = pd.DataFrame(res.data or [])
    if 'filing_date' in df.columns:
        df['filing_date'] = pd.to_datetime(df['filing_date'], errors='coerce').dt.date
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
    if 'wiped_amount' in df.columns:
        df['wiped_amount'] = pd.to_numeric(df['wiped_amount'], errors='coerce')
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


@st.cache_data(ttl=300)
def query_liens_by_address() -> dict:
    """
    Load all actionable liens from silver.fact_liens and return a dict:
        address (normalized) → {
            'detail':        "1st Mtg ($216k foreclosing), HOA ($2,500 survives)",
            'survive_total': 218602.0,
            'wiped_total':   0.0,
            'survive_count': 2,
            'wiped_count':   0,
        }
    Excludes RELEASED, INFO, REVIEW statuses.
    """
    sb = get_client()
    PAGE = 1000
    offset = 0
    rows = []
    while True:
        res = sb.schema('silver').table('fact_liens') \
                .select('address,label,amount,status,doc_type') \
                .not_.in_('status', ['RELEASED', 'INFO', 'REVIEW']) \
                .range(offset, offset + PAGE - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE

    if not rows:
        return {}

    # Group by address
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in rows:
        addr = (r.get('address') or '').lower().strip()
        if addr:
            grouped[addr].append(r)

    def _short_label(row):
        label = str(row.get('label') or row.get('doc_type') or 'Lien').strip()
        # Shorten common labels
        replacements = [
            ('1st Mortgage (foreclosing lien)', '1st Mtg'),
            ('Junior Mortgage', 'Jr Mtg'),
            ('Mortgage — Satisfied', 'Mtg (sat)'),
            ('Release / Satisfaction', 'Release'),
            ('DOMESTIC RELATIONS JUDGMENT', 'Dom. Rel. Judgment'),
            ('JUDGMENT', 'Judgment'),
        ]
        for full, short in replacements:
            if full.lower() in label.lower():
                label = short
                break
        return label

    def _status_tag(status):
        return {'FORECLOSING LIEN': 'foreclosing', 'SURVIVES': 'survives', 'WIPED': 'wiped'}.get(status, status.lower())

    result = {}
    for addr, liens in grouped.items():
        # Sort: foreclosing first, survives next, wiped last
        order = {'FORECLOSING LIEN': 0, 'SURVIVES': 1, 'WIPED': 2}
        liens_sorted = sorted(liens, key=lambda x: order.get(x.get('status', ''), 3))

        parts = []
        survive_total = 0.0
        wiped_total = 0.0
        survive_count = 0
        wiped_count = 0

        for lien in liens_sorted:
            status = lien.get('status', '')
            amt = lien.get('amount')
            label = _short_label(lien)
            tag = _status_tag(status)

            if status in ('FORECLOSING LIEN', 'SURVIVES'):
                survive_count += 1
                if amt:
                    survive_total += float(amt)
                    parts.append(f"{label} (${amt:,.0f} {tag})")
                else:
                    parts.append(f"{label} ({tag})")
            elif status == 'WIPED':
                wiped_count += 1
                if amt:
                    wiped_total += float(amt)
                    parts.append(f"{label} (${amt:,.0f} wiped)")
                else:
                    parts.append(f"{label} (wiped)")

        result[addr] = {
            'detail':        ', '.join(parts) if parts else '',
            'survive_total': survive_total,
            'wiped_total':   wiped_total,
            'survive_count': survive_count,
            'wiped_count':   wiped_count,
        }

    return result


@st.cache_data(ttl=300)
def query_annotations(case_number: str | None = None, address: str | None = None) -> pd.DataFrame:
    """Fetch annotations for a case or address."""
    sb = get_client()
    q = sb.schema('silver').table('dim_annotations').select('*')
    if case_number:
        q = q.eq('case_number', case_number)
    if address:
        q = q.eq('address', address.lower().strip())
    res = q.order('created_at', desc=True).execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
    return df


def upsert_annotation(case_number: str | None, address: str | None,
                      tag: str | None, note: str | None,
                      created_by: str = 'mike') -> dict:
    """Insert a new annotation row. Returns the inserted row."""
    sb = get_client()
    record = {
        'case_number': case_number or None,
        'address':     address.lower().strip() if address else None,
        'tag':         tag or None,
        'note':        note or None,
        'created_by':  created_by,
        # updated_at is set by DB default — omitting it avoids writing the string "now()"
    }
    res = sb.schema('silver').table('dim_annotations').insert(record).execute()
    query_annotations.clear()
    return res.data[0] if res.data else {}


def delete_annotation(annotation_id: int):
    """Delete an annotation by ID."""
    sb = get_client()
    sb.schema('silver').table('dim_annotations').delete().eq('id', annotation_id).execute()
    query_annotations.clear()


@st.cache_data(ttl=600)
def query_tax_delinquent() -> pd.DataFrame:
    """Fetch tax delinquent certificate records."""
    sb = get_client()
    res = sb.schema('silver').table('dim_tax_delinquent').select('*').execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    if 'amount_due' in df.columns:
        df['amount_due'] = pd.to_numeric(df['amount_due'], errors='coerce')
    if 'file_date' in df.columns:
        df['file_date'] = pd.to_datetime(df['file_date'], errors='coerce').dt.date
    return df


@st.cache_data(ttl=600)
def query_code_violations(status: str | None = None) -> pd.DataFrame:
    """Fetch code enforcement violations."""
    sb = get_client()
    q = sb.schema('silver').table('dim_code_violations').select('*')
    if status:
        q = q.eq('status', status)
    res = q.order('opened_date', desc=True).execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    for col in ['opened_date', 'closed_date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
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
    # The Clerk posts filings dated the previous business day, so "today" is the
    # most recent filing_date in the DB — not CURRENT_DATE.
    from datetime import timedelta
    latest_res = sb.schema('silver').table('fact_cases') \
                   .select('filing_date').order('filing_date', desc=True).limit(1).execute()
    if latest_res.data:
        import datetime
        latest_date = datetime.date.fromisoformat(latest_res.data[0]['filing_date'])
    else:
        import datetime
        latest_date = datetime.date.today()

    latest_str = latest_date.isoformat()
    week_str   = (latest_date - timedelta(days=7)).isoformat()

    res = sb.schema('silver').table('fact_cases').select('case_number', count='exact') \
            .eq('filing_date', latest_str).execute()
    kpis['new_today'] = res.count or 0
    res = sb.schema('silver').table('fact_cases').select('case_number', count='exact') \
            .gte('filing_date', week_str).execute()
    kpis['new_this_week'] = res.count or 0
    kpis['latest_filing_date'] = latest_str
    return kpis
