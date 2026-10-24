# ShowUp build plan

Build order follows SPEC.md section 14. Each phase ends runnable, tested and committed.

| Phase | Scope | Status |
|---|---|---|
| 1 Foundation | Repo, one-command dev/seed, FastAPI + SQLite (WAL) + all models, seed data, JWT cookie auth + demo login, design tokens, app shell (glass nav / tab bar, dark mode), onboarding, interests, settings | in progress |
| 2 Free-time calendar | 7 x 32 paint grid (rAF-batched, memoized cells), presets, "This week only" overrides, 400 ms debounced batched save, live "N events fit" pill, keyboard grid | next |
| 3 Matching and feed | Ranking, reasons, Almost list, feed UI, detail, save/dismiss, embeddings + fallback | |
| 4 Poster to listing | Extraction (mock + live), confirm screen, trust gate, reach preview, admin queue, reports | |
| 5 Attendance | Register animation + pass, SSE toasts, notification rules, reminders, waitlist, .ics, QR check-in, analytics | |
| 6 Timetable + polish | Timetable import, Telegram poster flow, states, a11y and performance passes, README | |

## Key decisions

- **Running it:** `make` is not installed on this Windows machine, so root `npm run dev` / `npm run seed` / `npm test` are the primary commands; the Makefile wraps them. `scripts/py.mjs` creates `backend/.venv` and installs requirements on first use, so a clean clone needs only `npm install && npm run dev`.
- **Backend endpoints** are plain `def` (FastAPI runs them in a threadpool) because SQLAlchemy sessions are sync; SSE (Phase 5) is async.
- **Hard filters are pulled into Phase 2** (`services/matching.py`) because the live "N events fit" pill needs them. Ranking stays in Phase 3.
- **Availability semantics:** a date's free time = recurring slots for that weekday + one-off `free` slots, minus one-off `busy_override` slots. The calendar shows the week and paints recurring by default, or one-off overrides with "This week only".
- **Onboarding order:** hero, account, interests, where and how much, then "When are you free?" which opens the calendar; finishing there shows the done check and Home. (Spec lists free time before location; moving it last lets the calendar be the final, longest step.)
- **Area search** uses the seeded Coimbatore venue table instead of Nominatim, so onboarding works offline.
- **Budget "Any"** is stored as `budget_max_inr = null`.

## Deviations from the spec (data only)

- Seed: Python Meetup runs Sat 17:00 to 18:00 (spec says to 18:30) because the demo student is free only until 18:00 and the spec requires the meetup in "For you" under strict schedule.
- Python 3.12 is used (spec says 3.11); nothing depends on 3.12-only features.
- Extra tables/columns the spec implies but does not list: `saved_events`, `users.home_area`, `users.interest_text`, `extraction_cache` (Phase 4).
