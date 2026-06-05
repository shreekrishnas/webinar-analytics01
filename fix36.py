CSS = r"""

/* ════════════════════════════════════════════════════════════════════════════
   v3.6 Phase 1 - Meeting Readiness + Lead Qualification
   ════════════════════════════════════════════════════════════════════════════ */

/* Readiness badges */
.readiness-badge {
  display: inline-flex;
  align-items: center;
  font-family: var(--font-ui);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 4px 10px;
  border-radius: 9999px;
  border: 1px solid;
  white-space: nowrap;
  text-transform: uppercase;
  position: relative;
}
.readiness-badge.is-manual::before {
  content: '★';
  margin-right: 4px;
  opacity: 0.7;
}

.readiness-hot           { background: #FEE2E2; color: #991B1B; border-color: #FCA5A5; }
.readiness-warm          { background: #FEF3C7; color: #92400E; border-color: #FDE68A; }
.readiness-cold          { background: #F3F4F6; color: #4B5563; border-color: #D1D5DB; }
.readiness-customer      { background: #DBEAFE; color: #1E40AF; border-color: #93C5FD; }
.readiness-prospect      { background: #DDD6FE; color: #5B21B6; border-color: #C4B5FD; }
.readiness-partner       { background: #FCE7F3; color: #9D174D; border-color: #F9A8D4; }
.readiness-internal      { background: #E5E7EB; color: #1F2937; border-color: #9CA3AF; }
.readiness-employee      { background: #E5E7EB; color: #1F2937; border-color: #9CA3AF; }
.readiness-meeting_ready { background: #FEE2E2; color: #991B1B; border-color: #FCA5A5; }

html.dark .readiness-hot      { background: rgba(239,68,68,0.18);  color: #FCA5A5; border-color: rgba(239,68,68,0.35); }
html.dark .readiness-warm     { background: rgba(245,158,11,0.18); color: #FCD34D; border-color: rgba(245,158,11,0.35); }
html.dark .readiness-cold     { background: rgba(148,163,184,0.15); color: #CBD5E1; border-color: rgba(148,163,184,0.3); }
html.dark .readiness-customer { background: rgba(59,130,246,0.20); color: #93C5FD; border-color: rgba(59,130,246,0.4); }
html.dark .readiness-prospect { background: rgba(124,58,237,0.20); color: #C4B5FD; border-color: rgba(124,58,237,0.4); }
html.dark .readiness-partner  { background: rgba(236,72,153,0.20); color: #F9A8D4; border-color: rgba(236,72,153,0.4); }
html.dark .readiness-internal,
html.dark .readiness-employee { background: rgba(148,163,184,0.18); color: #E2E8F0; border-color: rgba(148,163,184,0.35); }

/* Highlight Hot rows subtly */
.lb-table tbody tr[data-readiness="hot"] td,
.lb-table tbody tr[data-readiness="meeting_ready"] td {
  background: linear-gradient(90deg, rgba(239,68,68,0.04), transparent);
}
.lb-table tbody tr[data-readiness="customer"] td {
  background: linear-gradient(90deg, rgba(59,130,246,0.04), transparent);
}

/* Edit tag button */
.lb-tag-edit {
  width: 30px;
  height: 30px;
  border-radius: 0.5rem;
  background: rgba(99,102,241,0.08);
  border: 1px solid rgba(99,102,241,0.20);
  color: var(--accent-indigo);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.lb-tag-edit:hover {
  background: var(--accent-indigo);
  color: #fff;
  border-color: var(--accent-indigo);
  transform: translateY(-1px);
}

/* Tag pill row in editor modal */
.tag-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag-pill {
  font-family: var(--font-ui);
  font-size: 0.78rem;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 9999px;
  border: 1.5px solid var(--border-default);
  background: rgba(255,255,255,0.60);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.tag-pill:hover {
  background: rgba(99,102,241,0.10);
  border-color: var(--accent-indigo);
  color: var(--accent-indigo);
}
.tag-pill.active {
  background: var(--accent-indigo);
  color: #fff;
  border-color: var(--accent-indigo);
  box-shadow: 0 2px 8px rgba(99,102,241,0.35);
}
html.dark .tag-pill {
  background: rgba(30,41,59,0.60);
  border-color: rgba(255,255,255,0.18);
  color: var(--text-secondary);
}

/* Make lb table slightly tighter for more columns */
.lb-table th, .lb-table td {
  padding: 10px 12px !important;
  font-size: 0.85rem;
}
.lb-table .lb-email { font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); }
"""

content = open('static/trilliant.css', encoding='utf-8').read()
marker = 'v3.6 Phase 1'
if marker in content:
    idx = content.find('/* ════════════════════════════════════════════════════════════════════════════\n   v3.6 Phase 1')
    if idx >= 0:
        content = content[:idx]
content += CSS
open('static/trilliant.css', 'w', encoding='utf-8').write(content)
print(f'Done. Size: {len(content)} chars')
