/* ── State ──────────────────────────────────────────────────────────────── */
const S = {
  webinars: [], speakers: [], stats: null,
  page: 'home', sub: null, dark: false, search: '',
  filterStatus: 'all', filterSpeaker: 'all',
  _lbSpeaker: '', _lbWebinar: '',
};
const detailCache = {};

/* ── Helpers ────────────────────────────────────────────────────────────── */
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmt(n)    { return Number(n).toLocaleString('en-IN'); }
function fmtINR(n) { return '₹' + Number(n).toLocaleString('en-IN'); }
function fmtPct(n) { return Number(n).toFixed(1) + '%'; }

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  if (h < 21) return 'Good evening';
  return 'Good night';
}

function fmtDate(d) {
  if (!d) return '';
  return new Date(d + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function fmtDateTime(d) {
  if (!d) return '';
  return new Date(d).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

const AV_COLORS = ['#4f46e5','#0891b2','#059669','#7c3aed','#db2777','#ea580c','#0284c7','#65a30d','#dc2626','#d97706'];
function avColor(name) {
  let h = 0;
  for (const c of String(name)) h = (h * 31 + c.charCodeAt(0)) & 0xffffffff;
  return AV_COLORS[Math.abs(h) % AV_COLORS.length];
}
function initials(name) {
  return String(name).split(' ').map(p => p[0]).join('').slice(0,2).toUpperCase();
}

const DUR_COLORS = {
  '0–15 min':'#94a3b8','15–30 min':'#60a5fa','30–45 min':'#34d399',
  '45–60 min':'#a78bfa','60+ min':'#f472b6',
};
const SRC_COLORS = { email:'#6366f1', social:'#f59e0b', direct:'#10b981', referral:'#ef4444', upload:'#0891b2' };

/* ── API ────────────────────────────────────────────────────────────────── */
async function api(url, method='GET', body=null) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  if (r.status === 204) return null;
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function loadAll() {
  const [webinars, speakers, stats] = await Promise.all([
    api('/api/webinars'),
    api('/api/speakers'),
    api('/api/stats'),
  ]);
  S.webinars  = webinars;
  S.speakers  = speakers;
  S.stats     = stats;
  // Populate speaker datalist for modal
  const dl = document.getElementById('speaker-list');
  if (dl) {
    dl.innerHTML = S.speakers.map(sp => `<option value="${esc(sp.name)}">`).join('');
  }
}

/* ── Navigation ─────────────────────────────────────────────────────────── */
function nav(page, sub) {
  S.page = page;
  S.sub  = sub ?? null;
  document.querySelectorAll('.sb-icon[data-page]').forEach(b =>
    b.classList.toggle('active', b.dataset.page === page)
  );
  switch (page) {
    case 'home':        renderHome();              break;
    case 'analytics':   renderAnalytics();         break;
    case 'speakers':    renderSpeakers();           break;
    case 'leaderboard': renderLeaderboard();        break;
    case 'webinar':     renderWebinarDetail(sub);   break;
    case 'speaker':     renderSpeakerDetail(sub);   break;
  }
}

function setContent(html) {
  document.getElementById('content').innerHTML = html;
}

/* ══════════════════════════════════════════════════════════════════════════
   HOME — Webinar Dashboard
══════════════════════════════════════════════════════════════════════════ */
function renderHome() {
  const q  = S.search.toLowerCase();
  let list = S.webinars.filter(w =>
    !q || w.title.toLowerCase().includes(q) || w.speaker_name.toLowerCase().includes(q)
  );
  if (S.filterStatus !== 'all')  list = list.filter(w => w.status === S.filterStatus);
  if (S.filterSpeaker !== 'all') list = list.filter(w => w.speaker_id == S.filterSpeaker);

  const total    = S.webinars.length;
  const totalReg = S.webinars.reduce((a,w) => a+w.total_registrations, 0);
  const totalAtt = S.webinars.reduce((a,w) => a+w.total_attendees, 0);
  const avgRate  = total ? (S.webinars.reduce((a,w) => a+w.attendance_rate, 0) / total).toFixed(1) : '0.0';
  const upcoming = S.webinars.filter(w => w.status === 'upcoming').length;
  const completed= S.webinars.filter(w => w.status === 'completed').length;

  const speakerOptions = S.speakers.map(sp =>
    `<option value="${sp.id}" ${S.filterSpeaker==sp.id?'selected':''}>${esc(sp.name)}</option>`
  ).join('');

  const gridHTML = list.length
    ? `<div class="wb-grid">${list.map(webinarCardHTML).join('')}</div>`
    : `<div class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">No webinars found</div>
        <div class="empty-sub">Try adjusting your filters or add a new webinar.</div>
      </div>`;

  setContent(`
    <div>
      <!-- Header -->
      <div class="page-hd">
        <div>
          <h1 class="page-title">Webinar Dashboard</h1>
          <p class="page-sub">${total} webinars · ${S.speakers.length} speakers</p>
        </div>
        <button class="btn btn-primary" onclick="openWebinarModal()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add New Webinar
        </button>
      </div>

      <!-- Stats strip -->
      <div class="stats-strip">
        <div class="ss-item">
          <span class="ss-val">${total}</span>
          <span class="ss-lbl">Total Webinars</span>
        </div>
        <div class="ss-item">
          <span class="ss-val" style="color:#2563eb">${fmt(totalReg)}</span>
          <span class="ss-lbl">Registrations</span>
        </div>
        <div class="ss-item">
          <span class="ss-val" style="color:#059669">${fmt(totalAtt)}</span>
          <span class="ss-lbl">Attendees</span>
        </div>
        <div class="ss-item">
          <span class="ss-val" style="color:#7c3aed">${avgRate}%</span>
          <span class="ss-lbl">Avg. Rate</span>
        </div>
        <div class="ss-item">
          <span class="ss-val" style="color:#d97706">${upcoming}</span>
          <span class="ss-lbl">Upcoming</span>
        </div>
        <div class="ss-item">
          <span class="ss-val" style="color:#059669">${completed}</span>
          <span class="ss-lbl">Completed</span>
        </div>
      </div>

      <!-- Filters -->
      <div class="filter-bar">
        <span class="filter-pill ${S.filterStatus==='all'?'active':''}" onclick="setFilter('status','all')">All</span>
        <span class="filter-pill ${S.filterStatus==='completed'?'active':''}" onclick="setFilter('status','completed')">Completed</span>
        <span class="filter-pill ${S.filterStatus==='upcoming'?'active':''}" onclick="setFilter('status','upcoming')">Upcoming</span>
        <select class="filter-select" onchange="setFilter('speaker',this.value)">
          <option value="all">All Speakers</option>
          ${speakerOptions}
        </select>
      </div>

      <!-- Webinar cards -->
      ${gridHTML}
    </div>
  `);
}

function setFilter(type, value) {
  if (type === 'status')  S.filterStatus  = value;
  if (type === 'speaker') S.filterSpeaker = value;
  renderHome();
}

/* ── Webinar card ───────────────────────────────────────────────────────── */
function webinarCardHTML(w) {
  const color    = avColor(w.speaker_name);
  const ini      = initials(w.speaker_name);
  const rate     = w.attendance_rate || 0;
  const rateClr  = rate >= 60 ? '#059669' : rate >= 40 ? '#d97706' : rate > 0 ? '#dc2626' : 'var(--text-3)';
  const badgeCls = w.status === 'completed' ? 'completed' : w.status === 'upcoming' ? 'upcoming' : 'incomplete';
  const bothDone = w.has_registration_data && w.has_attendee_data;

  return `
    <div class="wb-card" onclick="nav('webinar',${w.id})">
      <div class="wb-card-top" style="background:${color}"></div>
      <div class="wb-card-body">
        <div class="wb-card-hd">
          <div class="wb-card-title">${esc(w.title)}</div>
          <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
            <span class="wb-badge ${badgeCls}">${w.status}</span>
            <button class="wb-card-del" title="Delete webinar"
              onclick="event.stopPropagation();confirmDeleteWebinar(${w.id},'${esc(w.title).replace(/'/g,"\\'")}')">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="wb-card-meta">
          <span>${fmtDate(w.date)}</span>
          ${w.time ? `<span class="wb-card-meta-dot"></span><span>${esc(w.time)}</span>` : ''}
        </div>
        <div class="wb-card-speaker">
          <div class="wb-card-spk-av" style="background:${color}">${ini}</div>
          ${esc(w.speaker_name)}
        </div>
        <div class="wb-card-stats">
          <div class="wb-card-stat">
            <div class="wb-card-stat-val" style="color:#2563eb">${fmt(w.total_registrations)}</div>
            <div class="wb-card-stat-lbl">Registered</div>
          </div>
          <div class="wb-card-stat">
            <div class="wb-card-stat-val" style="color:#059669">${fmt(w.total_attendees)}</div>
            <div class="wb-card-stat-lbl">Attended</div>
          </div>
          <div class="wb-card-stat">
            <div class="wb-card-stat-val" style="color:${rateClr}">${fmtPct(rate)}</div>
            <div class="wb-card-stat-lbl">Rate</div>
          </div>
        </div>
      </div>
      <div class="wb-card-upload-bar">
        ${bothDone
          ? `<span class="upload-tag has">✓ All data uploaded</span>`
          : `
            <span class="upload-tag ${w.has_registration_data?'has':'none'}">
              ${w.has_registration_data ? '✓' : '○'} Registrations
            </span>
            <span class="upload-tag ${w.has_attendee_data?'has':'none'}">
              ${w.has_attendee_data ? '✓' : '○'} Attendees
            </span>`
        }
      </div>
    </div>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   WEBINAR DETAIL
══════════════════════════════════════════════════════════════════════════ */
async function renderWebinarDetail(id) {
  setContent('<div class="pg-loading"><div class="spinner"></div><p>Loading…</p></div>');
  try {
    // Always re-fetch so upload results are fresh
    const w = await api(`/api/webinars/${id}`);
    detailCache[id] = w;
    _drawWebinarDetail(w);
  } catch(e) {
    setContent('<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-title">Failed to load</div></div>');
  }
}

function _drawWebinarDetail(w) {
  const color    = avColor(w.speaker_name);
  const ini      = initials(w.speaker_name);
  const noShow   = w.no_shows ?? (w.total_registrations - w.total_attendees);
  const rate     = w.attendance_rate || 0;
  const rateClr  = rate >= 60 ? '#059669' : rate >= 40 ? '#d97706' : rate > 0 ? '#dc2626' : 'var(--text-3)';
  const badgeCls = w.status === 'completed' ? 'completed' : w.status === 'upcoming' ? 'upcoming' : 'incomplete';

  // Smart upload section:
  // Show upload card only if that data type is missing — regardless of status
  const showRegUpload = !w.has_registration_data;
  const showAttUpload = !w.has_attendee_data;
  const showUploadSection = showRegUpload || showAttUpload;

  const uploadSVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>';

  const regCard = showRegUpload ? `
    <div class="upload-card" id="reg-upload-card"
         ondragover="event.preventDefault();this.classList.add('dragover')"
         ondragleave="this.classList.remove('dragover')"
         ondrop="handleFileDrop(event,${w.id},'registrations')">
      <div class="upload-card-icon">📤</div>
      <div class="upload-card-title">Registration Data</div>
      <div class="upload-card-sub">Upload list of people who registered</div>
      <input type="file" class="upload-file-input" id="reg-file-input"
             accept=".csv,.xlsx,.xls"
             onchange="handleFileSelect(event,${w.id},'registrations')"/>
      <button class="btn btn-primary btn-sm upload-card-btn"
              onclick="document.getElementById('reg-file-input').click()">
        ${uploadSVG} Upload File
      </button>
    </div>` : '';

  const attCard = showAttUpload ? `
    <div class="upload-card" id="att-upload-card"
         ondragover="event.preventDefault();this.classList.add('dragover')"
         ondragleave="this.classList.remove('dragover')"
         ondrop="handleFileDrop(event,${w.id},'attendees')">
      <div class="upload-card-icon">📥</div>
      <div class="upload-card-title">Attendee Data</div>
      <div class="upload-card-sub">Upload list of people who attended (e.g. Zoom report)</div>
      <input type="file" class="upload-file-input" id="att-file-input"
             accept=".csv,.xlsx,.xls"
             onchange="handleFileSelect(event,${w.id},'attendees')"/>
      <button class="btn btn-primary btn-sm upload-card-btn"
              onclick="document.getElementById('att-file-input').click()">
        ${uploadSVG} Upload File
      </button>
    </div>` : '';

  const uploadSectionHTML = showUploadSection ? `
    <div class="sec-hd" style="margin-bottom:12px">
      <span class="sec-title">Data Upload</span>
      <span style="font-size:12px;color:var(--text-3)">Upload CSV or Excel files</span>
    </div>
    <div class="upload-section" style="${!showRegUpload || !showAttUpload ? 'grid-template-columns:1fr' : ''}">
      ${regCard}
      ${attCard}
    </div>` : '';

  // Analysis cards
  const analysisHTML = `
    <div class="analysis-grid">
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:#dbeafe">📝</div>
        <div><div class="an-stat-val" style="color:#2563eb">${fmt(w.total_registrations)}</div><div class="an-stat-lbl">Registered</div></div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:#dcfce7">✅</div>
        <div><div class="an-stat-val" style="color:#059669">${fmt(w.total_attendees)}</div><div class="an-stat-lbl">Attended</div></div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:#fee2e2">❌</div>
        <div><div class="an-stat-val" style="color:#dc2626">${fmt(noShow)}</div><div class="an-stat-lbl">No-shows</div></div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:#ede9fe">📊</div>
        <div><div class="an-stat-val" style="color:${rateClr}">${rate}%</div><div class="an-stat-lbl">Attendance Rate</div></div>
      </div>
      ${w.duplicates_removed > 0 ? `
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:#fef3c7">🔄</div>
        <div><div class="an-stat-val" style="color:#d97706">${fmt(w.duplicates_removed)}</div><div class="an-stat-lbl">Duplicates Removed</div></div>
      </div>` : ''}
      ${w.unmatched_attendees > 0 ? `
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:#fef9ec">⚠️</div>
        <div><div class="an-stat-val" style="color:#b45309">${fmt(w.unmatched_attendees)}</div><div class="an-stat-lbl">Walk-ins (not registered)</div></div>
      </div>` : ''}
    </div>`;

  // Duration chart
  const durRows = (w.duration_breakdown || []).map(d => {
    const c = DUR_COLORS[d.range] || '#94a3b8';
    return `<div class="dur-row">
      <span class="dur-lbl">${esc(d.range)}</span>
      <div class="dur-track"><div class="dur-fill" style="width:${d.percentage}%;background:${c}"></div></div>
      <span class="dur-pct">${d.percentage}%</span>
      <span class="dur-cnt">${d.count} people</span>
    </div>`;
  }).join('');


  // Upload logs
  const logsHTML = (w.upload_logs || []).length ? `
    <div class="upload-log-section">
      <div class="upload-log-title">Upload History</div>
      ${(w.upload_logs||[]).map(l => `
        <div class="log-row">
          <span class="log-tag ${l.file_type==='registrations'?'reg':'att'}">${l.file_type}</span>
          <span class="log-file">${esc(l.filename||'—')}</span>
          <span class="log-stat">${l.original_count} → ${l.final_count} rows</span>
          ${l.duplicates_removed ? `<span class="log-stat" style="color:#d97706">${l.duplicates_removed} dupes removed</span>` : ''}
          <span class="log-stat">${fmtDateTime(l.uploaded_at)}</span>
        </div>`).join('')}
    </div>` : '';

  const safeTitle = esc(w.title).replace(/'/g,"\\'");

  setContent(`
    <div>
      <button class="back-btn" onclick="nav('home')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15,18 9,12 15,6"/></svg>
        All Webinars
      </button>

      <!-- Hero -->
      <div class="wd-hero">
        <div class="wd-hero-accent" style="background:${color}"></div>
        <div class="wd-hero-body">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap">
            <div>
              <div class="wd-hero-title">${esc(w.title)}</div>
              <div class="wd-hero-meta">${fmtDate(w.date)}${w.time?' · '+esc(w.time):''}</div>
              ${w.description ? `<div class="wd-hero-desc">${esc(w.description)}</div>` : ''}
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
              <span class="wb-badge ${badgeCls}" style="font-size:12px;padding:5px 14px">${w.status}</span>
              <button class="wb-card-del" style="width:32px;height:32px" title="Delete webinar"
                onclick="confirmDeleteWebinar(${w.id},'${safeTitle}')">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                  <path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="wd-hero-speaker">
            <div class="wb-card-spk-av" style="background:${color};width:26px;height:26px;font-size:11px">${ini}</div>
            ${esc(w.speaker_name)}
          </div>
        </div>
      </div>

      <!-- Smart upload section -->
      ${uploadSectionHTML}

      ${(w.total_registrations > 0 || w.total_attendees > 0) ? `
      <!-- Analysis -->
      <div class="sec-hd" style="margin-bottom:12px">
        <span class="sec-title">Analysis</span>
      </div>
      ${analysisHTML}

      ${durRows ? `
      <div class="dur-section">
        <div class="dur-section-title">Time Spent in Session</div>
        ${durRows}
      </div>` : ''}
      ` : ''}

      ${logsHTML}
    </div>`);
}

/* ── File upload handlers ───────────────────────────────────────────────── */
async function handleFileSelect(event, webinarId, type) {
  const file = event.target.files[0];
  if (!file) return;
  event.target.value = '';
  await uploadFile(webinarId, type, file);
}

async function handleFileDrop(event, webinarId, type) {
  event.preventDefault();
  event.currentTarget.classList.remove('dragover');
  const file = event.dataTransfer.files[0];
  if (!file) return;
  await uploadFile(webinarId, type, file);
}

async function uploadFile(webinarId, type, file) {
  // Show uploading state
  const cardId = type === 'registrations' ? 'reg-upload-card' : 'att-upload-card';
  const card = document.getElementById(cardId);
  if (card) {
    card.style.opacity = '0.6';
    card.style.pointerEvents = 'none';
  }
  showToast(`Uploading ${file.name}…`);

  try {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch(`/api/webinars/${webinarId}/upload/${type}`, {
      method: 'POST',
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Upload failed');
    }
    const result = await resp.json();
    showToast(result.message);
    // Invalidate cache and re-render detail
    delete detailCache[webinarId];
    // Update the webinar in S.webinars list with fresh data
    const fresh = await api(`/api/webinars/${webinarId}`);
    detailCache[webinarId] = fresh;
    const idx = S.webinars.findIndex(w => w.id === webinarId);
    if (idx >= 0) {
      S.webinars[idx].total_registrations = fresh.total_registrations;
      S.webinars[idx].total_attendees = fresh.total_attendees;
      S.webinars[idx].attendance_rate = fresh.attendance_rate;
      S.webinars[idx].has_registration_data = fresh.total_registrations > 0;
      S.webinars[idx].has_attendee_data = fresh.total_attendees > 0;
    }
    _drawWebinarDetail(fresh);
  } catch(e) {
    showToast(e.message || 'Upload failed', 'error');
    if (card) { card.style.opacity = ''; card.style.pointerEvents = ''; }
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   ANALYTICS
══════════════════════════════════════════════════════════════════════════ */
function renderAnalytics() {
  if (!S.stats) {
    setContent('<div class="pg-loading"><div class="spinner"></div><p>Loading…</p></div>');
    return;
  }
  const st = S.stats;
  const top10reg  = [...S.webinars].sort((a,b) => b.total_registrations - a.total_registrations).slice(0,10);
  const top10att  = [...S.webinars].filter(w => w.status==='completed').sort((a,b) => b.attendance_rate - a.attendance_rate).slice(0,10);
  const maxReg    = top10reg[0]?.total_registrations || 1;

  const spkStats = S.speakers.map(sp => {
    const wbs     = S.webinars.filter(w => w.speaker_id === sp.id);
    const totalReg = wbs.reduce((s,w) => s+w.total_registrations, 0);
    const totalAtt = wbs.reduce((s,w) => s+w.total_attendees, 0);
    const done     = wbs.filter(w => w.status==='completed');
    const avgRate  = done.length ? (done.reduce((s,w)=>s+w.attendance_rate,0)/done.length).toFixed(1) : '0.0';
    return { name:sp.name, totalReg, totalAtt, count:wbs.length, avgRate, color:avColor(sp.name) };
  }).sort((a,b) => b.totalReg - a.totalReg);
  const maxSpkReg = spkStats[0]?.totalReg || 1;

  setContent(`
    <div>
      <div class="page-hd">
        <div>
          <h1 class="page-title">Analytics</h1>
          <p class="page-sub">All-time platform performance</p>
        </div>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-label">Total Webinars</div>
          <div class="stat-value">${fmt(st.total_webinars)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Speakers</div>
          <div class="stat-value">${fmt(st.total_speakers)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Registrations</div>
          <div class="stat-value">${fmt(st.total_registrations)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Attendees</div>
          <div class="stat-value">${fmt(st.total_attendees)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Upcoming Webinars</div>
          <div class="stat-value" style="color:#d97706">${fmt(st.upcoming_webinars)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Avg. Attendance Rate</div>
          <div class="stat-value" style="color:#7c3aed">${fmtPct(st.overall_attendance_rate)}</div>
        </div>
      </div>

      <div class="an-grid">
        <div class="an-card">
          <div class="an-title">Top 10 by Registrations</div>
          ${top10reg.map(w => `
            <div class="an-row">
              <span class="an-row-lbl" title="${esc(w.title)}">${esc(w.title)}</span>
              <div class="an-bar-wrap"><div class="an-bar-fill" style="width:${Math.round(w.total_registrations/maxReg*100)}%;background:#6366f1"></div></div>
              <span class="an-row-val">${fmt(w.total_registrations)}</span>
            </div>`).join('')}
        </div>

        <div class="an-card">
          <div class="an-title">Top 10 by Attendance Rate</div>
          ${top10att.map(w => `
            <div class="an-row">
              <span class="an-row-lbl" title="${esc(w.title)}">${esc(w.title)}</span>
              <div class="an-bar-wrap"><div class="an-bar-fill" style="width:${Math.min(w.attendance_rate,100)}%;background:#22c55e"></div></div>
              <span class="an-row-val">${fmtPct(w.attendance_rate)}</span>
            </div>`).join('')}
        </div>

        <div class="an-card full">
          <div class="an-title">Speaker Performance</div>
          ${spkStats.map(sp => `
            <div class="an-row">
              <span class="an-row-lbl">
                <span style="display:inline-flex;align-items:center;gap:6px">
                  <span style="width:8px;height:8px;border-radius:50%;background:${sp.color};display:inline-block"></span>
                  ${esc(sp.name)} <span style="color:var(--text-3);font-size:11px">(${sp.count} webinars)</span>
                </span>
              </span>
              <div class="an-bar-wrap"><div class="an-bar-fill" style="width:${Math.round(sp.totalReg/maxSpkReg*100)}%;background:${sp.color}"></div></div>
              <span class="an-row-val">${fmt(sp.totalReg)}</span>
            </div>`).join('')}
        </div>
      </div>
    </div>`);
}

/* ══════════════════════════════════════════════════════════════════════════
   SPEAKERS
══════════════════════════════════════════════════════════════════════════ */
function renderSpeakers() {
  setContent(`
    <div>
      <div class="page-hd">
        <div>
          <h1 class="page-title">Speakers</h1>
          <p class="page-sub">${S.speakers.length} speakers</p>
        </div>
      </div>
      <div class="spk-grid">
        ${S.speakers.map(sp => {
          const color = avColor(sp.name);
          const ini   = initials(sp.name);
          return `
            <div class="spk-card" onclick="nav('speaker',${sp.id})">
              <div class="spk-av" style="background:${color}">${ini}</div>
              <div class="spk-name">${esc(sp.name)}</div>
              <div class="spk-bio">${esc(sp.bio || '—')}</div>
              <div class="spk-stats">
                <div>
                  <div class="spk-stat-val" style="color:${color}">${sp.total_webinars}</div>
                  <div class="spk-stat-lbl">Webinars</div>
                </div>
              </div>
            </div>`;
        }).join('')}
      </div>
    </div>`);
}

/* ── Speaker detail ─────────────────────────────────────────────────────── */
async function renderSpeakerDetail(id) {
  setContent('<div class="pg-loading"><div class="spinner"></div><p>Loading…</p></div>');
  try {
    if (!detailCache['spk_'+id]) detailCache['spk_'+id] = await api(`/api/speakers/${id}`);
    const sp = detailCache['spk_'+id];
    const color    = avColor(sp.name);
    const ini      = initials(sp.name);
    const totalReg = sp.webinars.reduce((a,w)=>a+(w.total_registrations||0),0);
    const totalAtt = sp.webinars.reduce((a,w)=>a+(w.total_attendees||0),0);
    const done     = sp.webinars.filter(w=>w.status==='completed');
    const avgRate  = done.length ? (done.reduce((a,w)=>a+w.attendance_rate,0)/done.length).toFixed(1) : '0.0';

    const wbItems = sp.webinars.map((w, i) => {
      const noShow = w.no_shows ?? (w.total_registrations - w.total_attendees);
      const rc = w.attendance_rate >= 60 ? '#059669' : w.attendance_rate >= 40 ? '#d97706' : '#dc2626';
      const durRows = (w.duration_breakdown||[]).map(d => {
        const c = DUR_COLORS[d.range]||'#94a3b8';
        return `<div class="dur-row"><span class="dur-lbl">${esc(d.range)}</span>
          <div class="dur-track"><div class="dur-fill" style="width:${d.percentage}%;background:${c}"></div></div>
          <span class="dur-pct">${d.percentage}%</span><span class="dur-cnt">${d.count} people</span></div>`;
      }).join('');
      return `
        <div class="wb-acc-item" id="wba-${i}">
          <div class="wb-acc-head" onclick="toggleAcc('wba-${i}')">
            <span class="wb-acc-title">${esc(w.title)}</span>
            <span class="wb-acc-meta">${fmtDate(w.date)}</span>
            <span class="wb-badge ${w.status==='completed'?'completed':w.status==='upcoming'?'upcoming':'incomplete'}" style="margin:0 4px">${w.status}</span>
            <svg class="wb-acc-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <div class="wb-acc-body">
            <div class="wb-acc-content">
              <div class="bk-metrics">
                <div class="bk-metric"><span class="bk-metric-icon">📝</span><div><div class="bk-metric-val" style="color:#2563eb">${fmt(w.total_registrations)}</div><div class="bk-metric-lbl">Registered</div></div></div>
                <div class="bk-metric"><span class="bk-metric-icon">✅</span><div><div class="bk-metric-val" style="color:#059669">${fmt(w.total_attendees)}</div><div class="bk-metric-lbl">Attended</div></div></div>
                <div class="bk-metric"><span class="bk-metric-icon">❌</span><div><div class="bk-metric-val" style="color:#dc2626">${fmt(noShow)}</div><div class="bk-metric-lbl">No-shows</div></div></div>
                <div class="bk-metric"><span class="bk-metric-icon">📊</span><div><div class="bk-metric-val" style="color:${rc}">${w.attendance_rate}%</div><div class="bk-metric-lbl">Rate</div></div></div>
              </div>
              ${durRows ? `<div class="bk-dur-title">Time Spent in Session</div>${durRows}` : ''}
            </div>
          </div>
        </div>`;
    }).join('');

    setContent(`
      <div>
        <button class="back-btn" onclick="nav('speakers')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15,18 9,12 15,6"/></svg>
          All Speakers
        </button>
        <div class="spk-hero">
          <div class="spk-hero-av" style="background:${color}">${ini}</div>
          <div style="flex:1">
            <div class="spk-hero-name">${esc(sp.name)}</div>
            <div class="spk-hero-bio">${esc(sp.bio || '—')}</div>
            <div class="spk-hero-stats">
              <div><div class="spk-hero-stat-val">${sp.total_webinars}</div><div class="spk-hero-stat-lbl">Webinars</div></div>
              <div><div class="spk-hero-stat-val">${fmt(totalReg)}</div><div class="spk-hero-stat-lbl">Registrations</div></div>
              <div><div class="spk-hero-stat-val">${fmt(totalAtt)}</div><div class="spk-hero-stat-lbl">Attendees</div></div>
              <div><div class="spk-hero-stat-val">${avgRate}%</div><div class="spk-hero-stat-lbl">Avg. Rate</div></div>
            </div>
            ${sp.email ? `<div class="spk-hero-email">✉ ${esc(sp.email)}</div>` : ''}
          </div>
        </div>
        <div class="sec-hd">
          <span class="sec-title">Webinar History</span>
          <span style="font-size:12px;color:var(--text-3)">${sp.total_webinars} total</span>
        </div>
        ${wbItems || '<div class="empty-state"><div class="empty-icon">📋</div><div class="empty-title">No webinars yet</div></div>'}
      </div>`);
  } catch(e) {
    setContent('<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-title">Failed to load speaker data</div></div>');
  }
}

function toggleAcc(id) {
  document.getElementById(id)?.classList.toggle('open');
}

/* ══════════════════════════════════════════════════════════════════════════
   LEADERBOARD
══════════════════════════════════════════════════════════════════════════ */
async function renderLeaderboard(speakerId, webinarId) {
  // Update persistent filter state if arguments provided
  if (speakerId !== undefined) S._lbSpeaker = speakerId;
  if (webinarId !== undefined) S._lbWebinar = webinarId;

  setContent('<div class="pg-loading"><div class="spinner"></div><p>Loading leaderboard…</p></div>');

  const params = new URLSearchParams();
  const selSpeaker = S._lbSpeaker || '';
  const selWebinar = S._lbWebinar || '';
  if (selSpeaker) params.set('speaker_id', selSpeaker);
  if (selWebinar) params.set('webinar_id', selWebinar);

  try {
    const lb = await api('/api/leaderboard?' + params.toString());

    const speakerOpts = S.speakers.map(sp =>
      `<option value="${sp.id}" ${selSpeaker==sp.id?'selected':''}>${esc(sp.name)}</option>`
    ).join('');
    const webinarOpts = S.webinars.map(w =>
      `<option value="${w.id}" ${selWebinar==w.id?'selected':''}>${esc(w.title)} (${fmtDate(w.date)})</option>`
    ).join('');

    const rankHTML = (rank) => {
      const cls = rank===1?'gold':rank===2?'silver':rank===3?'bronze':'other';
      return `<span class="lb-rank ${cls}">${rank}</span>`;
    };

    const tableHTML = lb.length ? `
      <div class="lb-table-wrap">
        <table class="lb-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Webinars Attended</th>
              <th>Total Time (min)</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            ${lb.map(e => `
              <tr>
                <td>${rankHTML(e.rank)}</td>
                <td><div class="lb-name">${esc(e.name)}</div></td>
                <td><div class="lb-email">${esc(e.email||'—')}</div></td>
                <td><div class="lb-email">${esc(e.phone||'—')}</div></td>
                <td style="text-align:center;font-weight:600;color:#059669">${e.webinars_attended}</td>
                <td style="text-align:center;color:var(--text-2)">${e.total_duration_minutes}</td>
                <td><span class="lb-score">⭐ ${e.score}</span></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>` : `<div class="lb-empty">No attendance data yet.<br>Upload attendee files to populate the leaderboard.</div>`;

    setContent(`
      <div>
        <div class="page-hd">
          <div>
            <h1 class="page-title">Attendee Leaderboard</h1>
            <p class="page-sub">Top attendees ranked by score · ${lb.length} entries</p>
          </div>
        </div>

        <div class="lb-filters">
          <select class="filter-select" onchange="S._lbSpeaker=this.value;S._lbWebinar='';renderLeaderboard()">
            <option value="" ${!selSpeaker?'selected':''}>All Speakers</option>
            ${speakerOpts}
          </select>
          <select class="filter-select" onchange="S._lbWebinar=this.value;S._lbSpeaker='';renderLeaderboard()">
            <option value="" ${!selWebinar?'selected':''}>All Webinars</option>
            ${webinarOpts}
          </select>
          <button class="btn btn-ghost btn-sm" onclick="S._lbSpeaker='';S._lbWebinar='';renderLeaderboard()">Clear Filters</button>
          <span style="font-size:12px;color:var(--text-3);margin-left:6px">
            Score = 10 pts per webinar attended + bonus for longer sessions
          </span>
        </div>

        ${tableHTML}
      </div>`);
  } catch(e) {
    setContent('<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-title">Failed to load leaderboard</div></div>');
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   NEW WEBINAR MODAL
══════════════════════════════════════════════════════════════════════════ */
function openWebinarModal() {
  // Default date to today
  const today = new Date().toISOString().split('T')[0];
  const dateInput = document.getElementById('nw-date');
  if (dateInput && !dateInput.value) dateInput.value = today;
  document.getElementById('modal-overlay').classList.add('open');
  setTimeout(() => document.getElementById('nw-title').focus(), 80);
}

function closeWebinarModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  ['nw-title','nw-time','nw-speaker','nw-desc'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
}

async function submitWebinarModal() {
  const title   = document.getElementById('nw-title').value.trim();
  const dateVal = document.getElementById('nw-date').value;
  const speaker = document.getElementById('nw-speaker').value.trim();

  // Validation
  if (!title) {
    document.getElementById('nw-title').focus();
    showToast('Please enter a webinar name', 'error');
    return;
  }
  if (!dateVal) {
    document.getElementById('nw-date').focus();
    showToast('Please choose a date', 'error');
    return;
  }
  if (!speaker) {
    document.getElementById('nw-speaker').focus();
    showToast('Please enter a speaker name', 'error');
    return;
  }

  // Disable button & show loading
  const btn = document.querySelector('#modal-overlay .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

  const payload = {
    title,
    date: dateVal,
    time: document.getElementById('nw-time').value.trim() || null,
    speaker_name: speaker,
    description: document.getElementById('nw-desc').value.trim() || null,
    status: document.getElementById('nw-status').value,
  };

  try {
    const created = await api('/api/webinars', 'POST', payload);
    closeWebinarModal();
    showToast(`"${title}" saved! Upload your data below.`);

    // Refresh lists so new speaker appears
    const [webinars, speakers] = await Promise.all([
      api('/api/webinars'),
      api('/api/speakers'),
    ]);
    S.webinars = webinars;
    S.speakers = speakers;

    // Update speaker datalist
    const dl = document.getElementById('speaker-list');
    if (dl) dl.innerHTML = S.speakers.map(sp => `<option value="${esc(sp.name)}">`).join('');

    // Go straight to the new webinar's upload/detail page
    nav('webinar', created.id);
  } catch(e) {
    showToast('Could not save webinar — please try again.', 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Create Webinar';
    }
  }
}

/* ── Delete webinar ─────────────────────────────────────────────────────── */
async function confirmDeleteWebinar(id, title) {
  if (!confirm(`Delete "${title}"?\n\nThis will permanently remove all registration and attendance data. This cannot be undone.`)) return;
  try {
    await api(`/api/webinars/${id}`, 'DELETE');
    S.webinars = S.webinars.filter(w => w.id !== id);
    showToast(`"${title}" deleted`);
    nav('home');
  } catch(e) {
    showToast('Failed to delete webinar', 'error');
  }
}

/* ── Search ─────────────────────────────────────────────────────────────── */
function onSearch(q) {
  S.search = q;
  if (S.page === 'home')      renderHome();
  else if (S.page === 'speakers') renderSpeakers();
}

/* ── Dark mode ──────────────────────────────────────────────────────────── */
function toggleDark() {
  S.dark = !S.dark;
  document.documentElement.classList.toggle('dark', S.dark);
  localStorage.setItem('wiq-dark', S.dark);
  const icon = document.getElementById('dark-icon');
  if (icon) {
    icon.innerHTML = S.dark
      ? '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
      : '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
  }
}

/* ── Toast ──────────────────────────────────────────────────────────────── */
function showToast(msg, type='success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast show${type==='error'?' error':''}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 3000);
}

/* ── Init ───────────────────────────────────────────────────────────────── */
async function init() {
  if (localStorage.getItem('wiq-dark') === 'true') {
    S.dark = true;
    document.documentElement.classList.add('dark');
  }
  const greet = document.getElementById('tb-greeting');
  if (greet) greet.textContent = `${greeting()}, ShreeKrishna!`;

  try {
    await loadAll();
  } catch(e) {
    console.error('API load failed:', e);
  }
  nav('home');
}

document.addEventListener('DOMContentLoaded', init);
