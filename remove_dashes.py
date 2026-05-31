"""Remove em dash (—) from all user-visible strings in app.js and index.html.
Keep it only in CSS comments (not user-visible) and code comments."""

# ── app.js ────────────────────────────────────────────────────────────────────
content = open('static/app.js', encoding='utf-8').read()

# User-visible string replacements
replacements = [
    # Descriptions / UI text
    ("attendance rate — Grade", "attendance rate · Grade"),
    ("% attendance — Grade", "% attendance · Grade"),
    ("across every webinar — all in one place.", "across every webinar, all in one place."),
    ("timed to market news, framed in their voice.", "timed to market news, framed in their voice."),
    ("No ad creatives yet — click", "No ad creatives yet. Click"),
    ("Could not save webinar — please try again.", "Could not save webinar. Please try again."),
    ("Failed to save ad — please try again.", "Failed to save ad. Please try again."),
    # Fallback values (keep as N/A instead of dash)
    ("return { grade: '—'", "return { grade: 'N/A'"),
    (": '—';", ": 'N/A';"),
    ("? fmtPct(avgRate) : '—'", "? fmtPct(avgRate) : 'N/A'"),
    ("? fmtPct(completionRate) : '—'", "? fmtPct(completionRate) : 'N/A'"),
    ("info.grade === '—' ? 'none'", "info.grade === 'N/A' ? 'none'"),
    ("info.grade === '—' ? 'none' : info.grade", "info.grade === 'N/A' ? 'none' : info.grade"),
    ("l.filename||'—'", "l.filename||'N/A'"),
    ("? fmtPct(sp.avgR) : '—'", "? fmtPct(sp.avgR) : 'N/A'"),
    ("sp.bio || '—'", "sp.bio || 'No bio available'"),
    ("sp.bio || '—'", "sp.bio || 'No bio available'"),
    ("esc(sp.bio || '—')", "esc(sp.bio || 'No bio available')"),
    ("title=\"No email — cannot look up profile\"", "title=\"No email on file\""),
    ("e.email||'—'", "e.email||'N/A'"),
    ("e.phone||'—'", "e.phone||'N/A'"),
    ("ad.impressions != null ? fmt(ad.impressions) : '—'", "ad.impressions != null ? fmt(ad.impressions) : 'N/A'"),
    ("ad.clicks != null ? fmt(ad.clicks) : '—'", "ad.clicks != null ? fmt(ad.clicks) : 'N/A'"),
    ("ad.conversions != null ? fmt(ad.conversions) : 'N/A'", "ad.conversions != null ? fmt(ad.conversions) : 'N/A'"),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f'app.js fixed: {old[:60]}')

open('static/app.js', 'w', encoding='utf-8').write(content)

# ── index.html ────────────────────────────────────────────────────────────────
html = open('static/index.html', encoding='utf-8').read()
html = html.replace(
    '<title>WebinarIQ — Webinar Intelligence</title>',
    '<title>WebinarIQ · Webinar Intelligence</title>'
)
open('static/index.html', 'w', encoding='utf-8').write(html)
print('index.html: title fixed')

# ── Verify ────────────────────────────────────────────────────────────────────
js_remaining = open('static/app.js', encoding='utf-8').read().count('—')
html_remaining = open('static/index.html', encoding='utf-8').read().count('—')
print(f'\nRemaining em dashes — app.js: {js_remaining}, index.html: {html_remaining}')
print('(CSS comments are fine to keep)')
