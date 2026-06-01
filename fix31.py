CSS = r"""

/* ════════════════════════════════════════════════════════════════════════════
   v3.1 FIXES - chat fab hover, monthly chart, compare panel, score filter
   ════════════════════════════════════════════════════════════════════════════ */

/* ── Chat FAB hover fix ── */
.chat-fab {
  background: var(--grad-brand) !important;
  color: #fff !important;
}
.chat-fab:hover:not(.active) {
  background: linear-gradient(135deg, #6D28D9, #4338CA) !important;
  color: #fff !important;
  box-shadow: 0 14px 32px rgba(124,58,237,0.55) !important;
  transform: translateY(-2px) !important;
}
.chat-fab.active {
  background: rgba(15,23,42,0.85) !important;
  color: #fff !important;
}
.chat-fab.active:hover {
  background: rgba(15,23,42,1) !important;
  color: #fff !important;
}
.chat-fab svg { color: #fff !important; }
.chat-fab-label { color: #fff !important; }

/* ── Monthly volume chart ── */
.an-monthly-card {
  background: var(--surface-card) !important;
  backdrop-filter: blur(16px) saturate(140%) !important;
  border: 1px solid var(--border-subtle) !important;
  border-radius: 1.5rem !important;
  padding: 22px 24px 22px !important;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
  overflow: visible !important;
}
.an-month-chart {
  display: flex !important;
  align-items: flex-end !important;
  gap: 12px !important;
  padding: 18px 4px 4px !important;
  overflow-x: auto !important;
  min-height: 180px !important;
}
.an-month-col {
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  gap: 10px !important;
  min-width: 38px !important;
  flex: 1 !important;
}
.an-month-bars {
  display: flex !important;
  align-items: flex-end !important;
  gap: 3px !important;
  height: 120px !important;
}
.an-month-bar {
  width: 14px !important;
  border-radius: 4px 4px 0 0 !important;
  min-height: 2px !important;
  transition: opacity 0.2s !important;
}
.an-month-bar:hover { opacity: 0.85 !important; }
.an-month-label {
  font-family: var(--font-mono) !important;
  font-size: 0.7rem !important;
  color: var(--text-muted) !important;
  white-space: nowrap !important;
  font-weight: 600 !important;
  letter-spacing: 0 !important;
  padding-top: 4px !important;
}
.an-card-head {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  font-family: var(--font-serif) !important;
  font-weight: 700 !important;
  font-size: 1rem !important;
  color: var(--text-primary) !important;
  margin-bottom: 6px !important;
}
.an-chart-legend {
  display: flex !important;
  gap: 14px !important;
  font-family: var(--font-ui) !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  color: var(--text-secondary) !important;
}
.an-chart-legend span { display: inline-flex !important; align-items: center !important; gap: 5px !important; }
.an-leg-dot {
  width: 9px !important; height: 9px !important;
  border-radius: 9999px !important;
  display: inline-block !important;
}

/* ── Compare button ── */
.btn-ai-compare {
  display: inline-flex !important;
  align-items: center !important;
  gap: 6px !important;
  background: rgba(124,58,237,0.08) !important;
  border: 1px solid rgba(124,58,237,0.25) !important;
  color: var(--accent-primary) !important;
  border-radius: 9999px !important;
  font-family: var(--font-ui) !important;
  font-weight: 700 !important;
  font-size: 12.5px !important;
  padding: 7px 14px !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
  white-space: nowrap !important;
}
.btn-ai-compare:hover:not(:disabled) {
  background: rgba(124,58,237,0.15) !important;
  border-color: var(--accent-primary) !important;
  box-shadow: 0 4px 14px rgba(124,58,237,0.20) !important;
  transform: translateY(-1px) !important;
}
.btn-ai-compare:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ai-compare.ai-done {
  background: rgba(16,185,129,0.10) !important;
  border-color: var(--status-success) !important;
  color: var(--status-success) !important;
}

/* ── Compare panel ── */
.cmp-panel { padding: 0 !important; overflow: hidden !important; }
.cmp-headline {
  padding: 20px 24px;
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 1.05rem;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  background: var(--accent-primary-soft);
  border-bottom: 1px solid var(--border-subtle);
  line-height: 1.45;
}
.cmp-context {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 16px;
  padding: 20px 24px;
  align-items: center;
  border-bottom: 1px solid var(--border-subtle);
}
.cmp-card {
  background: rgba(255,255,255,0.50);
  border: 1px solid var(--border-subtle);
  border-radius: 1rem;
  padding: 14px 16px;
}
html.dark .cmp-card { background: rgba(15,23,42,0.50); }
.cmp-card-tag {
  font-family: var(--font-ui);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.cmp-card-cur .cmp-card-tag { color: var(--accent-primary); }
.cmp-card-title {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--text-primary);
  line-height: 1.3;
  margin-bottom: 4px;
}
.cmp-card-meta { font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); }
.cmp-vs {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--text-muted);
  text-align: center;
}

.cmp-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-ui);
}
.cmp-table th {
  font-size: 0.66rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  padding: 12px 24px;
  background: var(--surface-card-header);
  text-align: left;
  border-bottom: 1px solid var(--border-subtle);
}
.cmp-table td {
  padding: 14px 24px;
  border-bottom: 1px solid rgba(15,23,42,0.04);
  font-size: 0.875rem;
}
.cmp-lbl { color: var(--text-secondary); font-weight: 600; }
.cmp-val { font-family: var(--font-mono); font-weight: 600; color: var(--text-primary); }
.cmp-prev { color: var(--text-muted); }
.cmp-delta { font-family: var(--font-mono); font-weight: 700; }
.cmp-up   { color: var(--status-success); }
.cmp-down { color: var(--status-danger); }
.cmp-flat { color: var(--text-muted); }
.cmp-pct  { opacity: 0.85; }

.cmp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border-bottom: 1px solid var(--border-subtle);
}
.cmp-block { padding: 20px 24px; }
.cmp-block:first-child { border-right: 1px solid var(--border-subtle); }
.cmp-block-title {
  font-family: var(--font-ui);
  font-size: 0.78rem;
  font-weight: 700;
  margin-bottom: 12px;
}
.cmp-wins .cmp-block-title { color: var(--status-success); }
.cmp-losses .cmp-block-title { color: var(--status-danger); }
.cmp-block ul { list-style: none; padding: 0; margin: 0; }
.cmp-block li {
  font-family: var(--font-ui);
  font-size: 0.82rem;
  color: var(--text-secondary);
  padding: 5px 0 5px 16px;
  position: relative;
  line-height: 1.55;
}
.cmp-empty { opacity: 0.5; font-style: italic; }

.cmp-diagnosis, .cmp-action {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-subtle);
}
.cmp-action {
  background: var(--accent-primary-soft);
  border-bottom: none;
}
.cmp-diagnosis p, .cmp-action p {
  font-family: var(--font-ui);
  font-size: 0.875rem;
  color: var(--text-primary);
  line-height: 1.6;
  margin: 4px 0 0;
}
.cmp-action p strong { color: var(--accent-primary); }

/* ── Leaderboard score range filter ── */
.lb-score-range {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.60);
  border: 1px solid var(--border-subtle);
  border-radius: 9999px;
  padding: 4px 14px 4px 16px;
  backdrop-filter: blur(8px);
}
.lb-score-lbl {
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.lb-score-input {
  width: 70px !important;
  padding: 6px 8px !important;
  border-radius: 9999px !important;
  border: 1px solid var(--border-input) !important;
  background: var(--surface-input) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-mono) !important;
  font-size: 12px !important;
  text-align: center !important;
}
.lb-score-input:focus {
  border-color: var(--accent-indigo) !important;
  box-shadow: 0 0 0 2px rgba(99,102,241,0.15) !important;
}
.lb-score-dash {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

@media (max-width: 640px) {
  .cmp-context { grid-template-columns: 1fr; }
  .cmp-vs { padding: 4px 0; }
  .cmp-grid { grid-template-columns: 1fr; }
  .cmp-block:first-child { border-right: none; border-bottom: 1px solid var(--border-subtle); }
}
"""

content = open('static/trilliant.css', encoding='utf-8').read()
marker = '/* ════════════════════════════════════════════════════════════════════════════\n   v3.1 FIXES'
if marker in content:
    content = content[:content.find(marker)]
content += CSS
open('static/trilliant.css', 'w', encoding='utf-8').write(content)
print(f'Done. Size: {len(content)} chars')
