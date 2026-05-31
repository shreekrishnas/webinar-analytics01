content = open('static/styles.css', encoding='utf-8').read()

old = r""".topics-page { padding: 0 0 48px; }

/* Hero */
.topics-hero {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 20px; flex-wrap: wrap; margin-bottom: 32px; padding: 28px 0 20px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.topics-eyebrow {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
  color: #a78bfa; margin-bottom: 10px;
}
.topics-title { font-size: 26px; font-weight: 800; color: var(--text-1); margin: 0 0 8px; letter-spacing: -0.02em; }
.topics-sub   { font-size: 13.5px; color: var(--text-3); margin: 0; line-height: 1.6; }"""

new = r""".topics-page { padding: 0 0 48px; }

/* Hero */
.topics-hero {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 20px; flex-wrap: wrap; margin-bottom: 32px; padding: 28px 0 20px;
  border-bottom: 1px solid rgba(0,0,0,0.08);
}
html.dark .topics-hero { border-bottom-color: rgba(255,255,255,0.06); }

.topics-eyebrow {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
  color: #7c3aed; margin-bottom: 10px;
}
html.dark .topics-eyebrow { color: #a78bfa; }

.topics-title { font-size: 26px; font-weight: 800; color: #0f0f0f; margin: 0 0 8px; letter-spacing: -0.02em; }
html.dark .topics-title { color: rgba(255,255,255,0.92); }

.topics-sub   { font-size: 13.5px; color: #6b7280; margin: 0; line-height: 1.6; }
html.dark .topics-sub { color: rgba(255,255,255,0.45); }"""

content = content.replace(old, new)

