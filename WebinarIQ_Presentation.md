# WebinarIQ Analytics - Complete Platform Guide

## Platform Overview

WebinarIQ is an intelligent webinar analytics platform built for Right Horizons, an Indian financial advisory firm. It tracks, analyzes, and optimizes webinar campaigns across the entire programme, from registration to attendance to lead conversion, powered by AI.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI (serverless on Vercel) |
| Database | PostgreSQL via Supabase (production), SQLite (local dev) |
| Frontend | Vanilla JavaScript, single-page application |
| AI Engine | Claude Sonnet via OpenRouter API |
| News API | Tavily API for live trending topics |
| Hosting | Vercel (Singapore region), GitHub Actions CI/CD |
| Design System | Trilliant (glassmorphism, frosted glass UI) |

---

## Module-by-Module Breakdown

---

### 1. Dashboard (Home)

The command center of the platform. Shows a real-time overview of the entire webinar programme.

**What you see:**
- KPI banner with total webinars, registrations, attendees, and overall attendance rate
- Webinar list as cards with status badges (upcoming, completed, cancelled)
- Speaker name and ICP tag on each card
- Data upload status indicators (registration CSV uploaded, attendee CSV uploaded)
- Search bar and filters (by status, ICP segment, speaker, series)

**Outputs and Insights:**
| Output | What It Tells You |
|--------|-------------------|
| Total Webinars count | Scale of your programme |
| Total Registrations | Overall reach and marketing effectiveness |
| Total Attendees | Actual audience size |
| Overall Attendance Rate | Programme health (40%+ is the benchmark) |
| Status distribution | How many are upcoming vs completed vs cancelled |
| Upload status tags | Which webinars still need data uploaded |

---

### 2. New Webinar Form

Streamlined form to create or edit webinars.

**Fields captured:**
- Webinar Name, Date, Time (required)
- Speaker (required, searchable dropdown with all speakers)
- Co-host / Panellist (optional)
- Platform (Zoom, Google Meet, MS Teams, YouTube Live, LinkedIn Live, Webex, Custom)
- Category (Educational, Product Demo, Market Update, Q&A Session, Investor Webinar, Regulatory Update, Onboarding)
- ICP Segment (PMS, NRI, Retirement Planning, ESOPs, Family Office, AIF, Others)
- Status (Upcoming, Completed, Cancelled)
- Description and Internal Notes

**Output:** A new webinar record ready for data upload and analysis.

---

### 3. Webinar Detail Page

The deep-dive page for a single webinar. This is where the most powerful insights live.

#### 3a. Data Upload

- Two upload zones: Registration CSV and Attendee CSV
- Accepts standard exports from Zoom, Teams, Meet etc.
- Shows count after upload (e.g. "74 registrations, 43 attendees")

#### 3b. Auto-Calculated Metrics

**Outputs and Insights:**

| Metric | What It Tells You |
|--------|-------------------|
| Total Registrations | How many people signed up |
| Total Attendees | How many actually showed up |
| Attendance Rate (%) | Conversion from registration to attendance |
| No-show Count | How many registered but didn't attend |
| Engaged Attendees (45m+) | How many stayed for a meaningful duration |
| Average Session Duration | Mean time spent by all attendees |

#### 3c. Time Spent in Session Chart

A horizontal bar chart breaking down attendee engagement by duration.

| Duration Bucket | Insight |
|----------------|---------|
| 0 - 15 minutes | Early drop-offs. Indicates content didn't hook them or technical issues |
| 15 - 30 minutes | Partial engagement. Stayed for some value but left before the core |
| 30 - 45 minutes | Good engagement. Consumed most of the content |
| 45 - 60 minutes | Strong engagement. Stayed through almost the full session |
| 60+ minutes | Highest engagement. Stayed for Q&A and beyond |

**Key Insight:** If 60%+ of attendees are in the 45+ minute buckets, the content is resonating. If most are in 0-15 minutes, investigate technical issues or content quality.

