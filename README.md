# LinkPulse — URL Shortener & Analytics Platform
**Team Code Pheonix | Hackathon-ready full-stack project**

LinkPulse manages the full link lifecycle: create → redirect → track → analyze → disable/expire. This implementation is designed to run locally without external services, while keeping the project architecture extensible.

## Features
- Create short links with custom aliases, campaign names, tags, and optional passwords
- Redirect rule engine: active/disabled status, expiry, click cap, password protection
- Click analytics: daily activity, referrer/device breakdown, top links, recent events
- Basic bot filtering and user-agent parsing
- Admin panel to disable/enable links without deleting their history
- QR-code generation and PNG download
- CSV bulk import and CSV analytics export
- Dashboard search and status filters
- UTM campaign builder with source, medium, campaign, term and content parameters
- Edit destination/campaign in place, duplicate links, and permanently delete links
- Bulk JSON link creation endpoint (up to 100 links per request)
- Dedicated click-event CSV export for reporting
- SQLite works out of the box; MySQL schema and configuration included
- Redis is optional and documented as the next scaling layer

> **Safety note:** LinkPulse is a hackathon prototype, not a production security product. Passwords protect individual links but should not be used to share highly sensitive material. The demo's basic bot detection is heuristic, and IP addresses are not stored.

## Architecture
- **Frontend:** React + Vite + plain CSS
- **Backend:** Python + FastAPI + Pydantic
- **Database:** SQLite by default; MySQL 8 compatible configuration and SQL schema provided
- **Async processing:** FastAPI background task for click-event persistence (local demo); replace with Redis queue/worker for high volume
- **QR:** `qrcode` + Pillow

## Requirements
- Python 3.10+
- Node.js 20+
- (Optional) MySQL 8 and Redis for production-style extension

## Run locally (Windows PowerShell)
### 1. Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```
API docs: http://127.0.0.1:8000/docs

### 2. Frontend (new terminal)
```powershell
cd frontend
npm install
npm run dev
```
Open the Vite URL printed in the terminal (usually http://localhost:5173).

### Run with a single origin (optional)
Build the frontend with `npm run build`, then set `SERVE_FRONTEND=true` in backend `.env` and restart the backend. The current starter keeps Vite and API separate during development.

## Configuration
Copy `backend/.env.example` to `backend/.env`.
- `DATABASE_URL=sqlite:///./linkpulse.db` is the no-setup default.
- MySQL example: `mysql+pymysql://linkpulse:change-me@localhost:3306/linkpulse`
- `FRONTEND_ORIGIN=http://localhost:5173`
- `PUBLIC_BASE_URL=http://localhost:8000` (used for generated short links and QR codes)

Never commit real credentials. Change the demo admin password before deploying.

## Demo walkthrough (5 minutes)
1. Open the dashboard and create a link with a campaign and tag.
2. Copy/open the generated short URL. It redirects and records a click event.
3. Refresh analytics to see click totals and event details.
4. Create a password-protected or click-capped link to demonstrate rule enforcement.
5. Disable a link from the dashboard; the short URL stops redirecting while historical analytics remain.
6. Generate/download a QR code, upload a CSV, clone/edit/delete links, and use Growth tools to build UTM-tagged URLs.

## CSV import format
CSV headers: `destination_url,alias,campaign,tags,expires_at,click_cap,password`
- `tags` is a comma-separated list inside the CSV cell.
- `expires_at` should be ISO-8601, e.g. `2027-01-01T00:00:00Z`.
- Password is optional and is hashed in storage.

## API overview
- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/links`
- `POST /api/links`
- `GET /api/links/{id}`
- `PATCH /api/links/{id}/status`
- `GET /api/links/{id}/analytics`
- `PATCH /api/links/{id}` (edit destination/metadata)
- `POST /api/links/{id}/duplicate`
- `DELETE /api/links/{id}`
- `POST /api/links/bulk` (up to 100 links)
- `GET /api/export/analytics.csv`
- `GET /api/links/{id}/qr`
- `POST /api/import/csv`
- `GET /api/export/csv`
- `GET /{short_code}` (redirect rule engine)

## Production hardening checklist
- Add authentication, JWT/RBAC and owner-scoped authorization before public deployment
- Use Redis for cache and a durable queue/worker for click events
- Add request rate limiting, CSRF strategy if cookie auth is introduced, structured logs and alerting
- Integrate a maintained malicious URL reputation provider; current app does not claim to detect malicious URLs
- Add migrations, backups, retention policies, HTTPS, custom domains and load testing


### Expanded features (this build)
- **Edit link metadata** without changing its short URL: destination, campaign, tags, expiry, click cap and password.
- **Duplicate link** to create a new short code with copied campaign metadata.
- **Delete link** with its click history.
- **Bulk JSON creation API** for up to 100 links per request (`POST /api/links/bulk`).
- **Analytics CSV export** including timestamp, short code, destination, referrer, device, browser and bot flag (`GET /api/export/analytics.csv`).
- **Per-link QR code download** as PNG.
- **CSV import/export** for link inventories.
- **Campaign grouping and tag search** in the dashboard.
- **Visitor cookie identifier**, basic bot filtering, device/browser/referrer breakdown.
- **Expiry, click caps, password protection and instant pause/resume**.
- **API docs** automatically available at `/docs`.
- **SQLite by default** with a MySQL schema and optional `DATABASE_URL` configuration.

The project does not claim to provide live malware reputation checks, team RBAC, billing, or production-grade bot detection. Those require external integrations and additional deployment hardening.
