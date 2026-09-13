# Career Pro Services — Job Alerts + Statement Writer (PWA)

A combined, installable web app: NHS job alert signup + browsing, and an
AI-assisted supporting statement writer with PDF upload — built as a
Progressive Web App so your clients can "install" it to their phone home
screen without going through the App Store or Play Store.

## What changed from the earlier version

- `app.py` now serves one combined page (`templates/index.html`) with two
  tabs — Job alerts, and Statement writer — instead of separate pages.
- Added a real JSON API: `/api/jobs`, `/api/alerts`, `/api/draft-statement`.
- **The AI drafting call now happens on your server, not in the browser.**
  Your `ANTHROPIC_API_KEY` lives only in `.env` on your server — it is
  never sent to or visible from the client's phone or browser. This is the
  correct way to do this for anything you actually ship to clients.
- Added `static/manifest.json`, `static/sw.js`, and two placeholder icons
  so the site can be installed as an app. **Replace the icons** — the
  ones included are simple placeholders, not a real logo.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- Get an API key at console.anthropic.com and put it in `ANTHROPIC_API_KEY`.
  This is separate from any Claude.ai subscription — it's pay-as-you-go,
  billed per request. A single statement draft costs a small fraction of
  a cent to a couple of cents in API usage.
- Fill in SMTP details if you want the existing `alerts.py` script to send
  email digests (run it on a schedule via cron, same as before).

Run it locally:
```bash
python scraper.py        # populate some job data first (see prior README notes
                          # on verifying the NHS Jobs selectors before relying on this)
flask --app app run --debug
```
Open `http://127.0.0.1:5000` — you'll see the tabbed app. On a phone
browser pointed at your real deployed URL, you (or your clients) will see
an "Install app" button and/or the browser's own install prompt.

## Deploying so clients can actually install it

A PWA needs to be served over **HTTPS from a real domain** — install
prompts and service workers don't work over plain HTTP or `file://`.
Reasonable, cheap options:
- **Render.com** or **Railway.app** — free/cheap tiers, deploy a Flask app
  directly from a git repo, HTTPS included automatically.
- **A subdomain on your existing hosting** (e.g. `app.careerproservices.co.uk`)
  pointed at a small VPS running this with gunicorn + nginx, or a
  platform like the above sitting behind your domain.

Once it's live at a real HTTPS URL:
- On iPhone: open the URL in Safari → Share → "Add to Home Screen".
- On Android: open in Chrome → the browser will usually offer an install
  banner automatically, or use the in-app "Install app" button this
  project adds via the browser's install prompt.

## Notes on scope

- This is a private tool for your own clients, not a public app-store
  listing — that's the right scope for what you described, and it avoids
  Apple/Google developer accounts and review processes entirely.
- Job data (`/api/jobs`) only shows what your scraper has found — see the
  earlier README notes on verifying the scraper's selectors against the
  live NHS Jobs site before relying on it for real client use.
- Everything about legal/etiquette for scraping (from the earlier README)
  still applies — check current NHS Jobs / Trac / Scotland / HSCNI terms
  regarding automated access.
