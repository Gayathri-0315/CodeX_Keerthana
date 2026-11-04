# ShowUp

Every platform helps you find events. ShowUp helps you show up.

ShowUp recommends only the events a student can actually attend (free time, travel, budget, eligibility, interests), explains why each one fits, and then helps them get there: **Go together** (invite a friend with a link and your passes are linked), a pass with a leave-by time, reminders that name who you're going with, a one-tap "Can't make it" that hands the seat to the waitlist, and QR check-in. Organizers turn a poster into a listing with AI, behind a spam and trust gate, and see predicted vs actual turnout. Pilot city: Coimbatore (₹, IST).

Full brief: [SPEC.md](SPEC.md). Build plan and every decision or deviation: [PLAN.md](PLAN.md).

## Run it locally

Needs Node 20+ and Python 3.11+. No API keys needed.

```sh
npm install      # also installs the frontend
npm run seed     # LOCAL ONLY: creates backend/showup.db with sample events and accounts
npm run dev      # API on :8000, web on http://localhost:5173
```

The first run creates `backend/.venv` and installs the Python requirements. The database schema is created and upgraded by Alembic migrations on startup.

| Command | What it does |
|---|---|
| `npm run dev` | Start API and web, both reloading on change |
| `npm run seed` | `python manage.py seed_dev`: wipe the local database and load sample data. Refuses to run when `APP_ENV=production` |
| `npm run migrate` | `python manage.py migrate`: apply database migrations |
| `npm run create-admin -- --email you@org.com` | `python manage.py create_admin`: create (or reset) an admin; prompts for a strong password |
| `npm test` | Backend tests (pytest) |
| `npm run build` | Typecheck and build the frontend |

**Sample accounts (local only).** `npm run seed` creates `asha@example.com` (student), `club@example.com` (trusted organizer), `neworg@example.com` (new organizer), `admin@example.com` and `student1` to `student30@example.com`. Their password is `SEED_DEV_PASSWORD` from your `.env`; if that's empty, a random one is printed when you seed. Nothing is hardcoded, and production never contains sample data.

**Emails in local dev.** Without `EMAIL_API_KEY`, every email (verification codes, reset links, alerts) is written to the API log with the words `email skipped`, so you can copy the code from the terminal.

## Accounts and security

- Email + password (bcrypt). A new account must verify its email (6-digit code or the emailed link) before it can register for events or publish.
- Password reset by email link (30 minutes, single use); resetting signs out every other session.
- Five wrong passwords lock the account for 15 minutes; a password reset unlocks it. Sign-in, sign-up and email requests are rate limited per IP.
- Session cookie is httpOnly, SameSite=Lax and Secure in production. Every write request carries a CSRF token (double-submit cookie).
- Admin accounts exist only through `manage.py create_admin`; there is no admin sign-up.
- Poster images are stored in the database, so a redeploy never loses them. Timetable photos are read and discarded.

## Deploy (Render + free PostgreSQL)

Free hosting disks are wiped on every redeploy, so production data lives in PostgreSQL, never in SQLite.

