"""Global stylesheet injection.

Called once per session from app.py right after st.set_page_config.
Defines brand tokens as CSS variables and applies them to Streamlit's default
DOM. Streamlit class names drift between versions, so selectors aim at multiple
test-id variants where it matters (chat avatars, banners).
"""
from __future__ import annotations

import streamlit as st


_CSS = """
<style>
:root {
  --rs-primary: #2563EB; --rs-primary-700: #1D4ED8; --rs-primary-50: #EFF6FF;
  --rs-success: #15803D; --rs-success-bg: #DCFCE7;
  --rs-warning: #B45309; --rs-warning-bg: #FEF3C7;
  --rs-danger:  #B91C1C; --rs-danger-bg:  #FEE2E2;
  --rs-info:    #1D4ED8; --rs-info-bg:    #DBEAFE;
  --rs-ink: #0F172A; --rs-ink-2: #475569; --rs-ink-3: #94A3B8;
  --rs-surface: #FFFFFF; --rs-surface-2: #F8FAFC; --rs-surface-3: #F1F5F9;
  --rs-border: #E2E8F0; --rs-border-strong: #CBD5E1;
  --rs-radius: 12px; --rs-radius-sm: 8px;
  --rs-shadow: 0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06);
  --rs-shadow-lg: 0 4px 12px rgba(15,23,42,.06), 0 2px 6px rgba(15,23,42,.04);
}

/* ---------- Typography ---------- */
.stApp h1 { font-size: 28px; font-weight: 600; letter-spacing: -0.015em; color: var(--rs-ink); }
.stApp h2 { font-size: 22px; font-weight: 600; letter-spacing: -0.01em; color: var(--rs-ink); }
.stApp h3 { font-size: 17px; font-weight: 600; color: var(--rs-ink); margin-bottom: 4px; }
.stApp p, .stApp li, .stApp label { color: var(--rs-ink); font-size: 15px; line-height: 1.55; }
.stApp [data-testid="stCaptionContainer"], .stApp small { color: var(--rs-ink-3); font-size: 13px; }

/* ---------- Card surface (st.container with border) ---------- */
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
    padding: 4px 4px;
}
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: var(--rs-radius) !important;
    border-color: var(--rs-border) !important;
    background: var(--rs-surface);
    box-shadow: var(--rs-shadow);
}

/* ---------- Buttons ---------- */
.stButton button {
    border-radius: var(--rs-radius-sm) !important;
    font-weight: 500 !important;
    transition: background-color .12s ease, border-color .12s ease, transform .04s ease;
}
.stButton button[kind="primary"], .stButton button[kind="primaryFormSubmit"] {
    background: var(--rs-primary) !important;
    border: 1px solid var(--rs-primary) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}
.stButton button[kind="primary"]:hover, .stButton button[kind="primaryFormSubmit"]:hover {
    background: var(--rs-primary-700) !important;
    border-color: var(--rs-primary-700) !important;
}
.stButton button[kind="secondary"], .stButton button[kind="secondaryFormSubmit"] {
    background: var(--rs-surface) !important;
    color: var(--rs-ink-2) !important;
    border: 1px solid var(--rs-border-strong) !important;
}
.stButton button[kind="secondary"]:hover, .stButton button[kind="secondaryFormSubmit"]:hover {
    background: var(--rs-surface-2) !important;
    color: var(--rs-ink) !important;
}

/* ---------- Banners (st.success / .warning / .info / .error) ---------- */
[data-baseweb="notification"] { border-radius: var(--rs-radius-sm) !important; }
div[data-testid="stAlert"][kind="success"],
div[data-testid="stNotification"][kind="success"] {
    background: var(--rs-success-bg) !important; color: var(--rs-success) !important;
    border-left: 3px solid var(--rs-success) !important;
}
div[data-testid="stAlert"][kind="warning"],
div[data-testid="stNotification"][kind="warning"] {
    background: var(--rs-warning-bg) !important; color: var(--rs-warning) !important;
    border-left: 3px solid var(--rs-warning) !important;
}
div[data-testid="stAlert"][kind="info"],
div[data-testid="stNotification"][kind="info"] {
    background: var(--rs-info-bg) !important; color: var(--rs-info) !important;
    border-left: 3px solid var(--rs-info) !important;
}
div[data-testid="stAlert"][kind="error"],
div[data-testid="stNotification"][kind="error"] {
    background: var(--rs-danger-bg) !important; color: var(--rs-danger) !important;
    border-left: 3px solid var(--rs-danger) !important;
}

/* ---------- Chat avatars (override Streamlit default tints) ---------- */
[data-testid="stChatMessageAvatarUser"],
[data-testid="chatAvatarIcon-user"] {
    background-color: var(--rs-primary) !important;
    color: #FFFFFF !important;
}
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="chatAvatarIcon-assistant"] {
    background-color: var(--rs-ink) !important;
    color: #FFFFFF !important;
}
[data-testid="stChatMessageAvatarUser"] svg,
[data-testid="chatAvatarIcon-user"] svg,
[data-testid="stChatMessageAvatarAssistant"] svg,
[data-testid="chatAvatarIcon-assistant"] svg {
    fill: #FFFFFF !important;
}

/* ---------- Custom card chrome ---------- */
.rs-card-head {
    display: flex; align-items: center; gap: 12px;
    padding: 4px 0 6px 0;
}
.rs-card-icon {
    width: 36px; height: 36px; border-radius: 10px;
    background: var(--rs-primary-50); color: var(--rs-primary);
    display: inline-flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.rs-card-icon .material-symbols-outlined { font-size: 22px; }
.rs-card-title-block { display: flex; flex-direction: column; line-height: 1.25; }
.rs-card-title { font-size: 17px; font-weight: 600; color: var(--rs-ink); }
.rs-card-subtitle { font-size: 13px; color: var(--rs-ink-2); margin-top: 2px; }

/* ---------- Chips (quick actions) ---------- */
.rs-chip-row {
    display: flex; gap: 8px; flex-wrap: wrap;
    margin: 4px 0 12px 0;
}
.rs-chip-row .stButton button {
    background: var(--rs-surface) !important;
    border: 1px solid var(--rs-border) !important;
    color: var(--rs-ink-2) !important;
    border-radius: 9999px !important;
    padding: 4px 14px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
.rs-chip-row .stButton button:hover {
    background: var(--rs-primary-50) !important;
    border-color: var(--rs-primary) !important;
    color: var(--rs-primary) !important;
}

/* ---------- Hero metric (balance view) ---------- */
.rs-hero {
    padding: 12px 4px 8px 4px;
}
.rs-hero-label {
    font-size: 12px; color: var(--rs-ink-3);
    text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;
}
.rs-hero-metric {
    font-size: 40px; font-weight: 700; line-height: 1.1;
    color: var(--rs-ink); letter-spacing: -0.025em;
    margin: 4px 0;
}
.rs-hero-sub {
    font-size: 14px; color: var(--rs-ink-2);
}

/* Account mini-card grid */
.rs-account-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px; margin-top: 6px;
}
.rs-account-card {
    border: 1px solid var(--rs-border); border-radius: var(--rs-radius-sm);
    padding: 12px 14px; background: var(--rs-surface);
}
.rs-account-plan { font-size: 14px; font-weight: 600; color: var(--rs-ink); }
.rs-account-tag {
    display: inline-block; font-size: 11px; font-weight: 600;
    color: var(--rs-primary); background: var(--rs-primary-50);
    padding: 2px 8px; border-radius: 9999px; margin-top: 4px;
    text-transform: uppercase; letter-spacing: 0.04em;
}
.rs-account-balance {
    font-size: 18px; font-weight: 600; color: var(--rs-ink); margin-top: 8px;
}
.rs-account-vested { font-size: 12px; color: var(--rs-ink-3); }

/* ---------- Transaction list ---------- */
.rs-txn-filter-row { display: flex; gap: 6px; margin: 4px 0 8px 0; flex-wrap: wrap; }
.rs-txn-list { margin-top: 4px; }
.rs-txn-row {
    display: grid; grid-template-columns: 84px 1fr 110px;
    align-items: center; gap: 12px;
    padding: 10px 4px; border-bottom: 1px solid var(--rs-border);
}
.rs-txn-row:last-child { border-bottom: none; }
.rs-txn-date {
    font-size: 12px; color: var(--rs-ink-3); font-variant-numeric: tabular-nums;
}
.rs-txn-body { font-size: 14px; color: var(--rs-ink); }
.rs-txn-type {
    display: inline-block; font-size: 11px; font-weight: 600;
    color: var(--rs-ink-2); background: var(--rs-surface-3);
    padding: 1px 7px; border-radius: 9999px; margin-right: 6px;
    text-transform: capitalize;
}
.rs-txn-desc { color: var(--rs-ink-2); font-size: 13px; }
.rs-txn-amt {
    font-size: 15px; font-weight: 600; text-align: right;
    font-variant-numeric: tabular-nums;
}
.rs-txn-amt-pos { color: var(--rs-success); }
.rs-txn-amt-neg { color: var(--rs-danger); }
.rs-txn-amt-neu { color: var(--rs-ink); }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--rs-surface-2); }
.rs-brand-mark {
    display: flex; align-items: center; gap: 10px;
    padding: 4px 0 0 0;
}
.rs-brand-logo {
    width: 36px; height: 36px; border-radius: 10px;
    background: var(--rs-primary); color: #FFFFFF;
    display: inline-flex; align-items: center; justify-content: center;
}
.rs-brand-logo .material-symbols-outlined { font-size: 22px; }
.rs-brand-name { font-size: 18px; font-weight: 700; color: var(--rs-ink); letter-spacing: -0.01em; }
.rs-brand-tag { font-size: 11px; color: var(--rs-ink-3); text-transform: uppercase; letter-spacing: 0.06em; }

.rs-cust-card {
    display: flex; align-items: center; gap: 12px;
    padding: 12px; background: var(--rs-surface);
    border: 1px solid var(--rs-border); border-radius: var(--rs-radius-sm);
    margin: 12px 0 8px 0;
}
.rs-cust-avatar {
    width: 40px; height: 40px; border-radius: 50%;
    background: var(--rs-primary); color: #FFFFFF;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 600; font-size: 16px; flex-shrink: 0;
}
.rs-cust-name { font-size: 14px; font-weight: 600; color: var(--rs-ink); line-height: 1.2; }
.rs-cust-id { font-size: 11px; color: var(--rs-ink-3); margin-top: 2px; }
.rs-cust-lastlogin { font-size: 11px; color: var(--rs-ink-3); margin-top: 4px; }

.rs-section-label {
    font-size: 11px; color: var(--rs-ink-3); font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.07em;
    margin: 14px 0 6px 0;
}

.rs-contact-card {
    background: var(--rs-surface); border: 1px solid var(--rs-border);
    border-radius: var(--rs-radius-sm); padding: 12px; margin-top: 8px;
}
.rs-contact-line {
    font-size: 12px; color: var(--rs-ink-2); display: flex; align-items: center; gap: 6px;
    margin: 4px 0;
}
.rs-contact-line .material-symbols-outlined { font-size: 16px; color: var(--rs-ink-3); }

.rs-security-badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px; color: var(--rs-success);
    background: var(--rs-success-bg); padding: 2px 8px;
    border-radius: 9999px; margin-top: 6px;
}
.rs-security-badge .material-symbols-outlined { font-size: 14px; }

/* ---------- Footer (compliance) ---------- */
.rs-footer {
    color: var(--rs-ink-3); font-size: 11px; line-height: 1.5;
    text-align: center; margin: 32px auto 8px auto; padding: 12px 16px;
    border-top: 1px solid var(--rs-border); max-width: 720px;
}

/* ---------- Request/document list rows ---------- */
.rs-list-row {
    display: grid; grid-template-columns: 1fr auto;
    align-items: center; gap: 12px;
    padding: 10px 8px; border-bottom: 1px solid var(--rs-border);
}
.rs-list-row:last-child { border-bottom: none; }
.rs-list-title { font-size: 14px; font-weight: 600; color: var(--rs-ink); }
.rs-list-meta { font-size: 12px; color: var(--rs-ink-3); margin-top: 2px; }
.rs-status-pill {
    display: inline-block; font-size: 11px; font-weight: 600;
    padding: 2px 10px; border-radius: 9999px;
    text-transform: capitalize;
}
.rs-status-pending { background: var(--rs-warning-bg); color: var(--rs-warning); }
.rs-status-completed { background: var(--rs-success-bg); color: var(--rs-success); }
.rs-status-cancelled { background: var(--rs-surface-3); color: var(--rs-ink-3); }
.rs-status-rejected { background: var(--rs-danger-bg); color: var(--rs-danger); }

/* ---------- Tighter inputs ---------- */
.stTextInput input, .stTextArea textarea, .stDateInput input, .stSelectbox [data-baseweb="select"] > div {
    border-radius: var(--rs-radius-sm) !important;
}

/* ---------- Drift indicator (rebalance) ---------- */
.rs-drift-pos { color: var(--rs-success); font-weight: 600; }
.rs-drift-neg { color: var(--rs-danger); font-weight: 600; }
.rs-drift-flat { color: var(--rs-ink-3); }
</style>

<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" />
"""


def inject_global_css() -> None:
    """Inject the brand stylesheet once per session."""
    if st.session_state.get("_rs_css_injected"):
        return
    st.markdown(_CSS, unsafe_allow_html=True)
    st.session_state["_rs_css_injected"] = True


def icon_html(name: str, size: int = 18) -> str:
    """Return a Material Symbols outlined icon as inline HTML."""
    return f'<span class="material-symbols-outlined" style="font-size:{size}px;vertical-align:middle;">{name}</span>'
