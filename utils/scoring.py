"""
Date bucket scoring — matches logic in build_workbook.py.
"""
import pandas as pd


# ── Foreclosure buckets (days to auction / days since filing) ────────────────
FC_BUCKETS = [
    (0,   7,   '🔴 0–7 Days',   'FFCDD2'),
    (8,   14,  '🟠 8–14 Days',  'FFE0B2'),
    (15,  30,  '🟡 15–30 Days', 'FFF9C4'),
    (31,  60,  '🟢 31–60 Days', 'C8E6C9'),
    (61,  9999,'⚪ 60+ Days',   'F5F5F5'),
]

# ── Probate / divorce / eviction buckets (days since filing) ─────────────────
PB_BUCKETS = [
    (0,   90,  '🔴 0–90 Days',   'FFCDD2'),
    (91,  180, '🟠 91–180 Days', 'FFE0B2'),
    (181, 365, '🟡 181–365 Days','FFF9C4'),
    (366, 9999,'🟢 365+ Days',   'C8E6C9'),
]


def fc_bucket(days) -> str:
    if pd.isna(days) or days is None: return '⚪ 60+ Days'
    d = int(days)
    for lo, hi, label, _ in FC_BUCKETS:
        if lo <= d <= hi:
            return label
    return '⚪ 60+ Days'


def pb_bucket(days) -> str:
    if pd.isna(days) or days is None: return '🟢 365+ Days'
    d = int(days)
    for lo, hi, label, _ in PB_BUCKETS:
        if lo <= d <= hi:
            return label
    return '🟢 365+ Days'


def bucket_sort_key(label: str) -> int:
    """Lower = higher priority (more urgent)."""
    order = {
        '🔴 0–7 Days': 0,   '🔴 0–90 Days': 0,
        '🟠 8–14 Days': 1,  '🟠 91–180 Days': 1,
        '🟡 15–30 Days': 2, '🟡 181–365 Days': 2,
        '🟢 31–60 Days': 3, '🟢 365+ Days': 3,
        '⚪ 60+ Days': 4,
    }
    return order.get(label, 5)


BUCKET_COLORS = {b[2]: f'#{b[3]}' for buckets in (FC_BUCKETS, PB_BUCKETS) for b in buckets}


def add_fc_bucket(df: pd.DataFrame, days_col: str = 'days_since_filing') -> pd.DataFrame:
    df = df.copy()
    df['bucket'] = df[days_col].apply(fc_bucket)
    df['bucket_sort'] = df['bucket'].apply(bucket_sort_key)
    return df.sort_values('bucket_sort')


def add_pb_bucket(df: pd.DataFrame, days_col: str = 'days_since_filing') -> pd.DataFrame:
    df = df.copy()
    df['bucket'] = df[days_col].apply(pb_bucket)
    df['bucket_sort'] = df['bucket'].apply(bucket_sort_key)
    return df.sort_values('bucket_sort')


LAND_USE_LABELS = {
    # Single-family residential
    '0100': 'SFR', '0101': 'SFR', '0102': 'SFR', '0103': 'SFR',
    '0104': 'SFR', '0105': 'SFR', '0106': 'Townhouse', '0107': 'Townhouse',
    '0108': 'SFR', '0109': 'SFR',
    # Mobile homes
    '0200': 'Mobile Home', '0201': 'Mobile Home',
    # Multi-family / apartments
    '0300': 'Multi-Family', '0309': 'Multi-Family',
    '0310': 'Apartment (10+)', '0311': 'Apartment (10+)',
    '0320': 'Multi-Family (3–9)', '0330': 'Mobile Home Park',
    '0399': 'Condo Unit',
    # Condominiums
    '0400': 'Condo', '0401': 'Condo',
    # Cooperatives
    '0500': 'Co-op',
    # Commercial / office
    '0600': 'Commercial', '0610': 'Office',
    '0611': 'Prof. Office', '0619': 'Office',
    '0620': 'Light Commercial', '0630': 'Retail Store',
    '0640': 'Shopping Center', '0650': 'Supermarket',
    '0660': 'Medical Office', '0670': 'Financial',
    '0680': 'Gas Station', '0690': 'Restaurant',
    '0699': 'Commercial',
    # Hotels / transient
    '0700': 'Hotel/Motel', '0710': 'Hotel',
    '0720': 'Motel', '0730': 'Resort',
    # Industrial
    '0800': 'Industrial', '0810': 'Light Industrial',
    '0820': 'Warehouse', '0830': 'Heavy Industrial',
    # Institutional
    '0900': 'Institutional',
    '0910': 'Religious', '0920': 'Private School',
    '0930': 'Hospital', '0940': 'Nursing Home',
    '0950': 'Assisted Living',
    # Agricultural / misc
    '1000': 'Agricultural',
    '1100': 'Timberland',
    '1140': 'Pasture',
    '1750': 'Agricultural',
    '1820': 'Agricultural',
    '1830': 'Agricultural',
    # Multi-family in 28xx-48xx range
    '2814': 'Multi-Family',
    '4830': 'Multi-Family',
    # Condos in 86xx range (HCPA alternate coding)
    '8600': 'Condo', '8601': 'Condo', '8602': 'Condo',
    '8610': 'Condo',
    # Misc
    '7100': 'Parking', '7300': 'Park/Rec', '7500': 'Gov\'t',
    '8900': 'Other',
    '9000': 'Vacant',
}

# Residential DOR code prefixes (first two digits)
_RESIDENTIAL_PREFIXES = {'01', '02', '03', '04', '05', '86'}

KEEP_LAND_USE = _RESIDENTIAL_PREFIXES   # for filtering residential-only leads


def is_residential(land_use: str) -> bool:
    """Return True if the DOR code indicates a residential property type."""
    if not land_use:
        return True  # unknown → include
    return str(land_use)[:2] in _RESIDENTIAL_PREFIXES


def is_likely_care_facility(land_use_code: str, owner_raw: str, decedent_last: str) -> bool:
    """
    Return True when a probate decedent address looks like a care facility rather
    than the decedent's own home.  Triggered when ALL of:
      1. The DOR code is commercial / institutional (not residential)
      2. The owner of record does NOT contain the decedent's surname
    """
    if not land_use_code:
        return False
    code = str(land_use_code).strip()
    prefix = code[:2]
    if prefix in _RESIDENTIAL_PREFIXES:
        return False          # it IS a residential property — not a facility
    if not decedent_last:
        return True           # non-residential and can't check name
    owner = str(owner_raw or '').upper()
    last = str(decedent_last or '').upper().strip()
    return bool(last) and last not in owner

def land_use_label(code) -> str:
    try:
        if pd.isna(code):
            return ''
    except (TypeError, ValueError):
        pass
    s = str(code).strip()
    if s in ('', 'nan', 'None', 'NA', '<NA>'):
        return ''
    return LAND_USE_LABELS.get(s, '')

