"""Global stylesheet injection.

Called once per session from app.py right after st.set_page_config.
Defines brand tokens as CSS variables and applies them to Streamlit's default
DOM. Streamlit class names drift between versions, so selectors aim at multiple
test-id variants where it matters (chat avatars, banners).

Aesthetic: dark sidebar (charcoal), white main surface, pastel-tinted account
cards and chips — inspired by the dashboard reference.
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
  --rs-radius: 16px; --rs-radius-sm: 10px; --rs-radius-pill: 9999px;
  --rs-shadow: 0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06);
  --rs-shadow-lg: 0 8px 24px rgba(15,23,42,.06), 0 2px 8px rgba(15,23,42,.04);

  /* Dark sidebar palette */
  --rs-dark: #0B1220; --rs-dark-2: #131C2E; --rs-dark-3: #1E293B;
  --rs-dark-ink: #F1F5F9; --rs-dark-ink-2: #94A3B8; --rs-dark-ink-3: #64748B;
  --rs-dark-border: #1E293B;

  /* Pastel surfaces for asset/account cards */
  --rs-pastel-violet: #F3E8FF; --rs-pastel-violet-ink: #6D28D9;
  --rs-pastel-mint:   #D1FAE5; --rs-pastel-mint-ink:   #047857;
  --rs-pastel-peach:  #FFEDD5; --rs-pastel-peach-ink:  #C2410C;
  --rs-pastel-cream:  #FEF3C7; --rs-pastel-cream-ink:  #92400E;
  --rs-pastel-sky:    #DBEAFE; --rs-pastel-sky-ink:    #1E40AF;
  --rs-pastel-rose:   #FCE7F3; --rs-pastel-rose-ink:   #BE185D;

  /* Page background: very soft mint */
  --rs-page: #EFF6F4;
}

/* ---------- Page chrome ---------- */
.stApp {
    background: var(--rs-page);
}
/* Hide Streamlit's default top toolbar (Deploy button + hamburger) for a
   fully branded surface. */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDeployButton"],
#MainMenu,
header[data-testid="stHeader"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
}
.stApp > header { display: none !important; height: 0 !important; }

.main .block-container {
    background: var(--rs-surface);
    border-radius: 24px;
    padding: 28px 32px 32px 32px;
    margin-top: 12px;
    margin-bottom: 16px;
    box-shadow: var(--rs-shadow-lg);
    max-width: 880px;
}

/* ---------- Typography ---------- */
.stApp h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; color: var(--rs-ink); margin-bottom: 4px; }
.stApp h2 { font-size: 22px; font-weight: 600; letter-spacing: -0.01em; color: var(--rs-ink); }
.stApp h3 { font-size: 17px; font-weight: 600; color: var(--rs-ink); margin-bottom: 4px; }
.stApp p, .stApp li, .stApp label { color: var(--rs-ink); font-size: 15px; line-height: 1.55; }
.stApp [data-testid="stCaptionContainer"], .stApp small { color: var(--rs-ink-3); font-size: 13px; }

/* ---------- Card surface (st.container with border) ---------- */
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: var(--rs-radius) !important;
    border-color: var(--rs-border) !important;
    background: var(--rs-surface);
    box-shadow: var(--rs-shadow);
}

/* ---------- Buttons (main column) ---------- */
.stButton button {
    border-radius: var(--rs-radius-sm) !important;
    font-weight: 500 !important;
    transition: background-color .12s ease, border-color .12s ease, transform .04s ease;
}
.stButton button[kind="primary"], .stButton button[kind="primaryFormSubmit"] {
    background: var(--rs-ink) !important;
    border: 1px solid var(--rs-ink) !important;
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

/* ---------- Banners ---------- */
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

/* ---------- Chat avatars ---------- */
[data-testid="stChatMessageAvatarUser"],
[data-testid="chatAvatarIcon-user"] {
    background-color: var(--rs-ink) !important;
    color: #FFFFFF !important;
}
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="chatAvatarIcon-assistant"] {
    background-color: var(--rs-pastel-mint) !important;
    color: var(--rs-pastel-mint-ink) !important;
}
[data-testid="stChatMessageAvatarUser"] svg,
[data-testid="chatAvatarIcon-user"] svg { fill: #FFFFFF !important; }
[data-testid="stChatMessageAvatarAssistant"] svg,
[data-testid="chatAvatarIcon-assistant"] svg { fill: var(--rs-pastel-mint-ink) !important; }

/* ---------- Custom card chrome (main column) ---------- */
.rs-card-head {
    display: flex; align-items: center; gap: 12px;
    padding: 4px 0 8px 0;
}
.rs-card-icon {
    width: 38px; height: 38px; border-radius: 12px;
    background: var(--rs-pastel-mint); color: var(--rs-pastel-mint-ink);
    display: inline-flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.rs-card-icon .material-symbols-outlined { font-size: 22px; }
.rs-card-title-block { display: flex; flex-direction: column; line-height: 1.25; }
.rs-card-title { font-size: 17px; font-weight: 600; color: var(--rs-ink); }
.rs-card-subtitle { font-size: 13px; color: var(--rs-ink-2); margin-top: 2px; }

/* ---------- Chips (quick actions empty state) ---------- */
.rs-chip-row {
    display: flex; gap: 8px; flex-wrap: wrap;
    margin: 8px 0 14px 0;
}
.rs-chip-row .stButton button {
    background: var(--rs-pastel-mint) !important;
    border: 1px solid transparent !important;
    color: var(--rs-pastel-mint-ink) !important;
    border-radius: var(--rs-radius-pill) !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    min-height: 56px !important;          /* equal height across chips */
    height: 56px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: nowrap !important;       /* keep labels on one line */
    line-height: 1.2 !important;
}
.rs-chip-row .stButton button p,
.rs-chip-row .stButton button div {
    margin: 0 !important;
    line-height: 1.2 !important;
}
.rs-chip-row .stButton button:hover {
    background: var(--rs-pastel-mint-ink) !important;
    color: #FFFFFF !important;
}
.rs-chip-row .stButton button:hover p,
.rs-chip-row .stButton button:hover div {
    color: #FFFFFF !important;
}

/* ---------- Hero metric (balance, RMD, loan quote) ---------- */
.rs-hero {
    background: var(--rs-pastel-mint);
    border-radius: var(--rs-radius);
    padding: 18px 20px;
    margin: 4px 0 12px 0;
}
.rs-hero-label {
    font-size: 12px; color: var(--rs-pastel-mint-ink);
    text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700;
}
.rs-hero-metric {
    font-size: 40px; font-weight: 700; line-height: 1.1;
    color: var(--rs-ink); letter-spacing: -0.025em;
    margin: 6px 0 2px 0;
}
.rs-hero-sub { font-size: 13px; color: var(--rs-ink-2); }

/* Account mini-card grid (balance view) */
.rs-account-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px; margin-top: 10px;
}
.rs-account-card {
    border: none; border-radius: var(--rs-radius);
    padding: 14px 16px;
    background: var(--rs-pastel-violet);
    color: var(--rs-pastel-violet-ink);
}
.rs-account-card:nth-child(2n) { background: var(--rs-pastel-peach); color: var(--rs-pastel-peach-ink); }
.rs-account-card:nth-child(3n) { background: var(--rs-pastel-sky);    color: var(--rs-pastel-sky-ink); }
.rs-account-card:nth-child(4n) { background: var(--rs-pastel-cream);  color: var(--rs-pastel-cream-ink); }
.rs-account-card:nth-child(5n) { background: var(--rs-pastel-rose);   color: var(--rs-pastel-rose-ink); }

.rs-account-plan { font-size: 14px; font-weight: 700; color: inherit; }
.rs-account-tag {
    display: inline-block; font-size: 10px; font-weight: 700;
    color: inherit; background: rgba(255,255,255,0.55);
    padding: 2px 8px; border-radius: var(--rs-radius-pill); margin-top: 6px;
    text-transform: uppercase; letter-spacing: 0.05em;
}
.rs-account-balance {
    font-size: 20px; font-weight: 700; color: var(--rs-ink); margin-top: 10px;
    letter-spacing: -0.01em;
}
.rs-account-vested { font-size: 12px; color: var(--rs-ink-2); margin-top: 2px; }

/* ---------- Transaction list ---------- */
.rs-txn-filter-row { display: flex; gap: 6px; margin: 6px 0 10px 0; flex-wrap: wrap; }
.rs-txn-list { margin-top: 4px; }
.rs-txn-row {
    display: grid; grid-template-columns: 84px 1fr 110px;
    align-items: center; gap: 12px;
    padding: 12px 4px; border-bottom: 1px solid var(--rs-border);
}
.rs-txn-row:last-child { border-bottom: none; }
.rs-txn-date {
    font-size: 12px; color: var(--rs-ink-3); font-variant-numeric: tabular-nums;
}
.rs-txn-body { font-size: 14px; color: var(--rs-ink); }
.rs-txn-type {
    display: inline-block; font-size: 11px; font-weight: 600;
    color: var(--rs-ink-2); background: var(--rs-surface-3);
    padding: 2px 8px; border-radius: var(--rs-radius-pill); margin-right: 6px;
    text-transform: capitalize;
}
.rs-txn-desc { color: var(--rs-ink-2); font-size: 13px; }
.rs-txn-amt {
    font-size: 15px; font-weight: 700; text-align: right;
    font-variant-numeric: tabular-nums; letter-spacing: -0.01em;
}
.rs-txn-amt-pos { color: var(--rs-success); }
.rs-txn-amt-neg { color: var(--rs-danger); }
.rs-txn-amt-neu { color: var(--rs-ink); }

/* ---------- Request/document list rows ---------- */
.rs-list-row {
    display: grid; grid-template-columns: 1fr auto;
    align-items: center; gap: 12px;
    padding: 12px 8px; border-bottom: 1px solid var(--rs-border);
}
.rs-list-row:last-child { border-bottom: none; }
.rs-list-title { font-size: 14px; font-weight: 600; color: var(--rs-ink); }
.rs-list-meta { font-size: 12px; color: var(--rs-ink-3); margin-top: 2px; }
.rs-status-pill {
    display: inline-block; font-size: 11px; font-weight: 700;
    padding: 3px 10px; border-radius: var(--rs-radius-pill);
    text-transform: capitalize;
}
.rs-status-pending { background: var(--rs-warning-bg); color: var(--rs-warning); }
.rs-status-completed { background: var(--rs-success-bg); color: var(--rs-success); }
.rs-status-cancelled { background: var(--rs-surface-3); color: var(--rs-ink-3); }
.rs-status-rejected { background: var(--rs-danger-bg); color: var(--rs-danger); }

/* ---------- Drift indicator ---------- */
.rs-drift-pos { color: var(--rs-success); font-weight: 700; }
.rs-drift-neg { color: var(--rs-danger); font-weight: 700; }
.rs-drift-flat { color: var(--rs-ink-3); }

/* ---------- Inputs ---------- */
.stTextInput input, .stTextArea textarea, .stDateInput input, .stNumberInput input,
.stSelectbox [data-baseweb="select"] > div {
    border-radius: var(--rs-radius-sm) !important;
}

/* ============================================================
   DARK SIDEBAR
   ============================================================ */
[data-testid="stSidebar"] {
    background: var(--rs-dark) !important;
}
[data-testid="stSidebar"] > div:first-child {
    background: var(--rs-dark) !important;
}
/* Sidebar typography */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] li {
    color: var(--rs-dark-ink) !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] small {
    color: var(--rs-dark-ink-3) !important;
}
[data-testid="stSidebar"] hr {
    border-color: var(--rs-dark-border) !important;
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    color: var(--rs-dark-ink-2) !important;
    border: 1px solid var(--rs-dark-border) !important;
    border-radius: var(--rs-radius-sm) !important;
    font-weight: 500 !important;
    text-align: left !important;
}
/* Reset: button label <p> should inherit from the button, not from the
   global sidebar typography rule (which forces near-white). */
[data-testid="stSidebar"] .stButton button p,
[data-testid="stSidebar"] .stButton button span,
[data-testid="stSidebar"] .stButton button div {
    color: inherit !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: var(--rs-dark-2) !important;
    color: var(--rs-dark-ink) !important;
    border-color: var(--rs-dark-3) !important;
}
/* Primary CTA — bright cream with deep-burnt text so it pops on the dark sidebar */
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: var(--rs-pastel-cream) !important;
    color: var(--rs-pastel-cream-ink) !important;
    border: 1px solid var(--rs-pastel-cream-ink) !important;
    border-radius: var(--rs-radius-pill) !important;
    font-weight: 800 !important;
    text-align: center !important;
    letter-spacing: 0.01em;
}
[data-testid="stSidebar"] .stButton button[kind="primary"] p,
[data-testid="stSidebar"] .stButton button[kind="primary"] span,
[data-testid="stSidebar"] .stButton button[kind="primary"] div {
    color: var(--rs-pastel-cream-ink) !important;
    font-weight: 800 !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
    background: var(--rs-pastel-cream-ink) !important;
    border-color: var(--rs-pastel-cream-ink) !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover p,
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover span,
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover div {
    color: #FFFFFF !important;
}

/* Brand mark in sidebar */
.rs-brand-mark {
    display: flex; align-items: center; gap: 12px;
    padding: 4px 4px 12px 4px;
}
.rs-brand-logo {
    width: 38px; height: 38px; border-radius: 11px;
    background: var(--rs-pastel-mint); color: var(--rs-pastel-mint-ink);
    display: inline-flex; align-items: center; justify-content: center;
}
.rs-brand-logo .material-symbols-outlined { font-size: 22px; }
.rs-brand-name { font-size: 18px; font-weight: 700; color: var(--rs-dark-ink); letter-spacing: -0.01em; }
.rs-brand-tag { font-size: 10px; color: var(--rs-dark-ink-3); text-transform: uppercase; letter-spacing: 0.08em; }

/* Profile pill at top of sidebar — matches the reference's avatar-name-chevron pill */
.rs-profile-pill {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px 8px 8px;
    background: var(--rs-dark-2);
    border-radius: var(--rs-radius-pill);
    margin: 8px 0 14px 0;
}
.rs-profile-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    background: var(--rs-pastel-violet); color: var(--rs-pastel-violet-ink);
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px;
}
.rs-profile-name { font-size: 13px; font-weight: 600; color: var(--rs-dark-ink); }
.rs-profile-id { font-size: 10px; color: var(--rs-dark-ink-3); }

/* Sidebar account snapshot card */
.rs-snap-card {
    background: var(--rs-dark-2);
    border-radius: var(--rs-radius);
    padding: 14px 16px;
    margin: 4px 0 14px 0;
}
.rs-snap-label {
    font-size: 10px; color: var(--rs-dark-ink-3);
    text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700;
}
.rs-snap-metric {
    font-size: 24px; font-weight: 700; color: var(--rs-dark-ink);
    letter-spacing: -0.02em; margin-top: 4px;
}
.rs-snap-sub { font-size: 11px; color: var(--rs-dark-ink-3); margin-top: 2px; }
.rs-snap-pills { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.rs-snap-pill {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 10px; font-weight: 700;
    padding: 3px 9px; border-radius: var(--rs-radius-pill);
    background: var(--rs-pastel-mint); color: var(--rs-pastel-mint-ink);
}
.rs-snap-pill.alt { background: var(--rs-pastel-violet); color: var(--rs-pastel-violet-ink); }

/* Section labels in sidebar */
.rs-section-label {
    font-size: 10px; color: var(--rs-dark-ink-3); font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.09em;
    margin: 14px 0 8px 4px;
}

/* Conversation list rows (sidebar) */
.rs-conv-list { display: flex; flex-direction: column; gap: 4px; }
[data-testid="stSidebar"] .rs-conv-list .stButton button {
    background: transparent !important;
    border: 1px solid transparent !important;
    color: var(--rs-dark-ink-2) !important;
    padding: 8px 10px !important;
    font-weight: 500 !important;
    line-height: 1.3 !important;
    white-space: normal !important;
    text-align: left !important;
}
[data-testid="stSidebar"] .rs-conv-list .stButton button:hover {
    background: var(--rs-dark-2) !important;
    color: var(--rs-dark-ink) !important;
    border-color: var(--rs-dark-border) !important;
}
[data-testid="stSidebar"] .rs-conv-list .stButton button.active {
    background: var(--rs-dark-2) !important;
    color: var(--rs-dark-ink) !important;
    border-color: var(--rs-dark-3) !important;
}
.rs-conv-empty {
    color: var(--rs-dark-ink-3); font-size: 12px; padding: 8px 10px;
    border: 1px dashed var(--rs-dark-border); border-radius: var(--rs-radius-sm);
}

/* Sidebar contact card */
.rs-contact-card {
    background: var(--rs-dark-2); border: none;
    border-radius: var(--rs-radius-sm); padding: 12px 14px; margin-top: 8px;
}
.rs-contact-line {
    font-size: 12px; color: var(--rs-dark-ink-2);
    display: flex; align-items: center; gap: 6px;
    margin: 4px 0;
}
.rs-contact-line .material-symbols-outlined { font-size: 16px; color: var(--rs-dark-ink-3); }
.rs-security-badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 10px; font-weight: 700; color: var(--rs-pastel-mint-ink);
    background: var(--rs-pastel-mint); padding: 3px 9px;
    border-radius: var(--rs-radius-pill); margin-top: 8px;
    text-transform: uppercase; letter-spacing: 0.05em;
}
.rs-security-badge .material-symbols-outlined { font-size: 12px; }

/* ---------- Compliance footer ---------- */
.rs-footer {
    color: var(--rs-ink-3); font-size: 11px; line-height: 1.5;
    text-align: center; margin: 24px auto 4px auto; padding: 14px 16px;
    border-top: 1px solid var(--rs-border); max-width: 720px;
}

/* ---------- Top profile pill (main column header) ---------- */
.rs-header-row {
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px; margin-bottom: 14px;
}
.rs-header-pill {
    display: inline-flex; align-items: center; gap: 10px;
    padding: 4px 14px 4px 4px;
    background: var(--rs-surface-2);
    border-radius: var(--rs-radius-pill);
    border: 1px solid var(--rs-border);
}
.rs-header-pill .rs-pill-avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--rs-pastel-violet); color: var(--rs-pastel-violet-ink);
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 12px;
}
.rs-header-pill .rs-pill-name { font-size: 13px; font-weight: 600; color: var(--rs-ink); }
.rs-header-pill .material-symbols-outlined {
    font-size: 16px; color: var(--rs-ink-3); margin-left: 2px;
}
</style>

<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" />
"""


def inject_global_css() -> None:
    """Inject the brand stylesheet.

    Must run on EVERY rerun. Streamlit drops any DOM element that the current
    run didn't produce, so a once-per-session guard would cause the page to
    lose its styling (and the Material Symbols font <link>) the moment a
    spinner or rerun fires after the first render. The `st.markdown` call is
    idempotent — Streamlit dedupes identical content cheaply.
    """
    st.markdown(_CSS, unsafe_allow_html=True)


def icon_html(name: str, size: int = 18) -> str:
    """Return a Material Symbols outlined icon as inline HTML."""
    return f'<span class="material-symbols-outlined" style="font-size:{size}px;vertical-align:middle;">{name}</span>'