# Fix card text colors
replacements = [
    # loading/error states
    ('font-size: 14px; color: var(--text-3); grid-column: 1 / -1;',
     'font-size: 14px; color: #6b7280; grid-column: 1 / -1;'),

    # speaker card
    ('.speaker-topics-card {\n  border: 1px solid rgba(255,255,255,0.07);\n  border-radius: 18px; overflow: hidden;\n  background: rgba(255,255,255,0.02);\n  transition: border-color 0.2s, transform 0.2s;\n}\n.speaker-topics-card:hover { border-color: rgba(255,255,255,0.12); transform: translateY(-2px); }',
     '.speaker-topics-card {\n  border: 1px solid rgba(0,0,0,0.09);\n  border-radius: 18px; overflow: hidden;\n  background: #ffffff;\n  box-shadow: 0 2px 16px rgba(0,0,0,0.06);\n  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;\n}\n.speaker-topics-card:hover { border-color: rgba(0,0,0,0.15); box-shadow: 0 6px 28px rgba(0,0,0,0.1); transform: translateY(-2px); }\nhtml.dark .speaker-topics-card { background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.08); box-shadow: none; }\nhtml.dark .speaker-topics-card:hover { border-color: rgba(255,255,255,0.14); }'),

    # stc header
    ('.stc-header {\n  display: flex; align-items: center; gap: 14px;\n  padding: 18px 22px; border-bottom: 1px solid rgba(255,255,255,0.06);\n  background: rgba(255,255,255,0.025);\n}',
     '.stc-header {\n  display: flex; align-items: center; gap: 14px;\n  padding: 18px 22px; border-bottom: 1px solid rgba(0,0,0,0.07);\n  background: rgba(0,0,0,0.02);\n}\nhtml.dark .stc-header { border-bottom-color: rgba(255,255,255,0.06); background: rgba(255,255,255,0.025); }'),

    # stc name and count
    ('.stc-name  { font-size: 15px; font-weight: 700; color: var(--text-1); margin-bottom: 2px; }',
     '.stc-name  { font-size: 15px; font-weight: 700; color: #111827; margin-bottom: 2px; }\nhtml.dark .stc-name { color: rgba(255,255,255,0.9); }'),
    ('.stc-count { font-size: 11px; color: var(--text-3); }',
     '.stc-count { font-size: 11px; color: #9ca3af; }\nhtml.dark .stc-count { color: rgba(255,255,255,0.35); }'),

    # topic card bg
    ('.topic-card {\n  display: flex; gap: 12px; padding: 14px 16px;\n  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);\n  border-radius: 12px; transition: all 0.2s;\n}\n.topic-card:hover { background: rgba(255,255,255,0.055); border-color: rgba(255,255,255,0.12); }',
     '.topic-card {\n  display: flex; gap: 12px; padding: 14px 16px;\n  background: #f9fafb; border: 1px solid rgba(0,0,0,0.07);\n  border-radius: 12px; transition: all 0.2s;\n}\n.topic-card:hover { background: #f3f4f6; border-color: rgba(0,0,0,0.12); }\nhtml.dark .topic-card { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.07); }\nhtml.dark .topic-card:hover { background: rgba(255,255,255,0.07); border-color: rgba(255,255,255,0.13); }'),

    # topic title
    ('.topic-title {\n  font-size: 13.5px; font-weight: 700; color: rgba(255,255,255,0.88);\n  margin-bottom: 6px; line-height: 1.5;\n}',
     '.topic-title {\n  font-size: 13.5px; font-weight: 700; color: #111827;\n  margin-bottom: 6px; line-height: 1.5;\n}\nhtml.dark .topic-title { color: rgba(255,255,255,0.88); }'),

    # topic hook
    ('.topic-hook {\n  font-size: 11.5px; color: rgba(255,255,255,0.45); line-height: 1.6;\n  margin-bottom: 8px;\n}',
     '.topic-hook {\n  font-size: 11.5px; color: #6b7280; line-height: 1.6;\n  margin-bottom: 8px;\n}\nhtml.dark .topic-hook { color: rgba(255,255,255,0.45); }'),

    # topic angle
    ('.topic-angle {\n  display: flex; align-items: flex-start; gap: 6px;\n  font-size: 11px; color: rgba(139,92,246,0.8);\n  background: rgba(139,92,246,0.07); border: 1px solid rgba(139,92,246,0.14);\n  border-radius: 7px; padding: 6px 9px; margin-bottom: 10px; line-height: 1.55;\n}',
     '.topic-angle {\n  display: flex; align-items: flex-start; gap: 6px;\n  font-size: 11px; color: #6d28d9;\n  background: rgba(109,40,217,0.07); border: 1px solid rgba(109,40,217,0.15);\n  border-radius: 7px; padding: 6px 9px; margin-bottom: 10px; line-height: 1.55;\n}\nhtml.dark .topic-angle { color: rgba(167,139,250,0.9); background: rgba(139,92,246,0.08); border-color: rgba(139,92,246,0.18); }'),

    # use topic button
    ('.topic-use-btn {\n  margin-left: auto; display: inline-flex; align-items: center; gap: 5px;\n  font-size: 11px; font-weight: 600; padding: 5px 12px;\n  border-radius: 8px; cursor: pointer;\n  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);\n  color: rgba(255,255,255,0.65); transition: all 0.18s;\n}\n.topic-use-btn:hover { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9); border-color: rgba(255,255,255,0.2); }',
     '.topic-use-btn {\n  margin-left: auto; display: inline-flex; align-items: center; gap: 5px;\n  font-size: 11px; font-weight: 600; padding: 5px 12px;\n  border-radius: 8px; cursor: pointer;\n  background: rgba(0,0,0,0.05); border: 1px solid rgba(0,0,0,0.12);\n  color: #374151; transition: all 0.18s;\n}\n.topic-use-btn:hover { background: rgba(0,0,0,0.1); color: #111827; border-color: rgba(0,0,0,0.2); }\nhtml.dark .topic-use-btn { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); }\nhtml.dark .topic-use-btn:hover { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.9); border-color: rgba(255,255,255,0.2); }'),

    # date footer
    ('.topics-date-footer {\n  grid-column: 1 / -1; text-align: center;\n  font-size: 11px; color: var(--text-3); opacity: 0.5;\n  padding-top: 16px; letter-spacing: 0.04em;\n}',
     '.topics-date-footer {\n  grid-column: 1 / -1; text-align: center;\n  font-size: 11px; color: #9ca3af;\n  padding-top: 16px; letter-spacing: 0.04em;\n}'),

    # loading text
    ('.topics-loading, .topics-error {\n  display: flex; align-items: center; gap: 14px;\n  padding: 60px; justify-content: center;\n  font-size: 14px; color: var(--text-3); grid-column: 1 / -1;\n}',
     '.topics-loading, .topics-error {\n  display: flex; align-items: center; gap: 14px;\n  padding: 60px; justify-content: center;\n  font-size: 14px; color: #6b7280; grid-column: 1 / -1;\n}'),
]

for old_s, new_s in replacements:
    if old_s in content:
        content = content.replace(old_s, new_s)
        print('Fixed:', old_s[:50].strip())
    else:
        print('NOT FOUND:', old_s[:50].strip())

open('static/styles.css', 'w', encoding='utf-8').write(content)
print('Done')
