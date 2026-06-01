extra = r"""

/* ════════════════════════════════════════════════════════════════════════════
   v3.3 RENDERING FIXES - bars, tracks, modal contrast, form contrast
   ════════════════════════════════════════════════════════════════════════════ */

/* === AI Analysis bars: track + fill colors that work on light bg === */
html:not(.dark) .aip-fn-track,
html:not(.dark) .aip-dur-track,
html:not(.dark) .aip-bench-track {
  background: #E2E8F0 !important;
  border-radius: 9999px !important;
  height: 10px !important;
  overflow: hidden !important;
}
html:not(.dark) .aip-fn-bar,
html:not(.dark) .aip-dur-fill,
html:not(.dark) .aip-bench-fill {
  height: 100% !important;
  border-radius: 9999px !important;
}

/* === Webinar list mini progress bars === */
.an-bar-fill { height: 100% !important; border-radius: 9999px !important; }

/* === Section headings === */
.sec-hd { display: flex !important; align-items: center !important; gap: 10px !important; margin-bottom: 16px !important; }
.sec-hd .sec-title {
  font-family: var(--font-serif) !important;
  font-weight: 700 !important;
  font-size: 1rem !important;
  color: var(--text-primary) !important;
}
.sec-hd > span:not(.sec-title) {
  font-family: var(--font-ui) !important;
  font-size: 0.78rem !important;
  color: var(--text-muted) !important;
}

/* === Webinar card hover backgrounds === */
.wb-card { background: rgba(255,255,255,0.85) !important; }
.wb-card:hover { background: rgba(255,255,255,0.95) !important; }
html.dark .wb-card { background: rgba(30,41,59,0.85) !important; }
html.dark .wb-card:hover { background: rgba(51,65,85,0.95) !important; }

/* === Status pill radios hidden but content visible === */
.status-pill input[type="radio"] {
  position: absolute !important;
  opacity: 0 !important;
  pointer-events: none !important;
}
.status-pill { position: relative !important; cursor: pointer !important; }
.sp-content {
  display: flex !important;
  flex-direction: column !important;
  gap: 2px !important;
  padding: 10px 14px !important;
}

/* === Upload tag (incomplete/complete) === */
.upload-tag {
  display: inline-flex !important;
  align-items: center !important;
  gap: 5px !important;
  font-family: var(--font-ui) !important;
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  padding: 4px 10px !important;
  border-radius: 9999px !important;
  white-space: nowrap !important;
}
.upload-tag.has { background: #ECFDF5 !important; color: #065F46 !important; }
.upload-tag.none { background: #FFFBEB !important; color: #B45309 !important; }

/* === Filter select width consistency === */
.filter-select { min-width: 140px !important; }

/* === Page loading spinner === */
.spinner {
  width: 32px !important; height: 32px !important;
  border: 3px solid rgba(99,102,241,0.15) !important;
  border-top-color: var(--accent-indigo) !important;
  border-radius: 50% !important;
  animation: plspin 0.75s linear infinite !important;
}

/* === Notification panel === */
.notif-panel {
  background: rgba(255,255,255,0.95) !important;
  backdrop-filter: blur(20px) saturate(180%) !important;
  border: 1px solid var(--border-subtle) !important;
  border-radius: 1.5rem !important;
  box-shadow: 0 24px 60px rgba(0,0,0,0.15) !important;
}
html.dark .notif-panel { background: rgba(30,41,59,0.95) !important; }
.notif-panel-title {
  font-family: var(--font-serif) !important;
  font-weight: 700 !important;
  font-size: 1.05rem !important;
  color: var(--text-primary) !important;
}
.notif-item {
  border-bottom: 1px solid var(--border-subtle) !important;
  padding: 14px 16px !important;
}
.notif-item-title { font-family: var(--font-ui) !important; font-weight: 600 !important; color: var(--text-primary) !important; }
.notif-item-desc { font-family: var(--font-ui) !important; font-size: 0.82rem !important; color: var(--text-secondary) !important; }

/* === Dashboard status breakdown chart === */
.sb-chart {
  background: var(--surface-card) !important;
  border: 1px solid var(--border-subtle) !important;
  border-radius: 1.5rem !important;
  padding: 22px 24px !important;
}
.sb-bar-track { background: #E2E8F0 !important; border-radius: 9999px !important; height: 10px !important; }
html.dark .sb-bar-track { background: rgba(255,255,255,0.10) !important; }
.sb-bar-fill { border-radius: 9999px !important; height: 100% !important; }

/* === Speaker rows on analytics === */
.an-spk-rate { font-family: var(--font-mono) !important; font-weight: 700 !important; color: var(--text-primary) !important; }
.an-spk-grade {
  font-family: var(--font-ui) !important;
  font-weight: 800 !important;
  border-radius: 0.5rem !important;
  padding: 3px 9px !important;
}

/* === Webinar list search focus === */
.wb-list-search:focus {
  border-color: var(--accent-indigo) !important;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.15), 0 6px 18px rgba(15,23,42,0.07) !important;
}

/* === Dropdown select arrow === */
select.filter-select, select.form-input {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%239CA3AF' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") !important;
  background-repeat: no-repeat !important;
  background-position: right 14px center !important;
  background-size: 10px !important;
  padding-right: 36px !important;
  -webkit-appearance: none !important;
  -moz-appearance: none !important;
  appearance: none !important;
}

/* === AI Analysis avg pill === */
html:not(.dark) .aip-avg-pill {
  background: rgba(124,58,237,0.08) !important;
  border: 1px solid rgba(124,58,237,0.25) !important;
  color: var(--text-primary) !important;
}
html:not(.dark) .aip-avg-pill svg { color: var(--accent-primary) !important; }
html:not(.dark) .aip-avg-pill strong { color: var(--text-primary) !important; }

/* === Webinar grid layout === */
.wb-grid {
  display: grid !important;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)) !important;
  gap: 18px !important;
}

/* === Status badges always have a bg in light mode === */
html:not(.dark) .wb-badge.completed   { background: #ECFDF5 !important; color: #065F46 !important; }
html:not(.dark) .wb-badge.incomplete  { background: #FFFBEB !important; color: #B45309 !important; }
html:not(.dark) .wb-badge.upcoming    { background: #EEF2FF !important; color: #4338CA !important; }
html:not(.dark) .wb-badge.cancelled   { background: #FEF2F2 !important; color: #991B1B !important; }

/* === Insights icon wrap in AI Analysis === */
.aip-insight-icon-wrap {
  background: rgba(124,58,237,0.10) !important;
  border: 1px solid rgba(124,58,237,0.20) !important;
  color: var(--accent-primary) !important;
}
html.dark .aip-insight-icon-wrap {
  background: rgba(124,58,237,0.18) !important;
  border-color: rgba(124,58,237,0.35) !important;
}

/* === Verdict text === */
.aip-verdict-text {
  font-family: var(--font-serif) !important;
  font-style: italic !important;
  font-size: 1rem !important;
  line-height: 1.7 !important;
  color: var(--text-primary) !important;
}

/* === Headlines in compare panel === */
.cmp-headline { color: var(--text-primary) !important; }

/* === Modal labels and inputs always readable === */
.modal-box .form-label { color: var(--text-secondary) !important; }
.modal-box .form-input {
  color: var(--text-primary) !important;
  background: var(--surface-input) !important;
  border-color: var(--border-input) !important;
}

/* === Status breakdown empty state === */
.empty-state { padding: 32px 24px !important; text-align: center !important; }
.empty-state .empty-icon { font-size: 1.5rem; color: var(--text-muted) !important; opacity: 0.5 !important; margin-bottom: 8px !important; }
.empty-state .empty-title { color: var(--text-primary) !important; }
.empty-state .empty-state-sub { color: var(--text-secondary) !important; font-size: 0.875rem !important; margin-top: 4px !important; }
"""

content = open('static/trilliant.css', encoding='utf-8').read()
marker_text = "v3.3 RENDERING FIXES"
if marker_text in content:
    # Strip the previous v3.3 block
    idx = content.find("/* ════════════════════════════════════════════════════════════════════════════\n   v3.3 RENDERING FIXES")
    if idx >= 0:
        content = content[:idx]
content += extra
open('static/trilliant.css', 'w', encoding='utf-8').write(content)
print(f'Done. Size: {len(content)} chars')
