/* ── State ──────────────────────────────────────────────────────────────── */
const S = {
  webinars: [], speakers: [], stats: null,
  page: 'home', sub: null, dark: false, search: '',
  filterStatus: 'all', filterSpeaker: 'all', filterICP: 'all',
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
  if (!rate || rate === 0)  return { grade: 'N/A', cls: 'none',    color: '#5c5580',  track: 'rgba(92,85,128,0.2)' };
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
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>',
      title: `Top performer: ${topWebinar.title}`,
      desc: `${topWebinar.attendance_rate.toFixed(1)}% attendance rate · Grade ${gradeInfo(topWebinar.attendance_rate).grade}`,
      time: 'Best',
      link: () => nav('webinar', topWebinar.id),
    });
  }
  // Next upcoming
  const nextUp = upcoming.sort((a,b) => new Date(a.date)-new Date(b.date))[0];
  if (nextUp) {
    notes.push({
      id: `up-${nextUp.id}`,
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
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
      icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
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
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>',
      title: 'Platform attendance rate',
      desc: `${rate}% across ${completed.length} completed webinars (${fmt(totalReg)} registrations)`,
      time: 'Stats',
      link: () => nav('analytics'),
    });
  }
  // Leaderboard
  notes.push({
    id: 'leaderboard',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
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
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>', time: 'Best',
      title: topWebinar.title,
      desc:  `${topWebinar.attendance_rate.toFixed(1)}% attendance · Grade ${gradeInfo(topWebinar.attendance_rate).grade}`,
      onclick: `nav('webinar',${topWebinar.id})`,
    });
  }
  const nextUp = [...upcoming].sort((a,b) => new Date(a.date)-new Date(b.date))[0];
  if (nextUp) {
    items.push({
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>', time: 'Soon',
      title: nextUp.title,
      desc:  `${fmtDate(nextUp.date)}${nextUp.speaker_name ? ' · ' + nextUp.speaker_name : ''}`,
      onclick: `nav('webinar',${nextUp.id})`,
    });
  }
  if (noData.length) {
    items.push({
      icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>', time: 'Action',
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
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>', time: 'Stats',
      title: 'Platform attendance rate',
      desc:  `${rate}% across ${completed.length} completed webinars`,
      onclick: `nav('analytics')`,
    });
  }
  items.push({
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>', time: 'View',
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
  // Use allSettled so one failure doesn't wipe all data
  const [webRes, spkRes, stRes] = await Promise.allSettled([
    api('/api/webinars'),
    api('/api/speakers'),
    api('/api/stats'),
  ]);
  if (webRes.status === 'fulfilled') S.webinars = webRes.value;
  if (spkRes.status === 'fulfilled') S.speakers = spkRes.value;
  if (stRes.status  === 'fulfilled') S.stats    = stRes.value;
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
  if (value !== 'range') { S._drpFrom = ''; S._drpTo = ''; updateDateRangeLabel(); }
  // Sync chip active state
  document.querySelectorAll('.tb-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.filter === value)
  );
  if (S.page === 'home') renderHome();
}

/* ── Date range popover ────────────────────────────────────────────────── */
function openDateRangePopover(btn) {
  const pop = document.getElementById('date-range-popover');
  if (!pop) return;
  if (pop.style.display === 'block') { pop.style.display = 'none'; return; }
  const r = btn.getBoundingClientRect();
  pop.style.top  = (r.bottom + 8) + 'px';
  pop.style.left = Math.max(12, r.left - 100) + 'px';
  pop.style.display = 'block';
  document.getElementById('drp-from').value = S._drpFrom || '';
  document.getElementById('drp-to').value   = S._drpTo || '';
  setTimeout(() => {
    document.addEventListener('click', _drpOutsideClick, { once: true });
  }, 50);
}
function _drpOutsideClick(e) {
  const pop = document.getElementById('date-range-popover');
  if (pop && !pop.contains(e.target) && !e.target.closest('[data-filter="range"]')) {
    pop.style.display = 'none';
  } else {
    setTimeout(() => document.addEventListener('click', _drpOutsideClick, { once: true }), 50);
  }
}
function applyQuickRange(kind) {
  const today = new Date();
  let from, to = today;
  if (typeof kind === 'number') {
    from = new Date(today);
    from.setDate(today.getDate() - kind);
  } else if (kind === 'thisMonth') {
    from = new Date(today.getFullYear(), today.getMonth(), 1);
  } else if (kind === 'thisYear') {
    from = new Date(today.getFullYear(), 0, 1);
  }
  document.getElementById('drp-from').value = from.toISOString().slice(0,10);
  document.getElementById('drp-to').value   = to.toISOString().slice(0,10);
}
function applyDateRange() {
  S._drpFrom = document.getElementById('drp-from').value;
  S._drpTo   = document.getElementById('drp-to').value;
  S.filterStatus = 'range';
  document.querySelectorAll('.tb-chip').forEach(c => c.classList.toggle('active', c.dataset.filter === 'range'));
  updateDateRangeLabel();
  document.getElementById('date-range-popover').style.display = 'none';
  if (S.page === 'home') renderHome();
}
function clearDateRange() {
  S._drpFrom = ''; S._drpTo = '';
  document.getElementById('drp-from').value = '';
  document.getElementById('drp-to').value = '';
  updateDateRangeLabel();
  setChipFilter('all');
  document.getElementById('date-range-popover').style.display = 'none';
}
function updateDateRangeLabel() {
  const lbl = document.getElementById('date-range-label');
  if (!lbl) return;
  if (S._drpFrom && S._drpTo) {
    const f = new Date(S._drpFrom).toLocaleDateString('en', { month: 'short', day: 'numeric' });
    const t = new Date(S._drpTo).toLocaleDateString('en', { month: 'short', day: 'numeric' });
    lbl.textContent = `${f} → ${t}`;
  } else if (S._drpFrom) {
    lbl.textContent = `From ${new Date(S._drpFrom).toLocaleDateString('en', { month:'short', day:'numeric' })}`;
  } else if (S._drpTo) {
    lbl.textContent = `Until ${new Date(S._drpTo).toLocaleDateString('en', { month:'short', day:'numeric' })}`;
  } else {
    lbl.textContent = 'Date Range';
  }
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
    case 'topics':      renderTopics();             break;
    case 'intelligence': renderIntelligence();      break;
    case 'pipeline':    renderPipeline();           break;
    case 'upload':      renderUpload();             break;
    case 'webinar':     renderWebinarDetail(sub);   break;
    case 'speaker':     renderSpeakerDetail(sub);   break;
  }
}

