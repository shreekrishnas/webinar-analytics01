/* ── State ──────────────────────────────────────────────────────────────── */
const S = {
  webinars: [], speakers: [], stats: null,
  page: 'home', sub: null, dark: false, search: '',
  filterStatus: 'all', filterSpeaker: 'all',
  _lbSpeaker: '', _lbWebinar: '',
};

/* Ad modal state (module-level so image stays across re-renders) */
let _adWebinarId   = null;
let _adImageBase64 = null;
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

const AV_COLORS = ['#6366f1','#f59e0b','#38bdf8','#10b981','#f97316','#a855f7','#22d3ee','#84cc16','#ec4899','#64748b'];
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

/* ── Health Score Helpers ───────────────────────────────────────────────── */
function gradeInfo(rate) {
  if (!rate || rate === 0)  return { grade: '—', cls: 'none',    color: '#5c5580',  track: 'rgba(92,85,128,0.2)' };
  if (rate >= 70)           return { grade: 'A',  cls: 'grade-A', color: '#10b981',  track: 'rgba(16,185,129,0.18)' };
  if (rate >= 50)           return { grade: 'B',  cls: 'grade-B', color: '#3b82f6',  track: 'rgba(59,130,246,0.18)' };
  if (rate >= 30)           return { grade: 'C',  cls: 'grade-C', color: '#f59e0b',  track: 'rgba(245,158,11,0.18)' };
  return                           { grade: 'D',  cls: 'grade-D', color: '#f43f5e',  track: 'rgba(244,63,94,0.18)' };
}

function donutRing(rate, size = 48) {
  const r    = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const fill = rate > 0 ? (rate / 100) * circ : 0;
  const info = gradeInfo(rate);
  return `<svg class="wb-health-ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${size/2}" cy="${size/2}" r="${r}"
      fill="none" stroke="${info.track}" stroke-width="4.5"/>
    <circle cx="${size/2}" cy="${size/2}" r="${r}"
      fill="none" stroke="${info.color}" stroke-width="4.5"
      stroke-linecap="round"
      stroke-dasharray="${circ}"
      stroke-dashoffset="${circ - fill}"
      transform="rotate(-90 ${size/2} ${size/2})"
      style="transition:stroke-dashoffset 0.8s cubic-bezier(.4,0,.2,1)"/>
  </svg>`;
}

function sparkBars(values, maxH = 28) {
  if (!values || !values.length) return '';
  const max = Math.max(...values, 1);
  const bars = values.map((v, i) => {
    const h = Math.max(3, Math.round((v / max) * maxH));
    const isCurrent = i === values.length - 1;
    return `<div class="spark-bar${isCurrent ? ' current' : ''}"
      style="height:${h}px;background:currentColor;animation-delay:${200 + i*40}ms"></div>`;
  }).join('');
  return `<div class="spark-bars">${bars}</div>`;
}

/* ── Notifications ──────────────────────────────────────────────────────── */
const _notifStore = { items: [], read: new Set() };

function getNotifications() {
  // Build activity from loaded data
  const notes = [];
  const completed = S.webinars.filter(w => w.status === 'completed');
  const upcoming  = S.webinars.filter(w => w.status === 'upcoming');
  const noData    = S.webinars.filter(w => !w.has_registration_data && !w.has_attendee_data && w.status === 'completed');

  // Top performer
  const topWebinar = [...completed].sort((a,b) => b.attendance_rate - a.attendance_rate)[0];
  if (topWebinar && topWebinar.attendance_rate > 0) {
    notes.push({
      id: `top-${topWebinar.id}`,
      icon: '🏆',
      title: `Top performer: ${topWebinar.title}`,
      desc: `${topWebinar.attendance_rate.toFixed(1)}% attendance rate — Grade ${gradeInfo(topWebinar.attendance_rate).grade}`,
      time: 'Best',
      link: () => nav('webinar', topWebinar.id),
    });
  }
  // Next upcoming
  const nextUp = upcoming.sort((a,b) => new Date(a.date)-new Date(b.date))[0];
  if (nextUp) {
    notes.push({
      id: `up-${nextUp.id}`,
      icon: '📅',
      title: `Upcoming: ${nextUp.title}`,
      desc: `Scheduled for ${fmtDate(nextUp.date)}${nextUp.speaker_name ? ' · ' + nextUp.speaker_name : ''}`,
      time: 'Soon',
      link: () => nav('webinar', nextUp.id),
    });
  }
  // Webinars missing data
  if (noData.length) {
    notes.push({
      id: 'missing-data',
      icon: '⚠️',
      title: `${noData.length} webinar${noData.length>1?'s':''} missing data`,
      desc: `Upload attendance & registration CSVs for accurate analytics`,
      time: 'Action',
      link: () => nav('home'),
    });
  }
  // Platform summary
  const totalReg = S.webinars.reduce((a,w) => a+w.total_registrations, 0);
  if (totalReg > 0) {
    const totalAtt = S.webinars.reduce((a,w) => a+w.total_attendees, 0);
    const rate = totalReg ? ((totalAtt/totalReg)*100).toFixed(1) : 0;
    notes.push({
      id: 'platform-rate',
      icon: '📊',
      title: 'Platform attendance rate',
      desc: `${rate}% across ${completed.length} completed webinars (${fmt(totalReg)} registrations)`,
      time: 'Stats',
      link: () => nav('analytics'),
    });
  }
  // Leaderboard
  notes.push({
    id: 'leaderboard',
    icon: '🎯',
    title: 'Check the leaderboard',
    desc: `See your most engaged attendees ranked by score`,
    time: 'View',
    link: () => nav('leaderboard'),
  });

  _notifStore.items = notes;
  return notes;
}

function toggleNotifPanel() {
  const panel    = document.getElementById('notif-panel');
  const backdrop = document.getElementById('notif-backdrop');
  const btn      = document.getElementById('tb-notif-btn');
  if (!panel) return;
  const isOpen = panel.classList.toggle('open');
  if (backdrop) backdrop.classList.toggle('open', isOpen);
  if (btn)      btn.classList.toggle('active', isOpen);
  if (isOpen) renderNotifPanel();
}

function closeNotifPanel() {
  const panel    = document.getElementById('notif-panel');
  const backdrop = document.getElementById('notif-backdrop');
  const btn      = document.getElementById('tb-notif-btn');
  if (panel)    panel.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  if (btn)      btn.classList.remove('active');
}

function renderNotifPanel() {
  const list  = document.getElementById('notif-list');
  const badge = document.getElementById('notif-badge');
  if (!list) return;
  const notes = getNotifications();
  if (!notes.length) {
    list.innerHTML = '<div class="notif-empty">No recent activity</div>';
    return;
  }
  const unreadCount = notes.filter(n => !_notifStore.read.has(n.id)).length;
  if (badge) {
    if (unreadCount > 0) {
      badge.textContent = unreadCount;
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }
  }
  list.innerHTML = notes.map(n => {
    const unread = !_notifStore.read.has(n.id);
    return `<div class="notif-item${unread?' unread':''}" onclick="closeNotifPanel();(${n.link.toString()})()">
      <div class="notif-icon">${n.icon}</div>
      <div class="notif-content">
        <div class="notif-title">${esc(n.title)}</div>
        <div class="notif-desc">${esc(n.desc)}</div>
      </div>
      <div class="notif-time">${esc(n.time)}</div>
    </div>`;
  }).join('');
}

function markAllRead() {
  getNotifications().forEach(n => _notifStore.read.add(n.id));
  renderNotifPanel();
  const badge = document.getElementById('notif-badge');
  if (badge) badge.style.display = 'none';
}

function updateNotifBadge() {
  const notes  = getNotifications();
  const badge  = document.getElementById('notif-badge');
  const unread = notes.filter(n => !_notifStore.read.has(n.id)).length;
  if (!badge) return;
  if (unread > 0) {
    badge.textContent = unread > 9 ? '9+' : unread;
    badge.style.display = 'flex';
  } else {
    badge.style.display = 'none';
  }
}

/* ── Activity feed builder (for dashboard panel) ────────────────────────── */
function buildActivityFeed() {
  const items     = [];
  const completed = S.webinars.filter(w => w.status === 'completed');
  const upcoming  = S.webinars.filter(w => w.status === 'upcoming');
  const noData    = S.webinars.filter(w => !w.has_registration_data && !w.has_attendee_data && w.status === 'completed');

  const topWebinar = [...completed].sort((a,b) => b.attendance_rate - a.attendance_rate)[0];
  if (topWebinar && topWebinar.attendance_rate > 0) {
    items.push({
      icon: '🏆', time: 'Best',
      title: topWebinar.title,
      desc:  `${topWebinar.attendance_rate.toFixed(1)}% attendance — Grade ${gradeInfo(topWebinar.attendance_rate).grade}`,
      onclick: `nav('webinar',${topWebinar.id})`,
    });
  }
  const nextUp = [...upcoming].sort((a,b) => new Date(a.date)-new Date(b.date))[0];
  if (nextUp) {
    items.push({
      icon: '📅', time: 'Soon',
      title: nextUp.title,
      desc:  `${fmtDate(nextUp.date)}${nextUp.speaker_name ? ' · ' + nextUp.speaker_name : ''}`,
      onclick: `nav('webinar',${nextUp.id})`,
    });
  }
  if (noData.length) {
    items.push({
      icon: '⚠️', time: 'Action',
      title: `${noData.length} webinar${noData.length>1?'s':''} missing data`,
      desc:  'Upload CSV files to enable full analytics',
      onclick: `nav('home')`,
    });
  }
  const totalReg = S.webinars.reduce((a,w) => a+w.total_registrations, 0);
  if (totalReg > 0) {
    const totalAtt = S.webinars.reduce((a,w) => a+w.total_attendees, 0);
    const rate = (totalAtt/totalReg*100).toFixed(1);
    items.push({
      icon: '📊', time: 'Stats',
      title: 'Platform attendance rate',
      desc:  `${rate}% across ${completed.length} completed webinars`,
      onclick: `nav('analytics')`,
    });
  }
  items.push({
    icon: '🎯', time: 'View',
    title: 'Attendee Leaderboard',
    desc:  'Top attendees ranked by engagement score',
    onclick: `nav('leaderboard')`,
  });
  return items;
}

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

