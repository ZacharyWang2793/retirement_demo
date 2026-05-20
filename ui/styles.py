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
  /* Brand palette */
  --rs-primary:     #1E7FD8;
  --rs-primary-dk:  #1668B8;
  --rs-primary-lt:  #EAF4FD;
  --rs-yellow:      #FFD600;
  --rs-yellow-lt:   #FDFFD0;
  --rs-yellow-dk:   #C9A800;

  /* Semantic status — keep conventional traffic-light */
  --rs-success:    #15803D; --rs-success-bg: #DCFCE7;
  --rs-warning:    #B45309; --rs-warning-bg: #FEF3C7;
  --rs-danger:     #B91C1C; --rs-danger-bg:  #FEE2E2;
  --rs-info:       #1E7FD8; --rs-info-bg:    #EAF4FD;

  /* Ink scale */
  --rs-ink:     #0F1523;
  --rs-ink-2:   #5C5C6E;
  --rs-ink-3:   #8A8AA0;

  /* Surfaces */
  --rs-surface:   #FFFFFF;
  --rs-surface-2: #F8F9FA;
  --rs-surface-3: #F1F2F5;

  /* Borders */
  --rs-border:        #C8C8D0;
  --rs-border-strong: #A0A0B0;

  /* Page: white */
  --rs-page: #FFFFFF;

  /* Geometry */
  --rs-radius:      16px;
  --rs-radius-sm:   10px;
  --rs-radius-pill: 9999px;
  --rs-shadow:      0 1px 2px rgba(15,21,35,.04), 0 1px 3px rgba(15,21,35,.06);
  --rs-shadow-lg:   0 8px 24px rgba(15,21,35,.06), 0 2px 8px rgba(15,21,35,.04);

  /* Dark sidebar */
  --rs-dark:        #0F1523;
  --rs-dark-2:      #1A2238;
  --rs-dark-3:      #243050;
  --rs-dark-ink:    #F1F5F9;
  --rs-dark-ink-2:  #9AA5B4;
  --rs-dark-ink-3:  #64748B;
  --rs-dark-border: #243050;
}

/* ---------- Page chrome ---------- */
.stApp {
    background: var(--rs-page);
}
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
    padding: 16px 32px 32px 32px;
    margin-top: 2px;
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
    background: var(--rs-primary) !important;
    border: 1px solid var(--rs-primary) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}