#### 3d. Human Knowledge (Team Notes)

Manual observations your team adds for context.

| Note Category | Purpose |
|--------------|---------|
| Observation | General observations about the event |
| Speaker Feedback | How the speaker performed, audience reactions |
| Tech Issue | Audio/video problems, platform glitches, connectivity issues |
| Content Quality | Was the content relevant, too basic, too advanced |
| Promotion | Notes about how the webinar was marketed |

**Key Insight:** These notes feed directly into the AI Analysis, giving the AI context that raw numbers cannot capture. For example, if there was a 20-minute audio glitch, the AI adjusts its assessment accordingly.

#### 3e. AI Analysis (On-demand)

One-click deep analysis powered by Claude AI. Produces 8 distinct output sections:

**Output 1: Overall Grade (A/B/C/D)**

| Grade | Meaning | Visual |
|-------|---------|--------|
| A - Excellent | Top-tier performance across all metrics | Green ring |
| B - Good | Strong performance with minor areas to improve | Indigo ring |
| C - Average | Meets baseline but significant room for improvement | Amber ring |
| D - Below Average | Underperforming, needs intervention | Red ring |

**Output 2: KPI Strip**

| KPI | What It Shows |
|-----|---------------|
| Registered | Total signups for this webinar |
| Attended | Total who showed up |
| Att. Rate | Attendance percentage |
| Engaged 45m+ | Count of deeply engaged attendees |
| Avg Session | Mean duration in minutes |

**Output 3: Audience Funnel**

| Funnel Stage | What It Shows |
|-------------|---------------|
| Registered (100%) | Baseline: everyone who signed up |
| Attended (X%) | What percentage actually came |
| Engaged 45m+ (Y%) | What percentage stayed meaningfully |
| No-shows (Z%) | What percentage didn't show up at all |

**Key Insight:** A healthy funnel has at least 40% registration-to-attendance conversion and at least 50% of attendees staying 45+ minutes.

**Output 4: Time in Session Breakdown**

| Segment | What It Means |
|---------|---------------|
| 45+ min (Highly engaged) | Your core audience. These people got real value |
| 15 - 44 min (Moderate) | Interested but didn't stay. Content may need tightening |
| Under 15 min (Early drop-off) | Likely wrong audience, tech issues, or misleading promotion |

**Output 5: Attendance Rate Benchmark**

| Comparison | What It Tells You |
|-----------|-------------------|
| This Webinar vs Platform Average | Are you above or below your own baseline |
| This Webinar vs Speaker's Average | Did this speaker do better or worse than their usual |
| Percentage points above/below | Exact gap to close or advantage to maintain |

**Output 6: AI Insights (5 Dimensions)**

| Dimension | What the AI Analyzes |
|-----------|---------------------|
| Audience Reach | Were registrations strong? What drove them? Were they on target? |
| Engagement Quality | How deep was engagement? Duration distribution quality |
| Registration Channels | Which sources (email, social, direct, referral) performed best and worst |
| Speaker Performance | How this speaker did vs their history. Strengths and areas to improve |
| Timing and Momentum | Were registrations spread out or last-minute? What does the pattern suggest |

Each insight includes a highlighted key finding (e.g. "41 leads with 18, 3M deal at 1")

**Output 7: Recommendations (3-5 actionable items)**

Examples of what the AI recommends:
- "Send 2x reminder WhatsApp messages to all 74 registrants pre-webinar, based on 31 no-shows (41.9%) converting 30% adds 4 attendees"
- "Drop SM budget entirely (delivered 7 registrations) and reallocate to double WhatsApp Community push from 17 to 34+ registrations"
- "Clone this NRI retirement topic with the same speaker but run 4-week advance promotion instead of current window"

**Output 8: AI Verdict**

