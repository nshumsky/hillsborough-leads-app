"""
A+ Home Buyers — entry point. Redirects straight to Dashboard.
"""
import streamlit as st

st.set_page_config(
    page_title='A+ Home Buyers — Leads',
    page_icon="https://image-cdn.carrot.com/uploads/sites/78630/2024/04/A_Plus_Logo.png",
    layout='wide',
    initial_sidebar_state='expanded',
)

st.switch_page("pages/1_📊_Dashboard.py")
