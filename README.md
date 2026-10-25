# ShowUp

Every platform helps you find events. ShowUp helps you show up.

ShowUp recommends only the events a student can actually attend (free time, travel, budget, eligibility), then helps them get there. Pilot city: Coimbatore. Full brief: [SPEC.md](SPEC.md). Build plan and decisions: [PLAN.md](PLAN.md).

## Run it

Needs Node 20+ and Python 3.11+.

```sh
npm install      # also installs the frontend
npm run dev      # API on :8000, web on http://localhost:5173
```

The first `npm run dev` creates `backend/.venv` and installs the Python requirements. With `DEMO_MODE=true` (the default) an empty database is seeded automatically.

| Command | What it does |
|---|---|
| `npm run dev` / `make dev` | Start API and web with live reload |
| `npm run seed` / `make seed` | Reset the database and load demo data |
| `npm test` / `make test` | Backend tests (pytest) |
| `npm run build` | Typecheck and build the frontend |

No API keys are needed. Copy `.env.example` to `.env` to change settings.

Interest matching uses keywords and synonyms out of the box. For semantic matching, install the optional model (large download): `backend/.venv/Scripts/python -m pip install -r backend/requirements-ml.txt` on Windows, or `backend/.venv/bin/python ...` elsewhere. It loads in the background on the next start; `/api/health` shows `"matching": "model"` once it's ready.

## Demo accounts

Password for all: `demo1234`. The sign-in screen also has one-tap demo buttons.

- `student@demo.app`: free Sat 2 to 6 PM and Sun 9 AM to 1 PM, likes AI, Python, hackathons, ₹200 budget, 20 km
- `organizer@demo.app`: Coimbatore AI Club (trusted)
- `neworg@demo.app`: QuickCareers Hub (new organizer, posts the spam examples)
- `admin@demo.app`

Seeded event dates are relative to the day you seed, so the demo is always upcoming.

## Status

Phases 1 to 5 are done: foundation, free-time calendar, matching and feed, poster to listing with the spam/trust gate, and registration, alerts, waitlist and check-in. Phase 6 (timetable import and polish) is next; see PLAN.md.

## Demo panel

In demo mode, open Settings → Demo panel (or `/demo`) for one-tap demo steps: publish the AI Workshop (fitting students get a live "A seat that fits your Saturday" alert), release a seat on the full Startup Pitch Night (the demo student is offered it), fast-forward to the "Time to head out" alert, switch accounts, and reset all demo data.

Alerts arrive live in the app. Email is printed to the API console unless `SMTP_HOST` is set. Telegram needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`; link it from Settings → Alerts.

## AI modes

Without `ANTHROPIC_API_KEY` (or with `AI_MODE=mock`) poster reading runs in mock mode: the six sample posters on the "New event" screen are recognised and filled in; any other file opens the manual form. Set `ANTHROPIC_API_KEY` to read real posters with Claude (`ANTHROPIC_MODEL`, default `claude-sonnet-5-5`); results are cached by file hash, and the trust gate also asks Claude for a second opinion.