A one-paragraph summary assessment tying everything together, for example:
> "58.1% attendance rate (21.6 pp above platform avg) proves the content and speaker combo works. Only 74 registrations (100 below platform avg of 157) means the content is under-marketed. Run a 4-week pre-launch campaign targeting Post Retirees and WhatsApp Community (32 combined here), aiming for 150+ registrations or 50% attendance to deliver 67 attendees to current 43."

#### 3f. Compare vs Previous (On-demand)

AI finds the most relevant previous webinar (same ICP or speaker) and produces a comparison.

**Outputs:**

| Section | What It Shows |
|---------|---------------|
| Current vs Previous cards | Side-by-side: title, date, speaker, ICP for both webinars |
| Comparison Table | Registrations, Attendees, Attendance Rate, Avg Duration, Engaged 45m+ with deltas |
| Delta indicators | Up/down arrows with absolute change and percentage change |
| Wins | What improved compared to the previous webinar |
| Losses | What got worse |
| Diagnosis | AI explanation of why changes happened |
| Next Action | One specific thing to do differently next time |

**Key Insight:** This tells you whether your programme is improving or declining and exactly what's driving the change.

#### 3g. Ad Creatives

Attach marketing materials used to promote each webinar.

| Output | What It Tells You |
|--------|-------------------|
| Creative attached per platform | Which designs were used on LinkedIn, WhatsApp, Email etc. |
| Correlation with registrations | Which creative style drives more signups |

---

### 4. Funnel Analytics

Platform-wide performance across all webinars combined.

**Outputs and Insights:**

#### Hero Stats
| Metric | What It Tells You |
|--------|-------------------|
| Overall Conversion Rate | Programme-wide registration-to-attendance percentage |
| Total Attendees | Cumulative audience across all webinars |
| Total Registrations | Cumulative reach |

#### 6 KPI Cards
| Card | Insight |
|------|---------|
| Total Webinars | Scale of the programme |
| Completed | How many have run with data |
| Registrations | Total reach across all events |
| Attendees | Total audience served |
| Avg Attendance Rate | Programme baseline (with 40% benchmark) |
| Conversion Rate | Overall effectiveness (with 40% benchmark) |

#### Programme Conversion Funnel
| Stage | Visual | Insight |
|-------|--------|---------|
| Registered | Full-width indigo bar | 100% baseline |
| Attended | Green bar (proportional) | Shows conversion drop-off |
| No-show | Red bar (proportional) | Shows leakage |

Plus 4 insight pills: Reg-to-Attendee rate, Avg Attendees/Webinar, Avg Registrations/Webinar, No-show Rate

#### Registration vs Attendance Trend Chart
| Element | Insight |
|---------|---------|
| Purple bars (per webinar) | Registration volume over time |
| Green bars (per webinar) | Attendance volume over time |
| Conversion dots | Per-webinar conversion rate (green if 40%+, amber if 25-40%, red if below 25%) |
| Summary strip | Earlier avg conversion vs Recent avg conversion with percentage point change |

**Key Insight:** This is the single most important chart for demonstrating programme growth. If conversion is trending upward, your strategy is working. If it's flat or declining, intervention is needed.

#### New Leads per Webinar
| Element | Insight |
|---------|---------|
| New registrants (dark bars) | First-time audience members |
| Returning registrants (light bars) | People who registered for a previous webinar too |

**Key Insight:** A healthy mix is 60-70% new and 30-40% returning. If almost all are returning, your reach isn't growing. If almost all are new, you're not building loyalty.

#### Monthly Trend
| Output | Insight |
|--------|---------|
| Monthly registration bars | Which months drive the most signups |
| Monthly attendance bars | Which months have the best turnout |

**Key Insight:** Identifies seasonal patterns. For example, if January and March perform best, front-load your calendar.

#### Attendees by ICP
| Output | Insight |
|--------|---------|
| Bar per ICP segment | Which segments have the most attendees |
| Attendance rate per segment | Which segments convert best |
| 40% benchmark line | Which segments are above/below target |

**Key Insight:** Tells you which investor profiles are most engaged so you can allocate budget accordingly.

