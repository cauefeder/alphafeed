# Alpha Feed

A quant dashboard integrating BTC volatility analysis, Polymarket prediction markets, and smart-money consensus signals from the PolyTraders and HedgePoly projects.

**Live demo**: Deploy frontend to Vercel/Netlify · backend to Render/Railway

---

## Features

| Tab | Data |
|-----|------|
| **Overview** | BTC price, DVOL index chart, top Polymarket opportunities |
| **Vol Curve** | Intraday RV vs IV, day-of-week seasonality, historical HV |
| **Term Struct** | BTC options IV surface by expiry (Deribit) |
| **Polymarket** | All active markets ranked by edge score + **Resolves In** column |
| **Alpha** | Kelly-sized trade opportunities from top traders + smart-money signals |
| **Config** | Data source status, quick-start guide |

All external APIs are **free and require no authentication**.

---

## Architecture

```
AlphaFeed/
├── backend/                    # FastAPI server (Python 3.12)
│   ├── server.py               # CORS proxy + security headers + report reader
│   ├── requirements.txt        # Pinned runtime deps
│   ├── requirements-dev.txt    # pytest + httpx
│   └── adapters/
│       ├── polytraders_export.py   # PolyTraders pipeline → reports/polytraders.json
│       └── hedgepoly_export.py     # HedgePoly pipeline  → reports/hedgepoly.json
├── frontend/                   # Vite + React (Node 18+)
│   ├── src/
│   │   ├── App.jsx             # Root router (~150 lines)
│   │   ├── tokens.js           # Design system tokens
│   │   ├── styles.js           # Global CSS string
│   │   ├── math.js             # Pure vol / Kelly math
│   │   ├── api.js              # Data fetchers + seed data
│   │   ├── components/         # Shared UI primitives
│   │   └── tabs/               # One file per tab
│   └── index.html
├── reports/                    # JSON outputs from adapters (gitignored)
├── tests/                      # pytest suite
├── .github/workflows/ci.yml    # CI: pytest + npm build
├── render.yaml                 # Render.com deploy config
└── vercel.json                 # Vercel deploy config
```

The backend never modifies the existing Python projects — it imports them via `sys.path` and re-exports their outputs as JSON.

---

## Quick Start

### Prerequisites
- Python 3.10+ (3.12 recommended)
- Node.js 18+

### 1. Clone and set up environment

```bash
git clone https://github.com/cauefeder/alphafeed.git
cd alphafeed
cp .env.example .env    # edit if needed
```

### 2. Backend

```bash
# Linux / macOS
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8000

# Windows (PowerShell)
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

API available at `http://localhost:8000` · Docs at `http://localhost:8000/docs`.

### 3. Alpha signals (optional)

The Alpha tab shows trade signals from the PolyTraders and HedgePoly projects.
If you have those projects available, set their paths in `.env`:

```env
POLYTRADERS_DIR=/path/to/PolyTraders
HEDGEPOLY_DIR=/path/to/HedgePoly/prediction-market-analysis
```

Then run the adapters (or schedule via cron/Task Scheduler):

```bash
python backend/adapters/polytraders_export.py
python backend/adapters/hedgepoly_export.py
```

> If these paths are not set, the adapters look for sibling directories
> (`../PolyTraders` and `../HedgePoly/prediction-market-analysis`).
> The app works fine without them — the Alpha tab shows seed data.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

The Vite dev server proxies `/api/*` → `localhost:8000` automatically.

---

## API Reference

| Endpoint | Description | Cache |
|----------|-------------|-------|
| `GET /api/health` | Liveness check + available reports | — |
| `GET /api/polymarket` | Gamma API markets + `resolvesIn` field | 5 min |
| `GET /api/overview` | Aggregated overview stats | 5 min |
| `GET /api/kelly-signals` | PolyTraders Kelly opportunities | file-based |
| `GET /api/smart-money` | HedgePoly smart-money consensus | file-based |

### `resolvesIn` field

Added to every Polymarket market object:
```json
{ "resolvesIn": 12.3 }   // days until resolution (1 decimal)
{ "resolvesIn": null }    // no end date set
```

---

## Deployment

### Frontend → Vercel / Netlify

```bash
cd frontend && npm run build
# Deploy the dist/ folder
```

Set environment variable:
```
VITE_API_BASE=https://your-backend.onrender.com
```

### Backend → Render / Railway

Point the service to `backend/` with:
```
Build: pip install -r requirements.txt
Start: uvicorn server:app --host 0.0.0.0 --port $PORT
```

---

## Running Tests

```bash
# Install dev deps (once)
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

pytest tests/ -v
```

---

## Data Sources

| Source | API | Notes |
|--------|-----|-------|
| Binance | `api.binance.com` | BTC spot price, hourly klines |
| Deribit | `deribit.com/api/v2/public` | DVOL index, historical vol, options book |
| Polymarket Gamma | `gamma-api.polymarket.com/markets` | Active markets, prices, liquidity |
| Polymarket Data | `data-api.polymarket.com` | Leaderboard, trader positions |

All endpoints are public, rate-limit friendly, and CORS-accessible from the backend.

---

*Not financial advice. All signals are informational only.*