1. **Create a free PostgreSQL database.** Recommended: [Neon](https://neon.tech) (free tier, doesn't expire). Sign up, create a project (region: Singapore is closest to India), and copy the connection string from the dashboard. It looks like `postgresql://user:password@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`. Supabase works the same way (Project settings, Database, connection string, "URI"). Render's own free Postgres is deleted after 30 days, so avoid it for real users.
2. **Create the web service.** In Render, New, Blueprint, pick this repository (it reads `render.yaml`), or New, Web Service with runtime Docker.
3. **Set the environment variables** (Render dashboard, Environment):

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | the Neon/Supabase connection string from step 1 |
| `JWT_SECRET` | Render generates it (or any random string of 32+ characters) |
| `EMAIL_PROVIDER` | `resend` or `brevo` |
| `EMAIL_API_KEY` | your provider API key |
| `EMAIL_FROM` | e.g. `ShowUp <hello@your-domain.com>`, a sender verified with the provider |
| `ANTHROPIC_API_KEY` | optional: reads posters and timetables with AI |
| `VITE_CONTACT_EMAIL` | optional: contact address shown in the footer |
| `PUBLIC_URL`, `FRONTEND_ORIGIN` | only if you use a custom domain (default: the Render URL) |

4. **Deploy.** On startup the app runs the migrations against the empty database. Check `https://<your-app>.onrender.com/health` returns `{"ok":true}`.
5. **Create the first admin** from Render's Shell tab: `python manage.py create_admin --email you@your-domain.com`.

The app refuses to start in production with SQLite or a short `JWT_SECRET`. `render.yaml` sets `autoDeploy: false`, so nothing deploys until you click Deploy.

## Environment variables

Copy `.env.example` to `.env` to change any of these. Never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `dev` | `production` turns on secure cookies, requires PostgreSQL and a strong `JWT_SECRET`, and blocks sample-data tools |
| `DATABASE_URL` | `sqlite:///./showup.db` | PostgreSQL in production (`postgres://` and `postgresql://` both work); SQLite for local dev only |
| `JWT_SECRET` | `change-me` | Signs session cookies |
| `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `EMAIL_FROM` | empty | Email over HTTPS (Resend or Brevo). Without a key emails go to the server log as "email skipped" |
| `AI_MODE` | `auto` | `auto` uses Claude when a key is set, `mock` never does, `live` requires a key |
| `ANTHROPIC_API_KEY` | empty | Live poster and timetable reading, and the trust gate's second opinion |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Model for extraction |
| `PUBLIC_URL`, `FRONTEND_ORIGIN` | `http://localhost:5173` | Base for links in emails, and the CORS origin |
| `WAITLIST_CONFIRM_MINUTES` | `15` | How long a promoted waitlister has to confirm |
| `ORS_API_KEY` | empty | Reserved for OpenRouteService travel times |
| `SEED_DEV_PASSWORD` | empty | Local only: password for the sample accounts |
| `VITE_CONTACT_EMAIL` | empty | Build time: contact address in the footer and legal pages |

Optional semantic matching: `backend/.venv/Scripts/python -m pip install -r backend/requirements-ml.txt` (Windows; `backend/.venv/bin/python` elsewhere). Without it, keyword and synonym matching is used.

## Architecture

```mermaid
flowchart LR
  subgraph Browser
    SPA[React SPA<br/>Vite, Tailwind, motion,<br/>TanStack Query]
  end
  subgraph API[FastAPI]
    R[Routers<br/>auth, feed, events, registrations,<br/>organizer, admin, notifications]
    S[Services<br/>matching, ranking, spam gate,<br/>extraction, waitlist, notify]
    J[APScheduler<br/>reminders, offer expiry,<br/>deadlines, closing events]
    H[SSE hub]
  end
  DB[(PostgreSQL in production<br/>SQLite locally)]
  C[Claude API<br/>optional]
  M[Email API<br/>Resend or Brevo]
  SPA -- JSON over /api --> R
  SPA -- EventSource /api/stream --> H
  R --> S --> DB
  J --> S
  S --> H
  S --> C
  S --> M
```

- `backend/app/services/matching.py` runs the hard filters (SPEC 5.2) and `ranking.py` the score and template reasons (5.3, 5.4). `feed.py` caches each user's evaluated feed for 30 s.
- `spam.py` is the trust gate (5.6). `listing.py` covers forms, duplicates, publishing and reach preview.
- `extraction.py` handles live and mock AI with Pydantic validation, one retry and caching by file hash (6.1 to 6.5).
- `registration.py` covers seats, the waitlist and promotion under a per-event lock (5.9). `showup_score.py` has likelihood and leave-by (5.7, 5.8).
- `notify.py` holds the alert rules and channels (5.5). `jobs.py` runs the scheduled work.
- `together.py` is Go together: invites, groups, alerts when a friend joins or drops out, and classmate counts (department and year, a count only).
- On the frontend, pages live in `frontend/src/pages`. The calendar paint grid is in `components/calendar`, the register animation and pass in `components/attendance`, and the design tokens in `src/styles/index.css`.

## Quality checks

- **Backend:** `npm test` runs 135 pytest tests: auth (verification, lockout, reset, CSRF, roles), filters, ranking, reasons, every spam rule and the 29/30/59/60 thresholds, extraction validation and retry, notification caps, quiet hours, pause and dedupe, waitlist promotion (including concurrent cancels), leave-by and reminders, likelihood bounds and monotonicity, check-in, timetable gaps, and Go together (invites, pairing, group alerts, classmate counts).
- **On PostgreSQL:** set `TEST_DATABASE_URL` to an empty throwaway PostgreSQL database and run `npm test`; the suite wipes it on every test. All tests pass on PostgreSQL 16 and SQLite.
- **Accessibility:** axe-core (WCAG 2.1 AA) passes on 10 key screens in light phone, light desktop and dark desktop. Focus rings are visible, tap targets are 44 px, and reduced motion is respected.
- **Performance** (production build, phone, 4x CPU slowdown): LCP 1.0 to 1.24 s on 4G (9 Mbps, 85 ms RTT), and 1.75 to 1.98 s on Lighthouse's slow profile (1.6 Mbps, 150 ms). First-load JS is about 126 KB gzipped, and the QR scanner (100 KB) loads only on the check-in screen. The calendar paints with no long tasks, and a 500-event feed ranks well under 50 ms.

### Manual smoke checklist (frontend)

- [ ] Onboarding: hero → account → interests → area/distance/budget → timetable or paint → done check → Home count-up
- [ ] Calendar: drag-paint a rectangle, refresh, still there. Presets, "This week only", keyboard (arrows, Space, Shift+arrows)
- [ ] Timetable import fills in left to right and shows the review banner
- [ ] Feed shows reasons; swipe left hides with Undo; Almost shows the clash line
- [ ] Register animation completes and the pass opens; Can't make it releases the seat
- [ ] Organizer poster flow: "Check this" fields, live trust check and reach, publish / blocked / appeal
- [ ] Check-in by QR and by code; the event page counts update
- [ ] Offline banner appears with the network off; unknown URLs show "This page doesn't exist"

## Known limitations

- **Expected turnout is a transparent rule-based planning estimate**, not a trained model, and is labelled as such. Organizers see only the total, never a score per student.
- **Mock vs live AI:** mock mode recognises only the sample posters and timetables. Any other upload opens the manual form or the paint grid. Live mode needs `ANTHROPIC_API_KEY`.
- **The spam gate is a first line of defence.** Rules plus an optional AI opinion can be fooled, so reports and the admin queue back it up.
- **Interest matching:** without the optional embedding model it uses keywords and synonyms, which miss loosely related topics.
- **Travel time** is straight-line distance x 1.4 at 22 km/h city speed, not live traffic.
- **Single-process pilot:** the feed cache, SSE hub and waitlist locks live in memory, so run one API worker.
- **Local sample data** is small (31 students), so reach previews show small numbers locally.

## Roadmap

Teammate matching for hackathons, Google Calendar free/busy import, WhatsApp alerts, Tamil and English poster reading, smarter ranking from real pilot attendance data, payments, native apps, more cities.
