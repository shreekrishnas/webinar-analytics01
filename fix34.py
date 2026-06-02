CSS = r"""

/* ════════════════════════════════════════════════════════════════════════════
   v3.4 NEW FEATURES — Date range, Notes, Leaderboard controls
   ════════════════════════════════════════════════════════════════════════════ */

/* ── Date range popover ── */
.date-range-popover {
  position: fixed;
  z-index: 800;
  background: rgba(255,255,255,0.98);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid var(--border-subtle);
  border-radius: 1.25rem;
  box-shadow: 0 24px 60px rgba(0,0,0,0.18);
  padding: 18px;
  width: 320px;
  font-family: var(--font-ui);
}
html.dark .date-range-popover {
  background: rgba(30,41,59,0.98);
  border-color: rgba(255,255,255,0.10);
}
.drp-header {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.drp-quick {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 14px;
}
.drp-quick button {
  background: rgba(99,102,241,0.08);
  border: 1px solid rgba(99,102,241,0.18);
  color: var(--accent-indigo);
  border-radius: 0.625rem;
  font-family: var(--font-ui);
  font-size: 0.78rem;
  font-weight: 600;
  padding: 7px 10px;
  cursor: pointer;
  transition: all 0.15s;
}
.drp-quick button:hover {
  background: rgba(99,102,241,0.16);
  border-color: var(--accent-indigo);
}
.drp-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}
.drp-fields label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.drp-fields input[type="date"] {
  font-family: var(--font-ui);
  padding: 8px 10px !important;
  font-size: 0.85rem !important;
}
.drp-actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.drp-clear {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  border-radius: 0.5rem;
  font-family: var(--font-ui);
  font-weight: 600;
  font-size: 0.82rem;
  padding: 7px 14px;
  cursor: pointer;
}
.drp-apply {
  background: var(--accent-indigo);
  color: #fff;
  border: none;
  border-radius: 0.5rem;
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: 0.82rem;
  padding: 7px 16px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(99,102,241,0.35);
}
.drp-apply:hover { background: var(--accent-indigo-deep); }

/* Make Range chip a bit wider since it shows dates */
button.tb-chip[data-filter="range"] {
  padding: 7px 14px !important;
}

/* ── Human Notes section ── */
.notes-section {
  margin: 24px 0 18px;
  background: var(--surface-card);
  backdrop-filter: blur(16px) saturate(140%);
  border: 1px solid var(--border-subtle);
  border-radius: 1.5rem;
  padding: 22px 26px;
}
.notes-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.notes-title {
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.notes-sub {
  font-family: var(--font-ui);
  font-size: 0.78rem;
  color: var(--text-muted);
}
.btn-add-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-indigo);
  color: #fff;
  border: none;
  border-radius: 0.75rem;
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: 0.82rem;
  padding: 8px 14px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(99,102,241,0.35);
  flex-shrink: 0;
}
.btn-add-note:hover {
  background: var(--accent-indigo-deep);
  box-shadow: 0 6px 16px rgba(99,102,241,0.45);
  transform: translateY(-1px);
}

.note-form {
  background: rgba(99,102,241,0.04);
  border: 1px solid rgba(99,102,241,0.18);
  border-radius: 1rem;
  padding: 16px;
  margin-bottom: 14px;
}
.note-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}
.note-content {
  width: 100%;
  margin-bottom: 10px;
  resize: vertical;
  min-height: 70px;
  font-family: var(--font-ui) !important;
}
.note-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.notes-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.notes-empty {
  font-family: var(--font-ui);
  font-size: 0.82rem;
  color: var(--text-muted);
  padding: 14px 18px;
  background: rgba(0,0,0,0.02);
  border: 1px dashed var(--border-subtle);
  border-radius: 0.75rem;
  text-align: center;
}
html.dark .notes-empty { background: rgba(255,255,255,0.03); }
.note-card {
  background: rgba(255,255,255,0.55);
  border: 1px solid var(--border-subtle);
  border-radius: 0.875rem;
  padding: 14px 16px;
}
html.dark .note-card { background: rgba(15,23,42,0.55); }
.note-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  gap: 10px;
}
.note-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.note-cat {
  font-family: var(--font-ui);
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 3px 9px;
  border-radius: 9999px;
  border: 1px solid;
}
.note-author {
  font-family: var(--font-ui);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
}
.note-time {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
}
.note-delete {
  background: transparent;
  border: none;
  color: var(--text-muted);
  width: 28px;
  height: 28px;
  border-radius: 0.5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.note-delete:hover {
  background: rgba(220,38,38,0.10);
  color: var(--status-danger);
}
.note-content-display {
  font-family: var(--font-ui);
  font-size: 0.875rem;
  color: var(--text-primary);
  line-height: 1.55;
  white-space: pre-wrap;
}

/* ── Leaderboard bottom controls ── */
.lb-bottom-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 4px;
  margin-top: 16px;
  border-top: 1px solid var(--border-subtle);
  gap: 16px;
  flex-wrap: wrap;
}
.lb-score-help {
  font-family: var(--font-ui);
  font-size: 0.78rem;
  color: var(--text-muted);
}
.lb-show-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: rgba(255,255,255,0.60);
  border: 1px solid var(--border-subtle);
  border-radius: 9999px;
  padding: 4px 8px 4px 16px;
  backdrop-filter: blur(8px);
}
.lb-show-control span {
  font-family: var(--font-ui);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
}
.lb-show-control select {
  min-width: 80px !important;
  padding: 5px 30px 5px 12px !important;
  font-family: var(--font-mono) !important;
  font-weight: 600 !important;
}
"""

content = open('static/trilliant.css', encoding='utf-8').read()
marker = 'v3.4 NEW FEATURES'
if marker in content:
    idx = content.find('/* ════════════════════════════════════════════════════════════════════════════\n   v3.4 NEW FEATURES')
    if idx >= 0:
        content = content[:idx]
content += CSS
open('static/trilliant.css', 'w', encoding='utf-8').write(content)
print(f'Done. Size: {len(content)} chars')