#### Top 8 Rankings
| List | Insight |
|------|---------|
| Top 8 by Registrations | Which topics/speakers generate the most signups |
| Top 8 by Attendance Rate | Which topics/speakers have the best conversion |

**Key Insight:** High registrations but low attendance rate = good marketing, weak content. Low registrations but high attendance rate = great content that needs more promotion.

---

### 5. Speakers

Track individual speaker performance over time.

**Speaker Directory Outputs:**

| Output | Insight |
|--------|---------|
| Webinar count per speaker | Who presents most frequently |
| Total attendees per speaker | Who draws the largest audiences |
| Avg attendance rate per speaker | Who consistently converts registrations to attendees |

**Speaker Detail Page Outputs:**

| Output | Insight |
|--------|---------|
| Speaker bio and contact | Quick reference |
| Performance timeline | How their metrics trend across webinars |
| Per-webinar breakdown | Date, title, registrations, attendees, rate for each session |
| Best/worst webinar | Their peak and trough performances |

**Current Speakers:**
1. Anil Rego - Personal finance and wealth management
2. Priya Sharma - Investment analysis, ex-Goldman Sachs
3. Rajesh Kumar - Tax planning for HNIs
4. Meera Nair - Retirement planning
5. Vikram Patel - Equity research and portfolio management
6. Shakthi Prabhu - Insurance and risk management

**Key Insight:** Compare speakers to find who should present to which ICP. For example, if Anil Rego has 65% attendance for NRI webinars but only 35% for PMS, assign him to NRI.

---

### 6. Topic Planner

AI-powered topic suggestion engine using live news data.

**How it works:**
1. Click "Generate Topics"
2. System runs 5 targeted Tavily API searches for current financial news
3. News articles + speaker expertise + ICP data sent to Claude AI
4. AI generates topic suggestions grouped by speaker

**Output per topic suggestion:**

| Field | What It Contains |
|-------|-----------------|
| Title | A compelling webinar name (e.g. "NRI Tax Changes 2025: What You Must Know Before Filing") |
| Hook | The opening angle to grab attention |
| Angle | The approach or framework for the content |
| Expected Outcome | What attendees will learn or gain |
| Use Topic button | One-click to create a webinar from this suggestion |

**Key Insight:** Topics are always timely because they're generated from current news. No auto-calls: AI runs only when you click, preserving API credits.

---

### 7. Pipeline (Lead Management)

Track leads generated from webinars through the sales process.

**Outputs:**

| Field | Purpose |
|-------|---------|
| Lead name and email | From webinar registration data |
| Source webinar | Which webinar generated this lead |
| Status | New, Contacted, Qualified, or Converted |
| Assigned to | Which salesperson owns this lead |
| Follow-up date | When to reach out next |
| Notes | Call notes, interest areas, context |
| Tags | For segmentation (e.g. "high-value", "interested-in-PMS") |

**Key Insight:** Closes the loop between marketing (webinars) and sales (revenue). Answers: "How many leads did this webinar generate?" and "How many converted to clients?"

---

### 8. ICP Intelligence

Deep analytics per customer segment.

**Outputs per ICP segment:**

| Output | Insight |
|--------|---------|
| Webinar count | How many webinars have been run for this segment |
| Total registrations | Reach within this segment |
| Total attendees | Actual audience from this segment |
| Attendance rate | How well this segment converts |
| Best speaker | Which speaker performs best for this ICP |
| Topic performance | Which topics resonate most with this segment |
| Trend over time | Is this segment growing or shrinking |

**Key Insight:** Answers strategic allocation questions:
- "Should we run more NRI webinars or more PMS webinars?"
- "Is Retirement Planning our strongest segment?"
- "Which speaker should present to Family Office clients?"

---

### 9. Leaderboard

Ranks all webinars by a composite performance score (0 to 100).

**Scoring Formula:**

