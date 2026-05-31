content = open('static/styles.css', encoding='utf-8').read()

# Find and replace the ICP badge section
old_icp = r""".icp-badge {
  display: inline-flex; align-items: center;
  font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
  padding: 2px 7px; border-radius: 4px;
  text-transform: uppercase; white-space: nowrap;
  border: 1px solid;
}
.icp-pms              { background: rgba(99,102,241,0.12);  color: #6366f1; border-color: rgba(99,102,241,0.3); }
.icp-retirement-planning { background: rgba(16,185,129,0.1); color: #059669; border-color: rgba(16,185,129,0.3); }
.icp-nri              { background: rgba(245,158,11,0.12);  color: #d97706; border-color: rgba(245,158,11,0.3); }
.icp-esops            { background: rgba(239,68,68,0.10);   color: #dc2626; border-color: rgba(239,68,68,0.25); }
.icp-family-office    { background: rgba(168,85,247,0.12);  color: #9333ea; border-color: rgba(168,85,247,0.3); }
.icp-others           { background: rgba(100,116,139,0.10); color: #64748b; border-color: rgba(100,116,139,0.2); }

.filter-icp { min-width: 130px; }"""

new_icp = r""".icp-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 10.5px; font-weight: 800; letter-spacing: 0.06em;
  padding: 4px 10px; border-radius: 6px;
  text-transform: uppercase; white-space: nowrap;
  border: 1.5px solid; position: relative;
}
/* Alpha glow pulse on hover */
.icp-badge:hover { filter: brightness(1.15); transform: translateY(-1px); transition: all 0.15s; }

.icp-pms              { background: rgba(99,102,241,0.15);  color: #818cf8; border-color: rgba(99,102,241,0.4);  box-shadow: 0 0 10px rgba(99,102,241,0.15); }
.icp-retirement-planning { background: rgba(16,185,129,0.15); color: #34d399; border-color: rgba(16,185,129,0.4); box-shadow: 0 0 10px rgba(16,185,129,0.15); }
.icp-nri              { background: rgba(245,158,11,0.15);  color: #fbbf24; border-color: rgba(245,158,11,0.4);  box-shadow: 0 0 10px rgba(245,158,11,0.15); }
.icp-esops            { background: rgba(239,68,68,0.13);   color: #f87171; border-color: rgba(239,68,68,0.35);  box-shadow: 0 0 10px rgba(239,68,68,0.12); }
.icp-family-office    { background: rgba(168,85,247,0.15);  color: #c084fc; border-color: rgba(168,85,247,0.4);  box-shadow: 0 0 10px rgba(168,85,247,0.15); }
.icp-others           { background: rgba(100,116,139,0.10); color: #94a3b8; border-color: rgba(100,116,139,0.25); }

/* Light mode ICP adjustments */
html:not(.dark) .icp-pms              { color: #4f46e5; background: rgba(99,102,241,0.1);  box-shadow: none; }
html:not(.dark) .icp-retirement-planning { color: #059669; background: rgba(16,185,129,0.1); box-shadow: none; }
html:not(.dark) .icp-nri              { color: #d97706; background: rgba(245,158,11,0.1);  box-shadow: none; }
html:not(.dark) .icp-esops            { color: #dc2626; background: rgba(239,68,68,0.08);   box-shadow: none; }
html:not(.dark) .icp-family-office    { color: #9333ea; background: rgba(168,85,247,0.1);   box-shadow: none; }

.filter-icp { min-width: 130px; }"""

content = content.replace(old_icp, new_icp)
open('static/styles.css', 'w', encoding='utf-8').write(content)
print('ICP CSS upgraded')