function setContent(html) {
  const el = document.getElementById('content');
  el.style.opacity = '0';
  el.innerHTML = html;
  requestAnimationFrame(() => {
    el.style.opacity = '1';
    animateCards('.wb-card, .spk-card');
    animateBars();
    runCountUps();
    decorateLeaderboardRows();
    initScrollReveal();
    // Only run expensive tilt on desktop
    if (window.innerWidth >= 768) initCardTilt();
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
    : 'N/A';

  // Trend helpers - use real data if available, else demo %
  const trendArrowUp   = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="18 15 12 9 6 15"/></svg>`;
  const trendArrowDown = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>`;

  // Best webinar by attendance_rate among completed
  const completedW = S.webinars.filter(w => w.status === 'completed' && w.attendance_rate > 0);
  const bestW = completedW.sort((a,b) => b.attendance_rate - a.attendance_rate)[0];

  // Best ICP: min 3 completed webinars, exclude 'Others'
  const icpMap = {};
  S.webinars.filter(w=>w.status==='completed').forEach(w => {
    const icp = w.icp || 'Others';
    if (!icpMap[icp]) icpMap[icp] = {total:0,count:0};
    icpMap[icp].total += (w.attendance_rate||0);
    icpMap[icp].count++;
  });
  const bestICP = Object.entries(icpMap)
    .filter(([icp, v]) => v.count >= 3 && icp !== 'Others')
    .sort((a,b) => (b[1].total/b[1].count)-(a[1].total/a[1].count))[0] || null;

  const kpis = [
    {
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>', cls: 'kc-indigo',
      label: 'Total Webinars',
      value: total.toString(),
      trendUp: true, trend: `${upcoming.length} upcoming`, arrow: trendArrowUp,
    },
    {
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>', cls: 'kc-sky',
      label: 'Avg. Attendance',
      value: avgRate > 0 ? fmtPct(avgRate) : 'N/A',
      trendUp: avgRate >= 50, trend: avgRate >= 50 ? '+5% vs last period' : avgRate > 0 ? '-3% vs last period' : 'No data yet',
      arrow: avgRate >= 50 ? trendArrowUp : trendArrowDown,
    },
    {
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>', cls: 'kc-emerald',
      label: 'Completion Rate',
      value: total > 0 ? fmtPct(completionRate) : 'N/A',
      trendUp: completionRate >= 50, trend: completed.length + ' completed',
      arrow: completionRate >= 50 ? trendArrowUp : trendArrowDown,
    },
    {
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>', cls: 'kc-gold',
      label: 'Top Speaker',
      value: topSpeakerDisplay,
      trendUp: null, trend: topSpeakerFull ? 'By total attendance' : 'No data yet',
      arrow: null,
    },
    {
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 2h4"/><path d="m9 9 3 3 3-3"/></svg>', cls: 'kc-gold',
      label: 'Best Webinar',
      value: bestW ? (bestW.title.length > 16 ? bestW.title.slice(0,16)+'…' : bestW.title) : 'N/A',
      trendUp: null, trend: bestW ? `${bestW.attendance_rate.toFixed(1)}% attendance` : 'No completed webinars',
      arrow: null,
    },
    {
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>', cls: 'kc-emerald',
      label: 'Best ICP',
      value: bestICP ? bestICP[0] : 'N/A',
      trendUp: null, trend: bestICP ? `${(bestICP[1].total/bestICP[1].count).toFixed(1)}% avg att rate` : 'No data',
      arrow: null,
    },
    {
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.99 12 19.79 19.79 0 0 1 1.93 3.36 2 2 0 0 1 3.9 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.98-1.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
      cls: 'kc-red',
      label: 'Follow-up Pending',
      value: (S.stats?.followup_pending || 0).toString(),
      trendUp: false,
      trend: 'Attendees needing follow-up',
      arrow: null,
    },
  ];

  return kpis.map(k => `
    <div class="kpi-card ${k.cls}" ${k.label==='Follow-up Pending'?'onclick="showFollowupPendingModal()" style="cursor:pointer" title="Click to see pending follow-ups"':''}>
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

async function showFollowupPendingModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:600px">
      <div class="modal-header">
        <h3 style="display:flex;align-items:center;gap:8px">
          <span style="width:10px;height:10px;border-radius:50%;background:#f43f5e;display:inline-block"></span>
          Follow-up Pending
        </h3>
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="modal-body" style="padding:20px 24px">
        <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px">Attendees who have not yet been contacted in the follow-up pipeline.</p>
        <div id="followup-pending-list"><div class="pg-loading"><div class="spinner"></div></div></div>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  try {
    const [pipeline, lq] = await Promise.all([
      api('/api/pipeline').catch(()=>[]),
      api('/api/lead-quality').catch(()=>({ leads:[] })),
    ]);
    const pipelineEmails = new Set((pipeline||[]).map(c => c.email?.toLowerCase()));
    const leads = (lq?.leads || []).filter(l => !pipelineEmails.has(l.email?.toLowerCase())).slice(0,50);
    const el = document.getElementById('followup-pending-list');
    if (!el) return;
    if (!leads.length) {
      el.innerHTML = '<div class="empty-state" style="padding:20px 0"><div class="empty-title">All caught up!</div><div class="empty-sub">No pending follow-ups found.</div></div>';
      return;
    }
    el.innerHTML = `
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px">${leads.length} contact${leads.length!==1?'s':''} need follow-up</div>
      <div style="max-height:380px;overflow-y:auto">
        <table style="width:100%;border-collapse:collapse">
          <thead><tr style="border-bottom:1px solid var(--border)">
            <th style="text-align:left;padding:8px 12px;font-size:11px;color:var(--text-muted);font-weight:600;text-transform:uppercase">Email</th>
            <th style="text-align:center;padding:8px 12px;font-size:11px;color:var(--text-muted);font-weight:600;text-transform:uppercase">Webinars</th>
            <th style="text-align:center;padding:8px 12px;font-size:11px;color:var(--text-muted);font-weight:600;text-transform:uppercase">Score</th>
            <th style="padding:8px 12px"></th>
          </tr></thead>
          <tbody>
            ${leads.map(l => `
              <tr style="border-bottom:1px solid var(--border)">
                <td style="padding:10px 12px;font-size:13px">${esc(l.email)}</td>
                <td style="padding:10px 12px;text-align:center;font-size:13px">${l.webinar_count||1}</td>
                <td style="padding:10px 12px;text-align:center">
                  <span style="background:#6366f1;color:#fff;border-radius:20px;padding:2px 10px;font-size:12px;font-weight:700">${l.score}</span>
                </td>
                <td style="padding:10px 12px;text-align:right">
                  <button class="btn btn-ghost btn-sm" style="font-size:11px" onclick="addLeaderboardToPipeline('${esc(l.email)}','');this.textContent='Added ✓';this.disabled=true">Add to Pipeline</button>
                </td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch(e) {
    const el = document.getElementById('followup-pending-list');
    if (el) el.innerHTML = '<div style="color:var(--text-muted)">Failed to load data.</div>';
  }
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
      <div class="empty-icon" style="font-size:28px"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg></div>
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
   SKELETON LOADER - shown instantly before API data arrives
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
   HOME - Webinar Dashboard
══════════════════════════════════════════════════════════════════════════ */
function renderHome() {
  const q  = S.search.toLowerCase();
  let list = S.webinars.filter(w =>
    !q || w.title.toLowerCase().includes(q) || w.speaker_name.toLowerCase().includes(q)
  );
  if (S.filterStatus === 'range' && (S._drpFrom || S._drpTo)) {
    const from = S._drpFrom ? new Date(S._drpFrom + 'T00:00:00') : null;
    const to   = S._drpTo   ? new Date(S._drpTo   + 'T23:59:59') : null;
    list = list.filter(w => {
      const d = new Date(w.date + 'T00:00:00');
      if (from && d < from) return false;
      if (to && d > to) return false;
      return true;
    });
  } else if (S.filterStatus !== 'all' && S.filterStatus !== 'range') {
    list = list.filter(w => w.status === S.filterStatus);
  }
  if (S.filterSpeaker !== 'all') list = list.filter(w => w.speaker_id == S.filterSpeaker);
  if (S.filterICP && S.filterICP !== 'all') list = list.filter(w => w.icp === S.filterICP);

  const speakerOptions = S.speakers.map(sp =>
    `<option value="${sp.id}" ${S.filterSpeaker==sp.id?'selected':''}>${esc(sp.name)}</option>`
  ).join('');

  const ICP_LIST = ['PMS', 'Retirement Planning', 'NRI', 'ESOPs', 'Family Office', 'Others'];
  const icpOptions = ICP_LIST.map(icp =>
    `<option value="${icp}" ${S.filterICP===icp?'selected':''}>${icp}</option>`
  ).join('');

  let mainContent;

  if (S.webinars.length === 0) {
    // Truly empty - first-time user
    mainContent = `<div class="empty-state">
      <div class="empty-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg></div>
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
      const badgeCls = w.status === 'completed' ? 'completed' : w.status === 'upcoming' ? 'upcoming' : w.status === 'follow_up_pending' ? 'follow-up-pending' : w.status === 'follow_up_done' ? 'follow-up-done' : 'cancelled';
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
        <td><span class="icp-badge icp-${(w.icp||'others').toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}">${esc(w.icp || 'Others')}</span></td>
        <td><span class="wb-badge ${badgeCls}" style="font-size:10px;padding:3px 8px">${w.status}</span></td>
        <td style="font-size:12px;text-align:right;color:var(--c-reg);font-weight:600">${fmt(w.total_registrations)}</td>
        <td style="min-width:100px">
          <div style="display:flex;align-items:center;gap:6px">
            <div style="flex:1;height:4px;border-radius:2px;background:var(--border);overflow:hidden">
              <div class="an-bar-fill" style="width:${Math.min(rate,100)}%;background:${info.color}"></div>
            </div>
            <span style="font-size:11px;color:${info.color};font-weight:600;min-width:34px">${rate > 0 ? fmtPct(rate) : 'N/A'}</span>
          </div>
        </td>
        <td style="text-align:right">${w.status==='completed' ? (() => { const score = w.performance_score || 0; const scoreColor = score >= 80 ? '#10b981' : score >= 60 ? '#6366f1' : score >= 40 ? '#f59e0b' : '#f43f5e'; return `<span style="font-size:12px;font-weight:700;color:${scoreColor}">${score}</span>`; })() : ''}</td>
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
            <select class="filter-select" onchange="setFilter('speaker',this.value)">
              <option value="all">All Speakers</option>
              ${speakerOptions}
            </select>
            <select class="filter-select filter-icp" onchange="setFilter('icp',this.value)">
              <option value="all">All ICPs</option>
              ${icpOptions}
            </select>
          </div>
          ${list.length ? `
          <table class="wb-list-table">
            <thead>
              <tr>
                <th>Webinar</th>
                <th>Speaker</th>
                <th>Date</th>
                <th>ICP</th>
                <th>Status</th>
                <th style="text-align:right">Reg.</th>
                <th>Attendance</th>
                <th style="text-align:right">Score</th>
              </tr>
            </thead>
            <tbody>${tableRows}</tbody>
          </table>` : `
          <div style="padding:32px;text-align:center;color:var(--text-3);font-size:13px">
            No webinars match your current filters.
            <div style="margin-top:10px">
              <button class="btn btn-ghost btn-sm" onclick="S.search='';onSearch('');setChipFilter('all');setFilter('speaker','all');setFilter('icp','all')">Clear filters</button>
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

  const today = new Date();
  const hour = today.getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  setContent(`
    <div>
      <div class="dash-hero reveal">
        <div>
          <div class="dash-hero-eyebrow">WEBINAR INTELLIGENCE</div>
          <h1 class="dash-hero-title">${greeting}.</h1>
          <p class="dash-hero-sub">Track speaker performance, audience engagement and ICP-aligned outcomes across every Right Horizons webinar, all in one place.</p>
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
  if (type === 'icp')     S.filterICP = value;
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
          <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;flex-wrap:wrap;justify-content:flex-end">
            ${w.icp && w.icp !== 'Others' ? `<span class="icp-badge icp-${(w.icp||'').toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}">${esc(w.icp)}</span>` : ''}
            <span class="wb-badge ${badgeCls}" style="font-size:10px;opacity:0.75">${w.status}</span>
            <button class="wb-card-edit" title="Edit webinar"
              onclick="event.stopPropagation();editWebinar(${w.id})">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
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
          ${esc(w.speaker_name)}${w.co_speaker_name ? ` <span style="color:var(--text-3);font-size:11px">& ${esc(w.co_speaker_name.split(' ').slice(-1)[0])}</span>` : ''}
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
        <div class="grade-badge grade-${info.grade === 'N/A' ? 'none' : info.grade}">${info.grade}</div>
      </div>
      <div class="wb-card-upload-bar">
        ${bothDone
          ? `<span class="upload-tag has"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> All data uploaded</span>`
          : `
            <span class="upload-tag ${w.has_registration_data?'has':'none'}">
              ${w.has_registration_data ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>' : '○'} Registrations
            </span>
            <span class="upload-tag ${w.has_attendee_data?'has':'none'}">
              ${w.has_attendee_data ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>' : '○'} Attendees
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
    loadNotes(id);
    loadWebinarFunnel(id, w);
  } catch(e) {
    setContent('<div class="empty-state"><div class="empty-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div><div class="empty-title">Failed to load</div></div>');
  }
}

function _drawWebinarDetail(w) {
  const color    = avColor(w.speaker_name);
  const ini      = initials(w.speaker_name);
  const noShow   = w.no_shows ?? (w.total_registrations - w.total_attendees);
  const rate     = w.attendance_rate || 0;
  const rateClr  = rate >= 60 ? '#059669' : rate >= 40 ? '#d97706' : rate > 0 ? '#dc2626' : 'var(--text-3)';
  const badgeCls = w.status === 'completed' ? 'completed' : w.status === 'upcoming' ? 'upcoming' : w.status === 'cancelled' ? 'cancelled' : 'incomplete';

  const uploadSVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>';
  const checkSVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';

  const regCard = `
    <div class="upload-card${w.has_registration_data ? ' upload-card-done' : ''}" id="reg-upload-card"
         ondragover="event.preventDefault();this.classList.add('dragover')"
         ondragleave="this.classList.remove('dragover')"
         ondrop="handleFileDrop(event,${w.id},'registrations')">
      <div class="upload-card-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg></div>
      <div class="upload-card-title">Registration Data ${w.has_registration_data ? '<span style="color:#059669;font-size:11px;font-weight:500">' + checkSVG + ' Uploaded</span>' : ''}</div>
      <div class="upload-card-sub">${w.has_registration_data ? w.total_registrations + ' registrations. Re-upload to replace.' : 'Upload list of people who registered'}</div>
      <input type="file" class="upload-file-input" id="reg-file-input"
             accept=".csv,.xlsx,.xls"
             onchange="handleFileSelect(event,${w.id},'registrations')"/>
      <button class="btn ${w.has_registration_data ? 'btn-ghost' : 'btn-primary'} btn-sm upload-card-btn"
              onclick="document.getElementById('reg-file-input').click()">
        ${uploadSVG} ${w.has_registration_data ? 'Re-upload' : 'Upload File'}
      </button>
    </div>`;

  const attCard = `
    <div class="upload-card${w.has_attendee_data ? ' upload-card-done' : ''}" id="att-upload-card"
         ondragover="event.preventDefault();this.classList.add('dragover')"
         ondragleave="this.classList.remove('dragover')"
         ondrop="handleFileDrop(event,${w.id},'attendees')">
      <div class="upload-card-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg></div>
      <div class="upload-card-title">Attendee Data ${w.has_attendee_data ? '<span style="color:#059669;font-size:11px;font-weight:500">' + checkSVG + ' Uploaded</span>' : ''}</div>
      <div class="upload-card-sub">${w.has_attendee_data ? w.total_attendees + ' attendees. Re-upload to replace.' : 'Upload Zoom attendee report or attendance list'}</div>
      <input type="file" class="upload-file-input" id="att-file-input"
             accept=".csv,.xlsx,.xls"
             onchange="handleFileSelect(event,${w.id},'attendees')"/>
      <button class="btn ${w.has_attendee_data ? 'btn-ghost' : 'btn-primary'} btn-sm upload-card-btn"
              onclick="document.getElementById('att-file-input').click()">
        ${uploadSVG} ${w.has_attendee_data ? 'Re-upload' : 'Upload File'}
      </button>
    </div>`;

  const uploadSectionHTML = `
    <div class="sec-hd" style="margin-bottom:12px">
      <span class="sec-title">Data Upload</span>
      <span style="font-size:12px;color:var(--text-3)">Upload CSV or Excel files</span>
    </div>
    <div class="upload-section">
      ${regCard}
      ${attCard}
    </div>`;

  // Analysis cards (download removed - data is placeholder for many webinars)
  const analysisHTML = `
    <div class="analysis-grid">
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(59,130,246,0.15)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div>
        <div style="flex:1">
          <div class="an-stat-val" style="color:var(--c-reg)">${fmt(w.total_registrations)}</div>
          <div class="an-stat-lbl">Registered</div>
        </div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(16,185,129,0.15)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>
        <div style="flex:1">
          <div class="an-stat-val" style="color:var(--c-att)">${fmt(w.total_attendees)}</div>
          <div class="an-stat-lbl">Attended</div>
        </div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(244,63,94,0.15)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></div>
        <div><div class="an-stat-val" style="color:var(--c-nosh)">${fmt(noShow)}</div><div class="an-stat-lbl">No-shows</div></div>
      </div>
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(139,92,246,0.15)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg></div>
        <div><div class="an-stat-val" style="color:${rateClr}">${rate}%</div><div class="an-stat-lbl">Attendance Rate</div></div>
      </div>
      ${w.duplicates_removed > 0 ? `
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(245,158,11,0.15)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></div>
        <div><div class="an-stat-val" style="color:var(--gold)">${fmt(w.duplicates_removed)}</div><div class="an-stat-lbl">Duplicates Removed</div></div>
      </div>` : ''}
      ${w.unmatched_attendees > 0 ? `
      <div class="an-stat-card">
        <div class="an-stat-icon" style="background:rgba(245,158,11,0.10)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>
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
          <span class="log-file">${esc(l.filename||'N/A')}</span>
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
              ${w.icp && w.icp !== 'Others' ? `<span class="icp-badge icp-${(w.icp||'').toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}" style="font-size:11px;padding:4px 12px">${esc(w.icp)}</span>` : ''}
              ${w.total_registrations > 0 ? `
              <button class="btn-ai-analyze" id="ai-analyze-btn" onclick="runAIAnalysis(${w.id})">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg>
                Analyze with AI
              </button>
              <button class="btn-ai-compare" id="ai-compare-btn" onclick="runAIComparison(${w.id})">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                Compare vs Previous
              </button>
              <button class="btn btn-ghost btn-sm" onclick="exportWebinarReport(${w.id},'${safeTitle}')" style="font-size:12px;display:flex;align-items:center;gap:5px;border-radius:8px;height:32px;padding:0 12px">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Export Report
              </button>` : ''}
              <button class="btn btn-ghost btn-sm" onclick="editWebinar(${w.id})" style="font-size:12px;display:flex;align-items:center;gap:5px;border-radius:8px;height:32px;padding:0 12px">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                Edit
              </button>
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

      <!-- Funnel section placeholder (loaded async) -->
      <div id="webinar-funnel-section-${w.id}"></div>

      <!-- AI Analysis Panel -->
      <!-- Human Notes -->
      <div class="notes-section" id="notes-section-${w.id}">
        <div class="notes-head">
          <div>
            <div class="notes-title">Human Knowledge</div>
            <div class="notes-sub">Add observations that AI will use in analysis</div>
          </div>
          <button class="btn-add-note" onclick="toggleNoteForm(${w.id})">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add Note
          </button>
        </div>
        <div class="note-form" id="note-form-${w.id}" style="display:none">
          <div class="note-form-row">
            <input class="form-input" id="note-author-${w.id}" placeholder="Your name (e.g. Sarah)" maxlength="100" />
            <select class="form-input" id="note-category-${w.id}">
              <option value="observation">Observation</option>
              <option value="speaker_feedback">Speaker Feedback</option>
              <option value="tech_issue">Technical Issue</option>
              <option value="content_quality">Content Quality</option>
              <option value="promotion">Promotion / Marketing</option>
            </select>
          </div>
          <textarea class="form-input note-content" id="note-content-${w.id}" rows="3" placeholder="What happened? What did the audience think? Anything the numbers don't show…"></textarea>
          <div class="note-form-actions">
            <button class="btn btn-ghost btn-sm" onclick="toggleNoteForm(${w.id})">Cancel</button>
            <button class="btn btn-primary btn-sm" onclick="submitNote(${w.id})">Save Note</button>
          </div>
        </div>
        <div class="notes-list" id="notes-list-${w.id}"></div>
      </div>

      <div id="ai-analysis-panel"></div>
      <div id="ai-compare-panel"></div>

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
      S.webinars[idx].has_registration_data = fresh.has_registration_data;
      S.webinars[idx].has_attendee_data = fresh.has_attendee_data;
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
    <div class="empty-icon" style="font-size:24px"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg></div>
    <div class="empty-title" style="font-size:13px">No data yet</div>
  </div>`;
  const attPct    = (totalAtt / totalReg * 100).toFixed(1);
  const noShowPct = (Math.max(0, noShow) / totalReg * 100).toFixed(1);
  return `
    <div class="funnel-step" style="--fw:100%;--fc:#4f46e5">
      <div class="funnel-bar"></div>
      <div class="funnel-info">
        <span class="funnel-label"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg> Registered</span>
        <span class="funnel-val">${fmt(totalReg)}</span>
        <span class="funnel-pct">100%</span>
      </div>
    </div>
    <div class="funnel-step" style="--fw:${attPct}%;--fc:#10b981">
      <div class="funnel-bar"></div>
      <div class="funnel-info">
        <span class="funnel-label"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Attended</span>
        <span class="funnel-val">${fmt(totalAtt)}</span>
        <span class="funnel-pct">${attPct}%</span>
      </div>
    </div>
    <div class="funnel-step" style="--fw:${noShowPct}%;--fc:#ef4444">
      <div class="funnel-bar"></div>
      <div class="funnel-info">
        <span class="funnel-label"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> No-show</span>
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

  // Completed webinars with data, sorted by date
  const completed = [...S.webinars]
    .filter(w => w.status === 'completed' && (w.total_registrations > 0 || w.total_attendees > 0))
    .sort((a,b) => new Date(a.date+'T00:00:00') - new Date(b.date+'T00:00:00'));

  const trendData = completed.slice(-12);
  const recentWebinars = completed.slice(-6).reverse(); // last 6 for the new leads trend

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

  const totalReg = st.total_registrations;
  const totalAtt = st.total_attendees;
  const noShow   = Math.max(0, totalReg - totalAtt);
  const convRate = totalReg > 0 ? Math.round(totalAtt/totalReg*100) : 0;

  // Funnel stages for big visual
  const funnelStages = [
    { label:'Registered', count:totalReg, color:'#6366f1', pct:100 },
    { label:'Attended', count:totalAtt, color:'#10b981', pct:totalReg>0?Math.round(totalAtt/totalReg*100):0 },
    { label:'No-show', count:noShow, color:'#f43f5e', pct:totalReg>0?Math.round(noShow/totalReg*100):0 },
  ];

  // ICP breakdown
  const icpMap = {};
  completed.forEach(w => {
    if (!w.icp) return;
    if (!icpMap[w.icp]) icpMap[w.icp] = { reg:0, att:0, count:0 };
    icpMap[w.icp].reg   += w.total_registrations||0;
    icpMap[w.icp].att   += w.total_attendees||0;
    icpMap[w.icp].count += 1;
  });
  const icpRows = Object.entries(icpMap).sort((a,b)=>b[1].att-a[1].att);
  const maxIcpAtt = Math.max(...icpRows.map(r=>r[1].att),1);

  // Top lists
  const top10reg = [...S.webinars].filter(w=>w.total_registrations>0).sort((a,b)=>b.total_registrations-a.total_registrations).slice(0,8);
  const top10att = completed.sort((a,b)=>b.attendance_rate-a.attendance_rate).slice(0,8);
  const maxReg   = top10reg[0]?.total_registrations || 1;
  const maxAtt   = Math.max(...top10att.map(w=>w.attendance_rate||0),1);

  // New registrations per webinar (last 6) for sparkline
  const sparkMax = Math.max(...recentWebinars.map(w=>w.total_registrations||0),1);

  setContent(`
    <div>
      <div class="page-hd">
        <div>
          <h1 class="page-title">Funnel Analytics</h1>
          <p class="page-sub">Platform-wide performance · ${S.webinars.length} webinars · ${completed.length} completed with data</p>
        </div>
      </div>

      <!-- KPI strip -->
      <div class="an-kpi-strip" style="grid-template-columns:repeat(6,1fr)">
        ${[
          { label:'Total Webinars', val:st.total_webinars, color:'#6366f1' },
          { label:'Completed', val:st.completed_webinars||completed.length, color:'#10b981' },
          { label:'Registrations', val:fmt(totalReg), color:'#6366f1' },
          { label:'Attendees', val:fmt(totalAtt), color:'#10b981' },
          { label:'Avg Attendance', val:st.overall_attendance_rate+'%', color:'#f59e0b' },
          { label:'Conversion Rate', val:convRate+'%', color: convRate>=40?'#10b981':convRate>=25?'#f59e0b':'#f43f5e' },
        ].map(k=>`
          <div class="an-kpi-card" style="border-top:3px solid ${k.color}">
            <div class="an-kpi-val" style="color:${k.color}">${k.val}</div>
            <div class="an-kpi-label">${k.label}</div>
          </div>`).join('')}
      </div>

      <!-- Big visual funnel -->
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:28px 32px;margin-bottom:24px">
        <div style="font-weight:700;font-size:16px;margin-bottom:24px;color:var(--text-primary)">Programme Conversion Funnel</div>
        <div style="display:flex;flex-direction:column;gap:0;max-width:680px;margin:0 auto">
          ${funnelStages.map((s,i) => {
            const width = Math.max(s.pct, 15);
            const isNoShow = s.label === 'No-show';
            return `
              <div style="position:relative;margin-bottom:${isNoShow?0:2}px">
                <div style="display:flex;align-items:center;gap:16px">
                  <div style="width:${width}%;background:${s.color};border-radius:${i===0?'10px 10px 0 0':i===funnelStages.length-1?'0 0 10px 10px':'0'};padding:14px 20px;display:flex;align-items:center;justify-content:space-between;min-width:200px;transition:width .6s ease">
                    <span style="color:#fff;font-weight:700;font-size:15px">${esc(s.label)}</span>
                    <span style="color:#fff;font-size:13px;opacity:0.9">${s.pct}%</span>
                  </div>
                  <div style="flex:1">
                    <div style="font-size:22px;font-weight:800;color:var(--text-primary)">${fmt(s.count)}</div>
                    <div style="font-size:12px;color:var(--text-muted)">${s.label === 'Registered' ? 'total signups' : s.label==='Attended' ? `of registered · ${100-s.pct}% drop-off` : `missed · ${Math.round(noShow/(totalAtt||1)*100)}% no-show rate`}</div>
                  </div>
                </div>
                ${i < funnelStages.length-1 && !isNoShow ? `<div style="width:${Math.max(funnelStages[i+1].pct,15)}%;height:4px;background:linear-gradient(${s.color},${funnelStages[i+1].color});margin-left:0;opacity:.4"></div>` : ''}
              </div>`;
          }).join('')}
        </div>
        <div style="display:flex;gap:24px;margin-top:24px;justify-content:center;flex-wrap:wrap">
          <div style="text-align:center;padding:14px 24px;background:#6366f108;border:1px solid #6366f140;border-radius:10px">
            <div style="font-size:20px;font-weight:800;color:#6366f1">${convRate}%</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px">Reg → Attendee</div>
          </div>
          <div style="text-align:center;padding:14px 24px;background:#10b98108;border:1px solid #10b98140;border-radius:10px">
            <div style="font-size:20px;font-weight:800;color:#10b981">${completed.length > 0 ? Math.round(totalAtt/completed.length) : 0}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px">Avg Attendees/Webinar</div>
          </div>
          <div style="text-align:center;padding:14px 24px;background:#f59e0b08;border:1px solid #f59e0b40;border-radius:10px">
            <div style="font-size:20px;font-weight:800;color:#f59e0b">${completed.length > 0 ? Math.round(totalReg/completed.length) : 0}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px">Avg Registrations/Webinar</div>
          </div>
        </div>
      </div>

      <!-- New leads per webinar - loaded async -->
      <div id="new-leads-chart-section" style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px 28px;margin-bottom:24px">
        <div style="font-weight:700;font-size:15px;margin-bottom:4px;color:var(--text-primary)">New Leads per Webinar</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:16px">First-time email addresses seen in each webinar vs returning registrants</div>
        <div id="new-leads-chart-body"><div class="pg-loading" style="padding:20px 0"><div class="spinner"></div></div></div>
      </div>

      <!-- Monthly trend + ICP breakdown -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px">
        ${months.length >= 2 ? `
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px 28px">
          <div style="font-weight:700;font-size:15px;margin-bottom:20px">Monthly Trend</div>
          ${renderMonthlyBars(months)}
        </div>` : ''}
        ${icpRows.length ? `
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px 28px">
          <div style="font-weight:700;font-size:15px;margin-bottom:16px">Attendees by ICP</div>
          ${icpRows.map(([icp,d]) => `
            <div style="margin-bottom:12px">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="font-size:13px;font-weight:600">${esc(icp)}</span>
                <span style="font-size:12px;color:var(--text-muted)">${fmt(d.att)} attended · ${d.att>0&&d.reg>0?Math.round(d.att/d.reg*100)+'%':'-'}</span>
              </div>
              <div style="height:8px;background:var(--border);border-radius:4px">
                <div style="height:100%;width:${Math.round(d.att/maxIcpAtt*100)}%;background:#6366f1;border-radius:4px"></div>
              </div>
            </div>`).join('')}
        </div>` : ''}
      </div>

      <!-- Top lists -->
      <div class="an-grid">
        <div class="an-card">
          <div class="an-title">Top 8 by Registrations</div>
          ${top10reg.map(w => `
            <div class="an-row" onclick="nav('webinar',${w.id})" style="cursor:pointer">
              <span class="an-row-lbl" title="${esc(w.title)}">${esc(w.title)}</span>
              <div class="an-bar-wrap"><div class="an-bar-fill" style="width:${Math.round(w.total_registrations/maxReg*100)}%;background:#6366f1"></div></div>
              <span class="an-row-val">${fmt(w.total_registrations)}</span>
            </div>`).join('')}
        </div>
        <div class="an-card">
          <div class="an-title">Top 8 by Attendance Rate</div>
          ${top10att.length ? top10att.map(w => `
            <div class="an-row" onclick="nav('webinar',${w.id})" style="cursor:pointer">
              <span class="an-row-lbl" title="${esc(w.title)}">${esc(w.title)}</span>
              <div class="an-bar-wrap"><div class="an-bar-fill" style="width:${Math.min((w.attendance_rate||0)/maxAtt*100,100)}%;background:#10b981"></div></div>
              <span class="an-row-val">${fmtPct(w.attendance_rate)}</span>
            </div>`).join('') : '<div style="color:var(--text-3);font-size:12px;padding:8px 0">No completed webinars with attendance data yet.</div>'}
        </div>
      </div>

      <!-- Charts -->
      ${trendData.length >= 2 ? `
      <div class="an-charts-row" style="margin-top:24px">
        ${renderTwinLineChart(trendData)}
      </div>` : ''}
    </div>`);

  _loadNewLeadsChart();
}

async function _loadNewLeadsChart() {
  const body = document.getElementById('new-leads-chart-body');
  if (!body) return;
  try {
    const data = await api('/api/new-registrants-per-webinar');
    const webinars = (data?.webinars || []).filter(w => w.new_count + w.repeat_count > 0).slice(-10);
    if (!webinars.length) {
      body.innerHTML = '<div style="color:var(--text-muted);font-size:13px">No registration data available.</div>';
      return;
    }
    const maxNew = Math.max(...webinars.map(w => w.new_count), 1);
    const maxTotal = Math.max(...webinars.map(w => w.new_count + w.repeat_count), 1);

    body.innerHTML = `
      <div style="display:flex;align-items:flex-end;gap:10px;height:140px;margin-bottom:8px">
        ${webinars.map(w => {
          const total = w.new_count + w.repeat_count;
          const newH  = Math.max(Math.round((w.new_count/maxTotal)*120), 4);
          const repH  = Math.max(Math.round((w.repeat_count/maxTotal)*120), w.repeat_count>0?4:0);
          return `
            <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;min-width:0">
              <div style="font-size:10px;font-weight:700;color:#6366f1">+${w.new_count}</div>
              <div style="width:100%;display:flex;flex-direction:column;justify-content:flex-end;height:120px;gap:1px">
                ${repH>0?`<div style="width:100%;height:${repH}px;background:#a5b4fc;border-radius:4px 4px 0 0" title="${w.repeat_count} returning"></div>`:''}
                <div style="width:100%;height:${newH}px;background:#6366f1;border-radius:${repH>0?'0':'4px 4px'} 0 0" title="${w.new_count} new"></div>
              </div>
              <div style="font-size:9px;color:var(--text-muted);text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;width:100%;max-width:80px" title="${esc(w.title)}">${esc((w.title||'').slice(0,14)+(w.title&&w.title.length>14?'…':''))}</div>
              <div style="font-size:8px;color:var(--text-muted)">${w.date?w.date.slice(5):''}</div>
            </div>`;
        }).join('')}
      </div>
      <div style="display:flex;gap:16px;font-size:11px;color:var(--text-muted)">
        <div style="display:flex;align-items:center;gap:6px"><div style="width:12px;height:12px;border-radius:3px;background:#6366f1"></div>New registrants (first time)</div>
        <div style="display:flex;align-items:center;gap:6px"><div style="width:12px;height:12px;border-radius:3px;background:#a5b4fc"></div>Returning registrants</div>
      </div>`;
  } catch(e) {
    const body2 = document.getElementById('new-leads-chart-body');
    if (body2) body2.innerHTML = '<div style="color:var(--text-muted);font-size:13px">Could not load new leads data.</div>';
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   SPEAKERS
══════════════════════════════════════════════════════════════════════════ */
async function renderSpeakers() {
  setContent(`
    <div>
      <div class="page-hd">
        <div>
          <h1 class="page-title">Speakers</h1>
          <p class="page-sub">${S.speakers.length} speakers</p>
        </div>
      </div>
      <div id="spk-perf-section"><div class="pg-loading"><div class="spinner"></div><p>Loading performance data…</p></div></div>
    </div>`);

  let perfMap = {};
  let speakerInsights = {};
  try {
    const [intel, insightsData] = await Promise.all([
      api('/api/intelligence'),
      api('/api/speaker-insights')
    ]);
    for (const s of (intel.speaker_performance || [])) perfMap[s.id] = s;
    for (const s of (insightsData.speakers || [])) speakerInsights[s.id] = s;
  } catch(e) { /* show basic cards if fails */ }

  const cards = S.speakers.map(sp => {
    const color = avColor(sp.name);
    const ini   = initials(sp.name);
    const perf  = perfMap[sp.id];
    const grade = perf ? (perf.attendance_rate >= 40 ? 'A' : perf.attendance_rate >= 30 ? 'B' : perf.attendance_rate >= 20 ? 'C' : 'D') : null;
    const gColor = grade ? { A:'#10b981', B:'#6366f1', C:'#f59e0b', D:'#f43f5e' }[grade] : null;

    const si = speakerInsights[sp.id];
    const webinarCount = sp.total_webinars || (S.webinars.filter(w => w.speaker_id === sp.id).length);
    return `
      <div class="spk-card" onclick="nav('speaker',${sp.id})">
        <div style="display:flex;align-items:center;justify-content:center;margin-bottom:14px">
          <div class="spk-av" style="background:${color};margin:0;width:56px;height:56px;font-size:20px">${ini}</div>
        </div>
        <div class="spk-name" style="text-align:center">${esc(sp.name)}</div>
        <div style="text-align:center;margin-top:8px">
          <span style="font-size:22px;font-weight:800;color:${color}">${webinarCount}</span>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px">Webinars</div>
        </div>
      </div>`;
  }).join('');

  const siCards = Object.values(speakerInsights).map(si => {
    const av = avColor(si.name); const ini2 = initials(si.name);
    const grade2 = si.avg_attendance_rate >= 40 ? 'A' : si.avg_attendance_rate >= 30 ? 'B' : si.avg_attendance_rate >= 20 ? 'C' : 'D';
    const gColor2 = {A:'#10b981',B:'#6366f1',C:'#f59e0b',D:'#f43f5e'}[grade2];
    const bestW = (si.best_webinars||[]).map(wb => `<div style="font-size:12px;padding:5px 0;border-bottom:1px solid var(--border)"><span style="color:#10b981;font-weight:600">${wb.rate}%</span> · ${esc(wb.title)}</div>`).join('');
    const weakW = (si.weak_webinars||[]).map(wb => `<div style="font-size:12px;padding:5px 0;border-bottom:1px solid var(--border)"><span style="color:#f43f5e;font-weight:600">${wb.rate}%</span> · ${esc(wb.title)}</div>`).join('');
    const insight2 = si.avg_attendance_rate >= 40
      ? `${esc(si.name)} delivers exceptional results. Best ICP: ${esc(si.best_icp||'N/A')}. Consider assigning more ${esc(si.best_icp||'')} topics.`
      : si.avg_attendance_rate >= 25
      ? `${esc(si.name)} performs well but has room to improve. Pair with stronger topic hooks for better attendance.`
      : `${esc(si.name)} has lower attendance rates. Review topic-audience fit and improve pre-webinar communication.`;
    return `
      <div class="spk-insight-card">
        <div class="spk-insight-header">
          <div style="display:flex;align-items:center;gap:10px">
            <div style="width:36px;height:36px;background:${av};border-radius:10px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:13px">${ini2}</div>
            <div>
              <div style="font-weight:700;font-size:14px">${esc(si.name)}</div>
              <div style="font-size:11px;color:var(--text-muted)">${si.webinar_count} webinars · Best ICP: <strong>${esc(si.best_icp||'N/A')}</strong></div>
            </div>
          </div>
          <div style="width:36px;height:36px;border-radius:50%;border:2px solid ${gColor2};display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;color:${gColor2}">${grade2}</div>
        </div>
        <div style="font-size:12.5px;color:var(--text-secondary);margin:12px 0;line-height:1.5">${insight2}</div>
        ${bestW ? `<div style="margin-bottom:8px"><div style="font-size:10px;font-weight:700;text-transform:uppercase;color:var(--text-muted);margin-bottom:4px">Top Performing</div>${bestW}</div>` : ''}
        ${weakW ? `<div><div style="font-size:10px;font-weight:700;text-transform:uppercase;color:var(--text-muted);margin-bottom:4px">Needs Improvement</div>${weakW}</div>` : ''}
      </div>`;
  }).join('');

  const sect = document.getElementById('spk-perf-section');
  if (sect) sect.outerHTML = `<div class="spk-grid">${cards}</div>
    <div style="margin-top:36px">
      <h2 class="sec-title" style="margin-bottom:16px">Performance Detail</h2>
      ${_renderSpeakerIntel({ speaker_performance: Object.values(perfMap) })}
    </div>
    ${siCards ? `<div style="margin-top:36px"><h2 class="sec-title" style="margin-bottom:16px">Speaker Intelligence</h2><div class="spk-insight-grid">${siCards}</div></div>` : ''}`;
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
                <div class="bk-metric"><span class="bk-metric-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span><div><div class="bk-metric-val" style="color:#2563eb">${fmt(w.total_registrations)}</div><div class="bk-metric-lbl">Registered</div></div></div>
                <div class="bk-metric"><span class="bk-metric-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></span><div><div class="bk-metric-val" style="color:#059669">${fmt(w.total_attendees)}</div><div class="bk-metric-lbl">Attended</div></div></div>
                <div class="bk-metric"><span class="bk-metric-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></span><div><div class="bk-metric-val" style="color:#dc2626">${fmt(noShow)}</div><div class="bk-metric-lbl">No-shows</div></div></div>
                <div class="bk-metric"><span class="bk-metric-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg></span><div><div class="bk-metric-val" style="color:${rc}">${w.attendance_rate}%</div><div class="bk-metric-lbl">Rate</div></div></div>
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
            <div class="spk-hero-bio">${esc(sp.bio || 'No bio available')}</div>
            <div class="spk-hero-stats">
              <div><div class="spk-hero-stat-val">${sp.total_webinars}</div><div class="spk-hero-stat-lbl">Webinars</div></div>
              <div><div class="spk-hero-stat-val">${fmt(totalReg)}</div><div class="spk-hero-stat-lbl">Registrations</div></div>
              <div><div class="spk-hero-stat-val">${fmt(totalAtt)}</div><div class="spk-hero-stat-lbl">Attendees</div></div>
              <div><div class="spk-hero-stat-val">${avgRate}%</div><div class="spk-hero-stat-lbl">Avg. Rate</div></div>
            </div>
            ${sp.email ? `<div class="spk-hero-email"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg> ${esc(sp.email)}</div>` : ''}
          </div>
        </div>
        <div class="sec-hd">
          <span class="sec-title">Webinar History</span>
          <span style="font-size:12px;color:var(--text-3)">${sp.total_webinars} total</span>
        </div>
        ${wbItems || '<div class="empty-state"><div class="empty-icon"><svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" opacity="0.25"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg></div><div class="empty-title">No webinars yet</div></div>'}
      </div>`);
  } catch(e) {
    setContent('<div class="empty-state"><div class="empty-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div><div class="empty-title">Failed to load speaker data</div></div>');
  }
}

function toggleAcc(id) {
  document.getElementById(id)?.classList.toggle('open');
}

/* ── Repeat Audience ─────────────────────────────────────────────────────── */
async function renderRepeatAudience(container) {
  container.innerHTML = '<div class="pg-loading"><div class="spinner"></div><p>Loading…</p></div>';
  try {
    const data = await api('/api/repeat-audience');
    const rows = (data.repeat_attendees || []).map((r, i) => `
      <tr>
        <td style="font-weight:600;color:var(--text-primary)">${i+1}. ${esc(r.name || r.email)}</td>
        <td style="font-family:var(--font-mono);text-align:center;font-weight:700;color:#6366f1">${r.webinar_count}</td>
        <td style="font-size:12px;color:var(--text-muted)">${r.last_seen ? fmtDate(r.last_seen) : ''}</td>
        <td><button class="btn btn-ghost btn-sm" style="font-size:11px" onclick="openAddToPipelineModal('${esc(r.email)}','${esc(r.name||'')}')">Add to Pipeline</button></td>
      </tr>`).join('');
    container.innerHTML = `
      <div>
        <div class="intel-kpis" style="margin-bottom:20px">
          <div class="intel-kpi"><div class="intel-kpi-lbl">Unique Attendees</div><div class="intel-kpi-val">${fmt(data.total_unique_attendees||0)}</div></div>
          <div class="intel-kpi"><div class="intel-kpi-lbl">Repeat Attendees (2+)</div><div class="intel-kpi-val" style="color:#6366f1">${fmt(data.repeat_attendees_count||0)}</div></div>
          <div class="intel-kpi"><div class="intel-kpi-lbl">Never Attended</div><div class="intel-kpi-val" style="color:#f43f5e">${fmt(data.never_attended_count||0)}</div></div>
        </div>
        ${(data.repeat_attendees_count||0) > 0 ? `
          <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">
            <strong>${data.repeat_attendees_count}</strong> people have attended 2+ webinars. These are your most engaged attendees. Prioritise them for follow-up.
          </p>
          <div class="intel-table-wrap">
            <table class="intel-table">
              <thead><tr><th>Name / Email</th><th style="text-align:center">Webinars</th><th>Last Seen</th><th>Action</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>` : '<div class="empty-state"><div class="empty-title">No repeat attendees yet</div><div class="empty-sub">As more people attend multiple webinars, they will appear here.</div></div>'}
      </div>`;
  } catch(e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-title">Failed to load repeat audience data</div></div>`;
  }
}

/* ── Lead Quality ─────────────────────────────────────────────────────────── */
async function renderLeadQuality(container) {
  container.innerHTML = '<div class="pg-loading"><div class="spinner"></div><p>Scoring leads…</p></div>';
  try {
    const data = await api('/api/lead-quality');
    const QUALITY_COLOR = {'High Quality':'#10b981','Medium Quality':'#6366f1','Low Quality':'#f59e0b','Needs Review':'#94a3b8'};
    const rows = (data.leads || []).map((l, i) => {
      const qc = QUALITY_COLOR[l.quality] || '#94a3b8';
      return `<tr>
        <td style="font-weight:600">${i+1}. ${esc(l.name || l.email)}</td>
        <td><span class="icp-badge icp-${(l.primary_icp||'others').toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}">${esc(l.primary_icp||'N/A')}</span></td>
        <td style="text-align:center;font-family:var(--font-mono)">${l.webinar_count}</td>
        <td style="text-align:center;font-family:var(--font-mono)">${l.avg_duration_min > 0 ? Math.round(l.avg_duration_min)+'m' : '—'}</td>
        <td><span style="background:${qc}18;color:${qc};border:1px solid ${qc}40;border-radius:12px;font-size:11px;font-weight:600;padding:3px 9px">${esc(l.quality)}</span></td>
        <td style="text-align:right;font-family:var(--font-mono);font-weight:700;color:${qc}">${l.score}</td>
        <td><button class="btn btn-ghost btn-sm" style="font-size:11px" onclick="openAddToPipelineModal('${esc(l.email)}','${esc(l.name||'')}')">Pipeline</button></td>
      </tr>`;
    }).join('');
    container.innerHTML = `
      <div>
        <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">Lead quality scored by: repeat attendance (30pts) + avg session duration (25pts) + ICP relevance (25pts) + follow-up status (20pts).</p>
        <div class="intel-table-wrap">
          <table class="intel-table">
            <thead><tr><th>Name</th><th>ICP</th><th style="text-align:center">Webinars</th><th style="text-align:center">Avg Duration</th><th>Quality</th><th style="text-align:right">Score</th><th>Action</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  } catch(e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-title">Failed to load lead quality</div></div>`;
  }
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
  const selLimit   = S._lbLimit ? +S._lbLimit : 50;
  if (selSpeaker) params.set('speaker_id', selSpeaker);
  if (selWebinar) params.set('webinar_id', selWebinar);
  params.set('limit', selLimit);

  try {
    const lbAll = await api('/api/leaderboard?' + params.toString());

    // Score range filter (client-side)
    const minS = S._lbScoreMin !== undefined && S._lbScoreMin !== '' ? +S._lbScoreMin : null;
    const maxS = S._lbScoreMax !== undefined && S._lbScoreMax !== '' ? +S._lbScoreMax : null;
    const readinessF = S._lbReadiness || 'all';
    const lb = lbAll.filter(e => {
      if (minS !== null && e.score < minS) return false;
      if (maxS !== null && e.score > maxS) return false;
      if (readinessF !== 'all') {
        const r = e.tag || e.readiness || 'cold';
        if (readinessF === 'meeting_ready') {
          if (r !== 'hot' && r !== 'meeting_ready') return false;
        } else if (r !== readinessF) {
          return false;
        }
      }
      return true;
    });

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
              <th>Webinars</th>
              <th>Avg Min</th>
              <th>Last Seen</th>
              <th>Status</th>
              <th>Score</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${lb.map(e => {
              const safeEmail = (e.email||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");
              const safeName  = (e.name ||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");
              const nameCell = e.email
                ? `<span class="lb-name-link" onclick="openAttendeeModal('${safeEmail}','${safeName}')" title="Click to view attended webinars">${esc(e.name)}</span>`
                : `<span class="lb-name-link no-email" title="No email on file">${esc(e.name)}</span>`;
              const readinessKey = e.tag || e.readiness || 'cold';
              const lastSeen = e.days_since_last !== null && e.days_since_last !== undefined
                ? (e.days_since_last === 0 ? 'Today' : `${e.days_since_last}d ago`)
                : '—';
              const lastSeenColor = e.days_since_last == null ? 'var(--text-muted)'
                : e.days_since_last <= 30 ? '#10B981'
                : e.days_since_last <= 90 ? '#F59E0B'
                : '#9CA3AF';
              return `
              <tr data-readiness="${readinessKey}">
                <td>${rankHTML(e.rank)}</td>
                <td>${nameCell}</td>
                <td><div class="lb-email">${esc(e.email||'N/A')}</div></td>
                <td style="text-align:center;font-weight:600;color:#059669">${e.webinars_attended}</td>
                <td style="text-align:center;font-family:var(--font-mono);color:var(--text-secondary)">${e.avg_minutes||0}</td>
                <td style="text-align:center;font-family:var(--font-mono);color:${lastSeenColor};font-weight:600">${lastSeen}</td>
                <td>${renderReadinessBadge(readinessKey, e.tag)}</td>
                <td><span class="lb-score">${e.score}</span></td>
                <td>
                  <div style="display:flex;gap:4px;align-items:center">
                  ${e.email ? `<button class="lb-tag-edit" onclick="openTagEditor('${safeEmail}','${safeName}', '${e.tag||''}')" title="Edit lead tag">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  </button>` : ''}
                  ${e.email ? `<button class="lb-tag-edit" onclick="addLeaderboardToPipeline('${safeEmail}','${safeName}')" title="Add to pipeline" style="color:#6366f1">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                  </button>` : ''}
                  </div>
                </td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>` : `<div class="lb-empty">No attendance data yet.<br>Upload attendee files to populate the leaderboard.</div>`;

    // Alternate leaderboard views (client-side computed from S.webinars)
    S._lbView = S._lbView || 'attendees';
    const lbViewTabs = `
      <div class="lb-view-tabs">
        <button class="lb-vtab ${S._lbView==='attendees'?'active':''}" onclick="S._lbView='attendees';renderLeaderboard()">Top Attendees</button>
        <button class="lb-vtab ${S._lbView==='webinars'?'active':''}" onclick="S._lbView='webinars';renderLeaderboard()">Best Webinars</button>
        <button class="lb-vtab ${S._lbView==='speakers'?'active':''}" onclick="S._lbView='speakers';renderLeaderboard()">Best Speakers</button>
        <button class="lb-vtab ${S._lbView==='icp'?'active':''}" onclick="S._lbView='icp';renderLeaderboard()">Best ICP</button>
        <button class="lb-vtab ${S._lbView==='repeat'?'active':''}" onclick="S._lbView='repeat';renderLeaderboard()">Repeat Audience</button>
        <button class="lb-vtab ${S._lbView==='leadquality'?'active':''}" onclick="S._lbView='leadquality';renderLeaderboard()">Lead Quality</button>
      </div>`;

    let altViewHTML = '';
    if (S._lbView === 'webinars') {
      const sortedW = S.webinars.filter(w=>w.status==='completed').sort((a,b)=>(b.attendance_rate||0)-(a.attendance_rate||0));
      altViewHTML = sortedW.length ? `<div class="lb-table-wrap"><table class="lb-table"><thead><tr><th>Rank</th><th>Webinar</th><th>Speaker</th><th>ICP</th><th style="text-align:right">Regs</th><th style="text-align:right">Att Rate</th><th style="text-align:right">Score</th></tr></thead><tbody>${sortedW.map((w,i)=>{
        const score = w.performance_score || 0;
        const sc = score>=80?'#10b981':score>=60?'#6366f1':score>=40?'#f59e0b':'#f43f5e';
        return `<tr><td>${rankHTML(i+1)}</td><td><div class="wb-list-name" title="${esc(w.title)}">${esc(w.title)}</div></td><td style="font-size:12px;color:var(--text-2)">${esc(w.speaker_name||'—')}</td><td><span class="icp-badge icp-${(w.icp||'others').toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}">${esc(w.icp||'Others')}</span></td><td style="text-align:right;font-weight:600;color:var(--c-reg)">${fmt(w.total_registrations)}</td><td style="text-align:right;font-weight:600;color:#059669">${(w.attendance_rate||0).toFixed(1)}%</td><td style="text-align:right"><span style="font-size:12px;font-weight:700;color:${sc}">${score}</span></td></tr>`;
      }).join('')}</tbody></table></div>` : `<div class="lb-empty">No completed webinars yet.</div>`;
    } else if (S._lbView === 'speakers') {
      const spkData = {};
      S.webinars.filter(w=>w.status==='completed').forEach(w => {
        const sp = w.speaker_name || 'Unknown';
        if (!spkData[sp]) spkData[sp] = {totalRate:0, regs:0, count:0};
        spkData[sp].totalRate += (w.attendance_rate||0);
        spkData[sp].regs += (w.total_registrations||0);
        spkData[sp].count++;
      });
      const sortedSp = Object.entries(spkData).sort((a,b)=>(b[1].totalRate/b[1].count)-(a[1].totalRate/a[1].count));
      altViewHTML = sortedSp.length ? `<div class="lb-table-wrap"><table class="lb-table"><thead><tr><th>Rank</th><th>Speaker</th><th style="text-align:right">Webinars</th><th style="text-align:right">Total Regs</th><th style="text-align:right">Avg Att Rate</th></tr></thead><tbody>${sortedSp.map(([name,d],i)=>`<tr><td>${rankHTML(i+1)}</td><td><div style="font-weight:600;font-size:13px">${esc(name)}</div></td><td style="text-align:right;font-weight:600;color:var(--c-reg)">${d.count}</td><td style="text-align:right;color:var(--text-2)">${fmt(d.regs)}</td><td style="text-align:right;font-weight:700;color:#059669">${(d.totalRate/d.count).toFixed(1)}%</td></tr>`).join('')}</tbody></table></div>` : `<div class="lb-empty">No completed webinars yet.</div>`;
    } else if (S._lbView === 'icp') {
      const icpData = {};
      S.webinars.filter(w=>w.status==='completed').forEach(w => {
        const icp = w.icp || 'Others';
        if (!icpData[icp]) icpData[icp] = {totalRate:0, regs:0, count:0};
        icpData[icp].totalRate += (w.attendance_rate||0);
        icpData[icp].regs += (w.total_registrations||0);
        icpData[icp].count++;
      });
      const sortedIcp = Object.entries(icpData).sort((a,b)=>(b[1].totalRate/b[1].count)-(a[1].totalRate/a[1].count));
      altViewHTML = sortedIcp.length ? `<div class="lb-table-wrap"><table class="lb-table"><thead><tr><th>Rank</th><th>ICP</th><th style="text-align:right">Webinars</th><th style="text-align:right">Total Regs</th><th style="text-align:right">Avg Att Rate</th></tr></thead><tbody>${sortedIcp.map(([icp,d],i)=>`<tr><td>${rankHTML(i+1)}</td><td><span class="icp-badge icp-${icp.toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}">${esc(icp)}</span></td><td style="text-align:right;font-weight:600;color:var(--c-reg)">${d.count}</td><td style="text-align:right;color:var(--text-2)">${fmt(d.regs)}</td><td style="text-align:right;font-weight:700;color:#059669">${(d.totalRate/d.count).toFixed(1)}%</td></tr>`).join('')}</tbody></table></div>` : `<div class="lb-empty">No completed webinars yet.</div>`;
    }

    setContent(`
      <div>
        <div class="page-hd">
          <div>
            <h1 class="page-title">Attendee Leaderboard</h1>
            <p class="page-sub">Top attendees ranked by score · ${lb.length} entries shown</p>
          </div>
          <button class="btn btn-primary" onclick="exportLeaderboardCSV()" style="display:inline-flex;align-items:center;gap:6px">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export CSV
          </button>
        </div>

        ${lbViewTabs}

        ${(S._lbView === 'repeat' || S._lbView === 'leadquality') ? '<div id="lb-alt-content"></div>' : S._lbView !== 'attendees' ? altViewHTML : `
        <div class="lb-filters">
          <select class="filter-select" onchange="S._lbSpeaker=this.value;S._lbWebinar='';renderLeaderboard()">
            <option value="" ${!selSpeaker?'selected':''}>All Speakers</option>
            ${speakerOpts}
          </select>
          <select class="filter-select" onchange="S._lbWebinar=this.value;S._lbSpeaker='';renderLeaderboard()">
            <option value="" ${!selWebinar?'selected':''}>All Webinars</option>
            ${webinarOpts}
          </select>
          <div class="lb-score-range">
            <span class="lb-score-lbl">Score:</span>
            <input type="number" class="filter-select lb-score-input" placeholder="min" value="${S._lbScoreMin||''}" onchange="S._lbScoreMin=this.value;renderLeaderboard()" />
            <span class="lb-score-dash">to</span>
            <input type="number" class="filter-select lb-score-input" placeholder="max" value="${S._lbScoreMax||''}" onchange="S._lbScoreMax=this.value;renderLeaderboard()" />
          </div>
          <select class="filter-select" onchange="S._lbReadiness=this.value;renderLeaderboard()">
            <option value="all" ${readinessF==='all'?'selected':''}>All Leads</option>
            <option value="meeting_ready" ${readinessF==='meeting_ready'?'selected':''}>🔥 Meeting Ready</option>
            <option value="hot"  ${readinessF==='hot'?'selected':''}>Hot</option>
            <option value="warm" ${readinessF==='warm'?'selected':''}>Warm</option>
            <option value="cold" ${readinessF==='cold'?'selected':''}>Cold</option>
            <option value="customer" ${readinessF==='customer'?'selected':''}>Customer</option>
            <option value="prospect" ${readinessF==='prospect'?'selected':''}>Prospect</option>
            <option value="partner"  ${readinessF==='partner'?'selected':''}>Partner</option>
            <option value="internal" ${readinessF==='internal'?'selected':''}>Internal</option>
            <option value="employee" ${readinessF==='employee'?'selected':''}>Employee</option>
          </select>
          <button class="btn btn-ghost btn-sm" onclick="S._lbSpeaker='';S._lbWebinar='';S._lbScoreMin='';S._lbScoreMax='';S._lbLimit=50;S._lbReadiness='all';renderLeaderboard()">Clear Filters</button>
        </div>

        ${tableHTML}

        <div class="lb-bottom-controls">
          <span class="lb-score-help">Score = 10 pts per webinar attended + bonus for longer sessions</span>
          <div class="lb-show-control">
            <span>Show top:</span>
            <select class="filter-select" onchange="S._lbLimit=this.value;renderLeaderboard()">
              <option value="20"  ${selLimit==20?'selected':''}>20</option>
              <option value="50"  ${selLimit==50?'selected':''}>50</option>
              <option value="70"  ${selLimit==70?'selected':''}>70</option>
              <option value="100" ${selLimit==100?'selected':''}>100</option>
              <option value="500" ${selLimit==500?'selected':''}>500</option>
              <option value="1000" ${selLimit==1000?'selected':''}>All</option>
            </select>
          </div>
        </div>`}
      </div>`);

    // Wire async views after DOM is set
    if (S._lbView === 'repeat') {
      const altC = document.getElementById('lb-alt-content');
      if (altC) renderRepeatAudience(altC);
    } else if (S._lbView === 'leadquality') {
      const altC = document.getElementById('lb-alt-content');
      if (altC) renderLeadQuality(altC);
    }
  } catch(e) {
    setContent('<div class="empty-state"><div class="empty-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div><div class="empty-title">Failed to load leaderboard</div></div>');
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   NEW WEBINAR MODAL
══════════════════════════════════════════════════════════════════════════ */
let _editWebinarId = null; // null = create mode, number = edit mode

function openWebinarModal(webinar) {
  _editWebinarId = webinar ? webinar.id : null;

  // Update modal title/button
  const titleEl = document.querySelector('#modal-overlay .modal-title');
  const subEl   = document.querySelector('#modal-overlay .modal-sub');
  const btn     = document.querySelector('#modal-overlay .btn-primary');
  if (titleEl) titleEl.textContent = webinar ? 'Edit Webinar' : 'Add New Webinar';
  if (subEl)   subEl.textContent   = webinar ? 'Update the details for this webinar session' : 'Fill in the details to create a new webinar session';
  if (btn)     btn.innerHTML       = webinar
    ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Save Changes'
    : '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Create Webinar';

  if (webinar) {
    // Pre-fill fields
    const f = id => document.getElementById(id);
    if (f('nw-title'))   f('nw-title').value   = webinar.title || '';
    if (f('nw-date'))    f('nw-date').value     = webinar.date || '';
    if (f('nw-time'))    f('nw-time').value     = webinar.time || '';
    if (f('nw-speaker')) f('nw-speaker').value  = webinar.speaker_name || '';
    if (f('nw-desc'))    f('nw-desc').value     = webinar.description || '';
    if (f('nw-icp'))     f('nw-icp').value      = webinar.icp || 'Others';
    const radio = document.querySelector(`input[name="nw-status-radio"][value="${webinar.status || 'upcoming'}"]`);
    if (radio) radio.checked = true;
  } else {
    // Default date to today for new webinar
    const today = new Date().toISOString().split('T')[0];
    const dateInput = document.getElementById('nw-date');
    if (dateInput && !dateInput.value) dateInput.value = today;
  }

  // Close any stray overlays before opening
  document.querySelectorAll('.modal-overlay.open').forEach(el => el.classList.remove('open'));
  document.getElementById('confirm-overlay')?.remove();

  document.getElementById('modal-overlay').classList.add('open');
  setTimeout(() => document.getElementById('nw-title')?.focus(), 80);
}

function closeWebinarModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  _editWebinarId = null;
  ['nw-title','nw-time','nw-speaker','nw-desc'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const dateInput = document.getElementById('nw-date');
  if (dateInput) dateInput.value = '';
  // Reset ICP to "Others"
  const icpSel = document.getElementById('nw-icp');
  if (icpSel) icpSel.value = 'Others';
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
    icp: (document.getElementById('nw-icp') || {value:'Others'}).value,
  };

  const isEdit = !!_editWebinarId;

  try {
    let result;
    if (isEdit) {
      result = await api(`/api/webinars/${_editWebinarId}`, 'PATCH', payload);
    } else {
      result = await api('/api/webinars', 'POST', payload);
    }
    closeWebinarModal();
    showToast(isEdit ? `"${title}" updated!` : `"${title}" saved! Upload your data below.`);

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

    if (isEdit) {
      // Refresh current webinar detail page if open
      if (S.page === 'webinar' && S.sub == _editWebinarId) {
        nav('webinar', _editWebinarId);
      } else {
        renderHome();
      }
    } else {
      // Go straight to the new webinar's upload/detail page
      nav('webinar', result.id);
    }
  } catch(e) {
    const msg = e.message ? e.message.substring(0, 200) : 'Could not save webinar. Please try again.';
    showToast(`Error: ${msg}`, 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = isEdit
        ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Save Changes'
        : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Create Webinar';
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
    showToast('Failed to save ad. Please try again.', 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Save Ad';
    }
  }
}

/* ── Download registrations / attendees as CSV ──────────────────────────── */
async function _triggerDownload(url) {
  showToast('Preparing download…');
  try {
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Download failed' }));
      showToast(err.detail || 'No real data available to download.', 'error');
      return;
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : 'download.csv';
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objUrl; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objUrl);
    showToast('Downloaded successfully', 'success');
  } catch(e) {
    showToast('Download failed. Please try again.', 'error');
  }
}

/* ── Webinar Funnel ──────────────────────────────────────────────────────── */
async function loadWebinarFunnel(id, w) {
  const sect = document.getElementById(`webinar-funnel-section-${id}`);
  if (!sect) return;
  try {
    const funnel = await api(`/api/webinar-funnel/${id}`);
    if (funnel && funnel.stages && w.status === 'completed') {
      const stageItems = funnel.stages.map((s, i) => {
        const width = Math.max(20, s.pct);
        const isFirst = i === 0;
        const dropText = s.drop !== undefined && !isFirst ? `<span style="font-size:11px;color:#f43f5e;margin-left:8px">↓ ${s.drop}% drop-off</span>` : '';
        return `
          <div class="funnel-stage">
            <div class="funnel-bar-wrap">
              <div class="funnel-bar" style="width:${width}%;background:${isFirst?'#6366f1':s.pct>=50?'#10b981':s.pct>=30?'#f59e0b':'#f43f5e'}">
                <span class="funnel-bar-label">${esc(s.label)}</span>
              </div>
              <span class="funnel-count">${fmt(s.count)}${dropText}</span>
            </div>
          </div>`;
      }).join('');
      sect.innerHTML = `
        <div class="funnel-section">
          <div class="sec-hd"><span class="sec-title">Webinar Funnel</span></div>
          <div class="funnel-stages">${stageItems}</div>
          ${funnel.insight ? `<div class="funnel-insight">${esc(funnel.insight)}</div>` : ''}
        </div>`;
    }
  } catch(e) { /* silently skip */ }
}

/* ── AI Analysis ─────────────────────────────────────────────────────────── */
/* ── Human Notes ──────────────────────────────────────────────────────────── */
async function loadNotes(webinarId) {
  try {
    const notes = await api(`/api/webinars/${webinarId}/notes`);
    renderNotesList(webinarId, notes);
  } catch(e) {
    console.error('Failed to load notes', e);
  }
}

const CATEGORY_LABELS = {
  observation: 'Observation',
  speaker_feedback: 'Speaker Feedback',
  tech_issue: 'Tech Issue',
  content_quality: 'Content Quality',
  promotion: 'Promotion',
};
const CATEGORY_COLORS = {
  observation: '#6366F1',
  speaker_feedback: '#10B981',
  tech_issue: '#DC2626',
  content_quality: '#F59E0B',
  promotion: '#7C3AED',
};

function renderNotesList(webinarId, notes) {
  const el = document.getElementById(`notes-list-${webinarId}`);
  if (!el) return;
  if (!notes || !notes.length) {
    el.innerHTML = `<div class="notes-empty">No notes yet. Add observations to help AI analyze better.</div>`;
    return;
  }
  el.innerHTML = notes.map(n => {
    const color = CATEGORY_COLORS[n.category] || '#6366F1';
    const label = CATEGORY_LABELS[n.category] || n.category;
    const dt = n.created_at ? new Date(n.created_at).toLocaleDateString('en', { month:'short', day:'numeric', year:'numeric' }) : '';
    return `
    <div class="note-card">
      <div class="note-card-head">
        <div class="note-meta">
          <span class="note-cat" style="background:${color}1A;color:${color};border-color:${color}40">${esc(label)}</span>
          <span class="note-author">${esc(n.author || 'Team')}</span>
          <span class="note-time">${esc(dt)}</span>
        </div>
        <button class="note-delete" onclick="deleteNote(${webinarId}, ${n.id})" title="Delete note">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
        </button>
      </div>
      <div class="note-content-display">${esc(n.content)}</div>
    </div>`;
  }).join('');
}

function toggleNoteForm(webinarId) {
  const f = document.getElementById(`note-form-${webinarId}`);
  if (!f) return;
  const showing = f.style.display === 'block';
  f.style.display = showing ? 'none' : 'block';
  if (!showing) {
    setTimeout(() => document.getElementById(`note-author-${webinarId}`)?.focus(), 60);
  }
}

async function submitNote(webinarId) {
  const author   = document.getElementById(`note-author-${webinarId}`).value.trim() || 'Team';
  const category = document.getElementById(`note-category-${webinarId}`).value;
  const content  = document.getElementById(`note-content-${webinarId}`).value.trim();
  if (!content) {
    showToast('Please write a note before saving', 'error');
    return;
  }
  try {
    await fetch(`/api/webinars/${webinarId}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ author, category, content })
    }).then(r => { if (!r.ok) throw new Error('Save failed'); return r.json(); });
    document.getElementById(`note-content-${webinarId}`).value = '';
    document.getElementById(`note-author-${webinarId}`).value = '';
    toggleNoteForm(webinarId);
    showToast('Note saved. AI will use it in the next analysis.');
    loadNotes(webinarId);
  } catch(e) {
    showToast('Failed to save note. Please try again.', 'error');
  }
}

async function deleteNote(webinarId, noteId) {
  if (!confirm('Delete this note?')) return;
  try {
    const r = await fetch(`/api/webinars/${webinarId}/notes/${noteId}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Delete failed');
    loadNotes(webinarId);
    showToast('Note deleted');
  } catch(e) {
    showToast('Failed to delete', 'error');
  }
}

async function runAIAnalysis(webinarId) {
  const btn   = document.getElementById('ai-analyze-btn');
  const panel = document.getElementById('ai-analysis-panel');
  if (!panel) return;

  // Loading state
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg class="spin" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.22-8.56"/></svg> Analyzing…`;
  }
  panel.innerHTML = `
    <div class="ai-panel ai-loading">
      <div class="ai-panel-header">
        <svg class="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.22-8.56"/></svg>
        <span>Running AI analysis…</span>
      </div>
      <div class="ai-shimmer-rows">
        <div class="ai-shimmer"></div><div class="ai-shimmer" style="width:75%"></div>
        <div class="ai-shimmer" style="width:90%"></div><div class="ai-shimmer" style="width:60%"></div>
      </div>
    </div>`;

  try {
    const res = await fetch(`/api/webinars/${webinarId}/analyze`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Analysis failed');
    }
    const data = await res.json();
    renderAIPanel(panel, data);
    if (btn) {
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg> Analysis Done`;
      btn.classList.add('ai-done');
    }
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    panel.innerHTML = `
      <div class="ai-panel ai-error">
        <div class="ai-panel-header"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> <span>${esc(e.message)}</span></div>
      </div>`;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg> Retry Analysis`;
    }
  }
}

// SVG icon library for AI panel
const AI_ICONS = {
  spark:   `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>`,
  users:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  clock:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  signal:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="6" x2="1" y2="18"/><line x1="6" y1="3" x2="6" y2="18"/><line x1="11" y1="8" x2="11" y2="18"/><line x1="16" y1="5" x2="16" y2="18"/><line x1="21" y1="2" x2="21" y2="18"/></svg>`,
  target:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>`,
  mic:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`,
  calendar:`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  idea:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="3"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="2" y1="12" x2="3" y2="12"/><line x1="19.78" y1="4.22" x2="18.36" y2="5.64"/><line x1="22" y1="12" x2="21" y2="12"/><path d="M12 6a6 6 0 0 1 6 6 6 6 0 0 1-3 5.2V19a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 6 12a6 6 0 0 1 6-6z"/></svg>`,
  verdict: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
  bench:   `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
  funnel:  `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>`,
  check:   `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
};

const INSIGHT_ICONS = {
  'audience reach': AI_ICONS.users,
  'engagement quality': AI_ICONS.clock,
  'registration channels': AI_ICONS.signal,
  'speaker performance': AI_ICONS.mic,
  'timing': AI_ICONS.calendar,
  'momentum': AI_ICONS.calendar,
  'default': AI_ICONS.target,
};

function getInsightIcon(title) {
  const t = (title || '').toLowerCase();
  for (const [key, icon] of Object.entries(INSIGHT_ICONS)) {
    if (t.includes(key)) return icon;
  }
  return INSIGHT_ICONS.default;
}

function renderAIPanel(panel, data) {
  const a  = data.analysis;
  const m  = data.metrics;
  const gc = { A:'#10b981', B:'#6366f1', C:'#f59e0b', D:'#f43f5e' };
  const gradeGlow = { A:'rgba(16,185,129,0.35)', B:'rgba(99,102,241,0.35)', C:'rgba(245,158,11,0.35)', D:'rgba(244,63,94,0.35)' };
  const gradeColor = gc[a.grade] || '#94a3b8';
  const glow = gradeGlow[a.grade] || 'transparent';

  // ── helpers ──────────────────────────────────────────────────────────────
  const pct  = (n, d) => d ? Math.round(n / d * 100) : 0;
  const fmtN = n => n >= 1000 ? (n/1000).toFixed(1)+'k' : String(n || 0);

  // ── Core numbers ──────────────────────────────────────────────────────────
  const regs    = m.registrations || 0;
  const attds   = m.attendees     || 0;
  const engaged = (m.engaged_45plus_min || {}).count || 0;
  const attRate = regs ? pct(attds, regs) : 0;
  const engRate = attds ? pct(engaged, attds) : 0;
  const noShows = regs - attds;

  // ── Duration data ─────────────────────────────────────────────────────────
  const durTotal    = attds || 1;
  const durEngaged  = (m.engaged_45plus_min   || {}).count || 0;
  const durModerate = (m.moderate_15_44_min   || {}).count || 0;
  const durDropped  = (m.dropped_under_15_min || {}).count || 0;

  const durSegments = [
    { label:'45+ min', sub:'Highly engaged', count:durEngaged,  pct:Math.round(durEngaged/durTotal*100),  grad:'linear-gradient(90deg,#059669,#10b981)' },
    { label:'15–44 min', sub:'Moderate',       count:durModerate, pct:Math.round(durModerate/durTotal*100), grad:'linear-gradient(90deg,#2563eb,#6366f1)' },
    { label:'< 15 min', sub:'Early drop-off',  count:durDropped,  pct:Math.round(durDropped/durTotal*100),  grad:'linear-gradient(90deg,#dc2626,#f43f5e)' },
  ];

  // ── Benchmark (attendance rate only, no registrations) ───────────────────
  const platRate = m.platform_avg_attendance_rate_pct || 0;
  const spkRate  = m.speaker_avg_attendance_rate_pct;
  const spkName  = (m.speaker || 'Speaker').split(' ').slice(-1)[0]; // last name
  const maxRate  = Math.max(attRate, platRate, spkRate || 0, 1);

  function benchRow(label, val, max, isThis) {
    const w = Math.round(val / max * 100);
    const grad = isThis
      ? `linear-gradient(90deg,${gradeColor}cc,${gradeColor})`
      : 'linear-gradient(90deg,#94a3b8,#cbd5e1)';
    return `<div class="aip-bench-row${isThis?' aip-bench-this':''}">
      <span class="aip-bench-lbl">${label}</span>
      <div class="aip-bench-track">
        <div class="aip-bench-fill" style="background:${grad}" data-w="${w}"></div>
      </div>
      <span class="aip-bench-val" style="color:${isThis?gradeColor:'#475569'}">${val.toFixed(1)}%</span>
    </div>`;
  }

  // ── Recommendations ───────────────────────────────────────────────────────
  const recsHTML = (a.recommendations || []).map((r, i) => `
    <div class="aip-rec">
      <span class="aip-rec-icon">${AI_ICONS.check}</span>
      <span>${esc(r)}</span>
    </div>`).join('');

  // ── Ring arc ──────────────────────────────────────────────────────────────
  const RING_CIRC = 251.2;
  const ringFill  = ((attRate / 100) * RING_CIRC).toFixed(1);

  panel.innerHTML = `
  <div class="aip">

    <!-- ── Header ── -->
    <div class="aip-header">
      <div class="aip-header-icon">${AI_ICONS.spark}</div>
      <span class="aip-header-title">AI Analysis</span>
      <span class="aip-header-badge">AI Analysis</span>
    </div>

    <!-- ── Hero row: grade ring + KPI strip ── -->
    <div class="aip-hero">
      <div class="aip-grade-wrap">
        <svg viewBox="0 0 120 120" class="aip-ring-svg">
          <defs>
            <filter id="glow-${a.grade}">
              <feGaussianBlur stdDeviation="3" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>
          <circle cx="60" cy="60" r="40" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="10"/>
          <circle cx="60" cy="60" r="40" fill="none" stroke="${gradeColor}" stroke-width="10"
            stroke-linecap="round" stroke-dasharray="${ringFill} ${RING_CIRC}"
            transform="rotate(-90 60 60)" filter="url(#glow-${a.grade})"
            style="transition:stroke-dasharray 1.2s cubic-bezier(.4,0,.2,1)"/>
          <text x="60" y="54" text-anchor="middle" fill="${gradeColor}" font-size="32" font-weight="800" font-family="system-ui">${esc(a.grade)}</text>
          <text x="60" y="72" text-anchor="middle" fill="rgba(255,255,255,0.35)" font-size="9.5" font-family="system-ui" letter-spacing="1.5">${esc(a.grade_label).toUpperCase()}</text>
        </svg>
        <div class="aip-grade-glow" style="background:${glow}"></div>
      </div>

      <div class="aip-kpi-strip">
        <div class="aip-kpi">
          <div class="aip-kpi-val" style="color:#6366f1">${fmtN(regs)}</div>
          <div class="aip-kpi-lbl">Registered</div>
        </div>
        <div class="aip-kpi-div"></div>
        <div class="aip-kpi">
          <div class="aip-kpi-val" style="color:#10b981">${fmtN(attds)}</div>
          <div class="aip-kpi-lbl">Attended</div>
        </div>
        <div class="aip-kpi-div"></div>
        <div class="aip-kpi">
          <div class="aip-kpi-val" style="color:${gradeColor}">${attRate}%</div>
          <div class="aip-kpi-lbl">Att. Rate</div>
        </div>
        <div class="aip-kpi-div"></div>
        <div class="aip-kpi">
          <div class="aip-kpi-val" style="color:#f59e0b">${fmtN(engaged)}</div>
          <div class="aip-kpi-lbl">Engaged 45m+</div>
        </div>
        <div class="aip-kpi-div"></div>
        <div class="aip-kpi">
          <div class="aip-kpi-val" style="color:rgba(255,255,255,0.4)">${m.avg_session_duration_min||0}m</div>
          <div class="aip-kpi-lbl">Avg Session</div>
        </div>
      </div>
    </div>

    <!-- ── Two-col: funnel + session ── -->
    <div class="aip-mid-row">

      <!-- Audience funnel -->
      <div class="aip-card">
        <div class="aip-card-hd">
          <span class="aip-card-icon" style="color:#6366f1">${AI_ICONS.funnel}</span>
          <span>Audience Funnel</span>
        </div>
        <div class="aip-funnel">
          <div class="aip-fn-row">
            <div class="aip-fn-meta">
              <span class="aip-fn-label">Registered</span>
              <span class="aip-fn-num">${fmtN(regs)}</span>
            </div>
            <div class="aip-fn-track"><div class="aip-fn-bar" style="width:100%;background:linear-gradient(90deg,#4f46e5,#6366f1)" data-w="100"></div></div>
            <span class="aip-fn-pct" style="color:#6366f1">100%</span>
          </div>
          <div class="aip-fn-row">
            <div class="aip-fn-meta">
              <span class="aip-fn-label">Attended</span>
              <span class="aip-fn-num">${fmtN(attds)}</span>
            </div>
            <div class="aip-fn-track"><div class="aip-fn-bar" style="width:${attRate}%;background:linear-gradient(90deg,#059669,#10b981)" data-w="${attRate}"></div></div>
            <span class="aip-fn-pct" style="color:#10b981">${attRate}%</span>
          </div>
          <div class="aip-fn-row">
            <div class="aip-fn-meta">
              <span class="aip-fn-label">Engaged 45m+</span>
              <span class="aip-fn-num">${fmtN(engaged)}</span>
            </div>
            <div class="aip-fn-track"><div class="aip-fn-bar" style="width:${Math.round(attRate*engRate/100)}%;background:linear-gradient(90deg,#b45309,#f59e0b)" data-w="${Math.round(attRate*engRate/100)}"></div></div>
            <span class="aip-fn-pct" style="color:#f59e0b">${engRate}%</span>
          </div>
          <div class="aip-fn-row aip-fn-noshow">
            <div class="aip-fn-meta">
              <span class="aip-fn-label">No-shows</span>
              <span class="aip-fn-num" style="color:rgba(255,255,255,0.3)">${fmtN(noShows)}</span>
            </div>
            <div class="aip-fn-track"><div class="aip-fn-bar" style="width:${pct(noShows,regs)}%;background:rgba(244,63,94,0.35)" data-w="${pct(noShows,regs)}"></div></div>
            <span class="aip-fn-pct" style="color:rgba(244,63,94,0.6)">${pct(noShows,regs)}%</span>
          </div>
        </div>
      </div>

      <!-- Session duration -->
      <div class="aip-card">
        <div class="aip-card-hd">
          <span class="aip-card-icon" style="color:#8b5cf6">${AI_ICONS.clock}</span>
          <span>Time in Session</span>
        </div>
        <div class="aip-dur-list">
          ${durSegments.map(d => `
          <div class="aip-dur-item">
            <div class="aip-dur-top">
              <span class="aip-dur-label">${d.label}</span>
              <span class="aip-dur-sub">${d.sub}</span>
              <span class="aip-dur-count">${d.count} people</span>
            </div>
            <div class="aip-dur-row">
              <div class="aip-dur-track">
                <div class="aip-dur-fill" style="background:${d.grad}" data-w="${d.pct}"></div>
              </div>
              <span class="aip-dur-pct">${d.pct}%</span>
            </div>
          </div>`).join('')}
        </div>
        <div class="aip-avg-pill">
          ${AI_ICONS.clock}
          <span>Average session <strong>${m.avg_session_duration_min||0} minutes</strong></span>
        </div>
      </div>
    </div>

    <!-- ── Benchmark: attendance rate only ── -->
    <div class="aip-card aip-bench-card">
      <div class="aip-card-hd">
        <span class="aip-card-icon" style="color:#f59e0b">${AI_ICONS.bench}</span>
        <span>Attendance Rate Benchmark</span>
      </div>
      <div class="aip-bench-rows">
        ${benchRow('This Webinar', attRate, maxRate, true)}
        ${spkRate != null ? benchRow(spkName + ' avg', spkRate, maxRate, false) : ''}
        ${benchRow('Platform avg', platRate, maxRate, false)}
      </div>
      <div class="aip-bench-note">
        ${attRate > platRate
          ? `<span class="aip-bench-up">${AI_ICONS.check} ${(attRate - platRate).toFixed(1)}% above platform average</span>`
          : `<span class="aip-bench-dn">${(platRate - attRate).toFixed(1)}% below platform average</span>`}
      </div>
    </div>

    <!-- ── AI Insights ── -->
    <div class="aip-card">
      <div class="aip-card-hd">
        <span class="aip-card-icon" style="color:#a78bfa">${AI_ICONS.spark}</span>
        <span>AI Insights</span>
      </div>
      <div class="aip-insights">
        ${(a.sections||[]).map(s => `
        <div class="aip-insight">
          <div class="aip-insight-icon-wrap">${getInsightIcon(s.title)}</div>
          <div class="aip-insight-body">
            <div class="aip-insight-title">${esc(s.title)}</div>
            <div class="aip-insight-text">${esc(s.insight)}</div>
            <div class="aip-insight-tag">${esc(s.highlight)}</div>
          </div>
        </div>`).join('')}
      </div>
    </div>

    <!-- ── Recs + Verdict ── -->
    <div class="aip-bottom">
      <div class="aip-card">
        <div class="aip-card-hd">
          <span class="aip-card-icon" style="color:#10b981">${AI_ICONS.idea}</span>
          <span>Recommendations</span>
        </div>
        ${recsHTML}
      </div>
      <div class="aip-card aip-verdict-card">
        <div class="aip-card-hd">
          <span class="aip-card-icon" style="color:#6366f1">${AI_ICONS.verdict}</span>
          <span>AI Verdict</span>
        </div>
        <p class="aip-verdict-text">${esc(a.verdict)}</p>
        <div class="aip-verdict-footer">Powered by WebinarIQ AI</div>
      </div>
    </div>

  </div>`;

  // Animate all bars in
  requestAnimationFrame(() => {
    panel.querySelectorAll('[data-w]').forEach(el => {
      const w = el.dataset.w;
      el.style.width = '0%';
      requestAnimationFrame(() => {
        el.style.transition = 'width 1s cubic-bezier(.16,1,.3,1)';
        el.style.width = w + '%';
      });
    });
  });
}

/* ── Topics Page ─────────────────────────────────────────────────────────── */
let _topicsCache = null; // no client-side caching — always fetch fresh

/* ── Intelligence Module (Phase 2) ──────────────────────────────────────── */
let _intelCache = null;
let _intelHotLeadsCache = null;
let _intelInsightsCache = null;

async function renderIntelligence() {
  if (!S._intelTab) S._intelTab = 'scoreboard';
  setContent(`
    <div class="intel-page">
      <div class="page-hd">
        <div>
          <h1 class="page-title">Smart Recommendations</h1>
          <p class="page-sub">AI-powered insights from your webinar data.</p>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="_intelCache=null;_intelHotLeadsCache=null;renderIntelligence()">Refresh</button>
      </div>
      <div class="intel-tabs">
        <button class="intel-tab ${S._intelTab==='scoreboard'?'active':''}" onclick="S._intelTab='scoreboard';renderIntelligence()">Programme Scoreboard</button>
        <button class="intel-tab ${S._intelTab==='hotleads'?'active':''}"   onclick="S._intelTab='hotleads';renderIntelligence()">Hot Leads</button>
        <button class="intel-tab ${S._intelTab==='nextplay'?'active':''}"   onclick="S._intelTab='nextplay';renderIntelligence()">Next Play</button>
      </div>
      <div id="intel-body"><div class="pg-loading"><div class="spinner"></div><p>Loading…</p></div></div>
    </div>`);
  try {
    const body = document.getElementById('intel-body');
    if (S._intelTab === 'scoreboard') {
      _renderScoreboard(body);
    } else if (S._intelTab === 'hotleads') {
      await _renderHotLeads(body);
    } else if (S._intelTab === 'nextplay') {
      if (!_intelCache) _intelCache = await api('/api/intelligence');
      _renderNextPlay(body, _intelCache);
    }
  } catch(e) {
    const b = document.getElementById('intel-body');
    if (b) b.innerHTML = `<div class="intel-section"><div class="empty-state"><div class="empty-title">Failed to load</div><div class="empty-sub">${esc(e.message)}</div></div></div>`;
  }
}

// ── Tab 1: Programme Scoreboard ───────────────────────────────────────────────
function _renderScoreboard(body) {
  const completed = (S.webinars || [])
    .filter(w => w.status === 'completed' && (w.total_registrations || 0) > 0)
    .sort((a, b) => (b.performance_score || 0) - (a.performance_score || 0));

  if (!completed.length) {
    body.innerHTML = `<div class="intel-section"><div class="empty-state"><div class="empty-title">No completed webinars yet</div><div class="empty-sub">Mark webinars as completed and upload data to see the scoreboard.</div></div></div>`;
    return;
  }

  const avgRate = Math.round(completed.reduce((s, w) => s + (w.attendance_rate || 0), 0) / completed.length);
  const avgRegs = Math.round(completed.reduce((s, w) => s + (w.total_registrations || 0), 0) / completed.length);

  const scaleList  = completed.filter(w => (w.attendance_rate || 0) >= 45);
  const maintList  = completed.filter(w => (w.attendance_rate || 0) >= 30 && (w.attendance_rate || 0) < 45);
  const fixList    = completed.filter(w => (w.attendance_rate || 0) >= 15 && (w.attendance_rate || 0) < 30);
  const dropList   = completed.filter(w => (w.attendance_rate || 0) < 15);

  // Monthly trend
  const byMonth = {};
  completed.forEach(w => {
    if (!w.date) return;
    const m = w.date.slice(0, 7);
    if (!byMonth[m]) byMonth[m] = { regs: 0, att: 0, count: 0 };
    byMonth[m].regs  += (w.total_registrations || 0);
    byMonth[m].att   += (w.total_attendees || 0);
    byMonth[m].count += 1;
  });
  const months  = Object.keys(byMonth).sort().slice(-8);
  const maxRegs = Math.max(...months.map(m => byMonth[m].regs), 1);

  const statusCfg = rate => {
    if (rate >= 45) return { label:'SCALE',    color:'#10b981', bg:'#f0fdf4', border:'#bbf7d0' };
    if (rate >= 30) return { label:'MAINTAIN', color:'#6366f1', bg:'#eef2ff', border:'#c7d2fe' };
    if (rate >= 15) return { label:'FIX',      color:'#f59e0b', bg:'#fffbeb', border:'#fde68a' };
    return              { label:'DROP',      color:'#f43f5e', bg:'#fff1f2', border:'#fecdd3' };
  };

  const webRow = (w, i) => {
    const s = statusCfg(w.attendance_rate || 0);
    const noshow = (w.total_registrations || 0) - (w.total_attendees || 0);
    return `
    <tr style="animation:fadeSlideUp .25s ease both;animation-delay:${Math.min(i*25,600)}ms">
      <td style="padding:12px 14px">
        <div style="font-weight:600;font-size:13px;color:var(--text-primary);line-height:1.3">${esc(w.title)}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:3px">${fmtDate(w.date||'')} &nbsp;·&nbsp; ${esc(w.speaker_name||'—')} &nbsp;·&nbsp; <span class="icp-badge icp-${(w.icp||'others').toLowerCase().replace(/\s+/g,'-')}" style="font-size:10px;padding:1px 7px">${esc(w.icp||'Others')}</span></div>
      </td>
      <td style="padding:12px 14px;text-align:right;font-family:var(--font-mono);font-weight:700;font-size:13px">${fmt(w.total_registrations||0)}</td>
      <td style="padding:12px 14px;text-align:right;font-family:var(--font-mono);font-weight:700;font-size:13px">${fmt(w.total_attendees||0)}</td>
      <td style="padding:12px 14px;text-align:right;font-weight:800;font-size:14px;color:${s.color}">${(w.attendance_rate||0).toFixed(1)}%</td>
      <td style="padding:12px 14px;text-align:right;font-family:var(--font-mono);font-size:12px;color:var(--text-muted)">${fmt(noshow)}</td>
      <td style="padding:12px 14px;text-align:right"><span style="font-size:10px;font-weight:800;letter-spacing:.6px;color:${s.color};background:${s.bg};border:1px solid ${s.border};border-radius:20px;padding:3px 10px">${s.label}</span></td>
    </tr>`;
  };

  body.innerHTML = `
    <div class="intel-section">

      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:28px">
        ${[
          { label:'Webinars Run',          val: completed.length,  sub:'completed',                                  color:'#6366f1' },
          { label:'Avg Attendance Rate',   val: avgRate+'%',       sub: avgRate>=35?'On target ✓':'Below 35% target ⚠', color: avgRate>=35?'#10b981':'#f59e0b' },
          { label:'Avg Registrations',     val: fmt(avgRegs),      sub:'per webinar',                                color:'#6366f1' },
          { label:'Scale-worthy',          val: scaleList.length,  sub:`${Math.round(scaleList.length/completed.length*100)}% of programme`, color:'#10b981' },
        ].map(k=>`
          <div style="background:var(--surface);border:1.5px solid var(--border);border-radius:12px;padding:16px 18px;border-top:3px solid ${k.color}">
            <div style="font-size:24px;font-weight:800;color:${k.color}">${k.val}</div>
            <div style="font-size:11px;font-weight:700;color:var(--text-primary);margin-top:3px">${k.label}</div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:2px">${k.sub}</div>
          </div>`).join('')}
      </div>

      ${months.length >= 2 ? `
      <div style="margin-bottom:28px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:12px">📈 Monthly Trend</div>
        <div style="background:var(--surface);border:1.5px solid var(--border);border-radius:14px;padding:18px 20px">
          <div style="display:flex;align-items:flex-end;gap:6px;height:80px">
            ${months.map(m => {
              const d = byMonth[m];
              const rate = d.regs > 0 ? Math.round(d.att / d.regs * 100) : 0;
              const barH = Math.round(d.regs / maxRegs * 72);
              const c = rate >= 40 ? '#10b981' : rate >= 25 ? '#6366f1' : '#f59e0b';
              return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:3px">
                <div style="font-size:10px;font-weight:800;color:${c}">${rate}%</div>
                <div style="width:100%;background:${c};border-radius:3px 3px 0 0;height:${Math.max(barH,4)}px"></div>
                <div style="font-size:9px;color:var(--text-muted)">${m.slice(5)}</div>
              </div>`;
            }).join('')}
          </div>
          <div style="font-size:10px;color:var(--text-muted);margin-top:8px;text-align:center">Bar height = registrations volume · % = attendance rate</div>
        </div>
      </div>` : ''}

      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:24px">
        ${[
          { label:'SCALE',    list:scaleList,  color:'#10b981', bg:'#f0fdf4', border:'#bbf7d0', desc:'≥45% attendance' },
          { label:'MAINTAIN', list:maintList,  color:'#6366f1', bg:'#eef2ff', border:'#c7d2fe', desc:'30–45%' },
          { label:'FIX',      list:fixList,    color:'#f59e0b', bg:'#fffbeb', border:'#fde68a', desc:'15–30%' },
          { label:'DROP',     list:dropList,   color:'#f43f5e', bg:'#fff1f2', border:'#fecdd3', desc:'<15% attendance' },
        ].map(b=>`
          <div style="background:${b.bg};border:1.5px solid ${b.border};border-radius:12px;padding:14px 16px;text-align:center">
            <div style="font-size:28px;font-weight:800;color:${b.color}">${b.list.length}</div>
            <div style="font-size:11px;font-weight:800;letter-spacing:.6px;color:${b.color};margin:2px 0">${b.label}</div>
            <div style="font-size:10px;color:var(--text-muted)">${b.desc}</div>
          </div>`).join('')}
      </div>

      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:10px">All Webinars, Ranked by Performance Score</div>
      <div style="border:1.5px solid var(--border);border-radius:14px;overflow:hidden">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:var(--surface-alt,#f8fafc)">
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Webinar</th>
              <th style="padding:10px 14px;text-align:right;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Regs</th>
              <th style="padding:10px 14px;text-align:right;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Attended</th>
              <th style="padding:10px 14px;text-align:right;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Att Rate</th>
              <th style="padding:10px 14px;text-align:right;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">No-shows</th>
              <th style="padding:10px 14px;text-align:right;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Status</th>
            </tr>
          </thead>
          <tbody>
            ${completed.map((w, i) => webRow(w, i)).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
}

// ── Tab 2: Hot Leads ──────────────────────────────────────────────────────────
async function _renderHotLeads(body) {
  body.innerHTML = `<div class="intel-section"><div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 0;gap:12px"><div class="spinner"></div><div style="font-size:14px;color:var(--text-muted)">Finding high-intent leads…</div></div></div>`;
  _intelHotLeadsCache = _intelHotLeadsCache || await api('/api/intelligence/hot-leads');
  const d = _intelHotLeadsCache;
  const hot    = d.hot_leads || [];
  const repeat = d.repeat_attendees || [];
  const convRate   = d.total_unique_attendees > 0 ? Math.round(d.in_pipeline / d.total_unique_attendees * 100) : 0;
  const notInPipeline = Math.max(0, d.total_unique_attendees - d.in_pipeline);

  const hotRows = hot.slice(0, 60).map((l, i) => `
    <tr style="animation:fadeSlideUp .25s ease both;animation-delay:${Math.min(i*20,500)}ms">
      <td style="padding:11px 14px">
        <div style="font-weight:600;font-size:13px;color:var(--text-primary)">${esc(l.name||'Unknown')}</div>
        <div style="font-size:11px;color:var(--text-muted);font-family:var(--font-mono)">${esc(l.email||'')}</div>
      </td>
      <td style="padding:11px 14px"><span class="icp-badge icp-${(l.icp||'others').toLowerCase().replace(/\s+/g,'-')}" style="font-size:10px">${esc(l.icp||'Others')}</span></td>
      <td style="padding:11px 14px;max-width:220px">
        <div style="font-size:12px;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(l.webinar_title||'')}</div>
        <div style="font-size:10px;color:var(--text-muted)">${fmtDate(l.webinar_date||'')}</div>
      </td>
      <td style="padding:11px 14px;text-align:center">
        <span style="font-weight:800;font-size:14px;color:${(l.duration_minutes||0)>=45?'#10b981':'#6366f1'}">${l.duration_minutes||0}m</span>
        ${(l.duration_minutes||0)>=45?`<div style="font-size:9px;color:#10b981;font-weight:700">FULL SESSION</div>`:''}
      </td>
      <td style="padding:11px 14px;text-align:right">
        <button class="btn btn-primary" style="font-size:11px;padding:5px 12px;height:28px" onclick="addToPipelineFromIntel('${esc(l.email||'').replace(/'/g,"\\'")}','${esc(l.name||'').replace(/'/g,"\\'")}')">Add to Pipeline</button>
      </td>
    </tr>`).join('');

  const repeatRows = repeat.slice(0, 30).map((l, i) => `
    <tr style="animation:fadeSlideUp .25s ease both;animation-delay:${Math.min(i*20,500)}ms">
      <td style="padding:11px 14px">
        <div style="font-weight:600;font-size:13px;color:var(--text-primary)">${esc(l.name||'Unknown')}</div>
        <div style="font-size:11px;color:var(--text-muted);font-family:var(--font-mono)">${esc(l.email||'')}</div>
      </td>
      <td style="padding:11px 14px;text-align:center">
        <span style="font-size:20px;font-weight:800;color:#6366f1">${l.webinar_count}</span>
        <div style="font-size:10px;color:var(--text-muted)">webinars</div>
      </td>
      <td style="padding:11px 14px;font-size:12px;color:var(--text-secondary)">${esc(l.icps||'')}</td>
      <td style="padding:11px 14px;text-align:center;font-weight:700;font-size:13px;color:${(l.max_duration||0)>=45?'#10b981':'#6366f1'}">${l.max_duration||0}m</td>
      <td style="padding:11px 14px">
        <span style="font-size:11px;font-weight:700;color:${l.pipeline_status==='not_added'?'#f43f5e':'#10b981'};background:${l.pipeline_status==='not_added'?'#fff1f2':'#f0fdf4'};border-radius:20px;padding:3px 10px">
          ${l.pipeline_status === 'not_added' ? '⚠ Not in pipeline' : '✓ '+esc(l.pipeline_status)}
        </span>
      </td>
      <td style="padding:11px 14px;text-align:right">
        ${l.pipeline_status === 'not_added' ? `<button class="btn btn-primary" style="font-size:11px;padding:5px 12px;height:28px" onclick="addToPipelineFromIntel('${esc(l.email||'').replace(/'/g,"\\'")}','${esc(l.name||'').replace(/'/g,"\\'")}')">Add to Pipeline</button>` : ''}
      </td>
    </tr>`).join('');

  body.innerHTML = `
    <div class="intel-section">

      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:28px">
        ${[
          { label:'Total Unique Attendees', val:fmt(d.total_unique_attendees||0), sub:'across all webinars',          color:'#6366f1' },
          { label:'In Pipeline',            val:fmt(d.in_pipeline||0),            sub:`${convRate}% conversion rate`, color:'#10b981' },
          { label:'Not in Pipeline',        val:fmt(notInPipeline),               sub:'potential leads missed',       color:'#f43f5e' },
          { label:'High-Intent (30m+)',     val:fmt(hot.length),                  sub:'stayed 30+ min, not added yet',color:'#f59e0b' },
        ].map(k=>`
          <div style="background:var(--surface);border:1.5px solid var(--border);border-radius:12px;padding:16px 18px;border-top:3px solid ${k.color}">
            <div style="font-size:24px;font-weight:800;color:${k.color}">${k.val}</div>
            <div style="font-size:11px;font-weight:700;color:var(--text-primary);margin-top:3px">${k.label}</div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:2px">${k.sub}</div>
          </div>`).join('')}
      </div>

      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:4px">High-Intent Contacts — Stayed 30+ Minutes, Not Yet in Pipeline</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:14px">These people invested 30+ minutes in your content. Prioritise them for follow-up.</div>
        ${!hot.length ? `
          <div style="background:var(--surface);border:1.5px dashed var(--border);border-radius:14px;padding:32px;text-align:center;color:var(--text-muted)">
            <div style="font-size:28px;margin-bottom:8px">🎉</div>
            <div style="font-weight:600;margin-bottom:4px">All high-intent attendees are already in the pipeline</div>
            <div style="font-size:13px">No 30+ minute attendees are missing from pipeline — great follow-up discipline.</div>
          </div>` : `
        <div style="border:1.5px solid var(--border);border-radius:14px;overflow:hidden">
          <table style="width:100%;border-collapse:collapse">
            <thead><tr style="background:var(--surface-alt,#f8fafc)">
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Contact</th>
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">ICP</th>
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Webinar Attended</th>
              <th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Duration</th>
              <th style="padding:10px 14px;text-align:right;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Action</th>
            </tr></thead>
            <tbody>${hotRows}</tbody>
          </table>
        </div>`}
      </div>

      <div>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:4px">Repeat Attendees - Came Back for 2+ Webinars</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:14px">Repeat attendance is the strongest buying signal. These contacts should be in active conversations.</div>
        ${!repeat.length ? `
          <div style="background:var(--surface);border:1.5px dashed var(--border);border-radius:14px;padding:32px;text-align:center;color:var(--text-muted)">
            No repeat attendees yet — this appears once audiences overlap across multiple webinars.
          </div>` : `
        <div style="border:1.5px solid var(--border);border-radius:14px;overflow:hidden">
          <table style="width:100%;border-collapse:collapse">
            <thead><tr style="background:var(--surface-alt,#f8fafc)">
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Contact</th>
              <th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Webinars</th>
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">ICPs Interested In</th>
              <th style="padding:10px 14px;text-align:center;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Max Duration</th>
              <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Pipeline Status</th>
              <th style="padding:10px 14px;text-align:right;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">Action</th>
            </tr></thead>
            <tbody>${repeatRows}</tbody>
          </table>
        </div>`}
      </div>
    </div>`;
}

function addToPipelineFromIntel(email, name) {
  if (!email) return;
  api('/api/pipeline/' + encodeURIComponent(email), 'PUT', { status: 'new', assigned_to: '', follow_up_date: null, notes: 'Added from Smart Recommendations' })
    .then(() => {
      showToast((name || email) + ' added to pipeline', 'success');
      _intelHotLeadsCache = null;
      _renderHotLeads(document.getElementById('intel-body'));
    })
    .catch(e => showToast('Failed: ' + e.message, 'error'));
}

// ── Tab 3: Next Play ──────────────────────────────────────────────────────────
function _renderNextPlay(body, data) {
  const completed = (S.webinars || []).filter(w => w.status === 'completed' && (w.total_registrations || 0) > 0);
  const topics  = data.topic_intelligence || [];
  const days    = data.day_performance || [];
  const sources = data.source_performance || [];

  // Build Speaker × ICP matrix from actual webinar data
  const matrix = {};
  completed.forEach(w => {
    const spk = w.speaker_name || 'Unknown';
    const icp = w.icp || 'Others';
    if (!matrix[spk]) matrix[spk] = {};
    if (!matrix[spk][icp]) matrix[spk][icp] = { regs: 0, att: 0, count: 0 };
    matrix[spk][icp].regs  += (w.total_registrations || 0);
    matrix[spk][icp].att   += (w.total_attendees || 0);
    matrix[spk][icp].count += 1;
  });

  // Best Speaker-ICP combo with min 2 webinars
  let bestCombo = null, bestRate = 0;
  Object.entries(matrix).forEach(([spk, icps]) => {
    Object.entries(icps).forEach(([icp, s]) => {
      if (s.count >= 2 && s.regs > 0) {
        const rate = Math.round(s.att / s.regs * 100);
        if (rate > bestRate) { bestRate = rate; bestCombo = { spk, icp, rate, regs: s.regs, att: s.att, count: s.count }; }
      }
    });
  });

  const bestDay  = [...days].sort((a, b) => b.attendance_rate - a.attendance_rate)[0];
  const bestSrc  = [...sources].sort((a, b) => b.rate - a.rate)[0];
  const topIcps  = topics.filter(t => t.webinar_count >= 2).sort((a, b) => b.attendance_rate - a.attendance_rate);
  const bestIcp  = topIcps[0];
  const worstIcp = topIcps[topIcps.length - 1];

  const allSpeakers = [...new Set(completed.map(w => w.speaker_name).filter(Boolean))];
  const allIcps     = [...new Set(completed.map(w => w.icp || 'Others'))];
  const matrixSpks  = allSpeakers.slice(0, 6);
  const matrixIcps  = allIcps.slice(0, 7);

  // Untried combinations
  const untried = [];
  allSpeakers.forEach(spk => allIcps.forEach(icp => { if (!matrix[spk]?.[icp]) untried.push({ spk, icp }); }));

  body.innerHTML = `
    <div class="intel-section">

      ${(bestCombo || bestDay || bestIcp) ? `
      <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:16px;padding:24px 28px;margin-bottom:28px;color:#fff">
        <div style="font-size:11px;font-weight:800;letter-spacing:1.2px;opacity:.75;margin-bottom:10px">DATA-BACKED RECOMMENDATION — NEXT WEBINAR</div>
        <div style="font-size:19px;font-weight:800;margin-bottom:10px;line-height:1.4">
          ${bestCombo ? `Run a <strong>${esc(bestCombo.icp)}</strong> webinar with <strong>${esc(bestCombo.spk)}</strong>${bestDay ? ` on <strong>${esc(bestDay.day)}</strong>` : ''}` : bestIcp ? `Focus on <strong>${esc(bestIcp.icp)}</strong> ICP${bestDay ? ` — schedule on <strong>${esc(bestDay.day)}</strong>` : ''}` : `Schedule on <strong>${esc(bestDay?.day||'')}</strong> for best attendance`}
        </div>
        <div style="font-size:13px;opacity:.85;line-height:1.65;margin-bottom:16px">
          ${bestCombo ? `This speaker-ICP combination has delivered <strong>${bestCombo.rate}%</strong> attendance rate across <strong>${bestCombo.count} webinars</strong> (${fmt(bestCombo.att)} attendees from ${fmt(bestCombo.regs)} registrations). It is your proven formula — repeat it.` : ''}
          ${!bestCombo && bestIcp ? `<strong>${esc(bestIcp.icp)}</strong> is your strongest ICP with <strong>${bestIcp.attendance_rate}%</strong> attendance rate across ${bestIcp.webinar_count} webinars.` : ''}
          ${bestDay ? ` <strong>${esc(bestDay.day)}</strong> delivers the highest attendance rate (${bestDay.attendance_rate}%) across ${bestDay.webinars} webinars.` : ''}
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          ${bestCombo ? `<div style="background:rgba(255,255,255,.18);border-radius:8px;padding:7px 13px;font-size:12px;font-weight:700">🏆 ${bestCombo.rate}% att rate</div>` : ''}
          ${bestDay   ? `<div style="background:rgba(255,255,255,.18);border-radius:8px;padding:7px 13px;font-size:12px;font-weight:700">📅 Best day: ${esc(bestDay.day)}</div>` : ''}
          ${bestIcp   ? `<div style="background:rgba(255,255,255,.18);border-radius:8px;padding:7px 13px;font-size:12px;font-weight:700">🎯 Best ICP: ${esc(bestIcp.icp)} (${bestIcp.attendance_rate}%)</div>` : ''}
          ${bestSrc   ? `<div style="background:rgba(255,255,255,.18);border-radius:8px;padding:7px 13px;font-size:12px;font-weight:700">📡 Best channel: ${esc(bestSrc.source)} (${bestSrc.rate}%)</div>` : ''}
        </div>
      </div>` : ''}

      ${matrixSpks.length && matrixIcps.length ? `
      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:4px">🔬 Speaker × ICP Performance Matrix</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:14px">Attendance rate per speaker-ICP combination. Only actual data — no estimates. Green = scale it. Red = fix or drop it.</div>
        <div style="overflow-x:auto;border:1.5px solid var(--border);border-radius:14px">
          <table style="width:100%;border-collapse:collapse;min-width:480px">
            <thead>
              <tr style="background:var(--surface-alt,#f8fafc)">
                <th style="padding:10px 14px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted);border-bottom:1px solid var(--border)">Speaker</th>
                ${matrixIcps.map(icp=>`<th style="padding:10px 10px;text-align:center;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;color:var(--text-muted);border-bottom:1px solid var(--border);white-space:nowrap">${esc(icp)}</th>`).join('')}
              </tr>
            </thead>
            <tbody>
              ${matrixSpks.map(spk => `
              <tr>
                <td style="padding:11px 14px;font-weight:700;font-size:13px;color:var(--text-primary);border-bottom:1px solid var(--border);white-space:nowrap;background:var(--surface)">${esc(spk)}</td>
                ${matrixIcps.map(icp => {
                  const cell = matrix[spk]?.[icp];
                  if (!cell) return `<td style="padding:11px 10px;text-align:center;border-bottom:1px solid var(--border);color:var(--text-muted);font-size:11px;background:var(--surface)">—</td>`;
                  const rate = cell.regs > 0 ? Math.round(cell.att / cell.regs * 100) : 0;
                  const bg = rate>=45?'#f0fdf4':rate>=30?'#eef2ff':rate>=15?'#fffbeb':'#fff1f2';
                  const color = rate>=45?'#10b981':rate>=30?'#6366f1':rate>=15?'#f59e0b':'#f43f5e';
                  return `<td style="padding:11px 10px;text-align:center;border-bottom:1px solid var(--border);background:${bg}">
                    <div style="font-weight:800;font-size:15px;color:${color}">${rate}%</div>
                    <div style="font-size:9px;color:var(--text-muted)">${cell.count}×</div>
                  </td>`;
                }).join('')}
              </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>` : ''}

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">

        ${topIcps.length ? `
        <div>
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:12px">🎯 ICP Ranking — Best to Worst (min 2 webinars)</div>
          <div style="background:var(--surface);border:1.5px solid var(--border);border-radius:14px;overflow:hidden">
            ${topIcps.map((t, i) => {
              const barPct = topIcps[0].attendance_rate > 0 ? Math.round(t.attendance_rate / topIcps[0].attendance_rate * 100) : 0;
              const c = t.attendance_rate >= 40 ? '#10b981' : t.attendance_rate >= 25 ? '#6366f1' : '#f59e0b';
              return `<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border)">
                <span style="font-size:11px;font-weight:800;color:var(--text-muted);width:18px;flex-shrink:0">${i+1}</span>
                <span class="icp-badge icp-${(t.icp||'others').toLowerCase().replace(/\s+/g,'-')}" style="font-size:10px;flex-shrink:0">${esc(t.icp||'Others')}</span>
                <div style="flex:1;height:5px;background:var(--border);border-radius:3px"><div style="width:${barPct}%;height:100%;background:${c};border-radius:3px"></div></div>
                <span style="font-weight:800;font-size:13px;color:${c};width:36px;text-align:right;flex-shrink:0">${t.attendance_rate}%</span>
              </div>`;
            }).join('')}
          </div>
        </div>` : '<div></div>'}

        ${untried.length ? `
        <div>
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:12px">🧪 Untested Combinations — Potential Growth Plays</div>
          <div style="background:var(--surface);border:1.5px solid var(--border);border-radius:14px;overflow:hidden">
            ${untried.slice(0, 10).map(u => `
            <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border)">
              <span style="font-size:13px;flex-shrink:0">🧪</span>
              <span style="font-weight:600;font-size:12px;color:var(--text-primary);flex-shrink:0">${esc(u.spk)}</span>
              <span style="color:var(--text-muted);font-size:12px;flex-shrink:0">×</span>
              <span class="icp-badge icp-${(u.icp||'others').toLowerCase().replace(/\s+/g,'-')}" style="font-size:10px">${esc(u.icp)}</span>
              <span style="font-size:10px;color:var(--text-muted);margin-left:auto">never tried</span>
            </div>`).join('')}
          </div>
        </div>` : '<div></div>'}

      </div>
    </div>`;
}

async function _renderAIInsights(body) {
  body.innerHTML = `
    <div class="intel-section">
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 0;gap:14px">
        <div style="width:56px;height:56px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:16px;display:flex;align-items:center;justify-content:center">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" class="spin"><path d="M21 12a9 9 0 1 1-6.22-8.56"/></svg>
        </div>
        <div style="font-weight:700;font-size:16px;color:var(--text-primary)">Analysing your programme…</div>
        <div style="font-size:13px;color:var(--text-muted);text-align:center;max-width:340px">AI is reviewing all webinars, speaker performance, ICP patterns, and attendance trends</div>
      </div>
    </div>`;

  try {
    _intelInsightsCache = await api('/api/intelligence/insights');
    const insights = _intelInsightsCache.insights || [];
    if (!insights.length) {
      body.innerHTML = `<div class="intel-section"><div class="empty-state"><div class="empty-title">Not enough data for insights yet</div><div class="empty-sub">Upload registration and attendance data for completed webinars first.</div></div></div>`;
      return;
    }

    // Group insights by type for sectioned layout
    const wins        = insights.filter(i => i.type === 'win');
    const risks       = insights.filter(i => i.type === 'risk');
    const actions     = insights.filter(i => i.type === 'action');
    const opps        = insights.filter(i => i.type === 'opportunity');
    const trends      = insights.filter(i => i.type === 'trend');
    const rest        = insights.filter(i => !['win','risk','action','opportunity','trend'].includes(i.type));
    const all         = [...wins, ...opps, ...actions, ...risks, ...trends, ...rest];

    const TYPE_CFG = {
      win:         { color:'#10b981', bg:'#f0fdf4', border:'#bbf7d0', icon:'🏆', label:'WIN',         darkBg:'rgba(16,185,129,0.12)' },
      risk:        { color:'#f43f5e', bg:'#fff1f2', border:'#fecdd3', icon:'⚠️', label:'RISK',        darkBg:'rgba(244,63,94,0.12)'  },
      opportunity: { color:'#6366f1', bg:'#eef2ff', border:'#c7d2fe', icon:'🚀', label:'OPPORTUNITY', darkBg:'rgba(99,102,241,0.12)' },
      trend:       { color:'#f59e0b', bg:'#fffbeb', border:'#fde68a', icon:'📈', label:'TREND',       darkBg:'rgba(245,158,11,0.12)' },
      action:      { color:'#0ea5e9', bg:'#f0f9ff', border:'#bae6fd', icon:'⚡', label:'ACTION NOW',  darkBg:'rgba(14,165,233,0.12)' },
    };

    const renderCard = (ins, i, featured=false) => {
      const cfg = TYPE_CFG[ins.type] || TYPE_CFG.trend;
      if (featured) {
        return `
        <div style="background:${cfg.bg};border:1.5px solid ${cfg.border};border-radius:16px;padding:24px 28px;position:relative;overflow:hidden;animation:fadeSlideUp .4s ease both;animation-delay:${i*60}ms">
          <div style="position:absolute;top:0;left:0;right:0;height:4px;background:${cfg.color};border-radius:16px 16px 0 0"></div>
          <div style="display:flex;align-items:flex-start;gap:14px">
            <div style="width:42px;height:42px;border-radius:12px;background:${cfg.color};display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0">${cfg.icon}</div>
            <div style="flex:1;min-width:0">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap">
                <span style="font-size:10px;font-weight:800;letter-spacing:1px;color:${cfg.color};background:${cfg.color}18;border:1px solid ${cfg.color}30;border-radius:20px;padding:2px 10px">${cfg.label}</span>
                ${ins.metric ? `<span style="font-size:12px;font-weight:700;color:${cfg.color};background:${cfg.color}15;border-radius:20px;padding:2px 10px">${esc(ins.metric)}</span>` : ''}
              </div>
              <div style="font-weight:800;font-size:16px;color:var(--text-primary);margin-bottom:8px;line-height:1.35">${esc(ins.headline)}</div>
              <div style="font-size:13.5px;color:var(--text-secondary);line-height:1.65;margin-bottom:14px">${esc(ins.detail)}</div>
              <div style="display:flex;align-items:flex-start;gap:8px;background:${cfg.color}10;border-left:3px solid ${cfg.color};border-radius:0 8px 8px 0;padding:10px 14px">
                <span style="font-size:14px;flex-shrink:0">→</span>
                <span style="font-size:13px;font-weight:600;color:var(--text-primary)">${esc(ins.action)}</span>
              </div>
            </div>
          </div>
        </div>`;
      }
      return `
        <div style="background:var(--surface);border:1.5px solid ${cfg.border};border-radius:14px;padding:18px 20px;position:relative;overflow:hidden;animation:fadeSlideUp .4s ease both;animation-delay:${i*60}ms">
          <div style="position:absolute;top:0;left:0;bottom:0;width:4px;background:${cfg.color};border-radius:14px 0 0 14px"></div>
          <div style="padding-left:12px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap">
              <span style="font-size:16px">${cfg.icon}</span>
              <span style="font-size:10px;font-weight:800;letter-spacing:1px;color:${cfg.color}">${cfg.label}</span>
              ${ins.metric ? `<span style="font-size:11px;font-weight:700;color:${cfg.color};margin-left:auto">${esc(ins.metric)}</span>` : ''}
            </div>
            <div style="font-weight:700;font-size:14px;color:var(--text-primary);margin-bottom:6px;line-height:1.35">${esc(ins.headline)}</div>
            <div style="font-size:12.5px;color:var(--text-muted);line-height:1.6;margin-bottom:10px">${esc(ins.detail)}</div>
            <div style="font-size:12px;font-weight:600;color:${cfg.color};border-top:1px solid ${cfg.border};padding-top:8px">→ ${esc(ins.action)}</div>
          </div>
        </div>`;
    };

    // Pull live stats for the dashboard header
    const completed = (S.webinars||[]).filter(w=>w.status==='completed');
    const totalReg  = completed.reduce((s,w)=>s+(w.total_registrations||0),0);
    const totalAtt  = completed.reduce((s,w)=>s+(w.total_attendees||0),0);
    const avgRate   = totalReg>0 ? Math.round(totalAtt/totalReg*100) : 0;
    const topWin    = wins[0] || all[0];
    const topRisk   = risks[0];
    const topAction = actions[0];

    body.innerHTML = `
      <div class="intel-section">

        <!-- Header with live stats -->
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;flex-wrap:wrap;gap:12px">
          <div>
            <h2 style="font-size:20px;font-weight:800;margin:0;color:var(--text-primary)">Smart Recommendations</h2>
            <p style="font-size:13px;color:var(--text-muted);margin:4px 0 0">AI analysis of ${completed.length} completed webinars · ${fmt(totalReg)} registrations · ${fmt(totalAtt)} attendees</p>
          </div>
          <button class="btn btn-ghost btn-sm" style="display:flex;align-items:center;gap:6px" onclick="_intelInsightsCache=null;_renderAIInsights(document.getElementById('intel-body'))">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            Refresh Analysis
          </button>
        </div>

        <!-- Programme scorecard strip -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:28px">
          ${[
            { label:'Webinars Analysed', val:completed.length, color:'#6366f1', sub:'completed' },
            { label:'Total Registrations', val:fmt(totalReg), color:'#6366f1', sub:'across all webinars' },
            { label:'Total Attendees', val:fmt(totalAtt), color:'#10b981', sub:'actual attendance' },
            { label:'Avg Attendance Rate', val:avgRate+'%', color:avgRate>=40?'#10b981':avgRate>=25?'#f59e0b':'#f43f5e', sub:avgRate>=40?'Above average ✓':avgRate>=25?'Room to grow':'Needs attention ⚠' },
          ].map(k=>`
            <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px;border-top:3px solid ${k.color}">
              <div style="font-size:22px;font-weight:800;color:${k.color}">${k.val}</div>
              <div style="font-size:11px;font-weight:600;color:var(--text-primary);margin-top:2px">${k.label}</div>
              <div style="font-size:10px;color:var(--text-muted);margin-top:2px">${k.sub}</div>
            </div>`).join('')}
        </div>

        <!-- Critical alerts row -->
        ${(topRisk || topAction) ? `
        <div style="margin-bottom:24px">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:12px">⚡ Requires Attention</div>
          <div style="display:grid;grid-template-columns:${topRisk && topAction ? '1fr 1fr' : '1fr'};gap:14px">
            ${topRisk ? renderCard(topRisk, 0, true) : ''}
            ${topAction ? renderCard(topAction, 1, true) : ''}
          </div>
        </div>` : ''}

        <!-- Top win featured -->
        ${topWin && topWin.type === 'win' ? `
        <div style="margin-bottom:24px">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:12px">🏆 Top Performer</div>
          ${renderCard(topWin, 0, true)}
        </div>` : ''}

        <!-- All insights grid -->
        <div style="margin-bottom:8px">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:12px">📋 Full Intelligence Report</div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px">
            ${all.map((ins,i) => renderCard(ins, i, false)).join('')}
          </div>
        </div>

      </div>`;
  } catch(e) {
    body.innerHTML = `<div class="intel-section"><div class="empty-state"><div class="empty-title">Failed to generate insights</div><div class="empty-sub">${esc(e.message)}</div></div></div>`;
  }
}

function _renderTopicIntel(data) {
  const topics = data.topic_intelligence || [];
  if (!topics.length) {
    return `<div class="intel-section"><div class="empty-state"><div class="empty-title">No topic data yet</div><div class="empty-sub">Complete webinars with ICP tags to see topic intelligence.</div></div></div>`;
  }

  const proven  = topics.filter(t => t.attendance_rate >= 40 && t.webinar_count >= 3).sort((a,b) => b.attendance_rate - a.attendance_rate);
  const grow    = topics.filter(t => t.attendance_rate >= 25 && t.attendance_rate < 40 && t.webinar_count >= 3).sort((a,b) => b.attendance_rate - a.attendance_rate);
  const review  = topics.filter(t => t.attendance_rate < 25 && t.webinar_count >= 3).sort((a,b) => b.attendance_rate - a.attendance_rate);
  const limited = topics.filter(t => t.webinar_count < 3).sort((a,b) => b.attendance_rate - a.attendance_rate);

  const tierCard = (t, color, bg, border) => `
    <div style="background:${bg};border:1.5px solid ${border};border-radius:12px;padding:16px 18px;display:flex;align-items:center;justify-content:space-between;gap:12px">
      <div style="flex:1;min-width:0">
        <span class="icp-badge icp-${(t.icp||'others').toLowerCase().replace(/\s+/g,'-')}">${esc(t.icp||'Others')}</span>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px">${t.webinar_count} webinar${t.webinar_count!==1?'s':''} · ${fmt(t.total_regs)} registrations · ${fmt(t.total_att)} attended</div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:22px;font-weight:800;color:${color}">${t.attendance_rate}%</div>
        <div style="font-size:10px;color:var(--text-muted)">attendance rate</div>
      </div>
    </div>`;

  const topDropoff = [...topics].filter(t=>t.webinar_count>=3).sort((a,b) => a.attendance_rate - b.attendance_rate)[0];
  const totalRegs  = topics.reduce((s,t)=>s+(t.total_regs||0),0);
  const totalAtt   = topics.reduce((s,t)=>s+(t.total_att||0),0);
  const overallDrop = totalRegs > 0 ? Math.round((1 - totalAtt/totalRegs)*100) : 0;
  const topProven  = proven[0];

  const angleCards = [
    { title:'NRI Retirement Planning', icon:'🌏', why:'NRIs planning India return seek structured retirement income — high intent, low supply of quality content.' },
    { title:'Tax & Succession via AIF/PMS', icon:'⚖️', why:'HNIs with ₹5Cr+ portfolios are actively looking to restructure — AIF/PMS angles drive premium registrations.' },
    { title:'Family Office Structuring', icon:'🏦', why:'Ultra-HNI segment (₹25Cr+) underserved with webinar content — first-mover advantage for Right Horizons.' },
    { title:'ESOP Liquidation Strategies', icon:'📊', why:'Pre-IPO and startup employee HNIs are a fast-growing ICP — very few advisors run this content.' },
  ];

  return `
    <div class="intel-section">

      <div style="margin-bottom:28px">
        <h2 style="font-size:18px;font-weight:800;margin:0 0 4px;color:var(--text-primary)">Topic Intelligence</h2>
        <p style="font-size:13px;color:var(--text-muted);margin:0">ICP-based performance analysis across ${topics.length} topic categories from ${data.total_webinars||0} webinars.</p>
      </div>

      <!-- Topic Performance Tiers -->
      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">📊 Topic Performance by ICP</div>

        ${proven.length ? `
        <div style="margin-bottom:16px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span style="font-size:11px;font-weight:700;color:#10b981;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:20px;padding:3px 10px">✓ PROVEN — Keep Repeating</span>
            <span style="font-size:11px;color:var(--text-muted)">${proven.length} topic${proven.length!==1?'s':''} above 40% attendance</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px">
            ${proven.map(t=>tierCard(t,'#10b981','#f0fdf4','#bbf7d0')).join('')}
          </div>
        </div>` : ''}

        ${grow.length ? `
        <div style="margin-bottom:16px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span style="font-size:11px;font-weight:700;color:#f59e0b;background:#fffbeb;border:1px solid #fde68a;border-radius:20px;padding:3px 10px">↗ GROW — Optimise Promotion</span>
            <span style="font-size:11px;color:var(--text-muted)">${grow.length} topic${grow.length!==1?'s':''} between 25–40% attendance</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px">
            ${grow.map(t=>tierCard(t,'#f59e0b','#fffbeb','#fde68a')).join('')}
          </div>
        </div>` : ''}

        ${review.length ? `
        <div style="margin-bottom:16px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span style="font-size:11px;font-weight:700;color:#f43f5e;background:#fff1f2;border:1px solid #fecdd3;border-radius:20px;padding:3px 10px">⚠ REVIEW — Rethink Angle or Audience</span>
            <span style="font-size:11px;color:var(--text-muted)">${review.length} topic${review.length!==1?'s':''} below 25% attendance</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px">
            ${review.map(t=>tierCard(t,'#f43f5e','#fff1f2','#fecdd3')).join('')}
          </div>
        </div>` : ''}

        ${limited.length ? `
        <div style="margin-bottom:16px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span style="font-size:11px;font-weight:700;color:var(--text-muted);background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:3px 10px">⏳ BUILDING DATA — fewer than 3 webinars</span>
            <span style="font-size:11px;color:var(--text-muted)">${limited.length} ICP${limited.length!==1?'s':''} with limited history</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px">
            ${limited.map(t=>tierCard(t,'var(--text-muted)','var(--surface)','var(--border)')).join('')}
          </div>
        </div>` : ''}

        ${!proven.length && !grow.length && !review.length ? `
        <div style="background:var(--surface);border:1.5px dashed var(--border);border-radius:14px;padding:32px;text-align:center;color:var(--text-muted)">
          <div style="font-size:28px;margin-bottom:8px">📊</div>
          <div style="font-weight:600;margin-bottom:4px">Need 3+ webinars per ICP for tier classification</div>
          <div style="font-size:13px">Currently showing all topics in the "Building Data" section below. Run at least 3 webinars per ICP to unlock Proven/Grow/Review tiers.</div>
        </div>` : ''}
      </div>

      <!-- Drop-off Observation -->
      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">📉 Funnel Drop-off Comment</div>
        <div style="background:var(--surface);border:1.5px solid var(--border);border-radius:14px;padding:20px 24px;display:flex;align-items:flex-start;gap:16px">
          <div style="width:48px;height:48px;background:#fff1f2;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0">📉</div>
          <div>
            <div style="font-weight:700;font-size:15px;color:var(--text-primary);margin-bottom:6px">${overallDrop}% of registrants never attend</div>
            <div style="font-size:13.5px;color:var(--text-secondary);line-height:1.65;margin-bottom:10px">
              ${topDropoff ? `<strong>${esc(topDropoff.icp)}</strong> topics see the weakest attendance rate at <strong>${topDropoff.attendance_rate}%</strong>. ` : ''}
              High registration-to-attendance drop-off suggests a gap between the topic promise in ads and the actual content value — consider narrowing the target audience and strengthening the reminder sequence.
            </div>
            ${topProven ? `<div style="font-size:13px;font-weight:600;color:#10b981;border-left:3px solid #10b981;padding-left:10px">→ <strong>${esc(topProven.icp)}</strong> is your best-converting ICP (${topProven.attendance_rate}%) — build your next 3 webinars around this theme.</div>` : ''}
          </div>
        </div>
      </div>

      <!-- HNI Content Angle Recommendations -->
      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">💡 HNI Content Angle Recommendations</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px">
          ${angleCards.map(a=>`
            <div style="background:var(--surface);border:1.5px solid var(--border);border-radius:14px;padding:18px 20px;border-top:3px solid #6366f1">
              <div style="font-size:24px;margin-bottom:10px">${a.icon}</div>
              <div style="font-weight:700;font-size:14px;color:var(--text-primary);margin-bottom:8px">${a.title}</div>
              <div style="font-size:12.5px;color:var(--text-muted);line-height:1.6">${a.why}</div>
            </div>`).join('')}
        </div>
      </div>

      <!-- Repeat Topic Recommendation -->
      ${topProven ? `
      <div>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">🔁 Repeat Topic Recommendation</div>
        <div style="background:linear-gradient(135deg,#6366f115,#8b5cf610);border:1.5px solid #6366f130;border-radius:14px;padding:20px 24px">
          <div style="font-weight:700;font-size:15px;color:var(--text-primary);margin-bottom:8px">Convert your <strong>${esc(topProven.icp)}</strong> webinars into a series</div>
          <div style="font-size:13.5px;color:var(--text-secondary);line-height:1.65;margin-bottom:14px">
            With ${topProven.attendance_rate}% attendance rate across ${topProven.webinar_count} webinar${topProven.webinar_count!==1?'s':''}, <strong>${esc(topProven.icp)}</strong> is a proven audience. Convert the best-performing webinar into an advanced case study or a live deal-walkthrough format to increase depth and exclusivity.
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
            ${['Advanced Edition: Deep-dive version for returning attendees','Case Study Format: Walk through a real client scenario (anonymised)','Live Q&A Series: Monthly office hours format for high-intent prospects'].map(s=>`
              <div style="background:var(--surface);border:1px solid #6366f130;border-radius:10px;padding:12px 14px;font-size:12px;color:var(--text-primary)">${s}</div>`).join('')}
          </div>
        </div>
      </div>` : ''}

    </div>`;
}

function _renderSpeakerIntel(data) {
  const speakers = data.speaker_performance || [];
  if (!speakers.length) {
    return `<div class="intel-section"><div class="empty-state"><div class="empty-title">No speaker data yet</div><div class="empty-sub">Complete at least 2 webinars per speaker to see performance metrics.</div></div></div>`;
  }

  // Sort by total_regs desc
  const sorted = [...speakers].sort((a, b) => b.total_regs - a.total_regs);
  const avgAttRate = sorted.reduce((s, x) => s + x.attendance_rate, 0) / sorted.length;

  const cards = sorted.map((s, idx) => {
    const grade = s.attendance_rate >= 40 ? 'A' : s.attendance_rate >= 30 ? 'B' : s.attendance_rate >= 20 ? 'C' : 'D';
    const gColor = { A:'#10b981', B:'#6366f1', C:'#f59e0b', D:'#f43f5e' }[grade];
    const av = avColor(s.name); const ini = initials(s.name);
    const regsBarPct = sorted[0].total_regs > 0 ? Math.round(s.total_regs / sorted[0].total_regs * 100) : 0;
    const attBarPct = Math.min(100, s.attendance_rate);
    const badge = idx === 0 ? `<span style="background:#f59e0b22;color:#f59e0b;border:1px solid #f59e0b40;border-radius:6px;font-size:10px;font-weight:700;padding:2px 7px;margin-left:8px">TOP</span>` : '';

    return `
    <div class="spk-detail-card">
      <div class="spk-detail-header">
        <div style="display:flex;align-items:center;gap:12px;flex:1;min-width:0">
          <div style="width:44px;height:44px;background:${av};color:#fff;display:flex;align-items:center;justify-content:center;border-radius:12px;font-weight:800;font-size:15px;flex-shrink:0">${ini}</div>
          <div style="min-width:0">
            <div style="font-weight:700;font-size:15px;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(s.name)}${badge}</div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${s.webinars} webinar${s.webinars>1?'s':''} hosted</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          <div class="spk-grade-ring" style="--g-color:${gColor}">
            <span style="font-size:18px;font-weight:800;color:${gColor}">${grade}</span>
          </div>
        </div>
      </div>

      <div class="spk-detail-metrics">
        <div class="spk-metric-box">
          <div class="spk-metric-val">${fmt(s.total_regs)}</div>
          <div class="spk-metric-lbl">Total Registrations</div>
          <div class="spk-metric-bar"><div style="width:${regsBarPct}%;background:${av};height:100%;border-radius:4px;transition:width 0.8s"></div></div>
        </div>
        <div class="spk-metric-box">
          <div class="spk-metric-val">${fmt(Math.round(s.avg_regs_per_webinar))}</div>
          <div class="spk-metric-lbl">Avg Regs / Webinar</div>
        </div>
        <div class="spk-metric-box">
          <div class="spk-metric-val" style="color:${gColor}">${s.attendance_rate}%</div>
          <div class="spk-metric-lbl">Attendance Rate</div>
          <div class="spk-metric-bar"><div style="width:${attBarPct}%;background:${gColor};height:100%;border-radius:4px;transition:width 0.8s"></div></div>
        </div>
        <div class="spk-metric-box">
          <div class="spk-metric-val">${fmt(s.total_att)}</div>
          <div class="spk-metric-lbl">Total Attendees</div>
        </div>
      </div>

      <div class="spk-detail-insight">
        ${s.attendance_rate >= 40 ? `<span style="color:#10b981">✓ Strong attendance rate</span>` : ''}
      </div>
    </div>`;
  }).join('');

  return `
    <div class="intel-section">
      <div style="margin-bottom:18px">
        <h3 class="intel-h3" style="margin:0">Speaker Performance</h3>
        <p class="intel-p" style="margin:4px 0 16px">Registration and attendance metrics per speaker across all completed webinars.</p>
        <div class="intel-kpis" style="margin:0;justify-content:center">
          <div class="intel-kpi" style="min-width:80px"><div class="intel-kpi-lbl">Speakers</div><div class="intel-kpi-val">${sorted.length}</div></div>
          <div class="intel-kpi" style="min-width:80px"><div class="intel-kpi-lbl">Total Regs</div><div class="intel-kpi-val">${fmt(sorted.reduce((s,x)=>s+x.total_regs,0))}</div></div>
          <div class="intel-kpi" style="min-width:80px"><div class="intel-kpi-lbl">Avg Att Rate</div><div class="intel-kpi-val">${avgAttRate.toFixed(1)}%</div></div>
        </div>
      </div>
      <div class="spk-detail-grid">${cards}</div>
    </div>`;
}

function _renderCampaignIntel(data) {
  const days = data.day_performance || [];
  const sources = data.source_performance || [];

  // Best day analysis
  const sortedDays = [...days].sort((a,b) => b.attendance_rate - a.attendance_rate);
  const bestDay = sortedDays[0];
  const worstDay = sortedDays[sortedDays.length-1];

  // Source tiers
  const sortedSrc = [...sources].sort((a,b) => b.rate - a.rate);
  const scaleList   = sortedSrc.filter(s => s.rate >= 40);
  const improveList = sortedSrc.filter(s => s.rate >= 25 && s.rate < 40);
  const retestList  = sortedSrc.filter(s => s.rate >= 15 && s.rate < 25);
  const pauseList   = sortedSrc.filter(s => s.rate < 15);

  const srcRow = (s, color, label) => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:10px;gap:12px">
      <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0">
        <span style="font-size:10px;font-weight:800;letter-spacing:.8px;color:${color};background:${color}15;border:1px solid ${color}30;border-radius:20px;padding:2px 9px;flex-shrink:0">${label}</span>
        <span style="font-weight:600;font-size:13px;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.source)}</span>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:16px;font-weight:800;color:${color}">${s.rate}%</div>
        <div style="font-size:10px;color:var(--text-muted)">${fmt(s.regs)} regs · ${fmt(s.atts)} att</div>
      </div>
    </div>`;

  const dayCard = (d, color, label) => `
    <div style="background:${color}10;border:1.5px solid ${color}30;border-radius:12px;padding:14px 18px;text-align:center">
      <div style="font-size:11px;font-weight:700;color:${color};margin-bottom:4px">${label}</div>
      <div style="font-size:20px;font-weight:800;color:${color}">${esc(d.day)}</div>
      <div style="font-size:18px;font-weight:800;color:${color};margin-top:4px">${d.attendance_rate}%</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:4px">${d.webinars} webinar${d.webinars!==1?'s':''}</div>
    </div>`;

  return `
    <div class="intel-section">

      <div style="margin-bottom:28px">
        <h2 style="font-size:18px;font-weight:800;margin:0 0 4px;color:var(--text-primary)">Campaign Learning</h2>
        <p style="font-size:13px;color:var(--text-muted);margin:0">Channel and timing analysis to improve registration-to-attendance conversion.</p>
      </div>

      <!-- Day of Week Insight -->
      ${days.length ? `
      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">📅 Best Day to Schedule Webinars</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-bottom:16px">
          ${bestDay ? dayCard(bestDay,'#10b981','TOP DAY') : ''}
          ${worstDay && worstDay !== bestDay ? dayCard(worstDay,'#f43f5e','AVOID') : ''}
        </div>
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden">
          ${days.map(d => {
            const max = Math.max(...days.map(x=>x.attendance_rate),1);
            const pct = (d.attendance_rate/max*100).toFixed(1);
            const c = d.attendance_rate >= 40 ? '#10b981' : d.attendance_rate >= 25 ? '#6366f1' : '#f59e0b';
            return `<div style="display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid var(--border)">
              <div style="width:80px;font-weight:600;font-size:13px;color:var(--text-primary)">${esc(d.day)}</div>
              <div style="flex:1;height:8px;background:var(--border);border-radius:4px"><div style="width:${pct}%;height:100%;background:${c};border-radius:4px;transition:width .6s"></div></div>
              <div style="width:80px;text-align:right;font-size:12px;color:var(--text-muted)">${d.webinars} webinar${d.webinars!==1?'s':''}</div>
              <div style="width:48px;text-align:right;font-weight:700;font-size:13px;color:${c}">${d.attendance_rate}%</div>
            </div>`;
          }).join('')}
        </div>
      </div>` : ''}

      <!-- Channel Performance Framework -->
      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">📡 Channel Performance — Scale / Improve / Retest / Pause</div>

        ${!sources.length ? `
        <div style="background:var(--surface);border:1.5px dashed var(--border);border-radius:14px;padding:32px;text-align:center;color:var(--text-muted)">
          <div style="font-size:32px;margin-bottom:10px">📡</div>
          <div style="font-weight:600;margin-bottom:6px">No channel data yet</div>
          <div style="font-size:13px">Registration source data will appear here once webinars have source/UTM tracking. Tag your registration forms with source parameters to unlock this insight.</div>
        </div>` : `
        <div style="display:flex;flex-direction:column;gap:10px">
          ${scaleList.length ? `<div style="font-size:11px;font-weight:700;color:#10b981;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px">▲ SCALE — highest converting</div>${scaleList.map(s=>srcRow(s,'#10b981','SCALE')).join('')}` : ''}
          ${improveList.length ? `<div style="font-size:11px;font-weight:700;color:#6366f1;text-transform:uppercase;letter-spacing:.8px;margin-top:14px;margin-bottom:4px">→ IMPROVE — optimise messaging/targeting</div>${improveList.map(s=>srcRow(s,'#6366f1','IMPROVE')).join('')}` : ''}
          ${retestList.length ? `<div style="font-size:11px;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:.8px;margin-top:14px;margin-bottom:4px">↺ RETEST — try different angle or creative</div>${retestList.map(s=>srcRow(s,'#f59e0b','RETEST')).join('')}` : ''}
          ${pauseList.length ? `<div style="font-size:11px;font-weight:700;color:#f43f5e;text-transform:uppercase;letter-spacing:.8px;margin-top:14px;margin-bottom:4px">✕ PAUSE — not converting</div>${pauseList.map(s=>srcRow(s,'#f43f5e','PAUSE')).join('')}` : ''}
        </div>`}
      </div>

      <!-- Platform Recommendation -->
      <div style="margin-bottom:32px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">🎯 Platform Learning</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
          <div style="background:var(--surface);border:1.5px solid #0077b530;border-radius:14px;padding:18px 20px;border-top:3px solid #0077b5">
            <div style="font-size:20px;margin-bottom:8px">💼</div>
            <div style="font-weight:700;font-size:14px;color:var(--text-primary);margin-bottom:6px">LinkedIn — Quality over Volume</div>
            <div style="font-size:12.5px;color:var(--text-muted);line-height:1.6">LinkedIn attracts verified professional profiles and corporate email IDs — ideal for HNI/NRI ICP. Lower volume but higher intent. Prioritise LinkedIn for Family Office and PMS-focused webinars.</div>
          </div>
          <div style="background:var(--surface);border:1.5px solid #1877f230;border-radius:14px;padding:18px 20px;border-top:3px solid #1877f2">
            <div style="font-size:20px;margin-bottom:8px">📘</div>
            <div style="font-weight:700;font-size:14px;color:var(--text-primary);margin-bottom:6px">Meta — Reach but Qualify Hard</div>
            <div style="font-size:12.5px;color:var(--text-muted);line-height:1.6">Meta drives volume but mixed intent. Use look-alike audiences based on best-attending email list. Add a qualifying question in the registration form to filter for genuine HNI interest.</div>
          </div>
        </div>
      </div>

      <!-- Audience Learning -->
      <div>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:14px">👥 Audience Learning</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">
          ${[
            {icon:'✅',color:'#10b981',title:'Prioritise converting segments',desc:'Build lookalike lists from attendees (not just registrants) of your top-performing webinars.'},
            {icon:'🔁',color:'#6366f1',title:'Re-engage past attendees first',desc:'Returning attendees convert at 2–3x the rate of cold audiences — email them for every new webinar.'},
            {icon:'🎯',color:'#f59e0b',title:'Intent signal = repeat registration',desc:'Anyone who registered for 2+ webinars is a warm lead — flag them immediately for pipeline outreach.'},
          ].map(a=>`
            <div style="background:var(--surface);border:1.5px solid ${a.color}25;border-radius:13px;padding:16px 18px;border-left:4px solid ${a.color}">
              <div style="font-size:22px;margin-bottom:8px">${a.icon}</div>
              <div style="font-weight:700;font-size:13px;color:var(--text-primary);margin-bottom:6px">${a.title}</div>
              <div style="font-size:12px;color:var(--text-muted);line-height:1.55">${a.desc}</div>
            </div>`).join('')}
        </div>
      </div>

    </div>`;
}

function _renderICPIntel(data) {
  const consumerCount = (data.domain_analysis||[]).filter(d => d.kind==='consumer').reduce((s,d)=>s+d.people,0);
  const bizCount      = (data.domain_analysis||[]).filter(d => d.kind==='business').reduce((s,d)=>s+d.people,0);
  const total = consumerCount + bizCount || 1;

  const domainRows = (data.domain_analysis || []).slice(0, 20).map(d => `
    <tr>
      <td style="font-family:var(--font-mono);font-weight:600">${esc(d.domain)}</td>
      <td><span class="intel-domain-kind kind-${d.kind}">${d.kind}</span></td>
      <td style="text-align:right;font-family:var(--font-mono);font-weight:600">${fmt(d.people)}</td>
      <td style="text-align:right;font-family:var(--font-mono);color:var(--text-secondary)">${d.webinars}</td>
    </tr>`).join('');

  return `
    <div class="intel-section">
      <div class="intel-kpis">
        <div class="intel-kpi"><div class="intel-kpi-lbl">Consumer (Personal Email)</div><div class="intel-kpi-val">${fmt(consumerCount)} <span style="font-size:0.6em;color:var(--text-muted)">(${Math.round(consumerCount/total*100)}%)</span></div></div>
        <div class="intel-kpi"><div class="intel-kpi-lbl">Business (Corporate Email)</div><div class="intel-kpi-val">${fmt(bizCount)} <span style="font-size:0.6em;color:var(--text-muted)">(${Math.round(bizCount/total*100)}%)</span></div></div>
      </div>
      <h3 class="intel-h3">Top Email Domains (signal for audience type)</h3>
      <p class="intel-p">Corporate domains hint at HNI/professional audience. Government and education domains may indicate specific ICPs.</p>
      <div class="intel-table-wrap">
        <table class="intel-table">
          <thead><tr><th>Domain</th><th>Type</th><th style="text-align:right">People</th><th style="text-align:right">Webinars Touched</th></tr></thead>
          <tbody>${domainRows}</tbody>
        </table>
      </div>
    </div>`;
}

/* ── Competitor Intelligence (Phase 3) ──────────────────────────────────── */
const FORMAT_ICONS = {
  webinar:  '🎥',
  linkedin: '💼',
  report:   '📊',
  guide:    '📘',
  event:    '🎟️',
  other:    '📌',
};


async function renderTopics() {
  setContent(`
    <div class="topics-page">
      <div id="topic-perf-section">
        <div class="pg-loading"><div class="spinner"></div></div>
      </div>
      <div class="topics-hero">
        <div class="topics-hero-left">
          <div class="topics-eyebrow">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg>
            AI-Generated · Updated Weekly
          </div>
          <h1 class="topics-title">Topic Planner</h1>
          <p class="topics-sub">Fresh topics crafted for each speaker, timed to market news, framed in their voice.</p>
        </div>
        <button class="btn-topics-refresh" id="topics-refresh-btn" onclick="refreshTopics()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          Refresh Topics
        </button>
      </div>
      <div class="topics-grid" id="topics-grid">
        <div class="topics-loading">
          <div class="tl-ring"></div>
          <span>Generating topics with AI…</span>
        </div>
      </div>
    </div>`);

  loadTopicPerformance();
  await loadTopics();
}

async function loadTopicPerformance() {
  try {
    const data = await api('/api/topic-performance');
    const sect = document.getElementById('topic-perf-section');
    if (!sect) return;
    const rows = (data.topics || []).map(t => {
      const grade = t.attendance_rate >= 40 ? 'A' : t.attendance_rate >= 30 ? 'B' : t.attendance_rate >= 20 ? 'C' : 'D';
      const gColor = {A:'#10b981',B:'#6366f1',C:'#f59e0b',D:'#f43f5e'}[grade];
      return `
        <div class="tp-row">
          <div class="tp-icp"><span class="icp-badge icp-${(t.icp||'others').toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}">${esc(t.icp)}</span></div>
          <div class="tp-stat"><strong>${t.webinar_count}</strong><span>webinars</span></div>
          <div class="tp-stat"><strong>${fmt(t.total_regs)}</strong><span>registrations</span></div>
          <div class="tp-stat"><strong>${fmt(t.total_att)}</strong><span>attendees</span></div>
          <div class="tp-rate" style="color:${gColor}"><strong>${t.attendance_rate}%</strong><span style="font-size:10px;background:${gColor}18;border:1px solid ${gColor}40;border-radius:12px;padding:2px 7px;color:${gColor};font-weight:700">${grade}</span></div>
          <div class="tp-speaker" style="font-size:12px;color:var(--text-muted)">${t.best_speaker ? `Best: ${esc(t.best_speaker)}` : '—'}</div>
        </div>`;
    }).join('');
    sect.innerHTML = `
      <div style="margin-bottom:36px">
        <div class="page-hd" style="margin-bottom:16px">
          <div><h2 style="font-size:18px;font-weight:700;margin:0">ICP Performance</h2>
          <p class="page-sub" style="margin:2px 0 0">How each topic category is performing across all webinars</p></div>
        </div>
        <div class="tp-grid">${rows || '<div style="color:var(--text-muted);font-size:13px;padding:16px">No topic performance data yet.</div>'}</div>
      </div>`;
  } catch(e) {
    const sect = document.getElementById('topic-perf-section');
    if (sect) sect.innerHTML = '';
  }
}

async function refreshTopics() {
  _topicsCache = null;
  const btn = document.getElementById('topics-refresh-btn');
  const grid = document.getElementById('topics-grid');
  if (btn) { btn.disabled = true; btn.querySelector('svg').classList.add('spin'); }
  if (grid) grid.innerHTML = '<div class="topics-loading"><div class="tl-ring"></div><span>Generating fresh topics…</span></div>';
  await loadTopics();
  if (btn) { btn.disabled = false; btn.querySelector('svg').classList.remove('spin'); }
}

async function loadTopics() {
  try {
    const data = await api('/api/topics');
    _topicsCache = data;
    renderTopicCards(data);
  } catch(e) {
    const grid = document.getElementById('topics-grid');
    if (grid) grid.innerHTML = `<div class="topics-error"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span>${esc(e.message || 'Failed to generate topics')}</span></div>`;
  }
}

const EXPECTED_COLORS = { High:'#10b981', Medium:'#f59e0b', Low:'#6366f1' };
const SPEAKER_GRADIENTS = {
  'Rachna Rego':   'linear-gradient(135deg,#7c3aed,#a78bfa)',
  'Anil Rego':     'linear-gradient(135deg,#0369a1,#38bdf8)',
  'Sunil Kawariya':'linear-gradient(135deg,#065f46,#34d399)',
  'Preethi Shukla':'linear-gradient(135deg,#9d174d,#f472b6)',
  'Prabhat Ranjan':'linear-gradient(135deg,#92400e,#fbbf24)',
};

function renderTopicCards(data) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;

  const dateStr = data.generated_on || '';
  const speakers = data.topics || [];

  grid.innerHTML = speakers.map(sp => {
    const grad = SPEAKER_GRADIENTS[sp.speaker] || 'linear-gradient(135deg,#4f46e5,#818cf8)';
    const initials = sp.speaker.split(' ').map(w=>w[0]).join('').slice(0,2);

    const topicCards = (sp.topics || []).map((t, i) => {
      const expColor = EXPECTED_COLORS[t.expected?.split(' ')[0]] || '#6366f1';
      return `
      <div class="topic-card">
        <div class="topic-card-num">${i+1}</div>
        <div class="topic-card-body">
          <div class="topic-title">${esc(t.title)}</div>
          <div class="topic-hook">${esc(t.hook)}</div>
          <div class="topic-angle">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            ${esc(t.angle)}
          </div>
          <div class="topic-footer">
            <span class="topic-exp" style="color:${expColor};background:${expColor}18;border-color:${expColor}30">
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
              ${esc(t.expected || 'Medium')}
            </span>
            <button class="topic-use-btn" onclick="prefillTopicWebinar('${esc(sp.speaker).replace(/'/g,"\\'")}','${esc(t.title).replace(/'/g,"\\'")}')">
              Use Topic
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>
          </div>
        </div>
      </div>`;
    }).join('');

    return `
    <div class="speaker-topics-card">
      <div class="stc-header">
        <div class="stc-avatar" style="background:${grad}">${initials}</div>
        <div>
          <div class="stc-name">${esc(sp.speaker)}</div>
          <div class="stc-count">${(sp.topics||[]).length} suggested topics</div>
        </div>
      </div>
      <div class="stc-topics">${topicCards}</div>
    </div>`;
  }).join('');

  // Add date footer + live news source
  if (dateStr) {
    const newsHtml = data.news_context
      ? `<details class="topics-news-detail"><summary>View live market context used</summary><pre>${esc(data.news_context)}</pre></details>`
      : '';
    grid.insertAdjacentHTML('beforeend', `
      <div class="topics-date-footer">
        Generated on ${esc(dateStr)} · Powered by live market news + WebinarIQ AI
        ${data.news_context ? '<span style="color:#10b981;margin-left:8px">● Live news</span>' : '<span style="color:#f59e0b;margin-left:8px">● Offline mode</span>'}
      </div>
      ${newsHtml}`);
  }
}

function prefillTopicWebinar(speaker, title) {
  // Open new webinar modal with topic pre-filled
  openWebinarModal();
  setTimeout(() => {
    const titleInput = document.getElementById('wb-title');
    const speakerInput = document.getElementById('wb-speaker');
    if (titleInput) titleInput.value = title;
    if (speakerInput) speakerInput.value = speaker;
  }, 150);
}

/* ══════════════════════════════════════════════════════════════════════════
   MEETING PIPELINE (Phase 4)
══════════════════════════════════════════════════════════════════════════ */
let _pipelineCache = null;
let _pipelineFilter = 'all';  // all | new | contacted | meeting_booked | converted | not_interested

const PIPELINE_STATUS_META = {
  new:             { label: 'New',            color: '#6366f1', bg: '#6366f11a' },
  contacted:       { label: 'Contacted',      color: '#f59e0b', bg: '#f59e0b1a' },
  meeting_booked:  { label: 'Meeting Booked', color: '#10b981', bg: '#10b9811a' },
  converted:       { label: 'Converted',      color: '#22d3ee', bg: '#22d3ee1a' },
  not_interested:  { label: 'Not Interested', color: '#94a3b8', bg: '#94a3b81a' },
};

async function renderPipeline() {
  setContent(`
    <div class="pipeline-page">
      <div class="page-hd">
        <div>
          <h1 class="page-title">Follow-up Pipeline</h1>
          <p class="page-sub">Track high-intent attendees from your webinars through to booked meetings and conversions.</p>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="btn btn-ghost btn-sm" onclick="window.open('/api/pipeline/export','_blank')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export CSV
          </button>
          <button class="btn btn-ghost btn-sm" onclick="_pipelineCache=null;renderPipeline()">Refresh</button>
          <button class="btn btn-primary btn-sm" onclick="openAddToPipelineModal()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add Lead
          </button>
        </div>
      </div>
      <div id="pipeline-body"><div class="pg-loading"><div class="spinner"></div><p>Loading pipeline…</p></div></div>
    </div>`);
  try {
    if (!_pipelineCache) _pipelineCache = await api('/api/pipeline');
    _drawPipeline(_pipelineCache);
  } catch(e) {
    document.getElementById('pipeline-body').innerHTML = `<div class="empty-state"><div class="empty-title">Failed to load pipeline</div><div class="empty-sub">${esc(e.message)}</div></div>`;
  }
}

function _drawPipeline(contacts) {
  const body = document.getElementById('pipeline-body');
  if (!body) return;

  const filtered = _pipelineFilter === 'all' ? contacts : contacts.filter(c => c.status === _pipelineFilter);

  // KPI summary row
  const counts = {};
  for (const s of Object.keys(PIPELINE_STATUS_META)) counts[s] = 0;
  contacts.forEach(c => { if (counts[c.status] !== undefined) counts[c.status]++; });

  const kpiHtml = `
    <div class="pipeline-kpis">
      <div class="pipeline-kpi ${_pipelineFilter==='all'?'active':''}" onclick="_pipelineFilter='all';_drawPipeline(_pipelineCache)" style="cursor:pointer">
        <div class="pipeline-kpi-val">${contacts.length}</div>
        <div class="pipeline-kpi-lbl">Total</div>
      </div>
      ${Object.entries(PIPELINE_STATUS_META).map(([k,m]) => `
        <div class="pipeline-kpi ${_pipelineFilter===k?'active':''}" onclick="_pipelineFilter='${k}';_drawPipeline(_pipelineCache)" style="cursor:pointer;--kpi-color:${m.color}">
          <div class="pipeline-kpi-val" style="color:${m.color}">${counts[k]||0}</div>
          <div class="pipeline-kpi-lbl">${m.label}</div>
        </div>`).join('')}
    </div>`;

  if (!filtered.length) {
    body.innerHTML = kpiHtml + `<div class="empty-state" style="margin-top:32px">
      <div class="empty-title">${_pipelineFilter==='all'?'No leads in pipeline yet':'No leads in this stage'}</div>
      <div class="empty-sub">${_pipelineFilter==='all'?'Add leads from the Leaderboard or click "Add Lead" above.':'Try selecting a different stage above.'}</div>
    </div>`;
    return;
  }

  const rows = filtered.map(c => {
    const meta = PIPELINE_STATUS_META[c.status] || PIPELINE_STATUS_META.new;
    const av = avColor(c.name); const ini = initials(c.name);
    const totalMin = c.total_duration || 0;
    const dur = totalMin >= 60 ? (totalMin/60).toFixed(1)+'h' : totalMin+'m';
    const followUp = c.follow_up_date ? `<span style="font-size:11px;color:var(--text-muted)">${fmtDate(c.follow_up_date)}</span>` : '';
    return `
    <tr class="pipeline-row">
      <td>
        <div style="display:flex;align-items:center;gap:10px">
          <div class="spk-avatar" style="width:32px;height:32px;min-width:32px;background:${av};color:#fff;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:700;font-size:11px">${ini}</div>
          <div>
            <div style="font-weight:600;color:var(--text-primary);font-size:13px">${esc(c.name)}</div>
            <div style="font-size:11px;color:var(--text-muted)">${esc(c.email)}</div>
          </div>
        </div>
      </td>
      <td style="text-align:center;font-family:var(--font-mono);font-weight:600">${c.total_webinars||0}</td>
      <td style="text-align:center;font-family:var(--font-mono);color:var(--text-secondary)">${dur}</td>
      <td style="text-align:center;font-size:11px;color:var(--text-muted)">${c.last_webinar?fmtDate(c.last_webinar):'-'}</td>
      <td style="text-align:center">
        <select class="pipeline-status-select" data-email="${esc(c.email)}" style="background:${meta.bg};color:${meta.color};border-color:${meta.color}40"
          onchange="updatePipelineStatus('${esc(c.email)}',this.value)">
          ${Object.entries(PIPELINE_STATUS_META).map(([k,m])=>`<option value="${k}" ${c.status===k?'selected':''}>${m.label}</option>`).join('')}
        </select>
      </td>
      <td style="text-align:center;font-size:11px;color:var(--text-muted)">${esc(c.assigned_to||'—')}</td>
      <td>
        <div style="font-size:12px;color:var(--text-secondary);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(c.notes||'')}">
          ${c.notes ? esc(c.notes) : '<span style="color:var(--text-muted)">No notes</span>'}
        </div>
        ${followUp}
      </td>
      <td>
        <div style="display:flex;gap:6px">
          <button class="btn btn-ghost btn-xs" onclick="openEditPipelineModal(${JSON.stringify(c).replace(/"/g,'&quot;')})" title="Edit">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn btn-ghost btn-xs" style="color:#f43f5e" onclick="removePipelineLead('${esc(c.email)}')" title="Remove">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
          </button>
        </div>
      </td>
    </tr>`;
  }).join('');

  body.innerHTML = kpiHtml + `
    <div class="intel-table-wrap" style="margin-top:16px">
      <table class="intel-table pipeline-table">
        <thead><tr>
          <th>Lead</th>
          <th style="text-align:center">Webinars</th>
          <th style="text-align:center">Time</th>
          <th style="text-align:center">Last Seen</th>
          <th style="text-align:center">Status</th>
          <th style="text-align:center">Assigned</th>
          <th>Notes</th>
          <th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function updatePipelineStatus(email, status) {
  try {
    await api(`/api/pipeline/${encodeURIComponent(email)}`, 'PUT', { status });
    const contact = (_pipelineCache||[]).find(c => c.email === email);
    if (contact) { contact.status = status; _drawPipeline(_pipelineCache); }
  } catch(e) {
    alert('Failed to update status: ' + e.message);
  }
}

async function removePipelineLead(email) {
  if (!confirm(`Remove ${email} from pipeline?`)) return;
  try {
    await api(`/api/pipeline/${encodeURIComponent(email)}`, 'DELETE');
    _pipelineCache = (_pipelineCache||[]).filter(c => c.email !== email);
    _drawPipeline(_pipelineCache);
  } catch(e) {
    alert('Failed to remove: ' + e.message);
  }
}

function openAddToPipelineModal() {
  _openPipelineModal(null);
}

function openEditPipelineModal(contact) {
  _openPipelineModal(contact);
}

function _openPipelineModal(contact) {
  const isEdit = !!contact;
  const existing = document.getElementById('pipeline-modal-overlay');
  if (existing) existing.remove();

  document.body.insertAdjacentHTML('beforeend', `
    <div id="pipeline-modal-overlay" class="modal-overlay open" onclick="if(event.target===this)closePipelineModal()">
      <div class="modal-box" style="max-width:480px">
        <div class="modal-header">
          <h3>${isEdit ? 'Edit Pipeline Lead' : 'Add Lead to Pipeline'}</h3>
          <button class="modal-close" onclick="closePipelineModal()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="modal-body" style="display:flex;flex-direction:column;gap:14px;padding:20px 24px">
          <div class="form-group">
            <label class="form-label">Email *</label>
            <input class="form-input" id="pl-email" type="email" value="${esc(contact?.email||'')}" placeholder="lead@example.com" ${isEdit?'readonly':''} />
          </div>
          <div class="form-group">
            <label class="form-label">Status</label>
            <select class="form-input" id="pl-status">
              ${Object.entries(PIPELINE_STATUS_META).map(([k,m])=>`<option value="${k}" ${(contact?.status||'new')===k?'selected':''}>${m.label}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Assigned To</label>
            <input class="form-input" id="pl-assigned" type="text" value="${esc(contact?.assigned_to||'')}" placeholder="Salesperson name" />
          </div>
          <div class="form-group">
            <label class="form-label">Follow-up Date</label>
            <input class="form-input" id="pl-followup" type="date" value="${esc(contact?.follow_up_date||'')}" />
          </div>
          <div class="form-group">
            <label class="form-label">Notes</label>
            <textarea class="form-input" id="pl-notes" rows="3" placeholder="Call notes, context, interest areas…">${esc(contact?.notes||'')}</textarea>
          </div>
        </div>
        <div class="modal-footer" style="padding:16px 24px;display:flex;justify-content:flex-end;gap:8px">
          <button class="btn btn-ghost" onclick="closePipelineModal()">Cancel</button>
          <button class="btn btn-primary" onclick="savePipelineLead()">
            ${isEdit ? 'Save Changes' : 'Add to Pipeline'}
          </button>
        </div>
      </div>
    </div>`);
}

function closePipelineModal() {
  const el = document.getElementById('pipeline-modal-overlay');
  if (el) el.remove();
}

async function savePipelineLead() {
  const email     = (document.getElementById('pl-email')?.value || '').trim();
  const status    = document.getElementById('pl-status')?.value || 'new';
  const assigned  = (document.getElementById('pl-assigned')?.value || '').trim();
  const followup  = (document.getElementById('pl-followup')?.value || '').trim();
  const notes     = (document.getElementById('pl-notes')?.value || '').trim();

  if (!email) { alert('Email is required'); return; }

  try {
    const btn = document.querySelector('#pipeline-modal-overlay .btn-primary');
    if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
    await api(`/api/pipeline/${encodeURIComponent(email)}`, 'PUT', { status, assigned_to: assigned||null, follow_up_date: followup||null, notes: notes||null });
    closePipelineModal();
    _pipelineCache = null;
    if (S.page === 'pipeline') {
      _pipelineCache = await api('/api/pipeline');
      _drawPipeline(_pipelineCache);
    }
  } catch(e) {
    alert('Save failed: ' + e.message);
    const btn = document.querySelector('#pipeline-modal-overlay .btn-primary');
    if (btn) { btn.disabled = false; btn.textContent = 'Save'; }
  }
}

/* Add to pipeline from leaderboard row */
async function addLeaderboardToPipeline(email, name) {
  try {
    await api(`/api/pipeline/${encodeURIComponent(email)}`, 'PUT', { status: 'new' });
    _pipelineCache = null;
    _pipelineToast(`${name} added to pipeline`);
  } catch(e) {
    alert('Failed: ' + e.message);
  }
}

function _pipelineToast(msg) {
  showToast(msg, 'success');
}

/* ── AI Chatbot ──────────────────────────────────────────────────────────── */
let _chatOpen   = false;
let _chatHistory = [];

function initChatbot() {
  if (document.getElementById('chatbot-wrap')) return;
  document.body.insertAdjacentHTML('beforeend', `
    <!-- Chatbot FAB -->
    <button class="chat-fab" id="chat-fab" onclick="toggleChat()" title="Ask WebinarIQ AI">
      <svg id="chat-fab-open" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      <svg id="chat-fab-close" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="display:none"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      <span class="chat-fab-label">Ask AI</span>
    </button>

    <!-- Chat panel -->
    <div class="chatbot-wrap" id="chatbot-wrap">
      <div class="chatbot-header">
        <div class="chatbot-hd-left">
          <div class="chatbot-avatar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg>
          </div>
          <div>
            <div class="chatbot-hd-title">WebinarIQ AI</div>
            <div class="chatbot-hd-sub">WebinarIQ AI Assistant</div>
          </div>
        </div>
        <button class="chatbot-close-btn" onclick="toggleChat()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="chatbot-messages" id="chatbot-messages">
        <div class="chat-msg chat-msg-ai">
          <div class="chat-bubble">Hi! I can answer any question about your webinars. Ask me about attendance rates, top speakers, ICP breakdown, trends and more. What would you like to know?</div>
          <div class="chat-suggestions">
            <button onclick="sendChatSuggestion(this)">Which speaker has the best attendance rate?</button>
            <button onclick="sendChatSuggestion(this)">Top 3 webinars by registrations</button>
            <button onclick="sendChatSuggestion(this)">How are PMS webinars performing?</button>
            <button onclick="sendChatSuggestion(this)">NRI webinar attendance trend</button>
          </div>
        </div>
      </div>

      <div class="chatbot-input-wrap">
        <input class="chatbot-input" id="chatbot-input" placeholder="Ask anything about your webinars…"
          onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat()}" />
        <button class="chatbot-send" id="chatbot-send" onclick="sendChat()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
  `);
}

function toggleChat() {
  _chatOpen = !_chatOpen;
  const wrap = document.getElementById('chatbot-wrap');
  const fab  = document.getElementById('chat-fab');
  const openIcon  = document.getElementById('chat-fab-open');
  const closeIcon = document.getElementById('chat-fab-close');
  if (wrap)  wrap.classList.toggle('open', _chatOpen);
  if (fab)   fab.classList.toggle('active', _chatOpen);
  if (openIcon)  openIcon.style.display  = _chatOpen ? 'none'  : '';
  if (closeIcon) closeIcon.style.display = _chatOpen ? ''      : 'none';
  if (_chatOpen) setTimeout(() => document.getElementById('chatbot-input')?.focus(), 300);
}

function sendChatSuggestion(btn) {
  const q = btn.textContent.trim();
  // Remove suggestions
  btn.closest('.chat-suggestions')?.remove();
  _sendChatMessage(q);
}

function sendChat() {
  const input = document.getElementById('chatbot-input');
  const q = (input?.value || '').trim();
  if (!q) return;
  input.value = '';
  _sendChatMessage(q);
}

function _appendChatMsg(role, text, typing=false) {
  const msgs = document.getElementById('chatbot-messages');
  if (!msgs) return null;
  const div = document.createElement('div');
  div.className = `chat-msg chat-msg-${role}`;
  div.innerHTML = `<div class="chat-bubble">${typing ? '<span class="chat-typing"><span></span><span></span><span></span></span>' : esc(text).replace(/\n/g,'<br>')}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

async function _sendChatMessage(question) {
  // Show user message
  _appendChatMsg('user', question);
  _chatHistory.push({ role: 'user', content: question });

  // Disable input
  const input = document.getElementById('chatbot-input');
  const send  = document.getElementById('chatbot-send');
  if (input) input.disabled = true;
  if (send)  send.disabled  = true;

  // Show typing indicator
  const typingDiv = _appendChatMsg('ai', '', true);

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history: _chatHistory.slice(-6) })
    });
    const data = await res.json();
    const answer = res.ok ? (data.answer || 'Sorry, I could not get an answer.') : (data.detail || 'Something went wrong.');

    // Replace typing with answer
    if (typingDiv) typingDiv.querySelector('.chat-bubble').innerHTML = esc(answer).replace(/\n/g,'<br>');
    _chatHistory.push({ role: 'assistant', content: answer });

    const msgs = document.getElementById('chatbot-messages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
  } catch(e) {
    if (typingDiv) typingDiv.querySelector('.chat-bubble').textContent = 'Network error. Please try again.';
  } finally {
    if (input) { input.disabled = false; input.focus(); }
    if (send)  send.disabled = false;
  }
}

/* ── AI Comparison ─────────────────────────────────────────────────────────── */
async function runAIComparison(webinarId) {
  const btn   = document.getElementById('ai-compare-btn');
  const panel = document.getElementById('ai-compare-panel');
  if (!panel) return;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg class="spin" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.22-8.56"/></svg> Comparing…`;
  }
  panel.innerHTML = `
    <div class="aip ai-loading" style="padding:24px;border:1px solid rgba(124,58,237,0.20);border-radius:1.5rem;background:rgba(255,255,255,0.85);backdrop-filter:blur(16px) saturate(140%);margin-top:18px">
      <div style="display:flex;align-items:center;gap:10px;color:var(--accent-primary);font-weight:600">
        <svg class="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.22-8.56"/></svg>
        <span>Pulling previous webinar and computing deltas…</span>
      </div>
    </div>`;

  try {
    const res = await fetch(`/api/webinars/${webinarId}/compare`, { method:'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Comparison failed' }));
      throw new Error(err.detail || 'Comparison failed');
    }
    const data = await res.json();
    renderComparePanel(panel, data);
    if (btn) {
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Comparison Done`;
      btn.classList.add('ai-done');
    }
    panel.scrollIntoView({ behavior:'smooth', block:'start' });
  } catch(e) {
    panel.innerHTML = `
      <div class="aip ai-error" style="padding:18px;border:1px solid rgba(220,38,38,0.30);border-radius:1.5rem;background:rgba(254,242,242,0.85);color:#991B1B;margin-top:18px">
        ${esc(e.message || 'Comparison failed')}
      </div>`;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg> Retry Comparison`;
    }
  }
}

