# ShowUp build plan

Build order follows SPEC.md section 14. Each phase ends runnable, tested and committed.

| Phase | Scope | Status |
|---|---|---|
| 1 Foundation | Repo, one-command dev/seed, FastAPI + SQLite (WAL) + all models, seed data, JWT cookie auth + demo login, design tokens, app shell (glass nav / tab bar, dark mode), onboarding, interests, settings | done |
| 2 Free-time calendar | 7 x 32 paint grid (rAF-batched, memoized cells), presets, "This week only" overrides, 400 ms debounced batched save, live "N events fit" pill, keyboard grid | done |
| 3 Matching and feed | Ranking, reasons, Almost list, feed UI, detail, save/dismiss, embeddings + fallback | done |
| 4 Poster to listing | Extraction (mock + live), confirm screen, trust gate, reach preview, admin queue, reports | done |
| 5 Attendance | Register animation + pass, SSE toasts, notification rules, reminders, waitlist, .ics, QR check-in, analytics | done |
| 6 Timetable + polish | Timetable import, Telegram poster flow, states, a11y and performance passes, README | done |

## Key decisions

- **Running it:** `make` is not installed on this Windows machine, so root `npm run dev` / `npm run seed` / `npm test` are the primary commands; the Makefile wraps them. `scripts/py.mjs` creates `backend/.venv` and installs requirements on first use, so a clean clone needs only `npm install && npm run dev`.
- **Backend endpoints** are plain `def` (FastAPI runs them in a threadpool) because SQLAlchemy sessions are sync; SSE (Phase 5) is async.
- **Hard filters are pulled into Phase 2** (`services/matching.py`) because the live "N events fit" pill needs them. Ranking stays in Phase 3.
- **Availability semantics:** a date's free time = recurring slots for that weekday + one-off `free` slots, minus one-off `busy_override` slots. The calendar shows the week and paints recurring by default, or one-off overrides with "This week only".
- **Onboarding order:** hero, account, interests, where and how much, then "When are you free?" which opens the calendar; finishing there shows the done check and Home. (Spec lists free time before location; moving it last lets the calendar be the final, longest step.)
- **Area search** uses the seeded Coimbatore venue table instead of Nominatim, so onboarding works offline.
- **Budget "Any"** is stored as `budget_max_inr = null`.
- **Calendar painting:** drags paint the rectangle from the first cell to the pointer (so Mon to Fri 5 to 9 PM is one drag), applied once per animation frame over a snapshot so shrinking a drag reverts cleanly. On touch, a tap toggles one cell and a 180 ms hold starts painting; a quick swipe still scrolls. Phones get a one-day snap pager plus a week overview. The 30-minute grid marks a cell free only when a slot covers all of it, and slot parts outside 06:00 to 22:00 are preserved on save.
- **Onboarding "Upload my timetable"** is added in Phase 6 with timetable import, so there is no dead-end button before then.
- **Organizer and admin** accounts land on a placeholder until Phase 4.
- **Interest matching:** `sentence-transformers` is optional (`backend/requirements-ml.txt`, it pulls in PyTorch). Without it, a keyword + synonym model is used with its own calibration range (0.05 to 0.55 cosine, vs the spec's 0.20 to 0.70 for MiniLM). `/api/health` reports which one is active.
- **Almost list** = events that fail only the schedule rule and have interest >= 40, sorted by interest. "Remind me of similar events" raises the weight of that event's tags in the user's interests.
- **Card reasons** skip distance and price (already shown as chips); the detail page shows every reason.
- **Register** lands in Phase 5, so until then the detail page's sticky bar offers Save and Share.
- **Live extraction** uses `client.messages.parse()` with the Pydantic schema as `output_format`, a 25 s timeout, one retry with the validation error appended, and a refusal check; on a second failure the fields that individually validate prefill the form. Model comes from `ANTHROPIC_MODEL` (`claude-sonnet-5-5` per the spec's `.env.example`). Server-side refusal fallbacks aren't enabled because the SDK docs bundled here don't cover combining them with `messages.parse()`; a refusal falls back to the manual form instead.
- **Sample posters** are drawn with Pillow at seed time (dates relative to today) into `seed/posters/generated/` (git-ignored). In demo mode the upload screen offers them as one-tap samples, and mock extraction matches them by file name or hash.
- **Trust gate details:** the three "personal UPI / phone / QR" checks count once (+40) as the spec's table lists one rule. Duplicates are found by embedding cosine > 0.92 or, because keyword vectors of a reworded copy fall short of 0.92, by >= 80% title-word overlap on the same date. Seeded events get their risk scores from the same gate.
- **Admin approval** gives `details_reviewed` (or `organizer_verified` if the organizer is verified/trusted); reports older than the last admin decision are treated as settled (`events.reviewed_at`).
- **"Check this" fields** clear when edited or when the organizer leaves the field (confirming an already-correct value).
- **Reach preview** with 31 seeded students shows small numbers (the spec's "about 140" assumes a bigger user base).
- **Waitlist safety:** seat changes for an event run under a per-event lock in one transaction (single-process pilot). Two cancels racing free two seats and make two offers, never the same seat twice (tested with threads). An unconfirmed offer becomes `cancelled` and the seat moves on.
- **Quiet hours** hold delivery (the alert is stored and sent by the next scheduler tick after quiet hours end); seat offers are the exception because they expire in minutes. Demo-panel actions bypass quiet hours so the demo works at night.
- **Notification types** beyond the spec's list: `waitlisted`, `reminder_24h`, `reminder_2h` (alongside `reminder_leave_by`) and `message` (organizer to registrants). Only `match`, `deadline` and `seat_opened` count toward the weekly cap.
- **Telegram** uses the Bot API over HTTPS directly (no `python-telegram-bot` dependency). Locally it long-polls every 3 s; in production set a webhook to `/api/telegram/webhook` with the secret from `routers/telegram.py:webhook_secret`. Poster upload by Telegram is Phase 6.
- **Check-in** accepts the QR token or a 6-character code printed under the QR.
- **Timetable import** replaces the weekly free time with the gaps between 08:00 and 21:00 (`TIMETABLE_DAY_START_MIN` / `END_MIN` in config) and keeps one-off changes. The 30-minute grid marks a cell free only when a gap covers all of it, so a 10-minute break between classes doesn't count. The import is not saved until it's applied; a review banner then asks the student to check it.
- **Contrast (SPEC 8.11 over 7.1):** a few spec colors miss WCAG AA in places. `#0071E3` stays as the filled-button color (`--accent-fill`) in both themes. Blue text uses `#0066CC` in light mode. Secondary text is `#636366` instead of `#6E6E73`, and dark-mode tinted backgrounds are a touch darker.
- **Performance:** the motion engine loads with the app (async loading left content invisible until it arrived), the first screen skips its enter animation, Home is in the main bundle, and `index.html` starts the session and first-screen API calls while the JS downloads. Icons, motion and shared UI are grouped into a few chunks to cut round trips.
- **Telegram posters** create a draft (`source: telegram`), run the trust gate, and offer Confirm and publish, Edit on web, or Cancel. Telegram re-encodes photos, so in mock mode only files sent as documents with a sample's file name are recognised.
- **Dev reload:** `scripts/py.mjs --watch app` restarts uvicorn on .py changes. uvicorn's own `--reload` is not used because on Windows it stops its worker with a console Ctrl+C that also kills `npm run dev`.

## Deviations from the spec (data only)

- Seed: Python Meetup runs Sat 17:00 to 18:00 (spec says to 18:30) because the demo student is free only until 18:00 and the spec requires the meetup in "For you" under strict schedule.
- Python 3.12 is used (spec says 3.11); nothing depends on 3.12-only features.
- Extra tables/columns the spec implies but does not list: `saved_events`, `users.home_area`, `users.interest_text`, `extraction_cache` (Phase 4).
