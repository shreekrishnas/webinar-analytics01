content = open('static/styles.css', encoding='utf-8').read()
idx = content.find('/* ══════════════════════════════════\n   20. AI ANALYSIS PANEL')
before = content[:idx]

css = r"""/* ══════════════════════════════════
   20. AI ANALYSIS PANEL — Premium v3
   ══════════════════════════════════ */

/* Analyze button */
.btn-ai-analyze {
  display:inline-flex;align-items:center;gap:7px;
  padding:8px 16px;border-radius:10px;font-size:12px;font-weight:600;letter-spacing:0.03em;
  cursor:pointer;border:1px solid rgba(139,92,246,0.4);
  background:rgba(139,92,246,0.08);color:#a78bfa;
  transition:all 0.2s ease;white-space:nowrap;
}
.btn-ai-analyze:hover:not(:disabled){
  background:rgba(139,92,246,0.16);border-color:rgba(139,92,246,0.7);
  box-shadow:0 0 20px rgba(139,92,246,0.2);color:#c4b5fd;transform:translateY(-1px);
}
.btn-ai-analyze:disabled{opacity:0.5;cursor:not-allowed;}
.btn-ai-analyze.ai-done{border-color:rgba(16,185,129,0.5);background:rgba(16,185,129,0.08);color:#34d399;}
.spin{animation:_spin .75s linear infinite;display:inline-block;}
@keyframes _spin{to{transform:rotate(360deg);}}

#ai-analysis-panel{margin:28px 0 8px;}

/* Loading / error states */
.ai-panel.ai-loading{padding:28px;border:1px solid rgba(139,92,246,0.2);border-radius:20px;background:rgba(8,8,14,0.8);}
.ai-panel.ai-error{padding:20px;border:1px solid rgba(244,63,94,0.3);border-radius:20px;background:rgba(244,63,94,0.04);}
.ai-panel-header{display:flex;align-items:center;gap:8px;padding:14px 20px;font-size:13px;font-weight:600;color:#a78bfa;border-bottom:1px solid rgba(139,92,246,0.12);background:rgba(139,92,246,0.06);}
.ai-powered-by{margin-left:auto;font-size:11px;color:var(--text-3);opacity:0.6;}
.ai-shimmer-rows{margin-top:16px;display:flex;flex-direction:column;gap:10px;}
.ai-shimmer{height:12px;border-radius:6px;background:linear-gradient(90deg,rgba(139,92,246,0.08) 25%,rgba(139,92,246,0.16) 50%,rgba(139,92,246,0.08) 75%);background-size:200% 100%;animation:_shimmer 1.5s infinite;}
@keyframes _shimmer{to{background-position:-200% 0;}}

/* ── Panel shell ── */
.aip{
  border:1px solid rgba(255,255,255,0.07);
  border-radius:20px;overflow:hidden;
  background:linear-gradient(160deg,rgba(12,12,20,0.97),rgba(8,8,16,0.99));
  box-shadow:0 24px 80px rgba(0,0,0,0.5),0 0 0 1px rgba(255,255,255,0.04);
}

/* ── Header ── */
.aip-header{
  display:flex;align-items:center;gap:10px;padding:16px 22px;
  background:linear-gradient(90deg,rgba(99,102,241,0.12),rgba(139,92,246,0.06));
  border-bottom:1px solid rgba(255,255,255,0.06);
}
.aip-header-icon{color:#a78bfa;display:flex;align-items:center;}
.aip-header-title{font-size:13px;font-weight:700;color:rgba(255,255,255,0.9);letter-spacing:0.02em;}
.aip-header-badge{
  margin-left:auto;font-size:10px;font-weight:600;letter-spacing:0.08em;
  padding:3px 10px;border-radius:20px;
  background:rgba(139,92,246,0.15);color:#a78bfa;
  border:1px solid rgba(139,92,246,0.25);
}

/* ── Hero ── */
.aip-hero{display:flex;align-items:center;gap:0;border-bottom:1px solid rgba(255,255,255,0.05);}

/* Grade ring */
.aip-grade-wrap{
  position:relative;width:156px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  padding:24px 20px;border-right:1px solid rgba(255,255,255,0.05);
}
.aip-ring-svg{width:110px;height:110px;position:relative;z-index:1;}
.aip-grade-glow{
  position:absolute;width:80px;height:80px;border-radius:50%;
  filter:blur(28px);opacity:0.5;pointer-events:none;
}

/* KPI strip */
.aip-kpi-strip{display:flex;align-items:center;flex:1;padding:0 4px;}
.aip-kpi{flex:1;padding:20px 16px;text-align:center;}
.aip-kpi-val{font-size:22px;font-weight:800;letter-spacing:-0.02em;line-height:1;margin-bottom:5px;}
.aip-kpi-lbl{font-size:10px;color:rgba(255,255,255,0.35);letter-spacing:0.06em;text-transform:uppercase;font-weight:500;}
.aip-kpi-div{width:1px;height:40px;background:rgba(255,255,255,0.05);flex-shrink:0;}

/* ── Mid row ── */
.aip-mid-row{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid rgba(255,255,255,0.05);}

/* ── Cards ── */
.aip-card{padding:22px 24px;border-right:1px solid rgba(255,255,255,0.05);}
.aip-card:last-child,.aip-card.aip-bench-card,.aip-bottom .aip-card:last-child{border-right:none;}
.aip-card-hd{
  display:flex;align-items:center;gap:8px;
  font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
  color:rgba(255,255,255,0.4);margin-bottom:18px;
}
.aip-card-icon{display:flex;align-items:center;opacity:0.9;}

/* ── Funnel ── */
.aip-funnel{display:flex;flex-direction:column;gap:11px;}
.aip-fn-row{display:flex;align-items:center;gap:10px;}
.aip-fn-noshow{opacity:0.6;}
.aip-fn-meta{display:flex;flex-direction:column;width:96px;flex-shrink:0;}
.aip-fn-label{font-size:11px;color:rgba(255,255,255,0.45);font-weight:500;}
.aip-fn-num{font-size:14px;font-weight:700;color:rgba(255,255,255,0.85);line-height:1.3;}
.aip-fn-track{flex:1;background:rgba(255,255,255,0.05);border-radius:6px;height:10px;overflow:hidden;}
.aip-fn-bar{height:100%;border-radius:6px;transition:width 1s cubic-bezier(.16,1,.3,1);}
.aip-fn-pct{width:36px;text-align:right;font-size:12px;font-weight:700;flex-shrink:0;}

/* ── Duration ── */
.aip-dur-list{display:flex;flex-direction:column;gap:14px;margin-bottom:14px;}
.aip-dur-item{}
.aip-dur-top{display:flex;align-items:baseline;gap:6px;margin-bottom:5px;}
.aip-dur-label{font-size:12px;font-weight:700;color:rgba(255,255,255,0.8);}
.aip-dur-sub{font-size:10px;color:rgba(255,255,255,0.35);flex:1;}
.aip-dur-count{font-size:10.5px;color:rgba(255,255,255,0.4);font-weight:600;}
.aip-dur-row{display:flex;align-items:center;gap:8px;}
.aip-dur-track{flex:1;background:rgba(255,255,255,0.05);border-radius:6px;height:8px;overflow:hidden;}
.aip-dur-fill{height:100%;border-radius:6px;}
.aip-dur-pct{font-size:11.5px;font-weight:700;width:32px;text-align:right;color:rgba(255,255,255,0.6);}
.aip-avg-pill{
  display:inline-flex;align-items:center;gap:7px;
  padding:7px 14px;border-radius:20px;
  background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.15);
  font-size:11.5px;color:rgba(255,255,255,0.5);
}
.aip-avg-pill strong{color:rgba(255,255,255,0.85);font-weight:700;}

/* ── Benchmark ── */
.aip-bench-card{border-right:none;border-top:1px solid rgba(255,255,255,0.05);}
.aip-bench-rows{display:flex;flex-direction:column;gap:10px;margin-bottom:14px;}
.aip-bench-row{display:flex;align-items:center;gap:12px;}
.aip-bench-this .aip-bench-lbl{color:rgba(255,255,255,0.8);font-weight:600;}
.aip-bench-lbl{font-size:11.5px;color:rgba(255,255,255,0.4);width:110px;flex-shrink:0;}
.aip-bench-track{flex:1;background:rgba(255,255,255,0.05);border-radius:6px;height:10px;overflow:hidden;}
.aip-bench-fill{height:100%;border-radius:6px;}
.aip-bench-val{font-size:12px;font-weight:700;width:40px;text-align:right;}
.aip-bench-note{font-size:11.5px;padding:10px 14px;border-radius:10px;display:inline-flex;align-items:center;gap:6px;}
.aip-bench-up{color:#10b981;background:rgba(16,185,129,0.08);padding:6px 12px;border-radius:8px;border:1px solid rgba(16,185,129,0.15);display:flex;align-items:center;gap:6px;}
.aip-bench-dn{color:#f43f5e;background:rgba(244,63,94,0.08);padding:6px 12px;border-radius:8px;border:1px solid rgba(244,63,94,0.15);}

/* ── AI Insights ── */
.aip-insights{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.aip-insight{
  display:flex;gap:12px;padding:14px 16px;
  background:rgba(255,255,255,0.03);
  border:1px solid rgba(255,255,255,0.07);
  border-radius:14px;transition:all 0.2s;
}
.aip-insight:hover{background:rgba(139,92,246,0.07);border-color:rgba(139,92,246,0.2);}
.aip-insight-icon-wrap{
  width:32px;height:32px;border-radius:8px;flex-shrink:0;
  background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.2);
  display:flex;align-items:center;justify-content:center;color:#a78bfa;margin-top:1px;
}
.aip-insight-body{flex:1;}
.aip-insight-title{font-size:12px;font-weight:700;color:rgba(255,255,255,0.85);margin-bottom:5px;}
.aip-insight-text{font-size:11px;color:rgba(255,255,255,0.45);line-height:1.6;margin-bottom:8px;}
.aip-insight-tag{
  display:inline-block;font-size:10px;font-weight:700;letter-spacing:0.04em;
  padding:3px 9px;border-radius:20px;
  background:rgba(139,92,246,0.12);color:#c4b5fd;border:1px solid rgba(139,92,246,0.2);
}

/* ── Bottom row ── */
.aip-bottom{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid rgba(255,255,255,0.05);}
.aip-bottom .aip-card{border-top:none;}

/* Recommendations */
.aip-rec{display:flex;align-items:flex-start;gap:10px;font-size:12.5px;color:rgba(255,255,255,0.55);margin-bottom:10px;line-height:1.6;}
.aip-rec:last-child{margin-bottom:0;}
.aip-rec-icon{
  width:20px;height:20px;border-radius:6px;flex-shrink:0;
  background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.2);
  display:flex;align-items:center;justify-content:center;color:#10b981;margin-top:2px;
}

/* Verdict */
.aip-verdict-card{background:rgba(99,102,241,0.04);}
.aip-verdict-text{font-size:13px;color:rgba(255,255,255,0.75);line-height:1.8;margin:0 0 14px;}
.aip-verdict-footer{font-size:10px;color:rgba(255,255,255,0.2);letter-spacing:0.06em;text-transform:uppercase;}

/* Responsive */
@media(max-width:700px){
  .aip-hero{flex-direction:column;}
  .aip-grade-wrap{width:100%;border-right:none;border-bottom:1px solid rgba(255,255,255,0.05);}
  .aip-kpi-strip{flex-wrap:wrap;}
  .aip-mid-row,.aip-bottom{grid-template-columns:1fr;}
  .aip-insights{grid-template-columns:1fr;}
  .aip-card{border-right:none;border-bottom:1px solid rgba(255,255,255,0.05);}
}
"""

result = before + css
open('static/styles.css', 'w', encoding='utf-8').write(result)
print('Done, size:', len(result))
