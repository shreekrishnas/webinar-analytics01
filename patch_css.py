content = open('static/styles.css', encoding='utf-8').read()
idx = content.find('/* ══════════════════════════════════\n   20. AI ANALYSIS PANEL')
before = content[:idx]

new_section = r"""/* ══════════════════════════════════
   20. AI ANALYSIS PANEL v2
   ══════════════════════════════════ */

/* Analyze button */
.btn-ai-analyze {
  display:inline-flex;align-items:center;gap:6px;
  padding:7px 14px;border-radius:8px;font-size:12.5px;font-weight:600;
  cursor:pointer;border:1.5px solid rgba(139,92,246,0.5);
  background:rgba(139,92,246,0.10);color:#a78bfa;
  transition:all 0.2s ease;white-space:nowrap;
}
.btn-ai-analyze:hover:not(:disabled){background:rgba(139,92,246,0.20);border-color:rgba(139,92,246,0.75);box-shadow:0 0 18px rgba(139,92,246,0.25);color:#c4b5fd;}
.btn-ai-analyze:disabled{opacity:0.6;cursor:not-allowed;}
.btn-ai-analyze.ai-done{border-color:rgba(16,185,129,0.5);background:rgba(16,185,129,0.10);color:#34d399;}
.spin{animation:ai-spin 0.8s linear infinite;display:inline-block;}
@keyframes ai-spin{to{transform:rotate(360deg);}}
#ai-analysis-panel{margin:24px 0 8px;}

/* Panel shell */
.ai-panel-v2{border:1.5px solid rgba(139,92,246,0.22);border-radius:18px;overflow:hidden;background:rgba(15,15,20,0.6);backdrop-filter:blur(12px);}
.ai-panel.ai-loading{padding:24px;border:1.5px solid rgba(139,92,246,0.22);border-radius:18px;background:rgba(15,15,20,0.6);}
.ai-panel.ai-error{padding:20px;border:1.5px solid rgba(239,68,68,0.3);border-radius:18px;background:rgba(239,68,68,0.04);}

/* Header */
.ai-panel-header{display:flex;align-items:center;gap:8px;padding:13px 20px;font-size:13px;font-weight:600;color:#a78bfa;border-bottom:1px solid rgba(139,92,246,0.14);background:rgba(139,92,246,0.07);}
.ai-powered-by{margin-left:auto;font-size:11px;font-weight:500;color:var(--text-3);opacity:0.6;}
.ai-card-title{font-size:11.5px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:var(--text-3);margin-bottom:14px;}

/* Top row */
.ai-top-row{display:grid;grid-template-columns:160px 1fr;gap:0;border-bottom:1px solid rgba(255,255,255,0.05);}
.ai-grade-card{padding:20px 16px;text-align:center;border-right:1px solid rgba(255,255,255,0.05);background:rgba(0,0,0,0.15);display:flex;flex-direction:column;align-items:center;gap:10px;}
.ai-grade-ring{width:100px;height:100px;}
.ai-ring-svg{width:100%;height:100%;}
.ai-grade-summary{font-size:11.5px;color:var(--text-2);line-height:1.5;text-align:center;}

/* Funnel */
.ai-funnel-card{padding:20px 22px;}
.ai-funnel{display:flex;flex-direction:column;gap:10px;}
.ai-funnel-row{display:flex;align-items:center;gap:10px;}
.ai-funnel-label{font-size:11px;color:var(--text-3);white-space:nowrap;width:90px;flex-shrink:0;}
.ai-funnel-bar-wrap{flex:1;background:rgba(255,255,255,0.05);border-radius:6px;overflow:hidden;height:28px;}
.ai-funnel-bar{height:100%;border-radius:6px;display:flex;align-items:center;padding:0 10px;font-size:12px;font-weight:700;color:rgba(0,0,0,0.75);white-space:nowrap;min-width:40px;transition:width 0.9s cubic-bezier(.4,0,.2,1);}
.ai-funnel-bar em{font-style:normal;font-size:11px;opacity:0.8;margin-left:5px;}

/* Charts row */
.ai-charts-row{display:grid;grid-template-columns:1fr 1fr;gap:0;border-bottom:1px solid rgba(255,255,255,0.05);}
.ai-chart-card{padding:20px 22px;}
.ai-chart-card:first-child{border-right:1px solid rgba(255,255,255,0.05);}

/* Duration bars */
.ai-dur-chart{display:flex;flex-direction:column;gap:8px;margin-bottom:10px;}
.ai-dur-row{display:flex;align-items:center;gap:8px;}
.ai-dur-lbl{font-size:10.5px;color:var(--text-3);width:120px;flex-shrink:0;}
.ai-dur-track{flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:8px;overflow:hidden;}
.ai-dur-fill{height:100%;border-radius:4px;transition:width 0.9s cubic-bezier(.4,0,.2,1);}
.ai-dur-stat{font-size:11px;font-weight:700;width:32px;text-align:right;}
.ai-dur-cnt{font-size:10px;color:var(--text-3);width:28px;}
.ai-avg-dur{font-size:12px;color:var(--text-2);padding-top:4px;}
.ai-avg-dur strong{color:var(--text-1);}

/* Donut */
.ai-donut-wrap{display:flex;align-items:center;gap:16px;}
.ai-donut-svg{width:90px;height:90px;flex-shrink:0;}
.ai-src-legend{display:flex;flex-direction:column;gap:6px;flex:1;}
.ai-src-leg{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--text-2);}
.ai-src-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;}
.ai-src-name{flex:1;text-transform:capitalize;}
.ai-src-pct{font-weight:700;color:var(--text-1);}

/* Benchmark */
.ai-bench-card{padding:20px 22px;border-bottom:1px solid rgba(255,255,255,0.05);}
.ai-bench-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;}
.ai-bench-group-title{font-size:11px;font-weight:600;color:var(--text-3);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;}
.ai-bench-row{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.ai-bench-lbl{font-size:10.5px;color:var(--text-3);width:90px;flex-shrink:0;}
.ai-bench-track{flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:8px;overflow:hidden;}
.ai-bench-fill{height:100%;border-radius:4px;transition:width 0.9s cubic-bezier(.4,0,.2,1);}
.ai-bench-val{font-size:11px;font-weight:700;width:40px;text-align:right;}

/* Insights */
.ai-insights-card{padding:20px 22px;border-bottom:1px solid rgba(255,255,255,0.05);}
.ai-insights-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.ai-insight-chip{display:flex;gap:10px;padding:12px 14px;background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.14);border-radius:10px;transition:background 0.15s;}
.ai-insight-chip:hover{background:rgba(139,92,246,0.10);}
.ai-insight-icon{font-size:18px;flex-shrink:0;margin-top:1px;}
.ai-insight-title{font-size:11.5px;font-weight:700;color:var(--text-1);margin-bottom:4px;}
.ai-insight-txt{font-size:11px;color:var(--text-2);line-height:1.55;margin-bottom:6px;}
.ai-insight-hl{display:inline-block;font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:20px;background:rgba(139,92,246,0.15);color:#c4b5fd;border:1px solid rgba(139,92,246,0.2);}

/* Bottom row */
.ai-bottom-row{display:grid;grid-template-columns:1fr 1fr;gap:0;}
.ai-recs-card{padding:20px 22px;border-right:1px solid rgba(255,255,255,0.05);}
.ai-verdict-card{padding:20px 22px;background:rgba(139,92,246,0.04);}
.ai-verdict-text{font-size:13px;color:var(--text-1);line-height:1.75;}
.ai-rec{display:flex;align-items:flex-start;gap:10px;font-size:12.5px;color:var(--text-2);margin-bottom:9px;line-height:1.55;}
.ai-rec:last-child{margin-bottom:0;}
.ai-rec-num{width:20px;height:20px;border-radius:50%;flex-shrink:0;background:rgba(139,92,246,0.18);color:#a78bfa;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;margin-top:1px;}

/* Shimmer */
.ai-shimmer-rows{margin-top:16px;display:flex;flex-direction:column;gap:10px;}
.ai-shimmer{height:12px;border-radius:6px;width:100%;background:linear-gradient(90deg,rgba(139,92,246,0.08) 25%,rgba(139,92,246,0.16) 50%,rgba(139,92,246,0.08) 75%);background-size:200% 100%;animation:ai-shimmer 1.5s infinite;}
@keyframes ai-shimmer{to{background-position:-200% 0;}}

/* Responsive */
@media(max-width:640px){
  .ai-top-row,.ai-charts-row,.ai-bench-grid,.ai-insights-grid,.ai-bottom-row{grid-template-columns:1fr;}
  .ai-grade-card{border-right:none;border-bottom:1px solid rgba(255,255,255,0.05);}
  .ai-chart-card:first-child{border-right:none;border-bottom:1px solid rgba(255,255,255,0.05);}
  .ai-recs-card{border-right:none;border-bottom:1px solid rgba(255,255,255,0.05);}
}
"""

result = before + new_section
open('static/styles.css', 'w', encoding='utf-8').write(result)
print('Done, total:', len(result))
