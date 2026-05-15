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
    '0100': 'SFR', '0101': 'SFR', '0102': 'SFR', '0104': 'SFR',
    '0106': 'Townhouse', '0107': 'Townhouse',
    '0200': 'Mobile Home',
    '0400': 'Condo',
    '0800': 'Multi-Family', '0802': 'Duplex', '0803': 'Triplex', '0804': 'Quadplex',
    '1000': 'Commercial',
}

KEEP_LAND_USE = {'01', '03', '08'}   # SFR, multi-family 10+, multi-family <10

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

def is_residential(land_use: str) -> bool:
    if not land_use:
        return True  # unknown → include
    return str(land_use)[:2] in KEEP_LAND_USE
