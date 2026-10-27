# Wind Forecast Intelligence — Gridbricks hiring challenge

A React + FastAPI dashboard that evaluates Elexon national wind-generation forecasts against actual generation for day-ahead purchasing decisions made in January 2026.

> **Scope:** This is a decision-support pilot, not a trading system. It uses only Elexon `FUELHH` actuals and `WINDFOR` forecast data. It does not calculate demand shortfall because the challenge explicitly excludes demand data.

## Product features

- Monthly overview of forecast accuracy: MAE, RMSE, signed forecast bias, WAPE, and matched data coverage.
- Daily mean forecast vs actual generation trend.
- Daily absolute-error chart.
- Delivery-day inspector with all 48 half-hourly settlement periods.
- Forecast publication timestamp and lead-time visibility for each selected vintage.
- Configurable decision cutoff in UK local time.
- CSV export for all expected half-hourly delivery periods.
- FastAPI documentation at `/docs`, health endpoint, upstream error handling, and a 10-minute in-memory response cache.
- Docker Compose setup for running the UI and API together.

## How the time logic works

The requested decision month is January 2026. A decision on date **D** is evaluated against delivery on **D+1**. Therefore the expected delivery slots cover 2 January through 1 February 2026: 31 decision days × 48 half-hourly slots = 1,488 expected periods.

For every delivery `startTime`, the backend selects the forecast record with the greatest `publishTime` that is **at or before the selected cutoff on the preceding UK-local decision date**. This prevents forecasts published after the decision deadline from leaking into the evaluation. Older forecasts published in December are queried too, so the first January decision can still use a forecast that was already available then. Times are parsed as timezone-aware values and normalized to UTC for matching; the business cutoff is created in `Europe/London`.

The challenge does not specify the client's exact trade deadline. The default of **10:00 UK time** is an explicit pilot assumption, not a claim about every UK market auction. The dropdown allows the reviewer to test other cutoffs. Confirm the real client's decision deadline before presenting the analysis as operational guidance.

## Metrics

- **Error:** forecast MW − actual MW. Positive values mean wind generation was over-forecast.
- **MAE:** mean absolute error in MW.
- **RMSE:** root mean square error in MW; larger errors receive more weight.
- **Bias:** mean signed error in MW; positive indicates average over-forecasting.
- **WAPE:** sum of absolute errors divided by sum of absolute actual generation, expressed as a percentage. Unlike MAPE, this does not divide by each individual actual observation, so zero-generation intervals are not automatically undefined.
- **Matched coverage:** the number of half-hourly periods with both an actual and an eligible forecast, divided by all 1,488 expected periods. Missing data stays missing and is not converted to zero.

Actual rows are filtered to `fuelType == WIND` and deduplicated by keeping the latest published row per delivery timestamp. Forecasts are joined by the same delivery `startTime`; the chosen forecast is the latest eligible vintage under the selected cutoff.

## Project structure

```text
.
├── backend/
│   ├── app/
│   │   ├── analysis.py       # Timestamp matching, forecast-vintage selection, metrics
│   │   ├── elexon.py         # Async client for Elexon FUELHH/WINDFOR stream endpoints
│   │   └── main.py           # FastAPI routes, CORS, validation, in-memory cache
│   ├── tests/
│   │   └── test_analysis.py  # Tests for cutoff selection and missing-data behavior
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Dashboard and interactions
│   │   ├── main.tsx
│   │   ├── types.ts
│   │   └── styles.css
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── .env.example
└── README.md
```

## Run locally with Docker

Prerequisites: Docker Desktop (including Docker Compose) and an internet connection for the Elexon API.

```bash
docker compose up --build
```

Open the UI at <http://localhost:8080>. The API health check is at <http://localhost:8000/api/health>, and interactive API docs are at <http://localhost:8000/docs>.

To stop the containers:

```bash
docker compose down
```

The first request may take some time because the backend fetches historical actuals and forecast vintages. Results are cached in memory for 10 minutes. Click **Refresh Elexon data** to bypass that cache.

## Run locally without Docker

### Backend

Python 3.11+ is recommended.

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to `http://localhost:8000` by default.

## Tests

From the repository root:

```bash
cd backend
pip install -r requirements.txt
python -m pytest -q
```

The unit tests use small in-memory records and do not require network access. They verify that a forecast published after the decision cutoff is rejected, the most recent eligible forecast is chosen, the latest actual revision is retained, and missing pairs remain missing.

## API

`GET /api/health`

`GET /api/analysis?month=2026-01&cutoff_time=10:00`

Optional `refresh=true` bypasses the 10-minute server cache. The month is intentionally limited to `2026-01` to enforce the assignment scope. `cutoff_time` is an `HH:MM` UK-local time.

## Deployment

A straightforward deployment is **React on Vercel + FastAPI on Render**. This uses Vercel for the app UI and a Python-capable host for the backend. Configure the URL between them explicitly.

### 1. Deploy the backend

1. Push this repository to GitHub.
2. In Render, create a new **Web Service** from the repo and select Docker runtime.
3. Set the Dockerfile path to `backend/Dockerfile` and the build context to the repository root if the Render configuration exposes that option. The Dockerfile copies `backend/requirements.txt` from the repository root.
4. Set environment variables:
   - `CORS_ORIGINS=https://YOUR-VERCEL-PROJECT.vercel.app`
   - `CACHE_TTL_SECONDS=600`
   - `ELEXON_API_BASE=https://data.elexon.co.uk/bmrs/api/v1/`
5. Deploy, then check `https://YOUR-API-HOST/api/health`.

If the selected Render build configuration cannot use the repository root as Docker context, change the build context or use a Python runtime with `backend` as the root directory; keep the app start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT` when running from the backend directory.

### 2. Deploy the frontend

1. Import the same repo into Vercel and set the **Root Directory** to `frontend`.
2. Add the build environment variable `VITE_API_BASE_URL=https://YOUR-API-HOST` (no trailing slash).
3. Deploy. The frontend's requests will be sent to the deployed backend; the backend must allow the exact Vercel origin in `CORS_ORIGINS`.
4. Open the deployed URL in a private/incognito window and verify the dashboard loads actual Elexon data, the cutoff dropdown triggers a reload, the delivery-day table works, and CSV export works.

Do not claim deployment is complete until both endpoints have been tested from the public internet.

## Before submission

- Verify the dashboard has nonzero `actual_periods`, `forecast_periods`, and `matched_periods`; investigate unexpected zero coverage instead of submitting a blank dashboard.
- Review the chosen cutoff with the hiring team/client context; `10:00` is a documented assumption.
- Run tests and inspect the code for correctness.
- Record an unlisted YouTube walkthrough no longer than 10 minutes: about 4–5 minutes for the customer-facing dashboard, then about 4–5 minutes for the technical architecture and code review.
- Create a **public GitHub repository with an anonymous/random repo name**, as required by the brief. Ensure the README includes the deployed app URL.
- Open both the deployed app and the unlisted video in incognito mode. Submit their public URLs and the repository URL in the provided form.

## AI assistance disclosure

OpenAI ChatGPT was used to assist with initial scaffolding, implementation drafting, and documentation. The submitter should run the tests, verify the upstream API behavior, review the code, and understand all key implementation decisions before submission.

## Data-source documentation

- [Elexon FUELHH stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream)
- [Elexon WINDFOR stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)
- [Elexon Insights API developer portal](https://developer.data.elexon.co.uk/)
