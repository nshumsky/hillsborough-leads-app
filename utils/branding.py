"""
A+ Home Buyers brand constants and shared page header helper.
Call apply_branding() at the top of every page (after set_page_config).
"""
import streamlit as st

LOGO_URL   = "https://image-cdn.carrot.com/uploads/sites/78630/2024/04/A_Plus_Logo.png"
NAVY       = "#002868"
STEEL      = "#7098b8"
SITE_URL   = "https://www.aplushomebuyer.com"

_BRANDING_CSS = """
<style>
/* ── Make sidebar logo much larger ─────────────────────────── */
[data-testid="stSidebarHeader"] {
    padding: 1.5rem 1.25rem 1rem 1.25rem !important;
    min-height: 0 !important;
}
[data-testid="stSidebarHeader"] img {
    height: auto !important;
    max-height: 200px !important;
    width: 100% !important;
    object-fit: contain !important;
}

/* ── Hide the auto-generated "app" nav entry (from app.py) ─── */
[data-testid="stSidebarNavItems"] > li:first-child {
    display: none !important;
}
</style>
"""


def apply_branding():
    """Inject large logo + hide stray 'app' nav entry. Call after set_page_config."""
    st.logo(LOGO_URL, link=SITE_URL, size="large")
    st.markdown(_BRANDING_CSS, unsafe_allow_html=True)
