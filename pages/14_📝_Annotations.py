"""
Annotations — add notes and tags to any case or address.
Quick-access log of all activity and observations.
"""
import streamlit as st
import pandas as pd
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_client, query_annotations, upsert_annotation, delete_annotation
from utils.branding import apply_branding, NAVY, STEEL

st.set_page_config(page_title='Annotations', page_icon='📝', layout='wide')
apply_branding()

st.markdown(f"<h2 style='color:{NAVY}; margin-bottom:0;'>📝 Annotations</h2>",
            unsafe_allow_html=True)
st.caption('Notes and tags on cases or addresses — visible across all pages')

# ── Add new annotation ────────────────────────────────────────────────────────
with st.expander('➕ Add New Annotation', expanded=True):
    col1, col2 = st.columns(2)
    case_input    = col1.text_input('Case Number (optional)', placeholder='e.g. 2024-CA-012345')
    address_input = col2.text_input('Address (optional)',     placeholder='e.g. 123 Main St')

    col3, col4 = st.columns([1, 3])
    TAG_OPTIONS = [
        '', 'Hot Lead', 'Called', 'Reached', 'Not Interested',
        'Skip', 'Watch', 'In Negotiation', 'Under Contract', 'Closed',
        'Absentee', 'Vacant', 'Code Violation', 'Tax Delinquent',
    ]
    tag_input  = col3.selectbox('Tag', TAG_OPTIONS)
    note_input = col4.text_area('Note', height=80, placeholder='Write any observation here…')

    if st.button('💾 Save Annotation', type='primary'):
        if not case_input and not address_input:
            st.warning('Enter a case number or address to attach this annotation to.')
        elif not tag_input and not note_input.strip():
            st.warning('Add a tag or note before saving.')
        else:
            upsert_annotation(
                case_number=case_input.strip() or None,
                address=address_input.strip() or None,
                tag=tag_input or None,
                note=note_input.strip() or None,
            )
            st.success('Annotation saved!')
            st.rerun()

st.divider()

# ── View all annotations ──────────────────────────────────────────────────────
st.subheader('📋 All Annotations')

# Search / filter
col_s1, col_s2, col_s3 = st.columns(3)
search_case    = col_s1.text_input('Filter by case number', placeholder='Partial match OK')
search_address = col_s2.text_input('Filter by address',     placeholder='Partial match OK')
search_tag     = col_s3.text_input('Filter by tag',         placeholder='e.g. Hot Lead')

try:
    annotations = query_annotations()
except Exception as e:
    annotations = pd.DataFrame()
    st.warning(f'Could not load annotations: {e}')

if annotations.empty:
    st.info('No annotations yet. Add one above to get started.')
else:
    # Apply filters
    filtered = annotations.copy()
    if search_case.strip():
        filtered = filtered[
            filtered['case_number'].fillna('').str.contains(search_case.strip(), case=False)
        ]
    if search_address.strip():
        filtered = filtered[
            filtered['address'].fillna('').str.contains(search_address.strip(), case=False)
        ]
    if search_tag.strip():
        filtered = filtered[
            filtered['tag'].fillna('').str.contains(search_tag.strip(), case=False)
        ]

    st.caption(f'{len(filtered)} annotation(s)')

    # Display with delete buttons
    for _, row in filtered.iterrows():
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1.5, 4, 0.8])
            c1.caption(row.get('case_number') or '—')
            c2.caption(str(row.get('address') or '—').title())
            tag = row.get('tag') or ''
            tag_color = {
                'Hot Lead': '🔴', 'Called': '📞', 'Reached': '✅',
                'Not Interested': '❌', 'Skip': '⏭️', 'Watch': '👀',
                'In Negotiation': '🤝', 'Under Contract': '📝', 'Closed': '🎉',
                'Absentee': '🔑', 'Vacant': '🏚️',
                'Code Violation': '🚨', 'Tax Delinquent': '🏛️',
            }.get(tag, '🏷️')
            c3.write(f'{tag_color} {tag}' if tag else '—')
            c4.write(row.get('note') or '—')
            ts = row.get('created_at')
            ts_str = ts.strftime('%m/%d %H:%M') if hasattr(ts, 'strftime') else str(ts or '')[:16]
            if c5.button('🗑️', key=f"del_{row['id']}", help='Delete this annotation'):
                delete_annotation(int(row['id']))
                st.success('Deleted.')
                st.rerun()
            st.caption(f'_by {row.get("created_by","mike")} · {ts_str}_')
        st.divider()

    # Bulk download
    csv = annotations.to_csv(index=False)
    st.download_button('⬇️ Export All Annotations', csv, 'annotations.csv', 'text/csv')
