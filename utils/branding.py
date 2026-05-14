"""
A+ Home Buyers brand constants and shared page header helper.
Call apply_branding() at the top of every page (after set_page_config).
"""
import streamlit as st

LOGO_URL   = "https://image-cdn.carrot.com/uploads/sites/78630/2024/04/A_Plus_Logo.png"
NAVY       = "#002868"
STEEL      = "#7098b8"
SITE_URL   = "https://www.aplushomebuyer.com"


def apply_branding():
    """Inject logo into sidebar. Call once per page after set_page_config."""
    st.logo(LOGO_URL, link=SITE_URL)
