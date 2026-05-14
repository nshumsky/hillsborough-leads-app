"""
Hillsborough Distressed Property Lead System
=============================================
Streamlit multi-page app. Start here — navigate via the sidebar.
"""
import streamlit as st

st.set_page_config(
    page_title='Hillsborough Leads',
    page_icon='🏚',
    layout='wide',
    initial_sidebar_state='expanded',
)

st.title('🏚 Hillsborough Distressed Property Leads')
st.markdown("""
Welcome! Use the sidebar to navigate between lead types.

| Tab | What's in it |
|-----|-------------|
| 📊 Dashboard | KPIs, daily new filings, pipeline snapshot |
| 🔥 Hot List | Highest priority leads across all types |
| 🏚 Foreclosures | Mortgage foreclosure filings |
| 📋 Probate | Estate / probate cases |
| 💔 Divorce | Dissolution of marriage filings |
| 🏠 Evictions | Residential eviction filings |
| 📤 Skip Trace | Export queue → Propstream upload CSV |
| 📥 Import Results | Upload Propstream results → save phone numbers |
| 👥 Multi-List | People & properties on 2+ lead lists (highest priority) |
""")

st.info('👈 Select a page from the sidebar to get started.')