/* ── Navbar chips ───────────────────────────────────────────────────────── */
function updateTopbarChips(page) {
  const chips = document.getElementById('nav-chips');
  if (!chips) return;
  if (page === 'home') {
    chips.style.display = 'flex';
    chips.querySelectorAll('.tb-chip').forEach(c => {
      c.classList.toggle('active', c.dataset.filter === S.filterStatus);
    });
  } else {
    chips.style.display = 'none';
  }
}

function setChipFilter(value) {
  S.filterStatus = value;
  // Sync chip active state
  document.querySelectorAll('.tb-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.filter === value)
  );
  if (S.page === 'home') renderHome();
}

/* ── Navigation ─────────────────────────────────────────────────────────── */
function nav(page, sub) {
  S.page = page;
  S.sub  = sub ?? null;
  // Update all nav-link elements (desktop + mobile menus)
  document.querySelectorAll('.nav-link[data-page]').forEach(b =>
    b.classList.toggle('active', b.dataset.page === page)
  );
  setBreadcrumb(page, sub);
  closeCmdPalette();
  closeNotifPanel();
  // Close mobile nav if open
  const mobileMenu = document.getElementById('nav-mobile-menu');
  if (mobileMenu && mobileMenu.classList.contains('open')) {
    mobileMenu.classList.remove('open');
  }
  updateTopbarChips(page);
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
  const el = document.getElementById('content');
  el.innerHTML = html;
  // Trigger animations after content is painted
  requestAnimationFrame(() => {
    animateCards('.wb-card, .spk-card');
    animateBars();
    runCountUps();
    decorateLeaderboardRows();
    initScrollReveal();
    initCardTilt();
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   KPI BANNER
══════════════════════════════════════════════════════════════════════════ */
function renderKpiBanner() {
  const total     = S.webinars.length;
  const completed = S.webinars.filter(w => w.status === 'completed');
  const upcoming  = S.webinars.filter(w => w.status === 'upcoming');
  const avgRate   = completed.length
    ? completed.reduce((a,w) => a + (w.attendance_rate||0), 0) / completed.length : 0;
  const completionRate = total ? (completed.length / total * 100) : 0;

  // Top speaker by total attendees
  const spkMap = {};
  S.webinars.forEach(w => {
    if (w.speaker_name) spkMap[w.speaker_name] = (spkMap[w.speaker_name]||0) + (w.total_attendees||0);
  });
  const topSpeakerFull = Object.keys(spkMap).sort((a,b) => spkMap[b]-spkMap[a])[0] || null;
  const topSpeakerDisplay = topSpeakerFull
    ? (topSpeakerFull.length > 14 ? topSpeakerFull.split(' ')[0] : topSpeakerFull)
    : '—';

  // Trend helpers — use real data if available, else demo %
  const trendArrowUp   = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="18 15 12 9 6 15"/></svg>`;
  const trendArrowDown = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>`;

  const kpis = [
    {
      icon: '🎙️', cls: 'kc-indigo',
      label: 'Total Webinars',
      value: total.toString(),
      trendUp: true, trend: `${upcoming.length} upcoming`, arrow: trendArrowUp,
    },
    {
      icon: '👥', cls: 'kc-sky',
      label: 'Avg. Attendance',
      value: avgRate > 0 ? fmtPct(avgRate) : '—',
      trendUp: avgRate >= 50, trend: avgRate >= 50 ? '+5% vs last period' : avgRate > 0 ? '-3% vs last period' : 'No data yet',
      arrow: avgRate >= 50 ? trendArrowUp : trendArrowDown,
    },
    {
      icon: '✅', cls: 'kc-emerald',
      label: 'Completion Rate',
      value: total > 0 ? fmtPct(completionRate) : '—',
      trendUp: completionRate >= 50, trend: completed.length + ' completed',
      arrow: completionRate >= 50 ? trendArrowUp : trendArrowDown,
    },
    {
      icon: '🏆', cls: 'kc-gold',
      label: 'Top Speaker',
      value: topSpeakerDisplay,
      trendUp: null, trend: topSpeakerFull ? 'By total attendance' : 'No data yet',
      arrow: null,
    },
  ];

  return kpis.map(k => `
    <div class="kpi-card ${k.cls}">
      <div class="kpi-card-head">
        <span class="kpi-card-label">${k.label}</span>
        <span class="kpi-card-icon">${k.icon}</span>
      </div>
      <div class="kpi-card-value">${k.value}</div>
      <div class="kpi-card-trend ${k.trendUp === true ? 'trend-up' : k.trendUp === false ? 'trend-down' : 'trend-neutral'}">
        ${k.arrow || ''}
        <span>${k.trend}</span>
      </div>
    </div>`).join('');
}

/* ── Status breakdown donut ─────────────────────────────────────────────── */
function renderStatusBreakdown() {
  const completed = S.webinars.filter(w => w.status === 'completed').length;
  const upcoming  = S.webinars.filter(w => w.status === 'upcoming').length;
  const cancelled = S.webinars.filter(w => w.status === 'cancelled').length;
  const total = completed + upcoming + cancelled;
  if (total === 0) return `<div class="status-donut-wrap">
    <div class="status-donut-title">Status Breakdown</div>
    <div class="empty-state" style="padding:30px 0;border:none">
      <div class="empty-icon" style="font-size:28px">📊</div>
      <div class="empty-title" style="font-size:14px">No data yet</div>
    </div>
  </div>`;

  const R    = 46;
  const circ = 2 * Math.PI * R;
  const cx = 60, cy = 60;

  const segs = [
    { len: completed/total*circ, color: '#10b981', label: 'Completed', n: completed },
    { len: upcoming/total*circ,  color: '#4f46e5', label: 'Upcoming',  n: upcoming  },
    { len: cancelled/total*circ, color: '#ef4444', label: 'Cancelled', n: cancelled },
  ].filter(s => s.n > 0);

  let offset = 0;
  const circles = segs.map(s => {
    const dashOffset = circ / 4 - offset; // start from top
    const el = `<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${s.color}"
      stroke-width="14" stroke-dasharray="${s.len.toFixed(1)} ${circ.toFixed(1)}"
      stroke-dashoffset="${dashOffset.toFixed(1)}" stroke-linecap="butt"/>`;
    offset += s.len;
    return el;
  }).join('');

  const legendItems = segs.map(s => `
    <div class="sdl-item">
      <div class="sdl-dot" style="background:${s.color}"></div>
      <span class="sdl-label">${s.label}</span>
      <span class="sdl-val">${s.n}</span>
      <span class="sdl-pct">${(s.n/total*100).toFixed(0)}%</span>
    </div>`).join('');

  return `<div class="status-donut-wrap">
    <div class="status-donut-title">Status Breakdown</div>
    <div class="status-donut-body">
      <svg viewBox="0 0 120 120" width="120" height="120" style="flex-shrink:0">
        <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="var(--border)" stroke-width="14"/>
        ${circles}
        <text x="${cx}" y="${cy-4}" text-anchor="middle" fill="var(--text)" font-size="18"
          font-weight="800" font-family="var(--font)">${total}</text>
        <text x="${cx}" y="${cy+10}" text-anchor="middle" fill="var(--text-3)" font-size="9"
          font-family="var(--font)">total</text>
      </svg>
      <div class="status-donut-legend">${legendItems}</div>
    </div>
  </div>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   ATTENDANCE TREND CHART
══════════════════════════════════════════════════════════════════════════ */
function renderAttendanceChart() {
  const data = S.webinars
    .filter(w => w.total_registrations > 0)
    .sort((a, b) => new Date(a.date + 'T00:00:00') - new Date(b.date + 'T00:00:00'))
    .slice(-12);
  if (data.length < 2) return '';

  const W = 700, H = 160;
  const padL = 44, padR = 16, padT = 16, padB = 40;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const xPos  = i => padL + (i / (data.length - 1)) * plotW;
  const yPos  = r => padT + plotH - (r / 100) * plotH;

  const points   = data.map((d, i) => `${xPos(i).toFixed(1)},${yPos(d.attendance_rate || 0).toFixed(1)}`).join(' ');
  const areaPath = [
    `M ${padL} ${padT + plotH}`,
    ...data.map((d, i) => `L ${xPos(i).toFixed(1)} ${yPos(d.attendance_rate || 0).toFixed(1)}`),
    `L ${xPos(data.length - 1).toFixed(1)} ${padT + plotH}`,
    'Z'
  ].join(' ');

  const gridLines = [0, 25, 50, 75, 100].map(v => {
    const y = yPos(v);
    return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}"
      stroke="rgba(79,70,229,0.07)" stroke-width="1" stroke-dasharray="${v === 0 ? '0' : '4,4'}"/>
    <text x="${(padL - 8).toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="end"
      fill="var(--text-3)" font-size="9" font-family="var(--font)">${v}%</text>`;
  }).join('');

  const xLabels = data.map((d, i) => {
    if (data.length > 8 && i % 2 !== 0) return '';
    const label = new Date(d.date + 'T00:00:00').toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
    return `<text x="${xPos(i).toFixed(1)}" y="${(H - 8).toFixed(1)}" text-anchor="middle"
      fill="var(--text-3)" font-size="9" font-family="var(--font)">${label}</text>`;
  }).join('');

  const dots = data.map((d, i) => {
    const x    = xPos(i), y = yPos(d.attendance_rate || 0);
    const info = gradeInfo(d.attendance_rate || 0);
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5"
      fill="${info.color}" stroke="var(--card)" stroke-width="2">
      <title>${esc(d.title)}: ${(d.attendance_rate || 0).toFixed(1)}%</title>
    </circle>`;
  }).join('');

  return `<div class="dash-chart-wrap">
    <div class="dash-chart-head">
      <div class="dash-chart-title">Attendance Rate Trend</div>
      <div class="dash-chart-sub">Last ${data.length} webinar${data.length !== 1 ? 's' : ''} with data · by date</div>
    </div>
    <svg class="dash-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="atCh" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stop-color="var(--accent)" stop-opacity="0.22"/>
          <stop offset="100%" stop-color="var(--accent)" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      ${gridLines}
      <path d="${areaPath}" fill="url(#atCh)"/>
      <polyline points="${points}" fill="none" stroke="var(--accent)" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"/>
      ${xLabels}
      ${dots}
    </svg>
  </div>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   SKELETON LOADER — shown instantly before API data arrives
══════════════════════════════════════════════════════════════════════════ */
function showSkeletonHome() {
  const skelCard = () => `
    <div class="wb-card" style="pointer-events:none">
      <div class="skel" style="height:8px;width:100%;border-radius:0"></div>
      <div style="padding:18px 20px 16px;display:flex;flex-direction:column;gap:10px">
        <div class="skel" style="height:14px;width:68%"></div>
        <div class="skel" style="height:11px;width:45%"></div>
        <div class="skel" style="height:11px;width:55%"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px">
          <div class="skel" style="height:32px"></div>
          <div class="skel" style="height:32px"></div>
        </div>
        <div class="skel" style="height:8px;width:100%;margin-top:4px;border-radius:3px"></div>
      </div>
    </div>`;

  const skelKpi = () => `
    <div class="kpi-item" style="pointer-events:none;gap:8px">
      <div class="skel" style="height:11px;width:80px"></div>
      <div class="skel" style="height:30px;width:60px;margin-top:4px"></div>
      <div class="skel" style="height:11px;width:100px;margin-top:2px"></div>
    </div>`;

  document.getElementById('content').innerHTML = `
    <div>
      <div class="page-hd">
        <div>
          <div class="skel" style="height:22px;width:220px;margin-bottom:8px"></div>
          <div class="skel" style="height:13px;width:160px"></div>
        </div>
      </div>
      <div class="kpi-banner">
        ${Array(4).fill(0).map(skelKpi).join('')}
      </div>
      <div class="wb-grid">
        ${Array(6).fill(0).map(skelCard).join('')}
      </div>
    </div>`;
}

/* ══════════════════════════════════════════════════════════════════════════
   HOME — Webinar Dashboard
══════════════════════════════════════════════════════════════════════════ */
function renderHome() {
  const q  = S.search.toLowerCase();
  let list = S.webinars.filter(w =>
    !q || w.title.toLowerCase().includes(q) || w.speaker_name.toLowerCase().includes(q)
  );
  if (S.filterStatus === 'month') {
    const now = new Date();
    list = list.filter(w => {
      const d = new Date(w.date + 'T00:00:00');
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    });
  } else if (S.filterStatus !== 'all') {
    list = list.filter(w => w.status === S.filterStatus);
  }
  if (S.filterSpeaker !== 'all') list = list.filter(w => w.speaker_id == S.filterSpeaker);

  const speakerOptions = S.speakers.map(sp =>
    `<option value="${sp.id}" ${S.filterSpeaker==sp.id?'selected':''}>${esc(sp.name)}</option>`
  ).join('');

  let mainContent;

  if (S.webinars.length === 0) {
    // Truly empty — first-time user
    mainContent = `<div class="empty-state">
      <div class="empty-icon">🎙️</div>
      <div class="empty-title">No webinars yet</div>
      <div class="empty-sub">Get started by creating your first webinar session. It only takes a few seconds.</div>
      <button class="btn btn-primary" onclick="openWebinarModal()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Create Your First Webinar
      </button>
    </div>`;
  } else {
    // Activity feed
    const feedHTML = buildActivityFeed().map(item => `
      <div class="act-feed-item" onclick="${item.onclick}">
        <div class="act-feed-icon">${item.icon}</div>
        <div class="act-feed-info">
          <div class="act-feed-item-title">${esc(item.title)}</div>
          <div class="act-feed-desc">${esc(item.desc)}</div>
        </div>
        <div class="act-feed-tag">${esc(item.time)}</div>
      </div>`).join('');

    // Table rows for filtered list
    const tableRows = list.map(w => {
      const color    = avColor(w.speaker_name);
      const rate     = w.attendance_rate || 0;
      const info     = gradeInfo(rate);
      const badgeCls = w.status === 'completed' ? 'completed' : w.status === 'upcoming' ? 'upcoming' : 'cancelled';
      const safeT    = esc(w.title).replace(/'/g,"\\'");
      return `<tr onclick="nav('webinar',${w.id})">
        <td><div class="wb-list-name" title="${esc(w.title)}">${esc(w.title)}</div></td>
        <td>
          <div style="display:flex;align-items:center;gap:6px">
            <div style="width:22px;height:22px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#fff;flex-shrink:0">${initials(w.speaker_name)}</div>
            <span style="font-size:12px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:90px">${esc(w.speaker_name)}</span>
          </div>
        </td>
        <td style="font-size:12px;color:var(--text-2);white-space:nowrap">${fmtDate(w.date)}</td>
        <td><span class="wb-badge ${badgeCls}" style="font-size:10.5px;padding:3px 10px">${w.status}</span></td>
        <td style="font-size:12px;text-align:right;color:var(--c-reg);font-weight:600">${fmt(w.total_registrations)}</td>
        <td style="min-width:110px">
          <div style="display:flex;align-items:center;gap:6px">
            <div style="flex:1;height:4px;border-radius:2px;background:var(--border);overflow:hidden">
              <div class="an-bar-fill" style="width:${Math.min(rate,100)}%;background:${info.color}"></div>
            </div>
            <span style="font-size:11px;color:${info.color};font-weight:600;min-width:38px">${rate > 0 ? fmtPct(rate) : '—'}</span>
          </div>
        </td>
        <td>
          <button class="wb-card-del" style="width:26px;height:26px" title="Delete"
            onclick="event.stopPropagation();confirmDeleteWebinar(${w.id},'${safeT}')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            </svg>
          </button>
        </td>
      </tr>`;
    }).join('');

    const countLabel = list.length !== S.webinars.length
      ? `${list.length} of ${S.webinars.length}`
      : `${list.length}`;

    mainContent = `
      <div class="dash-bottom-row">
        <!-- Left: Webinar table -->
        <div class="wb-list-card">
          <div class="wb-list-card-head">
            <div class="wb-list-card-title">All Webinars <span style="font-size:12px;color:var(--text-3);font-weight:400">${countLabel}</span></div>
            <input class="wb-list-search" placeholder="Search webinars…" oninput="onSearch(this.value)" value="${esc(S.search)}" />
            <select class="filter-select" style="font-size:12px;padding:5px 8px;min-width:0" onchange="setFilter('speaker',this.value)">
              <option value="all">All Speakers</option>
              ${speakerOptions}
            </select>
          </div>
          ${list.length ? `
          <table class="wb-list-table">
            <thead>
              <tr>
                <th>Webinar</th>
                <th>Speaker</th>
                <th>Date</th>
                <th>Status</th>
                <th style="text-align:right">Reg.</th>
                <th>Attendance</th>
                <th></th>
              </tr>
            </thead>
            <tbody>${tableRows}</tbody>
          </table>` : `
          <div style="padding:32px;text-align:center;color:var(--text-3);font-size:13px">
            No webinars match your current filters.
            <div style="margin-top:10px">
              <button class="btn btn-ghost btn-sm" onclick="S.search='';onSearch('');setChipFilter('all');setFilter('speaker','all')">Clear filters</button>
            </div>
          </div>`}
        </div>
        <!-- Right: Activity feed -->
        <div class="act-feed-card">
          <div class="act-feed-head">
            <span class="act-feed-title">Activity</span>
          </div>
          <div class="act-feed-body">${feedHTML}</div>
        </div>
      </div>`;
  }

  const hour = new Date().getHours();
  const timeMsg = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  setContent(`
    <div>
      <div class="dash-hero reveal">
        <div>
          <h1 class="dash-hero-title">${timeMsg} 👋<br>Webinar Intelligence</h1>
          <p class="dash-hero-sub">Track performance, speaker impact, and audience engagement across every webinar — all in one place.</p>
        </div>
        <div class="dash-hero-actions">
          <button class="btn btn-primary" onclick="openWebinarModal()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New Webinar
          </button>
        </div>
      </div>
      <div class="kpi-banner reveal rd1">${renderKpiBanner()}</div>
      <div class="dash-mid-row reveal rd2">
        ${renderAttendanceChart()}
        ${renderStatusBreakdown()}
      </div>
      <div class="reveal rd3">${mainContent}</div>
    </div>
  `);

  updateTopbarChips('home');
}

function setFilter(type, value) {
  if (type === 'status')  { S.filterStatus  = value; updateTopbarChips('home'); }
  if (type === 'speaker') S.filterSpeaker = value;
  renderHome();
}

/* ── Webinar card ───────────────────────────────────────────────────────── */
function webinarCardHTML(w) {
  const color    = avColor(w.speaker_name);
  const ini      = initials(w.speaker_name);
  const rate     = w.attendance_rate || 0;
  const info     = gradeInfo(rate);
  const badgeCls = w.status === 'completed' ? 'completed' : w.status === 'upcoming' ? 'upcoming' : w.status === 'cancelled' ? 'cancelled' : 'incomplete';
  const bothDone = w.has_registration_data && w.has_attendee_data;

  return `
    <div class="wb-card" onclick="nav('webinar',${w.id})">
      <div class="wb-card-top" style="background:linear-gradient(90deg,${color},${color}88)"></div>
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
            <div class="wb-card-stat-val" style="color:var(--c-reg)">${fmt(w.total_registrations)}</div>
            <div class="wb-card-stat-lbl">Registered</div>
          </div>
          <div class="wb-card-stat">
            <div class="wb-card-stat-val" style="color:var(--c-att)">${fmt(w.total_attendees)}</div>
            <div class="wb-card-stat-lbl">Attended</div>
          </div>
        </div>
      </div>
      <!-- Health score row -->
      <div class="wb-card-health">
        ${donutRing(rate, 44)}
        <div class="wb-health-info">
          <div class="wb-health-label">Health Score</div>
          <div class="wb-health-rate">${rate > 0 ? fmtPct(rate) : 'No data'}</div>
        </div>
        <div class="grade-badge grade-${info.grade === '—' ? 'none' : info.grade}">${info.grade}</div>
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
  const badgeCls = w.status === 'completed' ? 'completed' : w.status === 'upcoming' ? 'upcoming' : w.status === 'cancelled' ? 'cancelled' : 'incomplete';

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
  const regDlAttr = w.total_registrations > 0
    ? `onclick="downloadRegistrations(${w.id})" title="Click to download registrations CSV" style="cursor:pointer"`
    : '';
  const attDlAttr = w.total_attendees > 0
    ? `onclick="downloadAttendees(${w.id})" title="Click to download attendees CSV" style="cursor:pointer"`
    : '';
  const analysisHTML = `
    <div class="analysis-grid">
      <div class="an-stat-card an-stat-dl" ${regDlAttr}>
        <div class="an-stat-icon" style="background:rgba(59,130,246,0.15)">📝</div>
        <div style="flex:1">
          <div class="an-stat-val" style="color:var(--c-reg)">${fmt(w.total_registrations)}</div>
          <div class="an-stat-lbl">Registered
            ${w.total_registrations > 0 ? `<span class="dl-hint">↓ CSV</span>` : ''}
          </div>
        </div>
      </div>
      <div class="an-stat-card an-stat-dl" ${attDlAttr}>
        <div class="an-stat-icon" style="background:rgba(16,185,129,0.15)">✅</div>
        <div style="flex:1">
          <div class="an-stat-val" style="color:var(--c-att)">${fmt(w.total_attendees)}</div>
          <div class="an-stat-lbl">Attended
            ${w.total_attendees > 0 ? `<span class="dl-hint" style="background:rgba(16,185,129,.15);color:#059669">↓ CSV</span>` : ''}
          </div>
        </div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(244,63,94,0.15)">❌</div>
        <div><div class="an-stat-val" style="color:var(--c-nosh)">${fmt(noShow)}</div><div class="an-stat-lbl">No-shows</div></div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(139,92,246,0.15)">📊</div>
        <div><div class="an-stat-val" style="color:${rateClr}">${rate}%</div><div class="an-stat-lbl">Attendance Rate</div></div>
      </div>
      ${w.duplicates_removed > 0 ? `
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(245,158,11,0.15)">🔄</div>
        <div><div class="an-stat-val" style="color:var(--gold)">${fmt(w.duplicates_removed)}</div><div class="an-stat-lbl">Duplicates Removed</div></div>
      </div>` : ''}
      ${w.unmatched_attendees > 0 ? `
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(245,158,11,0.10)">⚠️</div>
        <div><div class="an-stat-val" style="color:var(--amber)">${fmt(w.unmatched_attendees)}</div><div class="an-stat-lbl">Walk-ins (not registered)</div></div>
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

      <!-- Ad Creatives section -->
      <div class="ads-section">
        <div class="sec-hd" style="margin-bottom:16px">
          <span class="sec-title">Ad Creatives</span>
          <span style="font-size:12px;color:var(--text-3)">${(w.ads||[]).length} ad${(w.ads||[]).length !== 1 ? 's' : ''}</span>
          <button class="btn btn-primary btn-sm" style="margin-left:auto" onclick="openAdModal(${w.id})">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add Ad
          </button>
        </div>
        ${renderAdCards(w.id, w.ads || [])}
      </div>
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

/* ── Twin line chart: registrations vs attendees ────────────────────────── */
function renderTwinLineChart(data) {
  if (!data || data.length < 2) return '';
  const W = 560, H = 180;
  const padL = 50, padR = 16, padT = 18, padB = 44;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const maxVal = Math.max(...data.map(d => Math.max(d.total_registrations||0, d.total_attendees||0)), 1);
  const xPos = i => padL + (i / (data.length - 1)) * plotW;
  const yPos = v => padT + plotH - (v / maxVal) * plotH;

  const regPts = data.map((d,i) => `${xPos(i).toFixed(1)},${yPos(d.total_registrations||0).toFixed(1)}`).join(' ');
  const attPts = data.map((d,i) => `${xPos(i).toFixed(1)},${yPos(d.total_attendees||0).toFixed(1)}`).join(' ');
  const regArea = [`M ${padL} ${padT+plotH}`, ...data.map((d,i) => `L ${xPos(i).toFixed(1)} ${yPos(d.total_registrations||0).toFixed(1)}`), `L ${xPos(data.length-1).toFixed(1)} ${padT+plotH} Z`].join(' ');
  const attArea = [`M ${padL} ${padT+plotH}`, ...data.map((d,i) => `L ${xPos(i).toFixed(1)} ${yPos(d.total_attendees||0).toFixed(1)}`), `L ${xPos(data.length-1).toFixed(1)} ${padT+plotH} Z`].join(' ');

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
    const v = maxVal * f, y = yPos(v);
    const label = v >= 1000 ? `${(v/1000).toFixed(0)}k` : Math.round(v).toString();
    return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W-padR}" y2="${y.toFixed(1)}" stroke="rgba(79,70,229,0.07)" stroke-width="1" stroke-dasharray="4,4"/>
      <text x="${(padL-6).toFixed(1)}" y="${(y+4).toFixed(1)}" text-anchor="end" fill="var(--text-3)" font-size="9" font-family="var(--font)">${label}</text>`;
  }).join('');
  const xLabels = data.map((d,i) => {
    if (data.length > 7 && i % 2 !== 0) return '';
    const lbl = new Date(d.date+'T00:00:00').toLocaleDateString('en-IN', { month:'short', day:'numeric' });
    return `<text x="${xPos(i).toFixed(1)}" y="${(H-6).toFixed(1)}" text-anchor="middle" fill="var(--text-3)" font-size="9" font-family="var(--font)">${lbl}</text>`;
  }).join('');

  return `<div class="an-trend-card">
    <div class="an-card-head">Registrations vs Attendees
      <span class="an-chart-legend">
        <span><span class="an-leg-dot" style="background:#4f46e5"></span>Reg</span>
        <span><span class="an-leg-dot" style="background:#10b981"></span>Att</span>
      </span>
    </div>
    <svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="twinRG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#4f46e5" stop-opacity="0.18"/>
          <stop offset="100%" stop-color="#4f46e5" stop-opacity="0.02"/>
        </linearGradient>
        <linearGradient id="twinAG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#10b981" stop-opacity="0.18"/>
          <stop offset="100%" stop-color="#10b981" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      ${gridLines}
      <path d="${regArea}" fill="url(#twinRG)"/>
      <path d="${attArea}" fill="url(#twinAG)"/>
      <polyline points="${regPts}" fill="none" stroke="#4f46e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <polyline points="${attPts}" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      ${xLabels}
    </svg>
  </div>`;
}

/* ── Monthly volume bar chart ───────────────────────────────────────────── */
function renderMonthlyBars(months) {
  if (!months.length) return '';
  const maxVal = Math.max(...months.map(m => Math.max(m.reg, m.att)), 1);
  const BAR_H  = 110;
  const bars = months.map(m => {
    const rH = Math.max(2, Math.round(m.reg / maxVal * BAR_H));
    const aH = Math.max(2, Math.round(m.att / maxVal * BAR_H));
    return `<div class="an-month-col">
      <div class="an-month-bars">
        <div class="an-month-bar" style="height:${rH}px;background:#4f46e5" title="Reg: ${fmt(m.reg)}"></div>
        <div class="an-month-bar" style="height:${aH}px;background:#10b981" title="Att: ${fmt(m.att)}"></div>
      </div>
      <div class="an-month-label">${m.label}</div>
    </div>`;
  }).join('');
  return `<div class="an-monthly-card">
    <div class="an-card-head">Monthly Volume
      <span class="an-chart-legend">
        <span><span class="an-leg-dot" style="background:#4f46e5"></span>Reg</span>
        <span><span class="an-leg-dot" style="background:#10b981"></span>Att</span>
      </span>
    </div>
    <div class="an-month-chart">${bars}</div>
  </div>`;
}

/* ── Engagement funnel ──────────────────────────────────────────────────── */
function renderEngagementFunnel(totalReg, totalAtt, noShow) {
  if (!totalReg) return `<div class="empty-state" style="padding:24px 0;border:none">
    <div class="empty-icon" style="font-size:24px">📊</div>
    <div class="empty-title" style="font-size:13px">No data yet</div>
  </div>`;
  const attPct    = (totalAtt / totalReg * 100).toFixed(1);
  const noShowPct = (Math.max(0, noShow) / totalReg * 100).toFixed(1);
  return `
    <div class="funnel-step" style="--fw:100%;--fc:#4f46e5">
      <div class="funnel-bar"></div>
      <div class="funnel-info">
        <span class="funnel-label">📝 Registered</span>
        <span class="funnel-val">${fmt(totalReg)}</span>
        <span class="funnel-pct">100%</span>
      </div>
    </div>
    <div class="funnel-step" style="--fw:${attPct}%;--fc:#10b981">
      <div class="funnel-bar"></div>
      <div class="funnel-info">
        <span class="funnel-label">✅ Attended</span>
        <span class="funnel-val">${fmt(totalAtt)}</span>
        <span class="funnel-pct">${attPct}%</span>
      </div>
    </div>
    <div class="funnel-step" style="--fw:${noShowPct}%;--fc:#ef4444">
      <div class="funnel-bar"></div>
      <div class="funnel-info">
        <span class="funnel-label">❌ No-show</span>
        <span class="funnel-val">${fmt(Math.max(0, noShow))}</span>
        <span class="funnel-pct">${noShowPct}%</span>
      </div>
    </div>`;
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

  // Trend data — last 12 webinars with any registration/attendance data
  const trendData = [...S.webinars]
    .filter(w => w.total_registrations > 0 || w.total_attendees > 0)
    .sort((a,b) => new Date(a.date+'T00:00:00') - new Date(b.date+'T00:00:00'))
    .slice(-12);

  // Monthly aggregates
  const monthMap = {};
  S.webinars.forEach(w => {
    if (!w.date) return;
    const d = new Date(w.date+'T00:00:00');
    const key   = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
    const label = d.toLocaleDateString('en-IN', { month:'short', year:'2-digit' });
    if (!monthMap[key]) monthMap[key] = { key, label, reg:0, att:0, count:0 };
    monthMap[key].reg   += w.total_registrations || 0;
    monthMap[key].att   += w.total_attendees || 0;
    monthMap[key].count += 1;
  });
  const months = Object.values(monthMap).sort((a,b) => a.key.localeCompare(b.key)).slice(-8);

  // Speaker performance
  const spkStats = S.speakers.map(sp => {
    const wbs  = S.webinars.filter(w => w.speaker_id === sp.id);
    const done = wbs.filter(w => w.status==='completed' && w.attendance_rate > 0);
    const avgR = done.length ? done.reduce((s,w) => s+w.attendance_rate, 0)/done.length : 0;
    return { ...sp, avgR, done:done.length, info:gradeInfo(avgR), color:avColor(sp.name) };
  }).sort((a,b) => b.avgR - a.avgR);
  const maxSpkR = Math.max(...spkStats.map(s => s.avgR), 1);

  // Top lists
  const top10reg = [...S.webinars].sort((a,b) => b.total_registrations - a.total_registrations).slice(0,10);
  const top10att = [...S.webinars].filter(w => w.status==='completed' && w.attendance_rate > 0)
    .sort((a,b) => b.attendance_rate - a.attendance_rate).slice(0,10);
  const maxReg = top10reg[0]?.total_registrations || 1;

  // Funnel
  const totalReg = st.total_registrations;
  const totalAtt = st.total_attendees;
  const noShow   = Math.max(0, totalReg - totalAtt);

  setContent(`
    <div>
      <div class="page-hd">
        <div>
          <h1 class="page-title">Analytics</h1>
          <p class="page-sub">Platform-wide performance · ${S.webinars.length} webinars</p>
        </div>
        ${st.total_attendees > 0 ? `
        <button class="btn btn-ghost btn-sm" onclick="downloadAllAttendees()" style="display:flex;align-items:center;gap:6px;flex-shrink:0">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download Attendees
        </button>` : ''}
      </div>

      <!-- KPI strip — 6 metrics -->
      <div class="an-kpi-strip">
        <div class="an-kpi-card">
          <div class="an-kpi-icon">🎙️</div>
          <div class="an-kpi-val" data-countup="${st.total_webinars}">${st.total_webinars}</div>
          <div class="an-kpi-label">Total Webinars</div>
        </div>
        <div class="an-kpi-card">
          <div class="an-kpi-icon">🎤</div>
          <div class="an-kpi-val" data-countup="${st.total_speakers}">${st.total_speakers}</div>
          <div class="an-kpi-label">Speakers</div>
        </div>
        <div class="an-kpi-card">
          <div class="an-kpi-icon">📝</div>
          <div class="an-kpi-val" data-countup="${st.total_registrations}">${fmt(st.total_registrations)}</div>
          <div class="an-kpi-label">Total Registrations</div>
        </div>
        <div class="an-kpi-card an-kpi-card-dl" ${st.total_attendees > 0 ? `onclick="downloadAllAttendees()" title="Download all attendees as CSV"` : ''}>
          <div class="an-kpi-icon">✅</div>
          <div class="an-kpi-val" data-countup="${st.total_attendees}">${fmt(st.total_attendees)}</div>
          <div class="an-kpi-label">Total Attendees${st.total_attendees > 0 ? ` <span class="dl-hint" style="background:rgba(16,185,129,.15);color:#059669">↓ CSV</span>` : ''}</div>
        </div>
        <div class="an-kpi-card">
          <div class="an-kpi-icon">📅</div>
          <div class="an-kpi-val" data-countup="${st.upcoming_webinars}" style="color:var(--gold)">${st.upcoming_webinars}</div>
          <div class="an-kpi-label">Upcoming</div>
        </div>
        <div class="an-kpi-card">
          <div class="an-kpi-icon">📊</div>
          <div class="an-kpi-val" data-countup="${st.overall_attendance_rate}" style="color:var(--accent)">${st.overall_attendance_rate}</div>
          <div class="an-kpi-label">Avg. Attendance %</div>
        </div>
      </div>

      <!-- Charts: twin line + monthly bars -->
      ${trendData.length >= 2 || months.length >= 2 ? `
      <div class="an-charts-row">
        ${renderTwinLineChart(trendData)}
        ${renderMonthlyBars(months)}
      </div>` : ''}

      <!-- Funnel + Speaker performance -->
      <div class="an-mid-row">
        <div class="an-funnel-card">
          <div class="an-card-head">Engagement Funnel</div>
          ${renderEngagementFunnel(totalReg, totalAtt, noShow)}
        </div>
        <div class="an-spk-card">
          <div class="an-card-head">Speaker Performance</div>
          ${spkStats.length ? spkStats.map(sp => `
            <div class="an-spk-row">
              <div class="an-spk-av" style="background:${sp.color}">${initials(sp.name)}</div>
              <div class="an-spk-info">
                <div class="an-spk-name">${esc(sp.name)} <span style="font-size:10.5px;color:var(--text-3);font-weight:400">${sp.total_webinars} webinar${sp.total_webinars!==1?'s':''}</span></div>
                <div class="an-spk-bar-wrap">
                  <div class="an-spk-bar-fill" style="width:${sp.avgR > 0 ? (sp.avgR/maxSpkR*100).toFixed(1) : 0}%;background:${sp.color}"></div>
                </div>
              </div>
              <div class="an-spk-grade grade-${sp.info.grade === '—' ? 'none' : sp.info.grade}">${sp.info.grade}</div>
              <div class="an-spk-rate">${sp.avgR > 0 ? fmtPct(sp.avgR) : '—'}</div>
            </div>`).join('') : `
          <div class="empty-state" style="padding:24px 0;border:none">
            <div class="empty-icon" style="font-size:24px">🎤</div>
            <div class="empty-title" style="font-size:13px">No speaker data yet</div>
          </div>`}
        </div>
      </div>

      <!-- Top 10 lists -->
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
          ${top10att.length ? top10att.map(w => `
            <div class="an-row">
              <span class="an-row-lbl" title="${esc(w.title)}">${esc(w.title)}</span>
              <div class="an-bar-wrap"><div class="an-bar-fill" style="width:${Math.min(w.attendance_rate,100)}%;background:#22c55e"></div></div>
              <span class="an-row-val">${fmtPct(w.attendance_rate)}</span>
            </div>`).join('') : '<div style="color:var(--text-3);font-size:12px;padding:8px 0">No completed webinars with attendance data yet.</div>'}
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
            ${lb.map(e => {
              // Use single-quoted strings in onclick to avoid breaking the HTML attribute
              const safeEmail = (e.email||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");
              const safeName  = (e.name ||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");
              const nameCell = e.email
                ? `<span class="lb-name-link" onclick="openAttendeeModal('${safeEmail}','${safeName}')" title="Click to view attended webinars">${esc(e.name)}</span>`
                : `<span class="lb-name-link no-email" title="No email — cannot look up profile">${esc(e.name)}</span>`;
              return `
              <tr>
                <td>${rankHTML(e.rank)}</td>
                <td>${nameCell}</td>
                <td><div class="lb-email">${esc(e.email||'—')}</div></td>
                <td><div class="lb-email">${esc(e.phone||'—')}</div></td>
                <td style="text-align:center;font-weight:600;color:#059669">${e.webinars_attended}</td>
                <td style="text-align:center;color:var(--text-2)">${e.total_duration_minutes}</td>
                <td><span class="lb-score">⭐ ${e.score}</span></td>
              </tr>`;
            }).join('')}
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
  // Reset status pills to "upcoming"
  const upcomingRadio = document.querySelector('input[name="nw-status-radio"][value="upcoming"]');
  if (upcomingRadio) upcomingRadio.checked = true;
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
    status: (document.querySelector('input[name="nw-status-radio"]:checked') || {value:'upcoming'}).value,
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

/* ══════════════════════════════════════════════════════════════════════════
   AD CREATIVE MODAL
══════════════════════════════════════════════════════════════════════════ */

function openAdModal(webinarId) {
  _adWebinarId   = webinarId;
  _adImageBase64 = null;

  // Reset all form fields
  ['ad-title','ad-headline','ad-cta','ad-description',
   'ad-landing-url','ad-budget','ad-spend','ad-notes','ad-creative-url'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  ['ad-impressions','ad-clicks','ad-conversions'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  ['ad-start-date','ad-end-date'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const platformEl = document.getElementById('ad-platform');
  const typeEl     = document.getElementById('ad-type');
  const statusEl   = document.getElementById('ad-status');
  if (platformEl) platformEl.value = '';
  if (typeEl)     typeEl.value     = '';
  if (statusEl)   statusEl.value   = 'active';

  clearAdImage();

  document.getElementById('ad-modal-overlay').classList.add('open');
  setTimeout(() => { const t = document.getElementById('ad-title'); if (t) t.focus(); }, 80);
}

function closeAdModal() {
  const overlay = document.getElementById('ad-modal-overlay');
  if (overlay) overlay.classList.remove('open');
  _adWebinarId   = null;
  _adImageBase64 = null;
}

function handleAdImageSelect(event) {
  const file = event.target.files[0];
  event.target.value = '';
  if (!file) return;
  _loadAdImageFile(file);
}

function handleAdImageDrop(event) {
  event.preventDefault();
  event.currentTarget.classList.remove('dragover');
  const file = event.dataTransfer.files[0];
  if (!file || !file.type.startsWith('image/')) return;
  _loadAdImageFile(file);
}

function _loadAdImageFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    _adImageBase64 = e.target.result;
    const preview = document.getElementById('ad-creative-preview');
    const holder  = document.getElementById('ad-creative-placeholder');
    const clearBtn = document.getElementById('ad-creative-clear');
    if (preview)  { preview.src = _adImageBase64; preview.style.display = 'block'; }
    if (holder)   holder.style.display   = 'none';
    if (clearBtn) clearBtn.style.display = 'block';
  };
  reader.readAsDataURL(file);
}

function clearAdImage() {
  _adImageBase64 = null;
  const preview  = document.getElementById('ad-creative-preview');
  const holder   = document.getElementById('ad-creative-placeholder');
  const clearBtn = document.getElementById('ad-creative-clear');
  if (preview)  { preview.src = ''; preview.style.display = 'none'; }
  if (holder)   holder.style.display   = 'flex';
  if (clearBtn) clearBtn.style.display = 'none';
}

async function submitAdModal() {
  const title = (document.getElementById('ad-title').value || '').trim();
  if (!title) {
    document.getElementById('ad-title').focus();
    showToast('Please enter an ad title', 'error');
    return;
  }

  const btn = document.getElementById('ad-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

  const parseIntOrNull = id => {
    const v = parseInt(document.getElementById(id)?.value, 10);
    return isNaN(v) ? null : v;
  };
  const strOrNull = id => document.getElementById(id)?.value.trim() || null;

  const payload = {
    title,
    platform:       strOrNull('ad-platform'),
    ad_type:        strOrNull('ad-type'),
    creative_image: _adImageBase64 || null,
    creative_url:   strOrNull('ad-creative-url'),
    headline:       strOrNull('ad-headline'),
    description:    strOrNull('ad-description'),
    cta_text:       strOrNull('ad-cta'),
    landing_url:    strOrNull('ad-landing-url'),
    budget:         strOrNull('ad-budget'),
    spend:          strOrNull('ad-spend'),
    impressions:    parseIntOrNull('ad-impressions'),
    clicks:         parseIntOrNull('ad-clicks'),
    conversions:    parseIntOrNull('ad-conversions'),
    start_date:     strOrNull('ad-start-date'),
    end_date:       strOrNull('ad-end-date'),
    status:         document.getElementById('ad-status')?.value || 'active',
    notes:          strOrNull('ad-notes'),
  };

  const wid = _adWebinarId;
  try {
    await api(`/api/webinars/${wid}/ads`, 'POST', payload);
    closeAdModal();
    showToast('Ad creative saved!');
    // Reload detail
    const fresh = await api(`/api/webinars/${wid}`);
    detailCache[wid] = fresh;
    _drawWebinarDetail(fresh);
  } catch(e) {
    showToast('Failed to save ad — please try again.', 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Save Ad';
    }
  }
}

/* ── Download registrations / attendees as CSV ──────────────────────────── */
function _triggerDownload(url) {
  showToast('Preparing download…');
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function downloadRegistrations(webinarId) {
  _triggerDownload(`/api/webinars/${webinarId}/registrations/download`);
}

function downloadAttendees(webinarId) {
  _triggerDownload(`/api/webinars/${webinarId}/attendees/download`);
}

function downloadAllAttendees() {
  _triggerDownload('/api/attendees/download');
}

async function deleteAdConfirm(adId, webinarId) {
  if (!confirm('Delete this ad creative? This cannot be undone.')) return;
  try {
    await api(`/api/webinars/${webinarId}/ads/${adId}`, 'DELETE');
    showToast('Ad deleted');
    const fresh = await api(`/api/webinars/${webinarId}`);
    detailCache[webinarId] = fresh;
    _drawWebinarDetail(fresh);
  } catch(e) {
    showToast('Failed to delete ad', 'error');
  }
}

function renderAdCards(webinarId, ads) {
  if (!ads || !ads.length) {
    return `<div class="ads-empty">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><polyline points="9.5 9 11 10.5 14.5 7.5"/></svg>
      <div>No ad creatives yet — click <strong>Add Ad</strong> to attach one to this webinar</div>
    </div>`;
  }

  return `<div class="ads-grid">${ads.map(ad => {
    const platform = ad.platform || '';
    // normalize platform to a CSS class key
    const platCls = platform.toLowerCase()
      .replace(/[^a-z]/g, '')
      .replace('googleads', 'google')
      .replace('twitterx', 'twitter') || 'other';
    const platLabel = platform || 'Other';

    const imgSrc = ad.creative_image || ad.creative_url;
    const imageHTML = imgSrc
      ? `<div class="ad-card-image"><img src="${imgSrc}" alt="${esc(ad.title)}" onerror="this.parentNode.innerHTML='<span class=ad-card-image-placeholder>Image unavailable</span>'" /></div>`
      : `<div class="ad-card-image"><span class="ad-card-image-placeholder">No creative image</span></div>`;

    const hasMets = ad.impressions != null || ad.clicks != null || ad.conversions != null;
    const metsHTML = hasMets ? `
      <div class="ad-card-metrics">
        <div class="ad-metric">
          <div class="ad-metric-val">${ad.impressions != null ? fmt(ad.impressions) : '—'}</div>
          <div class="ad-metric-label">Impressions</div>
        </div>
        <div class="ad-metric">
          <div class="ad-metric-val">${ad.clicks != null ? fmt(ad.clicks) : '—'}</div>
          <div class="ad-metric-label">Clicks</div>
        </div>
        <div class="ad-metric">
          <div class="ad-metric-val">${ad.conversions != null ? fmt(ad.conversions) : '—'}</div>
          <div class="ad-metric-label">Conv.</div>
        </div>
      </div>` : '';

    const budgetLine = [
      ad.budget ? `Budget: ${esc(ad.budget)}` : '',
      ad.spend  ? `Spend: ${esc(ad.spend)}`   : '',
    ].filter(Boolean).join(' · ');

    const ctrLine = (() => {
      if (ad.clicks != null && ad.impressions != null && ad.impressions > 0) {
        const ctr = (ad.clicks / ad.impressions * 100).toFixed(2);
        return `CTR: ${ctr}%`;
      }
      return '';
    })();

    const dateRange = ad.start_date || ad.end_date
      ? [ad.start_date ? fmtDate(ad.start_date) : '', ad.end_date ? fmtDate(ad.end_date) : ''].filter(Boolean).join(' – ')
      : '';

    return `
      <div class="ad-card">
        ${imageHTML}
        <div class="ad-card-body">
          <div class="ad-card-head-row">
            <div class="ad-card-title">${esc(ad.title)}</div>
            <span class="ad-platform-badge ${platCls}">${esc(platLabel)}</span>
          </div>
          ${ad.headline ? `<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:3px">${esc(ad.headline)}</div>` : ''}
          ${ad.description ? `<div class="ad-card-desc">${esc(ad.description)}</div>` : ''}
          ${ad.cta_text ? `<div style="display:inline-flex;align-items:center;background:var(--accent);color:#fff;font-size:10.5px;font-weight:700;padding:3px 11px;border-radius:20px;margin-bottom:6px">${esc(ad.cta_text)}</div>` : ''}
          ${metsHTML}
          ${ctrLine ? `<div style="font-size:11px;color:var(--text-3);margin-top:6px">${ctrLine}</div>` : ''}
          ${budgetLine ? `<div style="font-size:11px;color:var(--text-3)">${budgetLine}</div>` : ''}
          ${dateRange ? `<div style="font-size:11px;color:var(--text-3)">${dateRange}</div>` : ''}
          ${ad.landing_url ? `<a href="${esc(ad.landing_url)}" target="_blank" rel="noopener" style="font-size:11px;color:var(--accent);text-decoration:none;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(ad.landing_url)}">🔗 ${esc(ad.landing_url)}</a>` : ''}
          ${ad.notes ? `<div style="font-size:11.5px;color:var(--text-2);border-top:1px solid var(--border);padding-top:6px;margin-top:4px;line-height:1.4">${esc(ad.notes)}</div>` : ''}
        </div>
        <div class="ad-card-foot">
          <div style="display:flex;align-items:center;gap:2px">
            <span class="ad-status-dot ${esc(ad.status||'active')}"></span>
            <span class="ad-status-text">${esc(ad.status || 'active')}</span>
            ${ad.ad_type ? `<span style="margin-left:8px;font-size:11px;color:var(--text-3)">${esc(ad.ad_type)}</span>` : ''}
          </div>
          <button class="ad-delete-btn" onclick="event.stopPropagation();deleteAdConfirm(${ad.id},${webinarId})" title="Delete ad">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            </svg>
          </button>
        </div>
      </div>`;
  }).join('')}</div>`;
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

/* ── Toast ──────────────────────────────────────────────────────────────── */
function showToast(msg, type='success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast show${type==='error'?' error':''}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 3000);
}

/* ══════════════════════════════════════════════════════════════════════════
   ATTENDEE PROFILE DRAWER
══════════════════════════════════════════════════════════════════════════ */
async function openAttendeeModal(email, name) {
  // Show the drawer immediately with a loading state
  const overlay = document.getElementById('att-overlay');
  const avEl    = document.getElementById('att-av');
  const nameEl  = document.getElementById('att-name');
  const metaEl  = document.getElementById('att-meta');
  const statsEl = document.getElementById('att-stats');
  const bodyEl  = document.getElementById('att-body');

  const color = avColor(name);
  avEl.style.background  = color;
  avEl.textContent       = initials(name);
  nameEl.textContent     = name;
  metaEl.textContent     = email;
  statsEl.innerHTML      = '';
  bodyEl.innerHTML       = '<div class="pg-loading"><div class="spinner"></div><p>Loading…</p></div>';

  overlay.classList.add('open');

  try {
    const profile = await api('/api/attendee?email=' + encodeURIComponent(email));

    // Stats bar
    statsEl.innerHTML = `
      <div class="att-stat-item">
        <div class="att-stat-val" style="color:#059669">${profile.webinars_attended}</div>
        <div class="att-stat-lbl">Webinars</div>
      </div>
      <div class="att-stat-item">
        <div class="att-stat-val" style="color:#6366f1">${profile.total_duration_minutes}</div>
        <div class="att-stat-lbl">Total Min</div>
      </div>
      <div class="att-stat-item">
        <div class="att-stat-val" style="color:#d97706">⭐ ${profile.score}</div>
        <div class="att-stat-lbl">Score</div>
      </div>`;

    if (profile.phone) metaEl.textContent = `${email}  ·  ${profile.phone}`;

    // Webinar cards — max duration used for the bar scale
    const maxDur = Math.max(...profile.webinars.map(w => w.duration_minutes || 0), 1);

    const cards = profile.webinars.map(w => {
      const dur     = w.duration_minutes || 0;
      const barPct  = Math.round(dur / maxDur * 100);
      const durTxt  = dur ? `${dur} min` : 'Duration not recorded';
      const wbTitle = esc(w.title);
      const wbDate  = fmtDate(w.date);
      const spkName = esc(w.speaker_name);
      return `
        <div class="att-wb-card" onclick="closeAttendeeModal();nav('webinar',${w.webinar_id})" title="Open webinar">
          <div class="att-wb-card-title">${wbTitle}</div>
          <div class="att-wb-card-meta">
            <span>${wbDate}</span>
            <span class="att-wb-card-meta-dot"></span>
            <span>${spkName}</span>
          </div>
          ${dur ? `
          <div class="att-wb-dur">
            <div class="att-wb-dur-bar"><div class="att-wb-dur-fill" style="width:${barPct}%"></div></div>
            <span class="att-wb-dur-label">${durTxt}</span>
          </div>` : `<div style="font-size:12px;color:var(--text-3)">${durTxt}</div>`}
        </div>`;
    }).join('');

    bodyEl.innerHTML = `
      <div class="att-drawer-body-title">Webinars Attended (${profile.webinars_attended})</div>
      ${cards || '<div style="color:var(--text-3);font-size:13px">No attended webinars found.</div>'}`;
  } catch(e) {
    bodyEl.innerHTML = '<div style="color:#dc2626;font-size:13px;padding:12px 0">Could not load attendee data.</div>';
  }
}

function closeAttendeeModal() {
  document.getElementById('att-overlay').classList.remove('open');
}

/* ══════════════════════════════════════════════════════════════════════════
   ANIMATIONS
══════════════════════════════════════════════════════════════════════════ */

/** Count-up animation for a numeric element */
function countUp(el, target, duration = 900) {
  const start    = performance.now();
  const from     = 0;
  const isFloat  = String(target).includes('.');
  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = from + (target - from) * eased;
    el.textContent = isFloat ? value.toFixed(1) : Math.round(value).toLocaleString('en-IN');
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = isFloat ? target.toFixed(1) : Number(target).toLocaleString('en-IN');
  }
  requestAnimationFrame(step);
}

/** Run count-up on every element with data-countup attribute */
function runCountUps() {
  document.querySelectorAll('[data-countup]').forEach(el => {
    const val = parseFloat(el.dataset.countup);
    if (!isNaN(val)) countUp(el, val);
  });
}

/** Fade-in + translateY entrance for a list of cards with stagger */
function animateCards(selector = '.wb-card, .spk-card') {
  const cards = document.querySelectorAll(selector);
  cards.forEach((card, i) => {
    card.style.opacity    = '0';
    card.style.transform  = 'translateY(20px)';
    card.style.transition = 'none';
    requestAnimationFrame(() => {
      setTimeout(() => {
        card.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
        card.style.opacity    = '';
        card.style.transform  = '';
      }, i * 45);
    });
  });
}

/** Add rank-N class to lb-table rows so CSS can style top-3 rows */
function decorateLeaderboardRows() {
  const rows = document.querySelectorAll('.lb-table tbody tr');
  rows.forEach((row, i) => {
    row.classList.remove('rank-1','rank-2','rank-3');
    if (i === 0) row.classList.add('rank-1');
    else if (i === 1) row.classList.add('rank-2');
    else if (i === 2) row.classList.add('rank-3');
  });
}

/** Animate progress bars from 0 to their target width */
function animateBars() {
  document.querySelectorAll('.dur-fill, .an-bar-fill, .src-fill, .att-wb-dur-fill').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0%';
    requestAnimationFrame(() => {
      setTimeout(() => { bar.style.width = target; }, 80);
    });
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   BREADCRUMB
══════════════════════════════════════════════════════════════════════════ */
function setBreadcrumb(page, sub) {
  const bc = document.getElementById('tb-breadcrumb');
  if (!bc) return;
  const pageTitles = { home:'Dashboard', analytics:'Analytics', speakers:'Speakers', leaderboard:'Leaderboard', webinar:'Webinar', speaker:'Speaker' };
  const pageTitle = pageTitles[page] || '';
  if (!pageTitle || page === 'home') {
    bc.innerHTML = `<span class="tb-bc-home" onclick="nav('home')">WebinarIQ</span>`;
    return;
  }
  // For detail pages show title from cache
  let subLabel = '';
  if (page === 'webinar' && sub) {
    const w = S.webinars.find(x => x.id == sub) || detailCache[sub];
    subLabel = w ? w.title : 'Detail';
  } else if (page === 'speaker' && sub) {
    const cached = detailCache['spk_'+sub];
    subLabel = cached ? cached.name : 'Speaker';
  }
  bc.innerHTML = `
    <span class="tb-bc-home" onclick="nav('home')">WebinarIQ</span>
    <span class="tb-bc-sep">/</span>
    ${subLabel
      ? `<span class="tb-bc-page" onclick="nav('${page === 'webinar' ? 'webinar' : 'speakers'}')">${pageTitle}s</span>
         <span class="tb-bc-sep">/</span>
         <span class="tb-bc-page">${esc(subLabel)}</span>`
      : `<span class="tb-bc-page">${pageTitle}</span>`
    }`;
}

/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR RECENT (no-op — sidebar removed in website layout)
══════════════════════════════════════════════════════════════════════════ */
function updateSidebarRecent() { /* no sidebar in website layout */ }

/* ══════════════════════════════════════════════════════════════════════════
   MOBILE NAV TOGGLE
══════════════════════════════════════════════════════════════════════════ */
function toggleMobileNav() {
  const menu = document.getElementById('nav-mobile-menu');
  const btn  = document.getElementById('nav-hamburger');
  if (!menu) return;
  const isOpen = menu.classList.toggle('open');
  if (btn) btn.setAttribute('aria-expanded', isOpen);
  document.body.style.overflow = isOpen ? 'hidden' : '';
}
/* Keep old name as alias for any remaining references */
function toggleMobileSidebar() { toggleMobileNav(); }

/* ══════════════════════════════════════════════════════════════════════════
   CURSOR GLOW
══════════════════════════════════════════════════════════════════════════ */
function initCursorGlow() {
  const glow = document.getElementById('cursor-glow');
  if (!glow || window.matchMedia('(pointer: coarse)').matches) return; // skip touch
  document.addEventListener('mousemove', e => {
    glow.style.left = e.clientX + 'px';
    glow.style.top  = e.clientY + 'px';
  });
  document.addEventListener('mouseleave', () => {
    glow.style.left = '-600px';
    glow.style.top  = '-600px';
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   SCROLL REVEAL (IntersectionObserver)
══════════════════════════════════════════════════════════════════════════ */
function initScrollReveal() {
  const els = document.querySelectorAll('.reveal:not(.visible)');
  if (!els.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -30px 0px' });
  els.forEach(el => obs.observe(el));
}

/* ══════════════════════════════════════════════════════════════════════════
   NAVBAR SCROLL EFFECT
══════════════════════════════════════════════════════════════════════════ */
function initNavbarScroll() {
  const navbar = document.getElementById('navbar');
  if (!navbar) return;
  const onScroll = () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/* ══════════════════════════════════════════════════════════════════════════
   3D CARD TILT on webinar cards
══════════════════════════════════════════════════════════════════════════ */
function initCardTilt() {
  document.querySelectorAll('.wb-card, .spk-card').forEach(card => {
    if (card._tiltInit) return;
    card._tiltInit = true;
    card.addEventListener('mousemove', e => {
      const r  = card.getBoundingClientRect();
      const x  = (e.clientX - r.left) / r.width  - 0.5; // -0.5 to 0.5
      const y  = (e.clientY - r.top)  / r.height - 0.5;
      const rx =  y * -8;  // rotate X (pitch)
      const ry =  x *  8;  // rotate Y (yaw)
      card.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-6px) scale(1.02)`;
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   COMMAND PALETTE
══════════════════════════════════════════════════════════════════════════ */
let _cmdFocusIdx = -1;

function openCmdPalette() {
  const overlay = document.getElementById('cmd-overlay');
  const input   = document.getElementById('cmd-input');
  if (!overlay) return;
  overlay.classList.add('open');
  _cmdFocusIdx = -1;
  if (input) {
    input.value = '';
    setTimeout(() => input.focus(), 60);
  }
  renderCmdResults('');
  document.body.style.overflow = 'hidden';
}

function closeCmdPalette() {
  const overlay = document.getElementById('cmd-overlay');
  if (!overlay) return;
  overlay.classList.remove('open');
  document.body.style.overflow = '';
  _cmdFocusIdx = -1;
}

function onCmdSearch(q) {
  _cmdFocusIdx = -1;
  renderCmdResults(q.trim().toLowerCase());
}

function renderCmdResults(q) {
  const el = document.getElementById('cmd-results');
  if (!el) return;

  // Quick actions (always shown when q is empty)
  const actions = [
    { icon: '➕', title: 'New Webinar',        sub: 'Create a webinar session',           fn: () => { closeCmdPalette(); openWebinarModal(); } },
    { icon: '🏠', title: 'Dashboard',           sub: 'Go to webinar overview',             fn: () => nav('home') },
    { icon: '📊', title: 'Analytics',           sub: 'Platform-wide statistics',           fn: () => nav('analytics') },
    { icon: '🎤', title: 'Speakers',            sub: 'Browse all speakers',                fn: () => nav('speakers') },
    { icon: '🏆', title: 'Leaderboard',         sub: 'Top attendees by score',             fn: () => nav('leaderboard') },
  ];

  // Webinar results
  const wbMatches = q
    ? S.webinars.filter(w => w.title.toLowerCase().includes(q) || w.speaker_name.toLowerCase().includes(q))
    : S.webinars.slice(0, 5);

  // Speaker results
  const spkMatches = q
    ? S.speakers.filter(sp => sp.name.toLowerCase().includes(q))
    : S.speakers.slice(0, 3);

  const filteredActions = q
    ? actions.filter(a => a.title.toLowerCase().includes(q) || a.sub.toLowerCase().includes(q))
    : actions;

  if (!filteredActions.length && !wbMatches.length && !spkMatches.length) {
    el.innerHTML = `<div class="cmd-empty">No results for "<strong>${esc(q)}</strong>"</div>`;
    return;
  }

  let html = '';

  if (filteredActions.length) {
    html += `<div class="cmd-category">Actions</div>`;
    html += filteredActions.map((a, i) => `
      <div class="cmd-item" data-cmd-fn="${i}" onclick="_cmdActions[${i}]()">
        <div class="cmd-item-icon">${a.icon}</div>
        <div class="cmd-item-text">
          <div class="cmd-item-title">${esc(a.title)}</div>
          <div class="cmd-item-sub">${esc(a.sub)}</div>
        </div>
      </div>`).join('');
  }

  if (wbMatches.length) {
    html += `<div class="cmd-category">Webinars</div>`;
    html += wbMatches.slice(0, 6).map(w => `
      <div class="cmd-item" onclick="closeCmdPalette();nav('webinar',${w.id})">
        <div class="cmd-item-icon" style="background:${avColor(w.speaker_name)}20;font-size:13px;color:${avColor(w.speaker_name)}">
          ${initials(w.speaker_name)}
        </div>
        <div class="cmd-item-text">
          <div class="cmd-item-title">${esc(w.title)}</div>
          <div class="cmd-item-sub">${esc(w.speaker_name)} · ${fmtDate(w.date)}</div>
        </div>
        <span class="cmd-item-badge ${w.status}">${w.status}</span>
      </div>`).join('');
  }

  if (spkMatches.length) {
    html += `<div class="cmd-category">Speakers</div>`;
    html += spkMatches.slice(0, 4).map(sp => `
      <div class="cmd-item" onclick="closeCmdPalette();nav('speaker',${sp.id})">
        <div class="cmd-item-icon" style="background:${avColor(sp.name)};color:white;font-weight:700;font-size:12px">
          ${initials(sp.name)}
        </div>
        <div class="cmd-item-text">
          <div class="cmd-item-title">${esc(sp.name)}</div>
          <div class="cmd-item-sub">${sp.total_webinars} webinar${sp.total_webinars !== 1 ? 's' : ''}</div>
        </div>
      </div>`).join('');
  }

  el.innerHTML = html;

  // Store action fns for onclick
  window._cmdActions = filteredActions.map(a => a.fn);
}

function _cmdMoveFocus(dir) {
  const items = document.querySelectorAll('#cmd-results .cmd-item');
  if (!items.length) return;
  items.forEach(i => i.classList.remove('focused'));
  _cmdFocusIdx = (_cmdFocusIdx + dir + items.length) % items.length;
  const focused = items[_cmdFocusIdx];
  focused.classList.add('focused');
  focused.scrollIntoView({ block: 'nearest' });
}

function _cmdActivateFocused() {
  const focused = document.querySelector('#cmd-results .cmd-item.focused');
  if (focused) focused.click();
}

/* ── Dark/Light toggle (light is default; html.dark = dark mode) ── */
const MOON_ICON = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
const SUN_ICON  = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';

function _applyThemeIcon() {
  const icon = document.getElementById('dark-icon');
  if (icon) icon.innerHTML = S.dark ? SUN_ICON : MOON_ICON;
}
function toggleDark() {
  S.dark = !S.dark;
  document.documentElement.classList.toggle('dark', S.dark);
  localStorage.setItem('wiq-dark', S.dark);
  _applyThemeIcon();
}

/* ── Init ───────────────────────────────────────────────────────────────── */
async function init() {
  // Light-first: default is light. Apply dark class only if user explicitly chose dark.
  const saved = localStorage.getItem('wiq-dark');
  if (saved === 'true') {
    S.dark = true;
    document.documentElement.classList.add('dark');
  } else {
    S.dark = false;
  }
  _applyThemeIcon();

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    // ⌘K or Ctrl+K → open palette
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      const overlay = document.getElementById('cmd-overlay');
      if (overlay && overlay.classList.contains('open')) {
        closeCmdPalette();
      } else {
        openCmdPalette();
      }
      return;
    }
    // ESC → close palette or attendee drawer or ad modal
    if (e.key === 'Escape') {
      closeCmdPalette();
      closeAttendeeModal();
      closeAdModal();
      return;
    }
    // Arrow keys for palette navigation
    const overlay = document.getElementById('cmd-overlay');
    if (overlay && overlay.classList.contains('open')) {
      if (e.key === 'ArrowDown')  { e.preventDefault(); _cmdMoveFocus(1); }
      if (e.key === 'ArrowUp')    { e.preventDefault(); _cmdMoveFocus(-1); }
      if (e.key === 'Enter')      { e.preventDefault(); _cmdActivateFocused(); }
    }
  });

  // Show skeleton immediately — replaced by real content once loadAll() finishes
  showSkeletonHome();

  try {
    await loadAll();
  } catch(e) {
    console.error('API load failed:', e);
  }

  updateNotifBadge();
  nav('home');
  // Website enhancements
  initCursorGlow();
  initNavbarScroll();
  // Remove loading splash
  const _loader = document.getElementById('page-loader');
  if (_loader) { _loader.classList.add('fade'); setTimeout(() => _loader.remove(), 380); }
}

document.addEventListener('DOMContentLoaded', init);
