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
├── backend/                # FastAPI server (Python)
│   ├── server.py           # CORS proxy + report reader
│   ├── requirements.txt
│   └── adapters/
│       ├── polytraders_export.py   # Runs PolyTraders pipeline → reports/polytraders.json
│       └── hedgepoly_export.py     # Runs HedgePoly pipeline  → reports/hedgepoly.json
├── frontend/               # Vite + React dashboard
│   ├── src/App.jsx         # Main component (all tabs)
│   └── src/main.jsx
├── reports/                # JSON outputs from adapters (gitignored)
└── tests/                  # pytest suite
```

The backend never rewrites the existing Python projects — it imports them via `sys.path` and re-exports their outputs as JSON.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- The `PolyTraders` and `HedgePoly/prediction-market-analysis` directories must exist as siblings of `AlphaFeed/`

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

API available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### 2. Populate Alpha signals (optional)

```bash
# Run once (or schedule via cron)
python backend/adapters/polytraders_export.py
python backend/adapters/hedgepoly_export.py
```

This writes `reports/polytraders.json` and `reports/hedgepoly.json`.
Schedule every 6 hours for fresh signals:
```cron
0 */6 * * * cd /path/to/AlphaFeed && python backend/adapters/polytraders_export.py
0 */6 * * * cd /path/to/AlphaFeed && python backend/adapters/hedgepoly_export.py
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

The Vite dev server proxies `/api/*` requests to `localhost:8000` automatically.

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
pip install pytest httpx fastapi
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