.stButton button[kind="primary"] p,
.stButton button[kind="primary"] span,
.stButton button[kind="primary"] div,
.stButton button[kind="primaryFormSubmit"] p,
.stButton button[kind="primaryFormSubmit"] span,
.stButton button[kind="primaryFormSubmit"] div {
    color: #FFFFFF !important;
}
.stButton button[kind="primary"]:hover, .stButton button[kind="primaryFormSubmit"]:hover {
    background: var(--rs-primary-dk) !important;
    border-color: var(--rs-primary-dk) !important;
}
.stButton button[kind="secondary"], .stButton button[kind="secondaryFormSubmit"] {
    background: var(--rs-surface) !important;
    color: var(--rs-ink-2) !important;
    border: 1px solid var(--rs-border-strong) !important;
}
.stButton button[kind="secondary"] p,
.stButton button[kind="secondary"] span,
.stButton button[kind="secondary"] div,
.stButton button[kind="secondaryFormSubmit"] p,
.stButton button[kind="secondaryFormSubmit"] span,
.stButton button[kind="secondaryFormSubmit"] div {
    color: var(--rs-ink-2) !important;
}
.stButton button[kind="secondary"]:hover, .stButton button[kind="secondaryFormSubmit"]:hover {
    background: var(--rs-surface-2) !important;
    color: var(--rs-ink) !important;
}
/* Default (no kind) buttons */
.stButton button:not([kind]) {
    background: var(--rs-surface) !important;
    color: var(--rs-ink-2) !important;
    border: 1px solid var(--rs-border-strong) !important;
}
.stButton button:not([kind]) p,
.stButton button:not([kind]) span,
.stButton button:not([kind]) div {
    color: var(--rs-ink-2) !important;
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
[data-testid="stChatMessageAvatarUser"] svg,
[data-testid="chatAvatarIcon-user"] svg { fill: #FFFFFF !important; }

/* Assistant: cerulean circle — hide the default robot SVG */
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="chatAvatarIcon-assistant"] {
    background-color: var(--rs-primary) !important;
    color: #FFFFFF !important;
}
[data-testid="stChatMessageAvatarAssistant"] svg,
[data-testid="chatAvatarIcon-assistant"] svg {
    display: none !important;
}

/* ---------- Custom card chrome (main column) ---------- */
.rs-card-head {
    display: flex; align-items: center; gap: 12px;
    padding: 4px 0 8px 0;
}
.rs-card-icon {
    width: 38px; height: 38px; border-radius: 12px;
    background: rgba(30, 127, 216, 0.10);
    color: var(--rs-primary);
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
    background: var(--rs-yellow-lt) !important;
    border: 1px solid var(--rs-yellow) !important;
    color: var(--rs-ink) !important;
    border-radius: var(--rs-radius-pill) !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    min-height: 56px !important;
    height: 56px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: nowrap !important;
    line-height: 1.2 !important;
}
.rs-chip-row .stButton button p,
.rs-chip-row .stButton button div {
    margin: 0 !important;
    line-height: 1.2 !important;
    color: var(--rs-ink) !important;
}
.rs-chip-row .stButton button:hover {
    background: var(--rs-yellow) !important;
    border-color: var(--rs-yellow-dk) !important;
    color: var(--rs-ink) !important;
}
.rs-chip-row .stButton button:hover p,
.rs-chip-row .stButton button:hover div {
    color: var(--rs-ink) !important;
}

/* ---------- Hero metric (balance, RMD, loan quote) ---------- */
.rs-hero {
    background: var(--rs-yellow-lt);
    border: 1px solid rgba(201, 168, 0, 0.20);
    border-left: 4px solid var(--rs-yellow);
    border-radius: var(--rs-radius);
    padding: 18px 20px;
    margin: 4px 0 12px 0;
}
.rs-hero-label {
    font-size: 12px; color: var(--rs-yellow-dk);
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
    border: 1px solid var(--rs-border);
    border-left: 3px solid var(--rs-primary);
    border-radius: var(--rs-radius-sm);
    padding: 14px 16px;
    background: var(--rs-surface);
}
.rs-account-card:nth-child(even) {
    background: var(--rs-yellow-lt);
    border-left-color: var(--rs-yellow);
}

.rs-account-plan { font-size: 14px; font-weight: 700; color: var(--rs-ink); }
.rs-account-tag {
    display: inline-block; font-size: 10px; font-weight: 700;
    color: var(--rs-primary); background: var(--rs-primary-lt);
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
/* Primary CTA — yellow with near-black text so it pops on the dark sidebar */
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: var(--rs-yellow) !important;
    color: var(--rs-ink) !important;
    border: 1px solid var(--rs-yellow-dk) !important;
    border-radius: var(--rs-radius-pill) !important;
    font-weight: 800 !important;
    text-align: center !important;
    letter-spacing: 0.01em;
}
[data-testid="stSidebar"] .stButton button[kind="primary"] p,
[data-testid="stSidebar"] .stButton button[kind="primary"] span,
[data-testid="stSidebar"] .stButton button[kind="primary"] div {
    color: var(--rs-ink) !important;
    font-weight: 800 !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
    background: var(--rs-yellow-dk) !important;
    border-color: var(--rs-yellow-dk) !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover p,
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover span,
[data-testid="stSidebar"] .stButton button[kind="primary"]:hover div {
    color: var(--rs-ink) !important;
}

/* ── New conversation button (ChatGPT nav-item style) ── */
.rs-new-conv-btn .stButton button {
    background: var(--rs-dark-2) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: var(--rs-radius-sm) !important;
    text-align: left !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 10px 14px !important;
    margin-bottom: 8px !important;
}
.rs-new-conv-btn .stButton button p,
.rs-new-conv-btn .stButton button span,
.rs-new-conv-btn .stButton button div {
    color: #FFFFFF !important;
}
.rs-new-conv-btn .stButton button:hover {
    background: var(--rs-dark-3) !important;
    color: #FFFFFF !important;
}

/* Brand mark in sidebar */
.rs-brand-mark {
    display: flex; align-items: center; gap: 12px;
    padding: 4px 4px 12px 4px;
}
.rs-brand-logo {
    width: 38px; height: 38px; border-radius: 11px;
    background: var(--rs-primary); color: #FFFFFF;
    display: inline-flex; align-items: center; justify-content: center;
}
.rs-brand-logo .material-symbols-outlined { font-size: 22px; color: #FFFFFF; }
.rs-brand-name { font-size: 18px; font-weight: 700; color: var(--rs-dark-ink); letter-spacing: -0.01em; }
.rs-brand-tag { font-size: 10px; color: var(--rs-yellow); text-transform: uppercase; letter-spacing: 0.08em; }

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
    background: var(--rs-primary); color: #FFFFFF;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px;
}
.rs-profile-name { font-size: 13px; font-weight: 600; color: var(--rs-dark-ink); }
.rs-profile-id { font-size: 10px; color: var(--rs-dark-ink-3); }

/* Sidebar account snapshot card */
.rs-snap-card {
    background: var(--rs-dark-2);
    border-radius: var(--rs-radius);
    border-left: 3px solid var(--rs-yellow);
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
    background: rgba(30, 127, 216, 0.25); color: var(--rs-dark-ink);
}
.rs-snap-pill.alt { background: rgba(255, 214, 0, 0.25); color: var(--rs-dark-ink); }

/* Section labels in sidebar */
.rs-section-label {
    font-size: 10px; color: var(--rs-dark-ink-3); font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.09em;
    margin: 14px 0 8px 0;
    border-left: 2px solid var(--rs-yellow);
    padding-left: 8px;
}

/* Active / current conversation highlight */
.rs-conv-active {
    font-size: 14px; font-weight: 700;
    color: #FFFFFF;
    background: var(--rs-dark-3);
    border-left: 3px solid var(--rs-yellow);
    border-radius: 0 var(--rs-radius-sm) var(--rs-radius-sm) 0;
    padding: 9px 12px 9px 10px;
    margin: 0 0 10px 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    cursor: default;
    letter-spacing: 0.01em;
}

/* Conversation list rows (sidebar) — borderless, ChatGPT-style */
.rs-conv-list { display: flex; flex-direction: column; gap: 2px; }
[data-testid="stSidebar"] .rs-conv-list .stButton button {
    background: transparent !important;
    border: none !important;
    color: var(--rs-dark-ink-2) !important;
    padding: 8px 12px !important;
    font-weight: 400 !important;
    font-size: 14px !important;
    line-height: 1.4 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    text-align: left !important;
    border-radius: var(--rs-radius-sm) !important;
}
[data-testid="stSidebar"] .rs-conv-list .stButton button p,
[data-testid="stSidebar"] .rs-conv-list .stButton button span,
[data-testid="stSidebar"] .rs-conv-list .stButton button div {
    color: inherit !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
[data-testid="stSidebar"] .rs-conv-list .stButton button:hover {
    background: var(--rs-dark-2) !important;
    color: var(--rs-dark-ink) !important;
    border: none !important;
}
.rs-conv-empty {
    color: var(--rs-dark-ink-3); font-size: 13px;
    padding: 10px 12px; line-height: 1.5;
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
    font-size: 10px; font-weight: 700; color: var(--rs-dark-ink);
    background: rgba(255, 214, 0, 0.25); padding: 3px 9px;
    border-radius: var(--rs-radius-pill); margin-top: 8px;
    text-transform: uppercase; letter-spacing: 0.05em;
}
.rs-security-badge .material-symbols-outlined { font-size: 12px; }

/* ---------- Typing indicator (three bouncing dots) ---------- */
.rs-typing-indicator {
    display: flex; gap: 5px; align-items: center; padding: 4px 2px;
}
.rs-typing-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--rs-ink-3);
    animation: rs-bounce 1.2s infinite ease-in-out;
}
.rs-typing-dot:nth-child(2) { animation-delay: 0.2s; }
.rs-typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes rs-bounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.35; }
    30% { transform: translateY(-5px); opacity: 1; }
}

/* ---------- Compliance footer ---------- */
.rs-footer {
    color: var(--rs-ink-3); font-size: 11px; line-height: 1.5;
    text-align: center; margin: 24px auto 4px auto; padding: 14px 16px;
    border-top: 1px solid var(--rs-border); max-width: 720px;
}

/* (rs-header-row / rs-header-pill removed — main header is now plain h1) */
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