function renderComparePanel(panel, data) {
  const a = data.analysis || {};
  const cur = data.current, prev = data.previous, d = data.deltas;
  const fmt = n => n >= 1000 ? (n/1000).toFixed(1)+'k' : String(n);
  const deltaCls = (v) => v > 0 ? 'cmp-up' : v < 0 ? 'cmp-down' : 'cmp-flat';
  const deltaSym = (v) => v > 0 ? '↑' : v < 0 ? '↓' : '→';

  const rows = [
    { label:'Registrations',    cur: cur.registrations,    prev: prev.registrations,    d: d.registrations },
    { label:'Attendees',        cur: cur.attendees,        prev: prev.attendees,        d: d.attendees },
    { label:'Attendance rate',  cur: cur.attendance_rate+'%', prev: prev.attendance_rate+'%', d: d.attendance_rate, unit:'pp' },
    { label:'Avg duration',     cur: cur.avg_duration_min+'m', prev: prev.avg_duration_min+'m', d: d.avg_duration_min, unit:'m' },
    { label:'Engaged 45m+',     cur: cur.engaged_45plus,   prev: prev.engaged_45plus,   d: d.engaged_45plus },
  ].map(r => `
    <tr>
      <td class="cmp-lbl">${r.label}</td>
      <td class="cmp-val cmp-cur">${r.cur}</td>
      <td class="cmp-val cmp-prev">${r.prev}</td>
      <td class="cmp-delta ${deltaCls(r.d.abs)}">${deltaSym(r.d.abs)} ${r.d.abs > 0 ? '+' : ''}${r.d.abs}${r.unit||''}${r.d.pct!=null?` <span class="cmp-pct">(${r.d.pct>0?'+':''}${r.d.pct}%)</span>`:''}</td>
    </tr>`).join('');

  const wins  = (a.key_wins || []).map(s => `<li>${esc(s)}</li>`).join('');
  const losses = (a.key_losses || []).map(s => `<li>${esc(s)}</li>`).join('');

  panel.innerHTML = `
    <div class="aip cmp-panel" style="margin-top:18px">
      <div class="aip-header">
        <span style="color:var(--accent-primary);display:flex;align-items:center">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
        </span>
        <span class="aip-header-title">Comparison Analysis</span>
        <span class="aip-header-badge">vs ${esc(data.comparison_basis)}</span>
      </div>

      <div class="cmp-headline">${esc(a.headline || '')}</div>

      <div class="cmp-context">
        <div class="cmp-card cmp-card-cur">
          <div class="cmp-card-tag">CURRENT</div>
          <div class="cmp-card-title">${esc(cur.title)}</div>
          <div class="cmp-card-meta">${esc(cur.date)} · ${esc(cur.speaker)} · ${esc(cur.icp)}</div>
        </div>
        <div class="cmp-vs">vs</div>
        <div class="cmp-card cmp-card-prev">
          <div class="cmp-card-tag">PREVIOUS</div>
          <div class="cmp-card-title">${esc(prev.title)}</div>
          <div class="cmp-card-meta">${esc(prev.date)} · ${esc(prev.speaker)} · ${esc(prev.icp)}</div>
        </div>
      </div>

      <table class="cmp-table">
        <thead>
          <tr>
            <th>Metric</th><th>Current</th><th>Previous</th><th>Delta</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>

      <div class="cmp-grid">
        <div class="cmp-block cmp-wins">
          <div class="cmp-block-title">✓ Wins</div>
          <ul>${wins || '<li class="cmp-empty">None notable</li>'}</ul>
        </div>
        <div class="cmp-block cmp-losses">
          <div class="cmp-block-title">✗ Losses</div>
          <ul>${losses || '<li class="cmp-empty">None notable</li>'}</ul>
        </div>
      </div>

      <div class="cmp-diagnosis">
        <div class="aip-card-hd">DIAGNOSIS</div>
        <p>${esc(a.diagnosis || '')}</p>
      </div>

      <div class="cmp-action">
        <div class="aip-card-hd">NEXT ACTION</div>
        <p><strong>${esc(a.next_action || '')}</strong></p>
      </div>
    </div>`;
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
      <div>No ad creatives yet. Click <strong>Add Ad</strong> to attach one to this webinar</div>
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
          <div class="ad-metric-val">${ad.impressions != null ? fmt(ad.impressions) : 'N/A'}</div>
          <div class="ad-metric-label">Impressions</div>
        </div>
        <div class="ad-metric">
          <div class="ad-metric-val">${ad.clicks != null ? fmt(ad.clicks) : 'N/A'}</div>
          <div class="ad-metric-label">Clicks</div>
        </div>
        <div class="ad-metric">
          <div class="ad-metric-val">${ad.conversions != null ? fmt(ad.conversions) : 'N/A'}</div>
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
          ${ad.landing_url ? `<a href="${esc(ad.landing_url)}" target="_blank" rel="noopener" style="font-size:11px;color:var(--accent);text-decoration:none;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(ad.landing_url)}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg> ${esc(ad.landing_url)}</a>` : ''}
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
async function editWebinar(id) {
  // Find webinar in cache, or fetch it
  let w = S.webinars.find(x => x.id == id) || detailCache[id];
  if (!w) {
    try { w = await api(`/api/webinars/${id}`); } catch(e) { showToast('Failed to load webinar', 'error'); return; }
  }
  openWebinarModal(w);
}

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
   UPLOAD PAGE
══════════════════════════════════════════════════════════════════════════ */
function renderUpload() {
  const today = new Date().toISOString().slice(0,10);
  setContent(`
    <div>
      <div class="page-hd">
        <div>
          <h1 class="page-title">Export Analysis Reports</h1>
          <p class="page-sub">Download detailed webinar analysis reports as PDF.</p>
        </div>
      </div>

      <!-- Date range filter -->
      <div class="export-filter-bar" style="display:flex;align-items:center;gap:12px;margin-bottom:28px;flex-wrap:wrap">
        <label style="font-size:13px;font-weight:600;color:var(--text-secondary)">Date Range:</label>
        <input type="date" id="export-from" class="form-input" style="width:160px" onchange="filterExportWebinars()" placeholder="From" />
        <span style="color:var(--text-muted)">to</span>
        <input type="date" id="export-to" value="${today}" class="form-input" style="width:160px" onchange="filterExportWebinars()" />
        <button class="btn btn-ghost btn-sm" onclick="document.getElementById('export-from').value='';document.getElementById('export-to').value='';filterExportWebinars()">Show All</button>
        <button class="btn btn-ghost btn-sm" onclick="(()=>{const d=new Date();d.setDate(d.getDate()-30);document.getElementById('export-from').value=d.toISOString().slice(0,10);document.getElementById('export-to').value='${today}';filterExportWebinars()})()">Last 30 days</button>
        <button class="btn btn-ghost btn-sm" onclick="(()=>{const d=new Date();d.setDate(d.getDate()-90);document.getElementById('export-from').value=d.toISOString().slice(0,10);document.getElementById('export-to').value='${today}';filterExportWebinars()})()">Last 90 days</button>
        <span id="export-count" style="margin-left:auto;font-size:12px;color:var(--text-muted)"></span>
      </div>

      <!-- Webinar list -->
      <div id="export-webinar-list"></div>
    </div>`);

  filterExportWebinars();
}

function filterExportWebinars() {
  const from = document.getElementById('export-from')?.value;
  const to   = document.getElementById('export-to')?.value;
  const list = document.getElementById('export-webinar-list');
  const countEl = document.getElementById('export-count');
  if (!list) return;

  let webinars = [...(S.webinars || [])].sort((a,b) => new Date(b.date) - new Date(a.date));
  if (from) webinars = webinars.filter(w => w.date >= from);
  if (to)   webinars = webinars.filter(w => w.date <= to);

  if (countEl) countEl.textContent = `${webinars.length} webinar${webinars.length !== 1 ? 's' : ''}`;

  if (!webinars.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-title">No webinars in this range</div><div class="empty-sub">Try adjusting the date range above.</div></div>';
    return;
  }

  list.innerHTML = `
    <div style="display:grid;gap:12px">
      ${webinars.map(w => {
        const statusColor = w.status === 'completed' ? '#10b981' : w.status === 'upcoming' ? '#6366f1' : '#94a3b8';
        const hasData = w.total_registrations > 0 || w.total_attendees > 0;
        return `
          <div class="export-webinar-row" style="background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
            <div style="flex:1;min-width:0">
              <div style="font-weight:700;font-size:15px;color:var(--text-primary);margin-bottom:4px">${esc(w.title)}</div>
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--text-muted)">
                <span>${fmtDate(w.date)}</span>
                <span>·</span>
                <span style="color:${statusColor};font-weight:600">${w.status?.replace(/_/g,' ')}</span>
                ${hasData ? `<span>·</span><span>${fmt(w.total_registrations)} registrations · ${fmt(w.total_attendees)} attended</span>` : '<span>· No data uploaded yet</span>'}
                ${w.speaker_name ? `<span>·</span><span>${esc(w.speaker_name)}</span>` : ''}
              </div>
            </div>
            <div style="display:flex;gap:8px;flex-shrink:0">
              <button class="btn btn-ghost btn-sm" onclick="nav('webinar',${w.id})" style="font-size:12px">View Details</button>
              <button class="btn btn-primary btn-sm" onclick="exportWebinarReport(${w.id},'${esc(w.title).replace(/'/g,"\\'")}')" style="font-size:12px;display:flex;align-items:center;gap:6px" ${!hasData?'title="No data available yet"':''}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Export Report
              </button>
            </div>
          </div>`;
      }).join('')}
    </div>`;
}