| Factor | Max Points | What It Measures |
|--------|-----------|-----------------|
| Registration volume | 25 | Marketing effectiveness |
| Attendance rate | 25 | Audience quality and follow-through |
| ICP relevance and engagement | 25 | How well the content matched the target audience |
| Overall quality signals | 25 | Duration, engagement depth, speaker performance |

**Outputs:**

| Output | Insight |
|--------|---------|
| Ranked webinar list | Best to worst performers |
| Score per webinar | Composite quality score |
| Score range filter | Focus on top tier or identify underperformers |
| Exportable data | For reporting to management |

**Key Insight:** Identifies patterns in your best webinars. If your top 5 all share the same speaker, ICP, or topic theme, double down on that formula.

---

### 10. Communications

Pre-built message templates for the webinar lifecycle.

**Template Categories:**

| Template | When to Use | Insight |
|----------|------------|---------|
| Invitation | 2-4 weeks before the webinar | Drive initial registrations |
| Reminder | 1 day and 1 hour before | Reduce no-shows (can improve attendance by 10-15%) |
| Post-Webinar Thanks | Within 24 hours after | Attendee engagement and recording share |
| No-show Follow-up | 1-2 days after | Re-engage registrants who missed it with the recording |

**Output:** Ready-to-copy text for email and WhatsApp with one-click copy buttons.

---

### 11. Data Export

Export data for external reporting or CRM integration.

**Export Options:**

| Export | Format | Contents |
|--------|--------|----------|
| Webinar data | CSV | All webinar records with metadata |
| Registration data | CSV | All registrants with source and date |
| Attendance data | CSV | All attendees with duration and engagement |
| Per-webinar report | Full export | Includes AI analysis if generated |
| Leaderboard | CSV | Ranked scores with all metrics |

**Date range filter** available for all exports.

---

## Data Flow Lifecycle

```
Plan          -->  Topic Planner generates ideas from live news
                    |
Create        -->  New Webinar form captures details
                    |
Promote       -->  Communications templates for invites/reminders
                -->  Ad Creatives attached for tracking
                    |
Upload Data   -->  Registration CSV + Attendee CSV uploaded
                    |
Auto-Calculate --> Attendance rate, no-shows, duration buckets,
                   engagement segments, new vs returning leads
                    |
AI Analysis   -->  Grade, funnel, benchmarks, insights,
                   recommendations, verdict (on-demand)
                    |
Compare       -->  Side-by-side with previous webinar,
                   wins/losses, diagnosis, next action
                    |
Aggregate     -->  Funnel Analytics shows programme-wide trends
                -->  ICP Intelligence shows segment performance
                -->  Leaderboard ranks all webinars
                -->  Speaker page shows presenter performance
                    |
Follow Up     -->  Pipeline tracks leads to conversion
                    |
Iterate       -->  Trend charts show improvement over time
                -->  AI recommendations guide next webinar
```

---

## Key Metrics to Watch

| Metric | Healthy Range | Warning Sign |
|--------|--------------|-------------|
| Attendance Rate | 40%+ | Below 30% |
| Engaged 45m+ | 50%+ of attendees | Below 30% of attendees |
| New Lead Ratio | 60-70% new per webinar | Below 40% (audience not growing) |
| No-show Rate | Below 50% | Above 60% |
| Avg Session Duration | 35+ minutes | Below 20 minutes |
| Registration-to-Conversion (Pipeline) | 5-10% | Below 2% |

---

## Design Highlights

| Feature | Description |
|---------|-------------|
| Glassmorphism | Frosted glass card surfaces with transparency and blur |
| Colour palette | Purple and indigo (#7C3AED, #6366F1) matching Right Horizons brand |
| Fixed navigation | 96px icon sidebar + 72px top bar, always visible |
| Dark mode | Full dark theme support |
| Responsive | Desktop, tablet, and mobile layouts |
| Single-page app | No page reloads, instant navigation |
| No auto AI calls | All AI features require manual trigger to control costs |

---

*WebinarIQ Analytics - Turning webinar data into actionable growth insights.*
