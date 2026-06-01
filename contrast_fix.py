"""Append sweeping global contrast catch-all CSS for light mode."""

CSS = r"""

/* ════════════════════════════════════════════════════════════════════════════
   GLOBAL TEXT CONTRAST CATCH-ALL v25.2
   Force readable text everywhere in light mode
   ════════════════════════════════════════════════════════════════════════════ */

/* === Default colors for all text containers in light mode === */
html:not(.dark) body { color: var(--rh-text-1); }
html:not(.dark) p, html:not(.dark) span, html:not(.dark) div, html:not(.dark) label, html:not(.dark) li,
html:not(.dark) h1, html:not(.dark) h2, html:not(.dark) h3, html:not(.dark) h4, html:not(.dark) h5 {
  color: var(--rh-text-1);
}

/* === AI Analysis panel === */
html:not(.dark) .aip-fn-label,
html:not(.dark) .aip-bench-lbl,
html:not(.dark) .aip-dur-lbl,
html:not(.dark) .aip-card-hd,
html:not(.dark) .aip-grade-summary,
html:not(.dark) .aip-insight-text { color: var(--rh-text-2) !important; }

html:not(.dark) .aip-fn-num,
html:not(.dark) .aip-fn-pct,
html:not(.dark) .aip-bench-val,
html:not(.dark) .aip-dur-pct,
html:not(.dark) .aip-kpi-val,
html:not(.dark) .aip-grade-label,
html:not(.dark) .aip-score-summary,
html:not(.dark) .aip-insight-title,
html:not(.dark) .aip-rec,
html:not(.dark) .aip-verdict-text,
html:not(.dark) .aip-header-title { color: var(--rh-text-1) !important; }

html:not(.dark) .aip-kpi-lbl,
html:not(.dark) .aip-dur-sub,
html:not(.dark) .aip-dur-count,
html:not(.dark) .aip-powered-by,
html:not(.dark) .aip-verdict-footer { color: var(--rh-text-3) !important; }

/* AI Analysis avg session pill */
html:not(.dark) .aip-avg-pill {
  background: #fff7d6 !important;
  border-color: rgba(180,83,9,0.3) !important;
  color: var(--rh-text-1) !important;
}
html:not(.dark) .aip-avg-pill svg { color: var(--rh-amber) !important; }
html:not(.dark) .aip-avg-pill strong { color: var(--rh-text-1) !important; }

/* No-shows row full opacity */
.aip-fn-noshow { opacity: 1 !important; }
html:not(.dark) .aip-fn-noshow .aip-fn-label,
html:not(.dark) .aip-fn-noshow .aip-fn-num { color: var(--rh-text-2) !important; }

/* === Webinar detail === */
html:not(.dark) .wd-hero-title,
html:not(.dark) .an-stat-val,
html:not(.dark) .upload-card-title,
html:not(.dark) .sec-title,
html:not(.dark) .upload-tag { color: var(--rh-text-1) !important; }

html:not(.dark) .wd-hero-desc,
html:not(.dark) .wd-hero-speaker,
html:not(.dark) .upload-card-sub { color: var(--rh-text-2) !important; }

html:not(.dark) .wd-hero-meta,
html:not(.dark) .an-stat-lbl,
html:not(.dark) .log-row span { color: var(--rh-text-3) !important; }

/* === Dashboard hero === */
html:not(.dark) .dash-hero-title { color: var(--rh-text-1) !important; -webkit-text-fill-color: var(--rh-text-1) !important; }
html:not(.dark) .dash-hero-sub { color: var(--rh-text-2) !important; }
html:not(.dark) .dash-hero-eyebrow { color: var(--rh-text-3) !important; }

/* === Tables === */
html:not(.dark) table th { color: var(--rh-text-3) !important; }
html:not(.dark) table td { color: var(--rh-text-1) !important; }
html:not(.dark) .wb-list-name { color: var(--rh-text-1) !important; }

/* === Forms === */
html:not(.dark) input, html:not(.dark) select, html:not(.dark) textarea {
  color: var(--rh-text-1) !important;
  background: var(--rh-surface) !important;
}
html:not(.dark) input::placeholder, html:not(.dark) textarea::placeholder { color: var(--rh-text-3) !important; }
html:not(.dark) .form-label { color: var(--rh-text-2) !important; }
html:not(.dark) .sp-label { color: var(--rh-text-1) !important; }
html:not(.dark) .sp-desc { color: var(--rh-text-3) !important; }

/* === Topic page === */
html:not(.dark) .topics-title,
html:not(.dark) .stc-name,
html:not(.dark) .topic-title { color: var(--rh-text-1) !important; }
html:not(.dark) .topics-sub,
html:not(.dark) .stc-count,
html:not(.dark) .topic-hook { color: var(--rh-text-2) !important; }
html:not(.dark) .topics-eyebrow { color: var(--rh-red) !important; }
html:not(.dark) .topic-angle { color: var(--rh-amber) !important; }
html:not(.dark) .topic-card-num { color: var(--rh-text-2) !important; }

/* === Speakers === */
html:not(.dark) .spk-name,
html:not(.dark) .spk-hero-title,
html:not(.dark) .spk-stat-val { color: var(--rh-text-1) !important; }
html:not(.dark) .spk-bio,
html:not(.dark) .spk-hero-bio,
html:not(.dark) .spk-hero-email { color: var(--rh-text-2) !important; }
html:not(.dark) .spk-stat-lbl { color: var(--rh-text-3) !important; }

/* === Leaderboard === */
html:not(.dark) .lb-name-link,
html:not(.dark) .lb-name { color: var(--rh-text-1) !important; }
html:not(.dark) .lb-pos,
html:not(.dark) .lb-email,
html:not(.dark) .lb-phone { color: var(--rh-text-3) !important; }

/* === Attendee modal === */
html:not(.dark) .att-modal-name,
html:not(.dark) .att-stat-num,
html:not(.dark) .att-wb-card-title,
html:not(.dark) .att-modal-section-title { color: var(--rh-text-1) !important; }
html:not(.dark) .att-modal-email,
html:not(.dark) .att-stat-lbl,
html:not(.dark) .att-wb-card-meta { color: var(--rh-text-2) !important; }
html:not(.dark) .att-wb-dur-label { color: var(--rh-text-1) !important; font-weight: 600 !important; }

/* === Activity feed === */
html:not(.dark) .act-feed-title,
html:not(.dark) .act-item-title { color: var(--rh-text-1) !important; }
html:not(.dark) .act-item-desc { color: var(--rh-text-2) !important; }
html:not(.dark) .act-item-time { color: var(--rh-text-3) !important; }

/* === Chatbot === */
html:not(.dark) .chat-msg-ai .chat-bubble { color: var(--rh-text-1) !important; background: var(--rh-surface-2) !important; }
html:not(.dark) .chat-suggestions button { color: var(--rh-text-1) !important; }
html:not(.dark) .chatbot-input { color: var(--rh-text-1) !important; }
html:not(.dark) .chatbot-input::placeholder { color: var(--rh-text-3) !important; }
html:not(.dark) .chatbot-hd-title { color: var(--rh-text-1) !important; }
html:not(.dark) .chatbot-hd-sub { color: var(--rh-text-3) !important; }

/* === KPI banner === */
html:not(.dark) .kpi-card-label { color: var(--rh-text-3) !important; }
html:not(.dark) .kpi-card-val { color: var(--rh-text-1) !important; -webkit-text-fill-color: var(--rh-text-1) !important; background: none !important; }
html:not(.dark) .kpi-card-trend { color: var(--rh-text-3) !important; }

/* === Webinar cards in grid === */
html:not(.dark) .wb-card-title { color: var(--rh-text-1) !important; }
html:not(.dark) .wb-card-meta { color: var(--rh-text-3) !important; }
html:not(.dark) .wb-card-speaker { color: var(--rh-text-2) !important; }
html:not(.dark) .wb-card-stat-val { color: var(--rh-text-1) !important; }
html:not(.dark) .wb-card-stat-lbl { color: var(--rh-text-3) !important; }

/* === Status breakdown chart === */
html:not(.dark) .sb-bar-label,
html:not(.dark) .sb-bar-count,
html:not(.dark) .sb-title,
html:not(.dark) .sb-legend-label { color: var(--rh-text-1) !important; }

/* === Notification panel === */
html:not(.dark) .notif-panel,
html:not(.dark) .notif-panel-title,
html:not(.dark) .notif-item-title { color: var(--rh-text-1) !important; }
html:not(.dark) .notif-item-desc { color: var(--rh-text-2) !important; }

/* === Filter chips === */
html:not(.dark) .tb-chip { color: var(--rh-text-2) !important; }
html:not(.dark) .tb-chip.active { color: var(--rh-bg) !important; }

/* === Modal === */
html:not(.dark) .modal-title { color: var(--rh-text-1) !important; }
html:not(.dark) .modal-sub { color: var(--rh-text-2) !important; }

/* === Empty states === */
html:not(.dark) .empty-state,
html:not(.dark) .empty-title,
html:not(.dark) .empty-state-title { color: var(--rh-text-1) !important; }
html:not(.dark) .empty-state-sub,
html:not(.dark) .empty-state-desc { color: var(--rh-text-2) !important; }
html:not(.dark) .empty-icon { color: var(--rh-text-3) !important; opacity: 0.4 !important; }

/* === Back button === */
html:not(.dark) .back-btn { color: var(--rh-text-2) !important; }
html:not(.dark) .back-btn:hover { color: var(--rh-text-1) !important; }

/* === Breadcrumb === */
html:not(.dark) .tb-bc-home,
html:not(.dark) .tb-bc-page,
html:not(.dark) .tb-bc-current { color: var(--rh-text-1) !important; }
html:not(.dark) .tb-bc-page { color: var(--rh-text-2) !important; }
html:not(.dark) .tb-bc-sep { color: var(--rh-text-3) !important; }

/* === Filter panel === */
html:not(.dark) .filter-panel,
html:not(.dark) .filter-section-title { color: var(--rh-text-1) !important; }

/* === Page sub-titles === */
html:not(.dark) .page-sub,
html:not(.dark) .page-eyebrow,
html:not(.dark) .section-sub { color: var(--rh-text-2) !important; }

/* === ICP filter dropdown === */
html:not(.dark) .filter-icp { color: var(--rh-text-1) !important; }

/* === Generic body text in any card === */
html:not(.dark) .card p,
html:not(.dark) .card span:not([class]),
html:not(.dark) .card-body p,
html:not(.dark) .card-body span:not([class]) { color: var(--rh-text-1) !important; }

/* === Toast === */
.toast { color: var(--rh-bg) !important; }
"""

content = open('static/styles.css', encoding='utf-8').read()
# Remove any old GLOBAL TEXT CONTRAST section if present
marker = '/* ════════════════════════════════════════════════════════════════════════════\n   GLOBAL TEXT CONTRAST CATCH-ALL v25.2'
if marker in content:
    content = content[:content.find(marker)]

content += CSS
open('static/styles.css', 'w', encoding='utf-8').write(content)
print(f'Done. Size: {len(content)} chars')
