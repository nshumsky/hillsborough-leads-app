"""
A+ Home Buyers — Hillsborough Distressed Property Lead System
=============================================================
Streamlit multi-page app. Start here — navigate via the sidebar.
"""
import streamlit as st

LOGO_URL = "https://image-cdn.carrot.com/uploads/sites/78630/2024/04/A_Plus_Logo.png"
NAVY     = "#002868"
STEEL    = "#7098b8"

st.set_page_config(
    page_title='A+ Home Buyers — Leads',
    page_icon=LOGO_URL,
    layout='wide',
    initial_sidebar_state='expanded',
)

# Sidebar logo (appears above page navigation)
st.logo(LOGO_URL, link="https://www.aplushomebuyer.com")

# ── Landing page ──────────────────────────────────────────────────────────────
st.image(LOGO_URL, width=320)
st.markdown(
    f"<h1 style='color:{NAVY}; margin-top:0.25rem;'>Welcome, Mike! 👋</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<h3 style='color:{STEEL}; margin-top:0;'>Hillsborough Distressed Property Leads</h3>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='color:#555; font-size:1.05rem;'>Live data from the Hillsborough Clerk — updated every weekday at 7 AM ET.</p>",
    unsafe_allow_html=True,
)

st.divider()

st.markdown("""
| Page | What's in it |
|------|-------------|
| 📊 **Dashboard** | KPIs, daily new filings, pipeline snapshot |
| 🔥 **Hot List** | Highest priority leads across all types |
| 🏚 **Foreclosures** | Mortgage foreclosure filings |
| 📋 **Probate** | Estate / probate cases |
| 💔 **Divorce** | Dissolution of marriage filings |
| 🏠 **Evictions** | Residential eviction filings |
| 📤 **Skip Trace** | Export queue → Propstream upload CSV |
| 📥 **Import Results** | Upload Propstream results → save phone numbers |
| 👥 **Multi-List** | People & properties on 2+ lead lists — highest priority |
""")

st.info('👈 Select a page from the sidebar to get started.')
