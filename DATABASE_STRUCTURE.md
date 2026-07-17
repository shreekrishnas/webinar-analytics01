# WebinarIQ Database Structure

## Overview

WebinarIQ uses **8 tables** built on SQLAlchemy ORM with support for both PostgreSQL (Supabase, production) and SQLite (local/fallback). The central entity is `webinars`, with all other tables radiating from it.

---

## Entity Relationship Diagram

```
speakers (1) ──────┐
                    ├──> webinars (1) ──┬──> registrations (1) ──> attendances
speakers (1) ──────┘       │           ├──> attendances
  (co_speaker)             │           ├──> upload_logs
                           │           ├──> webinar_ads
                           │           └──> webinar_notes
                           │
                           └── (via email) ──> pipeline_contacts
```

---

## Table Details

### 1. `speakers`

Stores webinar presenters and subject-matter experts.

| Column | Type    | Constraints       | Description                        |
|--------|---------|-------------------|------------------------------------|
| id     | Integer | PK, Auto, Indexed | Unique speaker identifier          |
| name   | String  | NOT NULL, Indexed | Full name (e.g. "Anil Rego")       |
| email  | String  | Nullable          | Contact email                      |
| bio    | Text    | Nullable          | Speaker biography / expertise area |

**Relationships:** One speaker can present many webinars (via `speaker_id` or `co_speaker_id`).

---

### 2. `webinars`

Central table. Every webinar event lives here.

| Column                 | Type    | Constraints          | Description                                      |
|------------------------|---------|----------------------|--------------------------------------------------|
| id                     | Integer | PK, Auto, Indexed    | Unique webinar identifier                        |
| title                  | String  | NOT NULL, Indexed    | Webinar title                                    |
| date                   | Date    | NOT NULL             | Event date                                       |
| time                   | String  | Nullable             | Event time (free-form string)                    |
| speaker_id             | Integer | FK -> speakers.id    | Primary speaker                                  |
| co_speaker_id          | Integer | FK -> speakers.id    | Optional co-speaker                              |
| description            | Text    | Nullable             | Webinar description / agenda                     |
| status                 | String  | Default: "completed" | "completed" or "incomplete"                      |
| icp                    | String  | Default: "Others"    | Ideal Customer Profile (NRI, HNI, PMS, etc.)    |
| platform               | String  | Nullable             | Zoom, Google Meet, etc.                          |
| category               | String  | Nullable             | Educational, Product Demo, etc.                  |
| language               | String  | Nullable             | English, Hindi, etc.                             |
| recording_url          | String  | Nullable             | Link to recorded session                         |
| tags                   | String  | Nullable             | Comma-separated tags                             |
| expected_registrations | Integer | Nullable             | Target registration count                        |
| notes                  | Text    | Nullable             | Internal team notes                              |
| series                 | String  | Nullable             | Webinar series name (e.g. "Wealth Masterclass")  |
| is_favourite           | Boolean | Default: False       | Starred/bookmarked flag                          |

**Relationships:**
- `speaker` -> Speaker (primary)
- `co_speaker` -> Speaker (optional)
- `registrations` -> Registration[] (cascade delete)
- `attendances` -> Attendance[] (cascade delete)
- `upload_logs` -> UploadLog[] (cascade delete)
- `ads` -> WebinarAd[] (cascade delete)

---

### 3. `registrations`

People who signed up for a webinar. Uploaded via CSV.

| Column        | Type     | Constraints                        | Description                       |
|---------------|----------|------------------------------------|-----------------------------------|
| id            | Integer  | PK, Auto, Indexed                  | Unique registration identifier    |
| webinar_id    | Integer  | FK -> webinars.id                  | Which webinar they registered for |
| attendee_name | String   | NOT NULL                           | Registrant's full name            |
| email         | String   | Indexed                            | Registrant's email                |
| phone         | String   | Nullable                           | Phone number                      |
| source        | String   | Nullable                           | How they found the webinar        |
| registered_at | DateTime | Default: now                       | Timestamp of registration         |

**Unique Constraint:** `(webinar_id, email)` prevents duplicate registrations per webinar.

**Relationships:**
- `webinar` -> Webinar
- `attendance` -> Attendance (one-to-one)

---

### 4. `attendances`

Tracks who actually showed up and engagement duration.

| Column          | Type     | Constraints              | Description                           |
|-----------------|----------|--------------------------|---------------------------------------|
| id              | Integer  | PK, Auto, Indexed        | Unique attendance identifier          |
| webinar_id      | Integer  | FK -> webinars.id        | Which webinar                         |
| registration_id | Integer  | FK -> registrations.id   | Links to the registration record      |
| joined_at       | DateTime | Nullable                 | When they joined                      |
| left_at         | DateTime | Nullable                 | When they left                        |
| duration_minutes| Integer  | Nullable                 | Total minutes attended                |
| attended        | Boolean  | Default: True            | Confirmed attendance flag             |

**Unique Constraint:** `(webinar_id, registration_id)` prevents duplicate attendance per webinar.

**Relationships:**
- `webinar` -> Webinar
- `registration` -> Registration (one-to-one)

**Key metric:** `duration_minutes >= 30` is the threshold used by Hot Leads to identify engaged attendees.

---

### 5. `upload_logs`

Audit trail for every CSV file uploaded (registration or attendee lists).

