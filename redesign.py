"""Append the complete editorial redesign CSS - keeps all functionality, just transforms visuals."""

REDESIGN = r"""

/* ════════════════════════════════════════════════════════════════════════════
   EDITORIAL REDESIGN v25 - "Right Horizons / WebinarIQ"
   Inspired by: Financial Times, Bloomberg, Linear, Stripe Atlas
   Typography-first, restrained palette, no gradients on text, no glow effects
   ════════════════════════════════════════════════════════════════════════════ */

:root {
  /* === Editorial palette === */
  --rh-bg:        #f5f4ef;        /* warm cream paper */
  --rh-surface:   #ffffff;
  --rh-surface-2: #fafaf7;
  --rh-border:    #e2e0d8;
  --rh-border-2:  #ebe8e0;
  --rh-text-1:    #171717;        /* near-black */
  --rh-text-2:    #525252;
  --rh-text-3:    #8a8a85;
  --rh-text-4:    #b0afa9;

  /* Accent: deep editorial black + serif red highlight */
  --rh-ink:       #0a0a0a;
  --rh-red:       #c41e3a;        /* NYT/FT editorial red */
  --rh-green:     #15803d;
  --rh-amber:     #b45309;
  --rh-blue:      #1e3a8a;

  /* Subtle backgrounds for status */
  --rh-tint-red:    #fef1f2;
  --rh-tint-green:  #ecfdf5;
  --rh-tint-amber:  #fef7e6;
  --rh-tint-blue:   #eff6ff;
  --rh-tint-paper:  #fef9c3;     /* paper-yellow highlight */

  /* Typography */
  --rh-serif:  'Fraunces', 'Source Serif Pro', Georgia, serif;
  --rh-sans:   'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --rh-mono:   'JetBrains Mono', 'IBM Plex Mono', 'Roboto Mono', ui-monospace, monospace;
}

html.dark {
  --rh-bg:        #0a0a0a;        /* true black */
  --rh-surface:   #141414;
  --rh-surface-2: #1a1a1a;
  --rh-border:    #262626;
  --rh-border-2:  #1f1f1f;
  --rh-text-1:    #fafafa;
  --rh-text-2:    #a3a3a3;
  --rh-text-3:    #6b6b6b;
  --rh-text-4:    #4a4a4a;
  --rh-ink:       #ffffff;
  --rh-red:       #f87171;
  --rh-green:     #22c55e;
  --rh-amber:     #f59e0b;
  --rh-blue:      #60a5fa;
  --rh-tint-red:    rgba(220,38,38,0.10);
  --rh-tint-green:  rgba(34,197,94,0.10);
  --rh-tint-amber:  rgba(245,158,11,0.10);
  --rh-tint-blue:   rgba(96,165,250,0.10);
  --rh-tint-paper:  rgba(250,204,21,0.10);
}

/* ── Reset base ── */
* { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
html, body {
  background: var(--rh-bg) !important;
  color: var(--rh-text-1) !important;
  font-family: var(--rh-sans) !important;
  font-feature-settings: 'cv11','ss01','ss03';
}

/* Kill all the blob/glow background effects (too AI-generated) */
.blob-bg, .blob, #cursor-glow { display: none !important; }
body::before, body::after { display: none !important; }

/* ════ NAVBAR ════ */
.navbar {
  background: var(--rh-bg) !important;
  border-bottom: 1px solid var(--rh-border) !important;
  box-shadow: none !important;
  backdrop-filter: none !important;
  height: 62px !important;
}
.navbar.scrolled { background: var(--rh-bg) !important; box-shadow: 0 1px 0 var(--rh-border-2) !important; }
.nav-container { height: 62px !important; }

/* Brand: serif + small logo */
.nav-brand-name {
  font-family: var(--rh-serif) !important;
  font-weight: 700 !important;
  font-size: 19px !important;
  letter-spacing: -0.01em !important;
  color: var(--rh-text-1) !important;
}
.brand-iq {
  color: var(--rh-red) !important;
  -webkit-text-fill-color: var(--rh-red) !important;
  font-family: var(--rh-serif) !important;
  font-style: italic !important;
  font-weight: 700 !important;
}
.nav-logo-mark {
  background: var(--rh-ink) !important;
  border-radius: 6px !important;
  width: 30px !important; height: 30px !important;
}
.nav-logo-mark svg { width: 16px !important; height: 14px !important; }
html.dark .nav-logo-mark { background: var(--rh-ink) !important; }
html.dark .nav-logo-mark svg polyline,
html.dark .nav-logo-mark svg circle { stroke: #000 !important; fill: #000 !important; }

/* Nav segmented pill */
.nav-links {
  background: transparent !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 8px !important;
  padding: 3px !important;
  gap: 0 !important;
}
.nav-link {
  font-family: var(--rh-sans) !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
  color: var(--rh-text-2) !important;
  background: transparent !important;
  border: none !important;
  border-radius: 6px !important;
  padding: 7px 14px !important;
  letter-spacing: 0 !important;
  box-shadow: none !important;
}
.nav-link svg { width: 13px !important; height: 13px !important; opacity: 0.55 !important; }
.nav-link:hover { background: var(--rh-surface) !important; color: var(--rh-text-1) !important; }
.nav-link.active {
  background: var(--rh-ink) !important;
  color: var(--rh-bg) !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}
.nav-link.active svg { opacity: 1 !important; color: var(--rh-bg) !important; }
html.dark .nav-link.active { background: #fafafa !important; color: #000 !important; }
html.dark .nav-link.active svg { color: #000 !important; }

/* Nav right controls */
.tb-notif-btn, .nav-theme-btn, .nav-hamburger {
  background: transparent !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 6px !important;
  width: 32px !important; height: 32px !important;
  color: var(--rh-text-2) !important;
}
.tb-notif-btn:hover, .nav-theme-btn:hover { background: var(--rh-surface) !important; color: var(--rh-text-1) !important; }
.notif-badge { background: var(--rh-red) !important; color: white !important; }

/* New Webinar button */
.btn.btn-primary, .nav-right .btn-primary {
  background: var(--rh-ink) !important;
  color: var(--rh-bg) !important;
  border: 1px solid var(--rh-ink) !important;
  border-radius: 7px !important;
  padding: 8px 14px !important;
  font-family: var(--rh-sans) !important;
  font-weight: 600 !important;
  font-size: 12.5px !important;
  letter-spacing: 0 !important;
  box-shadow: none !important;
  text-transform: none !important;
}
.btn.btn-primary:hover { background: #1a1a1a !important; transform: none !important; }
html.dark .btn.btn-primary { background: #fafafa !important; color: #000 !important; border-color: #fafafa !important; }
html.dark .btn.btn-primary:hover { background: #e5e5e5 !important; }
.btn.btn-ghost {
  background: transparent !important;
  color: var(--rh-text-1) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 7px !important;
  font-weight: 500 !important;
}
.btn.btn-ghost:hover { background: var(--rh-surface) !important; }

/* ════ MAIN CONTENT ════ */
.main, main { background: var(--rh-bg) !important; }

/* ════ HERO SECTION ════ */
.dash-hero {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 12px !important;
  padding: 36px 40px !important;
  position: relative !important;
  overflow: hidden !important;
}
.dash-hero::before {
  content: '' !important;
  position: absolute !important;
  inset: 0 !important;
  background: linear-gradient(180deg, transparent 0%, var(--rh-surface-2) 100%) !important;
  pointer-events: none !important;
  z-index: 0 !important;
  opacity: 0.5 !important;
}
.dash-hero > * { position: relative !important; z-index: 1 !important; }
.dash-hero-title {
  font-family: var(--rh-serif) !important;
  font-size: 34px !important;
  line-height: 1.1 !important;
  letter-spacing: -0.02em !important;
  font-weight: 600 !important;
  color: var(--rh-text-1) !important;
  background: none !important;
  -webkit-text-fill-color: var(--rh-text-1) !important;
  margin: 0 0 10px !important;
}
.dash-hero-sub {
  font-family: var(--rh-sans) !important;
  font-size: 14px !important;
  color: var(--rh-text-2) !important;
  max-width: 540px !important;
  line-height: 1.55 !important;
}

html.dark .dash-hero {
  background: var(--rh-surface) !important;
  border-color: var(--rh-border) !important;
}

/* ════ KPI CARDS ════ */
.an-kpi-strip, .kpi-grid, .kpi-row {
  gap: 14px !important;
}
.an-kpi-card, .kpi-card {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 10px !important;
  padding: 18px 22px !important;
  box-shadow: none !important;
  transition: border-color 0.15s !important;
}
.an-kpi-card::before, .kpi-card::before { display: none !important; }
.an-kpi-card:hover, .kpi-card:hover {
  border-color: var(--rh-text-3) !important;
  transform: none !important;
  box-shadow: none !important;
}
.an-kpi-label, .kpi-card-label, .an-kpi-lbl {
  font-family: var(--rh-sans) !important;
  font-size: 10.5px !important;
  font-weight: 600 !important;
  color: var(--rh-text-3) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
}
.an-kpi-val, .kpi-card-val {
  font-family: var(--rh-mono) !important;
  font-size: 32px !important;
  font-weight: 500 !important;
  letter-spacing: -0.025em !important;
  color: var(--rh-text-1) !important;
  background: none !important;
  -webkit-text-fill-color: var(--rh-text-1) !important;
  margin-top: 2px !important;
  font-feature-settings: 'tnum';
}
.an-kpi-icon, .kpi-card-icon {
  background: var(--rh-surface-2) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 6px !important;
  width: 32px !important; height: 32px !important;
  color: var(--rh-text-2) !important;
}
.an-kpi-trend, .kpi-card-trend { font-family: var(--rh-mono) !important; font-size: 11px !important; }

/* ════ ALL CARDS GENERIC ════ */
.card, .wb-card, .wb-list-card, .act-feed-card, .ad-card, .spk-card, .speaker-topics-card,
.an-stat-card, .modal-box {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 10px !important;
  box-shadow: none !important;
}

/* ════ WEBINAR CARDS GRID ════ */
.wb-card {
  border-radius: 10px !important;
  padding: 0 !important;
  transition: border-color 0.15s !important;
}
.wb-card:hover { border-color: var(--rh-text-3) !important; transform: none !important; box-shadow: none !important; }
.wb-card-top { display: none !important; }
.wb-card-body { padding: 18px 20px !important; }
.wb-card-title {
  font-family: var(--rh-serif) !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  letter-spacing: -0.005em !important;
  color: var(--rh-text-1) !important;
  line-height: 1.3 !important;
}
.wb-card-meta { font-family: var(--rh-mono) !important; font-size: 11.5px !important; color: var(--rh-text-3) !important; }
.wb-card-speaker { font-family: var(--rh-sans) !important; font-size: 12.5px !important; font-weight: 500 !important; color: var(--rh-text-2) !important; }
.wb-card-spk-av {
  border-radius: 5px !important;
  width: 24px !important; height: 24px !important;
  font-family: var(--rh-sans) !important;
  font-weight: 700 !important;
  font-size: 10px !important;
  letter-spacing: 0 !important;
}
.wb-card-stat-val { font-family: var(--rh-mono) !important; font-weight: 500 !important; letter-spacing: -0.02em !important; }
.wb-card-stat-lbl { font-family: var(--rh-sans) !important; font-size: 10.5px !important; text-transform: uppercase !important; letter-spacing: 0.06em !important; color: var(--rh-text-3) !important; }

/* ════ BADGES ════ */
.wb-badge {
  font-family: var(--rh-sans) !important;
  font-size: 10px !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  padding: 3px 8px !important;
  border-radius: 4px !important;
  border: 1px solid !important;
}
.wb-badge.completed   { background: var(--rh-tint-green) !important; color: var(--rh-green) !important; border-color: rgba(21,128,61,0.25) !important; }
.wb-badge.incomplete  { background: var(--rh-tint-amber) !important; color: var(--rh-amber) !important; border-color: rgba(180,83,9,0.25) !important; }
.wb-badge.upcoming    { background: var(--rh-tint-blue) !important;  color: var(--rh-blue) !important;  border-color: rgba(30,58,138,0.25) !important; }
.wb-badge.cancelled   { background: var(--rh-tint-red) !important;   color: var(--rh-red) !important;   border-color: rgba(196,30,58,0.25) !important; }

/* ICP badges - editorial style */
.icp-badge {
  font-family: var(--rh-sans) !important;
  font-size: 9.5px !important;
  font-weight: 700 !important;
  letter-spacing: 0.1em !important;
  text-transform: uppercase !important;
  padding: 3px 7px !important;
  border-radius: 3px !important;
  border: 1px solid !important;
  box-shadow: none !important;
  background: var(--rh-surface-2) !important;
}
.icp-pms               { color: var(--rh-blue)  !important; background: var(--rh-tint-blue)  !important; border-color: rgba(30,58,138,0.3)  !important; }
.icp-retirement-planning { color: var(--rh-green) !important; background: var(--rh-tint-green) !important; border-color: rgba(21,128,61,0.3) !important; }
.icp-nri               { color: var(--rh-amber) !important; background: var(--rh-tint-amber) !important; border-color: rgba(180,83,9,0.3)  !important; }
.icp-esops             { color: var(--rh-red)   !important; background: var(--rh-tint-red)   !important; border-color: rgba(196,30,58,0.3) !important; }
.icp-family-office     { color: #6d28d9 !important; background: rgba(109,40,217,0.06) !important; border-color: rgba(109,40,217,0.25) !important; }
.icp-others            { color: var(--rh-text-2)  !important; background: var(--rh-surface-2) !important; border-color: var(--rh-border) !important; }

/* ════ TABLES ════ */
.wb-list-table, table {
  font-family: var(--rh-sans) !important;
}
.wb-list-table th {
  font-family: var(--rh-sans) !important;
  font-size: 10px !important;
  font-weight: 700 !important;
  color: var(--rh-text-3) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.1em !important;
  padding: 11px 14px !important;
  background: var(--rh-surface-2) !important;
  border-bottom: 1px solid var(--rh-border) !important;
}
.wb-list-table td {
  padding: 11px 14px !important;
  font-size: 13px !important;
  font-family: var(--rh-sans) !important;
  border-bottom: 1px solid var(--rh-border-2) !important;
  vertical-align: middle !important;
}
.wb-list-table tbody tr:hover td { background: var(--rh-surface-2) !important; }
.wb-list-name { font-weight: 500 !important; color: var(--rh-text-1) !important; }

/* Numeric cells use mono */
.wb-list-table td[style*="text-align:right"],
.wb-list-table td[style*="color:var(--c-reg)"] {
  font-family: var(--rh-mono) !important;
  font-feature-settings: 'tnum';
}

/* ════ FORMS & INPUTS ════ */
.form-input, .filter-select, .wb-list-search, input[type="text"], input[type="email"], input[type="date"], select, textarea {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 6px !important;
  font-family: var(--rh-sans) !important;
  font-size: 13px !important;
  color: var(--rh-text-1) !important;
  padding: 8px 12px !important;
  box-shadow: none !important;
  transition: border-color 0.15s !important;
}
.form-input:focus, .filter-select:focus, .wb-list-search:focus, input:focus, select:focus, textarea:focus {
  border-color: var(--rh-text-1) !important;
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(23,23,23,0.06) !important;
}
.form-label {
  font-family: var(--rh-sans) !important;
  font-size: 11.5px !important;
  font-weight: 600 !important;
  color: var(--rh-text-2) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.05em !important;
}

/* ════ PAGE TITLES ════ */
.page-title, h1, .page-hd {
  font-family: var(--rh-serif) !important;
  font-weight: 600 !important;
  letter-spacing: -0.02em !important;
  background: none !important;
  -webkit-text-fill-color: var(--rh-text-1) !important;
  color: var(--rh-text-1) !important;
}
.page-sub { font-family: var(--rh-sans) !important; color: var(--rh-text-2) !important; font-size: 13px !important; }

/* ════ SECTION HEADERS ════ */
.sec-hd, .sec-title {
  font-family: var(--rh-sans) !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  color: var(--rh-text-1) !important;
}
.an-section-title, .wb-list-card-title {
  font-family: var(--rh-serif) !important;
  font-weight: 600 !important;
  font-size: 17px !important;
  letter-spacing: -0.01em !important;
  color: var(--rh-text-1) !important;
}

/* ════ WEBINAR DETAIL HERO ════ */
.wd-hero {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 12px !important;
  padding: 0 !important;
  box-shadow: none !important;
}
.wd-hero-accent {
  height: 3px !important;
  background: var(--rh-ink) !important;
  border-radius: 12px 12px 0 0 !important;
}
.wd-hero-body { padding: 32px 36px !important; }
.wd-hero-title {
  font-family: var(--rh-serif) !important;
  font-size: 28px !important;
  font-weight: 600 !important;
  letter-spacing: -0.02em !important;
  line-height: 1.2 !important;
  color: var(--rh-text-1) !important;
}
.wd-hero-meta {
  font-family: var(--rh-mono) !important;
  font-size: 12px !important;
  color: var(--rh-text-3) !important;
  margin-top: 8px !important;
  letter-spacing: 0 !important;
}
.wd-hero-desc { font-family: var(--rh-sans) !important; font-size: 13px !important; color: var(--rh-text-2) !important; }
.wd-hero-speaker { font-family: var(--rh-sans) !important; font-size: 13px !important; color: var(--rh-text-2) !important; }

/* ════ ANALYSIS STAT CARDS ════ */
.an-stat-card {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 8px !important;
  padding: 16px 18px !important;
  box-shadow: none !important;
}
.an-stat-val {
  font-family: var(--rh-mono) !important;
  font-weight: 500 !important;
  font-size: 22px !important;
  letter-spacing: -0.02em !important;
  font-feature-settings: 'tnum';
}
.an-stat-lbl {
  font-family: var(--rh-sans) !important;
  font-size: 10.5px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  color: var(--rh-text-3) !important;
  font-weight: 600 !important;
}
.an-stat-icon {
  background: var(--rh-surface-2) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 5px !important;
  width: 36px !important; height: 36px !important;
  color: var(--rh-text-2) !important;
}

/* ════ MODAL ════ */
.modal-overlay { background: rgba(10,10,10,0.45) !important; backdrop-filter: blur(4px) !important; }
.modal-box {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 12px !important;
  box-shadow: 0 24px 64px rgba(0,0,0,0.18) !important;
}
.modal-title {
  font-family: var(--rh-serif) !important;
  font-weight: 600 !important;
  font-size: 22px !important;
  letter-spacing: -0.01em !important;
  color: var(--rh-text-1) !important;
}

/* Status pills in modal */
.status-pill { border: 1px solid var(--rh-border) !important; border-radius: 8px !important; background: var(--rh-surface) !important; }
.status-pill:has(input:checked) { border-color: var(--rh-ink) !important; background: var(--rh-surface-2) !important; }

/* ════ LEADERBOARD ════ */
.lb-row, .leaderboard-row { background: var(--rh-surface) !important; border-bottom: 1px solid var(--rh-border-2) !important; }
.lb-name-link {
  font-family: var(--rh-sans) !important;
  font-weight: 500 !important;
  color: var(--rh-text-1) !important;
  border-bottom: 1px dashed var(--rh-text-4) !important;
  text-decoration: none !important;
}
.lb-name-link:hover { color: var(--rh-red) !important; border-bottom-color: var(--rh-red) !important; }
.lb-score {
  font-family: var(--rh-mono) !important;
  font-weight: 600 !important;
  font-size: 12px !important;
  background: var(--rh-ink) !important;
  color: var(--rh-bg) !important;
  border: 1px solid var(--rh-ink) !important;
  border-radius: 4px !important;
  padding: 3px 10px !important;
  box-shadow: none !important;
  text-shadow: none !important;
  letter-spacing: 0 !important;
}
html.dark .lb-score { background: #fafafa !important; color: #000 !important; border-color: #fafafa !important; }
.lb-email { font-family: var(--rh-mono) !important; font-size: 12px !important; color: var(--rh-text-3) !important; }

/* Attendee modal */
.att-modal { background: var(--rh-surface) !important; border-left: 1px solid var(--rh-border) !important; }
.att-modal-name { font-family: var(--rh-serif) !important; font-weight: 600 !important; }
.att-stat-num { font-family: var(--rh-mono) !important; font-weight: 500 !important; color: var(--rh-text-1) !important; }
.att-stat-lbl { font-family: var(--rh-sans) !important; font-size: 10px !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; color: var(--rh-text-3) !important; }
.att-wb-card { background: var(--rh-surface-2) !important; border: 1px solid var(--rh-border) !important; border-radius: 8px !important; }
.att-wb-card:hover { border-color: var(--rh-text-3) !important; background: var(--rh-surface) !important; transform: none !important; box-shadow: none !important; }
.att-wb-card-title { font-family: var(--rh-serif) !important; font-weight: 600 !important; font-size: 13px !important; color: var(--rh-text-1) !important; }
.att-wb-card-meta { font-family: var(--rh-mono) !important; font-size: 11px !important; color: var(--rh-text-3) !important; }
.att-wb-dur-label { font-family: var(--rh-mono) !important; font-weight: 500 !important; color: var(--rh-text-2) !important; }

/* ════ TOPICS PAGE ════ */
.topics-title { font-family: var(--rh-serif) !important; font-weight: 600 !important; font-size: 32px !important; color: var(--rh-text-1) !important; letter-spacing: -0.02em !important; }
.topics-eyebrow { color: var(--rh-red) !important; font-family: var(--rh-sans) !important; }
.topics-sub { font-family: var(--rh-sans) !important; color: var(--rh-text-2) !important; }
.btn-topics-refresh {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  color: var(--rh-text-1) !important;
  font-family: var(--rh-sans) !important;
  font-weight: 500 !important;
  border-radius: 7px !important;
}
.btn-topics-refresh:hover { background: var(--rh-surface-2) !important; border-color: var(--rh-text-3) !important; box-shadow: none !important; transform: none !important; }
.speaker-topics-card { background: var(--rh-surface) !important; border: 1px solid var(--rh-border) !important; border-radius: 12px !important; box-shadow: none !important; }
.stc-header { background: var(--rh-surface-2) !important; border-bottom: 1px solid var(--rh-border) !important; }
.stc-name { font-family: var(--rh-serif) !important; font-weight: 600 !important; color: var(--rh-text-1) !important; }
.stc-count { font-family: var(--rh-mono) !important; color: var(--rh-text-3) !important; }
.stc-avatar { border-radius: 6px !important; font-family: var(--rh-sans) !important; letter-spacing: 0 !important; }
.topic-card { background: var(--rh-surface-2) !important; border: 1px solid var(--rh-border) !important; border-radius: 8px !important; }
.topic-card:hover { background: var(--rh-surface) !important; border-color: var(--rh-text-3) !important; }
.topic-card-num {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  color: var(--rh-text-2) !important;
  font-family: var(--rh-mono) !important;
  border-radius: 4px !important;
}
.topic-title { font-family: var(--rh-serif) !important; font-weight: 600 !important; font-size: 14px !important; color: var(--rh-text-1) !important; }
.topic-hook { font-family: var(--rh-sans) !important; color: var(--rh-text-2) !important; line-height: 1.6 !important; }
.topic-angle { background: var(--rh-tint-paper) !important; border-color: rgba(180,83,9,0.2) !important; color: var(--rh-amber) !important; border-radius: 5px !important; }
html.dark .topic-angle { background: rgba(245,158,11,0.08) !important; color: var(--rh-amber) !important; }
.topic-exp { font-family: var(--rh-mono) !important; font-size: 10px !important; }
.topic-use-btn { font-family: var(--rh-sans) !important; background: var(--rh-surface) !important; border: 1px solid var(--rh-border) !important; color: var(--rh-text-1) !important; border-radius: 6px !important; }
.topic-use-btn:hover { background: var(--rh-ink) !important; color: var(--rh-bg) !important; border-color: var(--rh-ink) !important; }

/* ════ AI ANALYSIS PANEL ════ */
.aip {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}
.aip-header { background: var(--rh-surface-2) !important; border-bottom: 1px solid var(--rh-border) !important; }
.aip-header-title { font-family: var(--rh-serif) !important; font-weight: 600 !important; color: var(--rh-text-1) !important; font-size: 14px !important; }
.aip-header-badge { background: var(--rh-tint-red) !important; color: var(--rh-red) !important; border-color: rgba(196,30,58,0.25) !important; font-family: var(--rh-sans) !important; }
.aip-header-icon { color: var(--rh-red) !important; }
.aip-card-hd { color: var(--rh-text-3) !important; font-family: var(--rh-sans) !important; }
.aip-grade-card { background: var(--rh-surface-2) !important; border-right: 1px solid var(--rh-border) !important; }
.aip-kpi-val { font-family: var(--rh-mono) !important; font-weight: 500 !important; letter-spacing: -0.02em !important; color: var(--rh-text-1) !important; }
.aip-kpi-lbl { font-family: var(--rh-sans) !important; color: var(--rh-text-3) !important; }
.aip-card { border-right-color: var(--rh-border) !important; }
.aip-fn-label, .aip-bench-lbl, .aip-dur-lbl { font-family: var(--rh-sans) !important; color: var(--rh-text-3) !important; }
.aip-fn-num, .aip-bench-val, .aip-dur-pct, .aip-fn-pct { font-family: var(--rh-mono) !important; }
.aip-insight { background: var(--rh-surface-2) !important; border: 1px solid var(--rh-border) !important; border-radius: 8px !important; }
.aip-insight:hover { background: var(--rh-surface) !important; border-color: var(--rh-text-3) !important; }
.aip-insight-icon-wrap { background: var(--rh-surface) !important; border: 1px solid var(--rh-border) !important; color: var(--rh-text-1) !important; border-radius: 5px !important; }
.aip-insight-title { font-family: var(--rh-serif) !important; font-weight: 600 !important; color: var(--rh-text-1) !important; }
.aip-insight-text { font-family: var(--rh-sans) !important; color: var(--rh-text-2) !important; }
.aip-insight-tag { background: var(--rh-tint-red) !important; color: var(--rh-red) !important; border-color: rgba(196,30,58,0.25) !important; font-family: var(--rh-sans) !important; border-radius: 3px !important; }
.aip-verdict-card { background: var(--rh-tint-paper) !important; }
html.dark .aip-verdict-card { background: rgba(250,204,21,0.04) !important; }
.aip-verdict-text { font-family: var(--rh-serif) !important; font-style: italic !important; font-size: 14px !important; color: var(--rh-text-1) !important; }
.aip-verdict-footer { font-family: var(--rh-mono) !important; }
.aip-rec { font-family: var(--rh-sans) !important; color: var(--rh-text-2) !important; }
.aip-rec-icon { background: var(--rh-tint-green) !important; color: var(--rh-green) !important; border-color: rgba(21,128,61,0.3) !important; border-radius: 4px !important; }

/* Analyze with AI button */
.btn-ai-analyze {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-text-1) !important;
  color: var(--rh-text-1) !important;
  border-radius: 6px !important;
  font-family: var(--rh-sans) !important;
  font-weight: 600 !important;
  padding: 7px 13px !important;
  box-shadow: none !important;
}
.btn-ai-analyze:hover:not(:disabled) { background: var(--rh-ink) !important; color: var(--rh-bg) !important; box-shadow: none !important; transform: none !important; }
.btn-ai-analyze.ai-done { border-color: var(--rh-green) !important; color: var(--rh-green) !important; background: var(--rh-tint-green) !important; }

/* ════ CHATBOT ════ */
.chat-fab {
  background: var(--rh-ink) !important;
  color: var(--rh-bg) !important;
  border-radius: 10px !important;
  padding: 12px 18px !important;
  font-family: var(--rh-sans) !important;
  font-weight: 600 !important;
  box-shadow: 0 4px 14px rgba(0,0,0,0.15) !important;
}
.chat-fab:hover { background: #1f1f1f !important; box-shadow: 0 6px 20px rgba(0,0,0,0.22) !important; transform: translateY(-2px) !important; }
html.dark .chat-fab { background: #fafafa !important; color: #000 !important; }
.chatbot-wrap {
  background: var(--rh-surface) !important;
  border: 1px solid var(--rh-border) !important;
  border-radius: 12px !important;
  box-shadow: 0 24px 64px rgba(0,0,0,0.18) !important;
}
.chatbot-header { background: var(--rh-surface-2) !important; border-bottom: 1px solid var(--rh-border) !important; }
.chatbot-avatar { background: var(--rh-ink) !important; color: var(--rh-bg) !important; border-radius: 6px !important; }
html.dark .chatbot-avatar { background: #fafafa !important; color: #000 !important; }
.chatbot-hd-title { font-family: var(--rh-serif) !important; font-weight: 600 !important; color: var(--rh-text-1) !important; }
.chatbot-hd-sub { font-family: var(--rh-sans) !important; color: var(--rh-text-3) !important; }
.chat-bubble { font-family: var(--rh-sans) !important; font-size: 13px !important; line-height: 1.6 !important; }
.chat-msg-user .chat-bubble {
  background: var(--rh-ink) !important; color: var(--rh-bg) !important;
  border-radius: 10px 10px 3px 10px !important;
}
html.dark .chat-msg-user .chat-bubble { background: #fafafa !important; color: #000 !important; }
.chat-msg-ai .chat-bubble { background: var(--rh-surface-2) !important; color: var(--rh-text-1) !important; border: 1px solid var(--rh-border) !important; border-radius: 10px 10px 10px 3px !important; }
.chat-suggestions button { background: var(--rh-surface) !important; border: 1px solid var(--rh-border) !important; color: var(--rh-text-1) !important; border-radius: 14px !important; font-family: var(--rh-sans) !important; }
.chat-suggestions button:hover { background: var(--rh-ink) !important; color: var(--rh-bg) !important; border-color: var(--rh-ink) !important; }
.chatbot-input { background: var(--rh-surface-2) !important; border: 1px solid var(--rh-border) !important; color: var(--rh-text-1) !important; }
.chatbot-input:focus { border-color: var(--rh-text-1) !important; }
.chatbot-send { background: var(--rh-ink) !important; color: var(--rh-bg) !important; border-radius: 8px !important; }
html.dark .chatbot-send { background: #fafafa !important; color: #000 !important; }

/* ════ ACTIVITY FEED ════ */
.act-feed-card { background: var(--rh-surface) !important; border: 1px solid var(--rh-border) !important; border-radius: 10px !important; box-shadow: none !important; }
.act-feed-title { font-family: var(--rh-serif) !important; font-weight: 600 !important; color: var(--rh-text-1) !important; }
.act-item { border-bottom: 1px solid var(--rh-border-2) !important; }
.act-item-title { font-family: var(--rh-sans) !important; font-weight: 500 !important; color: var(--rh-text-1) !important; }
.act-item-desc { font-family: var(--rh-sans) !important; color: var(--rh-text-3) !important; }
.act-item-icon { background: var(--rh-surface-2) !important; border: 1px solid var(--rh-border) !important; border-radius: 6px !important; color: var(--rh-text-2) !important; }

/* ════ SPEAKER CARDS ════ */
.spk-card { background: var(--rh-surface) !important; border: 1px solid var(--rh-border) !important; border-radius: 10px !important; box-shadow: none !important; }
.spk-card:hover { border-color: var(--rh-text-3) !important; transform: none !important; box-shadow: none !important; }
.spk-name { font-family: var(--rh-serif) !important; font-weight: 600 !important; font-size: 16px !important; color: var(--rh-text-1) !important; }
.spk-bio { font-family: var(--rh-sans) !important; color: var(--rh-text-2) !important; }
.spk-stat-val { font-family: var(--rh-mono) !important; font-weight: 500 !important; color: var(--rh-text-1) !important; }
.spk-stat-lbl { font-family: var(--rh-sans) !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; color: var(--rh-text-3) !important; }
.spk-avatar { border-radius: 6px !important; font-family: var(--rh-sans) !important; font-weight: 700 !important; letter-spacing: 0 !important; }

/* ════ FILTER CHIPS (navbar) ════ */
.tb-chip {
  font-family: var(--rh-sans) !important;
  background: transparent !important;
  border: 1px solid var(--rh-border) !important;
  color: var(--rh-text-2) !important;
  border-radius: 6px !important;
  font-weight: 500 !important;
  font-size: 11.5px !important;
  padding: 5px 11px !important;
}
.tb-chip:hover { background: var(--rh-surface) !important; color: var(--rh-text-1) !important; }
.tb-chip.active { background: var(--rh-ink) !important; color: var(--rh-bg) !important; border-color: var(--rh-ink) !important; }
html.dark .tb-chip.active { background: #fafafa !important; color: #000 !important; border-color: #fafafa !important; }

/* ════ TOAST ════ */
.toast { background: var(--rh-ink) !important; color: var(--rh-bg) !important; border-radius: 8px !important; font-family: var(--rh-sans) !important; box-shadow: 0 8px 24px rgba(0,0,0,0.2) !important; }
html.dark .toast { background: #fafafa !important; color: #000 !important; }

/* ════ DASH HERO CTA ════ */
.dash-hero .btn { background: var(--rh-ink) !important; color: var(--rh-bg) !important; border: 1px solid var(--rh-ink) !important; }
html.dark .dash-hero .btn { background: #fafafa !important; color: #000 !important; border-color: #fafafa !important; }

/* ════ MONOSPACE all numbers in tables/cards ════ */
[data-countup], .countup, .stat-num, .metric-val { font-family: var(--rh-mono) !important; font-feature-settings: 'tnum'; }

/* ════ Generic resets for any remaining gradients ════ */
.an-bar-fill, .progress-fill { background: var(--rh-ink) !important; }
.bar-fill { background: var(--rh-ink) !important; }
html.dark .an-bar-fill, html.dark .progress-fill, html.dark .bar-fill { background: #fafafa !important; }

/* Status-color bars stay colored */
.an-bar-fill[style*="background:#10b981"], .an-bar-fill[style*="background:#15803d"] { background: var(--rh-green) !important; }
.an-bar-fill[style*="background:#f59e0b"], .an-bar-fill[style*="background:#d97706"] { background: var(--rh-amber) !important; }
.an-bar-fill[style*="background:#ef4444"], .an-bar-fill[style*="background:#dc2626"] { background: var(--rh-red) !important; }

/* ════ Scrollbar ════ */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--rh-border) !important; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--rh-text-3) !important; }

/* ════ Numeric color highlights stay semantic ════ */
[style*="color:var(--c-reg)"] { color: var(--rh-blue) !important; font-family: var(--rh-mono) !important; }
[style*="color:var(--c-att)"] { color: var(--rh-green) !important; font-family: var(--rh-mono) !important; }
[style*="color:var(--c-nosh)"] { color: var(--rh-red) !important; font-family: var(--rh-mono) !important; }

/* Remove decorative dot separators */
.wb-card-meta-dot, .att-wb-card-meta-dot { background: var(--rh-text-4) !important; opacity: 0.5 !important; }
"""

# Read existing CSS
content = open('static/styles.css', encoding='utf-8').read()

# Remove any old REDESIGN section
marker = '/* ════════════════════════════════════════════════════════════════════════════\n   EDITORIAL REDESIGN v25'
if marker in content:
    content = content[:content.find(marker)]

# Append the new redesign
content = content + REDESIGN

open('static/styles.css', 'w', encoding='utf-8').write(content)
print(f'Done. Final size: {len(content)} chars')
