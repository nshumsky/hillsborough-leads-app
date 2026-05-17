"""
utils/github.py
===============
Trigger GitHub Actions workflows from the Streamlit app.
Requires GITHUB_TOKEN in st.secrets (PAT with actions:write scope).
"""
import streamlit as st
import requests
from datetime import datetime, timezone

REPO  = 'nshumsky/hillsborough-leads'
API   = 'https://api.github.com'


def _headers() -> dict:
    token = st.secrets.get('GITHUB_TOKEN', '')
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def trigger_process_results() -> bool:
    """Dispatch process_results.yml on main. Returns True on success."""
    url = f'{API}/repos/{REPO}/actions/workflows/process_results.yml/dispatches'
    r = requests.post(url, headers=_headers(), json={'ref': 'main'}, timeout=10)
    return r.status_code == 204


def get_last_run(workflow: str = 'process_results.yml') -> dict | None:
    """Return the most recent run of a workflow (status, conclusion, timing)."""
    url = f'{API}/repos/{REPO}/actions/workflows/{workflow}/runs'
    r = requests.get(url, headers=_headers(), params={'per_page': 1}, timeout=10)
    if r.status_code != 200:
        return None
    runs = r.json().get('workflow_runs', [])
    if not runs:
        return None
    run = runs[0]
    started = run.get('run_started_at') or run.get('created_at', '')
    try:
        dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
        ago_min = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
        ago = f'{ago_min}m ago' if ago_min < 60 else f'{ago_min // 60}h {ago_min % 60}m ago'
    except Exception:
        ago = started
    return {
        'status':     run.get('status'),      # queued / in_progress / completed
        'conclusion': run.get('conclusion'),  # success / failure / None
        'ago':        ago,
        'url':        run.get('html_url', ''),
    }