| Column              | Type     | Constraints       | Description                          |
|---------------------|----------|--------------------|--------------------------------------|
| id                  | Integer  | PK, Auto, Indexed  | Unique log identifier                |
| webinar_id          | Integer  | FK -> webinars.id  | Which webinar the file was for       |
| file_type           | String   | NOT NULL           | "registrations" or "attendees"       |
| filename            | String   | Nullable           | Original file name                   |
| original_count      | Integer  | Default: 0         | Rows in the uploaded file            |
| final_count         | Integer  | Default: 0         | Rows actually inserted               |
| duplicates_removed  | Integer  | Default: 0         | Duplicate rows skipped               |
| unmatched_attendees | Integer  | Default: 0         | Attendees with no matching reg       |
| uploaded_at         | DateTime | Default: now       | Timestamp of upload                  |

---

### 6. `webinar_notes`

Team observations, feedback, and annotations per webinar. Used by the AI analysis engine.

| Column     | Type     | Constraints                    | Description                                                       |
|------------|----------|--------------------------------|-------------------------------------------------------------------|
| id         | Integer  | PK, Auto, Indexed              | Unique note identifier                                            |
| webinar_id | Integer  | FK -> webinars.id, ON DELETE CASCADE | Which webinar                                               |
| author     | String   | Default: "Team"                | Who wrote the note                                                |
| category   | String   | Default: "observation"         | observation, speaker_feedback, tech_issue, content_quality, promotion |
| content    | Text     | NOT NULL                       | The note text                                                     |
| created_at | DateTime | Default: now                   | Timestamp                                                         |

---

### 7. `pipeline_contacts`

Sales pipeline for converting webinar attendees into clients.

| Column         | Type     | Constraints    | Description                                                  |
|----------------|----------|----------------|--------------------------------------------------------------|
| email          | String   | PK, Indexed    | Contact's email (primary key, shared across webinars)        |
| status         | String   | Default: "new" | Pipeline stage: new, contacted, meeting_booked, converted, not_interested |
| assigned_to    | String   | Nullable       | Sales team member handling this lead                         |
| notes          | Text     | Nullable       | Follow-up notes                                              |
| follow_up_date | Date     | Nullable       | Next scheduled follow-up                                     |
| added_at       | DateTime | Default: now   | When the contact entered the pipeline                        |
| updated_at     | DateTime | Default: now   | Last status change (auto-updates on modify)                  |

**Pipeline Flow:** `new` -> `contacted` -> `meeting_booked` -> `converted` (or `not_interested`)

---

### 8. `webinar_ads`

Ad creatives and performance tracking per webinar campaign.

| Column         | Type     | Constraints                     | Description                                    |
|----------------|----------|---------------------------------|------------------------------------------------|
| id             | Integer  | PK, Auto, Indexed               | Unique ad identifier                           |
| webinar_id     | Integer  | FK -> webinars.id, ON DELETE CASCADE | Which webinar this ad promotes            |
| title          | String   | NOT NULL                        | Ad campaign name                               |
| platform       | String   | Nullable                        | Facebook, Instagram, Google, LinkedIn          |
| ad_type        | String   | Nullable                        | Image, Video, Carousel, Story, Reel, Banner    |
| creative_image | Text     | Nullable                        | Base64 data URI of the ad creative             |
| creative_url   | String   | Nullable                        | URL to hosted image (alternative to base64)    |
| headline       | String   | Nullable                        | Ad headline text                               |
| description    | Text     | Nullable                        | Ad body copy                                   |
| cta_text       | String   | Nullable                        | Call-to-action (e.g. "Register Now")           |
| landing_url    | String   | Nullable                        | Where the ad links to                          |
| budget         | String   | Nullable                        | Allocated budget (free-form, e.g. "5,000")     |
| spend          | String   | Nullable                        | Actual spend                                   |
| impressions    | Integer  | Nullable                        | Total impressions                              |
| clicks         | Integer  | Nullable                        | Total clicks                                   |
| conversions    | Integer  | Nullable                        | Registrations attributed to this ad            |
| start_date     | Date     | Nullable                        | Campaign start                                 |
| end_date       | Date     | Nullable                        | Campaign end                                   |
| status         | String   | Default: "active"               | active, paused, completed                      |
| notes          | Text     | Nullable                        | Internal notes about the campaign              |
| created_at     | DateTime | Default: now                    | Record creation timestamp                      |

---

## Data Flow

```
1. CREATE WEBINAR
   Speaker selected -> Webinar created with title, date, ICP, status

2. UPLOAD REGISTRATIONS (CSV)
   CSV parsed -> Rows inserted into registrations (deduped by email+webinar)
   -> upload_logs entry created with counts

3. UPLOAD ATTENDEES (CSV)
   CSV parsed -> Matched to registrations by email
   -> Rows inserted into attendances with duration
   -> upload_logs entry created (includes unmatched count)

4. ANALYTICS COMPUTED
   registrations COUNT = total signups
   attendances COUNT (attended=TRUE) = actual attendees
   Conversion rate = attendees / registrations * 100
   Hot leads = attended 30+ min AND not yet in pipeline

5. PIPELINE MANAGEMENT
   Hot lead email -> Added to pipeline_contacts as "new"
   Sales team updates status through the pipeline stages

6. AD TRACKING
   Ads created per webinar with creative + targeting
   Performance metrics (impressions, clicks, conversions) tracked
```

## Database Backends

| Environment         | Backend                | Connection                                      |
|---------------------|------------------------|-------------------------------------------------|
| Production (Vercel) | PostgreSQL via Supabase | `DATABASE_URL` env var, pg8000 driver, SSL      |
| Local development   | SQLite                 | `webinar_analytics.db` in project root          |
| Vercel (no DB URL)  | SQLite (ephemeral)     | `/tmp/webinar_analytics.db` (wiped on cold start)|

**Compatibility note:** Queries use standard SQL. The only dialect-specific function is aggregation: `STRING_AGG` on PostgreSQL, `GROUP_CONCAT` on SQLite, handled conditionally in code.