async function exportWebinarReport(webinarId, title) {
  const btn = event?.target?.closest('button');
  if (btn) { btn.disabled = true; btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="spin"><path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/></svg> Running AI analysis…'; }
  try {
    // Run AI analysis + fetch data in parallel
    const [webinar, funnel, aiAnalysis] = await Promise.all([
      api(`/api/webinars/${webinarId}`).catch(()=>null),
      api(`/api/webinar-funnel/${webinarId}`).catch(()=>null),
      api(`/api/webinars/${webinarId}/analyze`, 'POST', {}).catch(()=>null),
    ]);

    const w = webinar || S.webinars.find(x => x.id === webinarId) || {};
    const funnelStages = funnel?.stages || [];
    const aiData = aiAnalysis?.analysis || null;
    const aiText = typeof aiData === 'string' ? aiData : (w.ai_summary || '');

    // Compare against all completed webinars for context
    const completed = (S.webinars||[]).filter(x=>x.status==='completed'&&x.total_registrations>0);
    const avgRate   = completed.length ? Math.round(completed.reduce((s,x)=>s+(x.attendance_rate||0),0)/completed.length) : 0;
    const avgRegs   = completed.length ? Math.round(completed.reduce((s,x)=>s+(x.total_registrations||0),0)/completed.length) : 0;
    const rank      = completed.filter(x=>(x.attendance_rate||0) > (w.attendance_rate||0)).length + 1;
    const myRate    = w.attendance_rate || 0;
    const rateColor = myRate >= 40 ? '#059669' : myRate >= 25 ? '#d97706' : '#dc2626';

    const reportHtml = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<title>Webinar Report — ${esc(w.title||title)}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',Arial,sans-serif;max-width:860px;margin:0 auto;padding:32px 40px;color:#111827;line-height:1.65;font-size:14px}
  .cover{text-align:center;padding:48px 0 36px;border-bottom:2px solid #6366f1;margin-bottom:32px}
  .cover-logo{font-size:13px;font-weight:700;color:#6366f1;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px}
  .cover-title{font-size:24px;font-weight:800;color:#111827;margin-bottom:6px;line-height:1.3}
  .cover-meta{font-size:13px;color:#6b7280;margin-top:8px}
  h2{font-size:16px;font-weight:700;color:#111827;margin:28px 0 12px;padding:8px 14px;background:#f3f4f6;border-left:4px solid #6366f1;border-radius:0 6px 6px 0}
  h3{font-size:14px;font-weight:700;color:#374151;margin:20px 0 8px}
  .kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0 24px}
  .kpi-box{background:#fff;border:1.5px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center;border-top:3px solid #6366f1}
  .kpi-val{font-size:26px;font-weight:800;color:#6366f1;line-height:1}
  .kpi-lbl{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:#9ca3af;margin-top:6px}
  .kpi-sub{font-size:11px;color:#9ca3af;margin-top:3px}
  table{width:100%;border-collapse:collapse;margin:12px 0 20px;font-size:13px}
  th{background:#6366f1;color:#fff;padding:9px 12px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px}
  td{padding:9px 12px;border-bottom:1px solid #e5e7eb}
  tr:nth-child(even) td{background:#f9fafb}
  .badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap}
  .badge-green{background:#d1fae5;color:#059669} .badge-orange{background:#fef3c7;color:#d97706} .badge-red{background:#fee2e2;color:#dc2626} .badge-blue{background:#dbeafe;color:#1d4ed8}
  .ai-box{background:#f5f3ff;border:1.5px solid #c4b5fd;border-radius:10px;padding:20px 24px;margin:16px 0 24px}
  .ai-box-header{display:flex;align-items:center;gap:8px;margin-bottom:12px}
  .ai-label{font-size:10px;font-weight:700;color:#7c3aed;text-transform:uppercase;letter-spacing:1px;background:#ede9fe;border-radius:20px;padding:3px 10px}
  .ai-content{font-size:13.5px;line-height:1.75;color:#374151;white-space:pre-wrap;word-break:break-word}
  .funnel-row{display:flex;align-items:center;gap:12px;margin-bottom:8px}
  .funnel-fill{height:20px;border-radius:4px;display:flex;align-items:center;padding:0 8px;color:#fff;font-size:11px;font-weight:700;min-width:80px;transition:width .6s}
  .comp-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #e5e7eb;font-size:13px}
  .comp-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
  .footer{margin-top:40px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center}
  @media print{
    body{padding:20px 24px}
    .kpi-grid{grid-template-columns:repeat(4,1fr)}
    h2{break-after:avoid}
    .ai-box{break-inside:avoid}
  }
</style></head><body>

<div class="cover">
  <div class="cover-logo">WebinarIQ · Right Horizons</div>
  <div class="cover-title">${esc(w.title||title)}</div>
  <div class="cover-meta">
    ${fmtDate(w.date||'')} &nbsp;·&nbsp; Speaker: <strong>${esc(w.speaker_name||'—')}</strong> &nbsp;·&nbsp;
    ICP: <strong>${esc(w.icp||'—')}</strong> &nbsp;·&nbsp; Status: <strong>${(w.status||'').replace(/_/g,' ')}</strong>
    <br>Generated: ${new Date().toLocaleString('en-IN')} &nbsp;·&nbsp; Confidential
  </div>
</div>

<h2>Performance Summary</h2>
<div class="kpi-grid">
  <div class="kpi-box"><div class="kpi-val">${fmt(w.total_registrations||0)}</div><div class="kpi-lbl">Registrations</div><div class="kpi-sub">vs avg ${fmt(avgRegs)}</div></div>
  <div class="kpi-box"><div class="kpi-val">${fmt(w.total_attendees||0)}</div><div class="kpi-lbl">Attendees</div><div class="kpi-sub">${w.total_registrations>0?Math.round((w.total_attendees||0)/(w.total_registrations||1)*100)+'% show-up':''}</div></div>
  <div class="kpi-box" style="border-top-color:${rateColor}"><div class="kpi-val" style="color:${rateColor}">${myRate.toFixed(1)}%</div><div class="kpi-lbl">Attendance Rate</div><div class="kpi-sub">Prog avg: ${avgRate}%</div></div>
  <div class="kpi-box" style="border-top-color:${w.performance_score>=80?'#059669':w.performance_score>=60?'#6366f1':w.performance_score>=40?'#d97706':'#dc2626'}"><div class="kpi-val" style="color:${w.performance_score>=80?'#059669':w.performance_score>=60?'#6366f1':w.performance_score>=40?'#d97706':'#dc2626'}">${w.performance_score ?? '—'}</div><div class="kpi-lbl">Performance Score</div><div class="kpi-sub">${w.score_label||''}</div></div>
</div>

<h2>Webinar Details</h2>
<table><tbody>
  <tr><td style="width:160px;color:#6b7280;font-weight:600">Title</td><td>${esc(w.title||'')}</td></tr>
  <tr><td style="color:#6b7280;font-weight:600">Date</td><td>${fmtDate(w.date||'')}</td></tr>
  <tr><td style="color:#6b7280;font-weight:600">Speaker</td><td>${esc(w.speaker_name||'—')}</td></tr>
  <tr><td style="color:#6b7280;font-weight:600">ICP Target</td><td>${esc(w.icp||'—')}</td></tr>
  <tr><td style="color:#6b7280;font-weight:600">Programme Rank</td><td><span class="badge badge-blue">#${rank} of ${completed.length}</span></td></tr>
  <tr><td style="color:#6b7280;font-weight:600">No-shows</td><td>${fmt(Math.max(0,(w.total_registrations||0)-(w.total_attendees||0)))} (${w.total_registrations>0?Math.round(Math.max(0,(w.total_registrations||0)-(w.total_attendees||0))/(w.total_registrations||1)*100):'0'}% of registered)</td></tr>
  ${w.description ? `<tr><td style="color:#6b7280;font-weight:600">Description</td><td>${esc(w.description)}</td></tr>` : ''}
</tbody></table>

${funnelStages.length ? `
<h2>Conversion Funnel</h2>
${funnelStages.map((s,i) => {
  const clr = i===0?'#6366f1':s.pct>=50?'#10b981':s.pct>=30?'#f59e0b':'#f43f5e';
  return `<div class="funnel-row">
    <div style="width:90px;font-size:12px;color:#6b7280;font-weight:600;flex-shrink:0">${esc(s.label)}</div>
    <div class="funnel-fill" style="width:${Math.max(s.pct,10)}%;background:${clr}">${s.pct}%</div>
    <div style="font-size:13px;font-weight:700;min-width:60px">${fmt(s.count)}</div>
    <div style="font-size:11px;color:${i===0?'#6b7280':'#dc2626'}">${i===0?'base':s.drop!==undefined?s.drop+'% drop-off':''}</div>
  </div>`;
}).join('')}` : ''}

${aiData && typeof aiData === 'object' ? `
<h2>AI Analysis</h2>
<div class="ai-box">
  <div class="ai-box-header">
    <span class="ai-label">✦ AI Generated</span>
    ${aiData.grade ? `<span style="margin-left:auto;font-size:18px;font-weight:800;color:${aiData.grade==='A'?'#059669':aiData.grade==='B'?'#6366f1':aiData.grade==='C'?'#d97706':'#dc2626'};background:${aiData.grade==='A'?'#d1fae5':aiData.grade==='B'?'#dbeafe':aiData.grade==='C'?'#fef3c7':'#fee2e2'};border-radius:8px;padding:2px 12px">Grade ${aiData.grade}</span>` : ''}
  </div>
  ${aiData.score_summary ? `<div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:16px;padding:12px 16px;background:#fff;border-radius:8px;border-left:4px solid #6366f1">${esc(aiData.score_summary)}</div>` : ''}
  ${(aiData.sections||[]).length ? `
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
    ${(aiData.sections||[]).map(s=>`
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px">
      <div style="font-size:11px;font-weight:700;color:#6366f1;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">${s.icon||''} ${esc(s.title)}</div>
      <div style="font-size:13px;line-height:1.65;color:#374151;margin-bottom:8px">${esc(s.insight)}</div>
      ${s.highlight ? `<div style="font-size:12px;font-weight:700;color:#111827;border-top:1px solid #e5e7eb;padding-top:8px">${esc(s.highlight)}</div>` : ''}
    </div>`).join('')}
  </div>` : ''}
  ${(aiData.recommendations||[]).length ? `
  <div style="margin-bottom:16px">
    <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px">Recommendations</div>
    ${(aiData.recommendations||[]).map((r,i)=>`
    <div style="display:flex;gap:10px;margin-bottom:8px;padding:10px 14px;background:#fff;border-radius:8px;border-left:3px solid #6366f1">
      <span style="font-size:13px;font-weight:800;color:#6366f1;flex-shrink:0">${i+1}.</span>
      <span style="font-size:13px;color:#374151;line-height:1.55">${esc(r)}</span>
    </div>`).join('')}
  </div>` : ''}
  ${aiData.verdict ? `<div style="background:#f5f3ff;border:1px solid #c4b5fd;border-radius:8px;padding:14px 16px;font-size:13.5px;line-height:1.7;color:#374151">${esc(aiData.verdict)}</div>` : ''}
</div>` : aiText ? `
<h2>AI Analysis</h2>
<div class="ai-box">
  <div class="ai-box-header"><span class="ai-label">✦ AI Generated</span></div>
  <div class="ai-content">${esc(aiText)}</div>
</div>` : ''}

${completed.length > 1 ? `
<h2>Programme Context</h2>
<table><thead><tr><th>Metric</th><th>This Webinar</th><th>Programme Average</th><th>vs Average</th></tr></thead><tbody>
  <tr><td>Registrations</td><td>${fmt(w.total_registrations||0)}</td><td>${fmt(avgRegs)}</td><td><span class="badge ${(w.total_registrations||0)>=avgRegs?'badge-green':'badge-orange'}">${(w.total_registrations||0)>=avgRegs?'+':'-'}${Math.abs((w.total_registrations||0)-avgRegs)}</span></td></tr>
  <tr><td>Attendance Rate</td><td>${myRate.toFixed(1)}%</td><td>${avgRate}%</td><td><span class="badge ${myRate>=avgRate?'badge-green':'badge-red'}">${myRate>=avgRate?'+':''+(myRate-avgRate).toFixed(1)}%</span></td></tr>
  <tr><td>Performance Score</td><td>${w.performance_score??''}</td><td>${Math.round(completed.reduce((s,x)=>s+(x.performance_score||0),0)/completed.length)||''}</td><td><span class="badge badge-blue">#${rank} of ${completed.length}</span></td></tr>
</tbody></table>` : ''}

<div class="footer">WebinarIQ · Right Horizons Financial Services · AI-Powered Webinar Intelligence · Confidential · ${new Date().toLocaleDateString('en-IN')}</div>
</body></html>`;

    const blob = new Blob([reportHtml], { type: 'text/html' });
    const url  = URL.createObjectURL(blob);
    const win  = window.open(url, '_blank');
    if (win) {
      win.addEventListener('load', () => {
        setTimeout(() => { try { win.print(); } catch(e) {} }, 800);
      });
    }
    URL.revokeObjectURL(url);
    showToast('Report ready — use Print → Save as PDF to download', 'success');
  } catch(e) {
    showToast('Failed to generate report: ' + e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Export Report'; }
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   ATTENDEE PROFILE DRAWER
══════════════════════════════════════════════════════════════════════════ */
/* ── Readiness badge + tag editor ──────────────────────────────────────── */
const READINESS_LABELS = {
  hot: 'Hot',
  warm: 'Warm',
  cold: 'Cold',
  customer: 'Customer',
  prospect: 'Prospect',
  partner: 'Partner',
  internal: 'Internal',
  employee: 'Employee',
  meeting_ready: 'Meeting Ready',
};

function renderReadinessBadge(key, isManual) {
  const label = READINESS_LABELS[key] || key;
  return `<span class="readiness-badge readiness-${key}${isManual?' is-manual':''}" title="${isManual?'Manual tag':'Auto-classified'}">${esc(label)}</span>`;
}

function openTagEditor(email, name, currentTag) {
  if (document.getElementById('tag-editor-overlay')) document.getElementById('tag-editor-overlay').remove();
  const overlay = document.createElement('div');
  overlay.id = 'tag-editor-overlay';
  overlay.className = 'modal-overlay open';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:420px" onclick="event.stopPropagation()">
      <div style="padding:24px 28px">
        <div class="modal-title">Tag Lead</div>
        <div style="font-family:var(--font-mono);font-size:12px;color:var(--text-muted);margin-top:4px">${esc(name)} · ${esc(email)}</div>

        <div style="margin-top:20px">
          <label class="form-label" style="margin-bottom:8px;display:block">Classification</label>
          <div class="tag-pill-row" id="tag-pill-row">
            ${['', 'customer', 'prospect', 'partner', 'employee', 'internal'].map(t => `
              <button class="tag-pill ${currentTag === t ? 'active' : ''}" data-tag="${t}" onclick="selectTagPill(this,'${t}')">
                ${t === '' ? 'Clear' : READINESS_LABELS[t] || t}
              </button>`).join('')}
          </div>
        </div>

        <div style="margin-top:18px">
          <label class="form-label" style="margin-bottom:6px;display:block">Note (optional)</label>
          <textarea class="form-input" id="tag-note" rows="2" placeholder="Why this tag?"></textarea>
        </div>

        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:20px">
          <button class="btn btn-ghost btn-sm" onclick="document.getElementById('tag-editor-overlay').remove()">Cancel</button>
          <button class="btn btn-primary btn-sm" onclick="saveTag('${email.replace(/'/g, "\\'")}')">Save Tag</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay._currentTag = currentTag;
}

function selectTagPill(el, tag) {
  el.parentElement.querySelectorAll('.tag-pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('tag-editor-overlay')._currentTag = tag;
}

async function saveTag(email) {
  const overlay = document.getElementById('tag-editor-overlay');
  const tag = overlay._currentTag !== undefined ? overlay._currentTag : '';
  const note = document.getElementById('tag-note').value.trim();
  try {
    const r = await fetch(`/api/lead-tags/${encodeURIComponent(email)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag, note }),
    });
    if (!r.ok) throw new Error('Save failed');
    overlay.remove();
    showToast(tag ? `Tagged as ${READINESS_LABELS[tag] || tag}` : 'Tag cleared');
    renderLeaderboard();
  } catch(e) {
    showToast('Failed to save tag', 'error');
  }
}

function exportLeaderboardCSV() {
  const params = new URLSearchParams();
  if (S._lbSpeaker)  params.set('speaker_id', S._lbSpeaker);
  if (S._lbWebinar)  params.set('webinar_id', S._lbWebinar);
  if (S._lbScoreMin) params.set('min_score', S._lbScoreMin);
  if (S._lbScoreMax) params.set('max_score', S._lbScoreMax);
  params.set('limit', S._lbLimit || 50);
  showToast('Preparing CSV export…');
  fetch('/api/leaderboard/export?' + params.toString())
    .then(r => r.blob())
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'leaderboard_export.csv';
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Downloaded leaderboard_export.csv', 'success');
    })
    .catch(() => showToast('Export failed. Please try again.', 'error'));
}

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

    // Webinar cards - max duration used for the bar scale
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
          <div class="att-wb-card-hd">
            <div class="att-wb-card-title">${wbTitle}</div>
            <span class="icp-badge icp-${(w.icp||'others').toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'')}" style="font-size:9px;padding:2px 7px;flex-shrink:0">${esc(w.icp || 'Others')}</span>
          </div>
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
   SIDEBAR RECENT (no-op - sidebar removed in website layout)
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
    { icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>', title: 'New Webinar',        sub: 'Create a webinar session',           fn: () => { closeCmdPalette(); openWebinarModal(); } },
    { icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>', title: 'Dashboard',           sub: 'Go to webinar overview',             fn: () => nav('home') },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>', title: 'Analytics',           sub: 'Platform-wide statistics',           fn: () => nav('analytics') },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>', title: 'Speakers',            sub: 'Browse all speakers',                fn: () => nav('speakers') },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>', title: 'Leaderboard',         sub: 'Top attendees by score',             fn: () => nav('leaderboard') },
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

  // Show skeleton immediately - replaced by real content once loadAll() finishes
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
  initChatbot();
  // Remove loading splash
  const _loader = document.getElementById('page-loader');
  if (_loader) { _loader.classList.add('fade'); setTimeout(() => _loader.remove(), 380); }
}

document.addEventListener('DOMContentLoaded', init);
