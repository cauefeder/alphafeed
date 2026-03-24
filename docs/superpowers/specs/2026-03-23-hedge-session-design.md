# Hedge Session — Design Spec
**Date:** 2026-03-23
**Project:** AlphaFeed
**Status:** Approved for implementation

---

## 1. Problem

A user holding a real-world position (BTC long, tech stocks, Brazilian equities) or exposed to a macro risk (rate hike, tariff shock, geopolitical conflict) has no structured way to find Polymarket prediction markets that would pay out in their worst-case scenario. Searching Polymarket manually is slow and lacks quantitative ranking.

---

## 2. Goal

A **Hedge Session** tab in AlphaFeed where the user describes their exposure in plain language, and the system returns a ranked list of Polymarket bets — each with full quant data and a plain-English explanation of how it pays off if the worst case happens.

---

## 3. Constraints

- **Cost:** Free Gemini Flash tier only. Token usage minimised by sending condensed market data (4 fields per market, not full objects).
- **No new API calls to Polymarket** — reuses `reports/poly2.json` (85 markets) and `reports/polytraders.json` (Kelly opportunities), both already cached by existing adapters.
- **LLM provider is swappable** — one `llm_client.py` module abstracts the Gemini call. Changing to Claude or a paid model requires editing one env var and one line.
- **TDD** — tests written before implementation for engine logic and API endpoint.

---

## 4. Architecture

```
User Input (free text + optional structured tags)
        │
        ▼
POST /api/hedge-session
        │
   ┌────┴──────────────────────────────────────┐
   │  Stage 1 — Exposure Extraction (~150 tok) │
   │  Gemini Flash                             │
   │  Output: { asset, direction, risk_type,   │
   │            scenario_description }         │
   └────┬──────────────────────────────────────┘
        │
   ┌────┴──────────────────────────────────────┐
   │  Stage 2 — Market Scoring (~3k tok in)    │
   │  Gemini Flash                             │
   │  Input: structured exposure +             │
   │    85 markets (question, yes_price,       │
   │    volume_24h, days_left only)            │
   │  Output: top 8 markets with               │
   │    correlation_score (0-10), hedge_side,  │
   │    narrative (2 sentences max)            │
   └────┬──────────────────────────────────────┘
        │
   Backend enriches with Kelly + smart money
   from polytraders.json (slug join)
        │
        ▼
   JSON response → Hedge tab
```

---

## 5. Backend

### New files

**`backend/llm_client.py`**
- Single function: `complete(prompt: str) -> str`
- Reads `GEMINI_API_KEY` and `GEMINI_MODEL` (default: `gemini-2.0-flash`) from env
- Raises `LLMError` on failure
- Swappable: changing model requires only env var change

**`backend/adapters/hedge_engine.py`**
- `parse_exposure(text, asset, risk_type) -> dict` — calls Stage 1
- `score_markets(exposure, markets, kelly_opps) -> list[HedgeResult]` — calls Stage 2, enriches
- `run_hedge_session(text, asset, risk_type) -> HedgeSessionResult` — orchestrates both stages, loads cached JSONs

### Endpoint (added to `server.py`)

```
POST /api/hedge-session
Content-Type: application/json

Request:
{
  "exposure": "I hold 2 BTC and worry about a tariff-driven risk-off event",
  "asset": "BTC",          // optional
  "risk_type": "risk-off"  // optional
}

Response:
{
  "exposure_parsed": {
    "asset": "BTC",
    "direction": "long",
    "risk_type": "risk-off",
    "scenario": "..."
  },
  "hedges": [
    {
      "question": "Will BTC drop below $60K in March?",
      "url": "https://polymarket.com/event/...",
      "hedge_side": "YES",
      "correlation_score": 8.5,
      "narrative": "...",
      "yes_price": 0.25,
      "volume_24h": 512750,
      "days_left": 14,
      "kelly_bet": 3.5,
      "smart_money_exposure": 78465,
      "cross_signal": true
    }
  ]
}
```

### Enrichment logic

Join `hedges` from Stage 2 to `polytraders.json` opportunities by matching market slug. Where a match exists:
- Set `kelly_bet` and `smart_money_exposure` from polytraders data
- Set `cross_signal: true` (LLM + smart money both point same direction)

Where no match: `kelly_bet: null`, `smart_money_exposure: null`, `cross_signal: false`.

---

## 6. Frontend

### New tab

`🛡️ Hedge` — inserted between Alpha and Macro in the nav bar.

### New file: `frontend/src/tabs/Hedge.jsx`

**Three zones:**

1. **Exposure Input**
   - Textarea: free text description
   - Optional fields: Asset (text input), Risk Type (dropdown: Risk-off / Rate hike / Recession / Geopolitical / Crypto crash / Tech selloff / Other)
   - `Run Hedge` button

2. **Parsed Exposure Card** (shown after run)
   - Displays what the LLM understood: asset, direction, risk type, scenario summary
   - Allows user to confirm before trusting results

3. **Hedge List** (ranked by `correlation_score` descending)
   - Each card: correlation badge, hedge side (YES/NO), question, price, volume, days left
   - Kelly bet + smart money exposure shown where available
   - ⭐ `cross_signal` badge when Kelly smart money also holds this position
   - Collapsible narrative paragraph

**States:** `idle` → `loading` (spinner) → `results` → `error`

### `api.js` addition

```js
export async function postHedgeSession({ exposure, asset, riskType }) { ... }
```

Reuses existing `API_BASE` and `tryFetch` pattern.

---

## 7. Tests (TDD — written before implementation)

### `tests/test_llm_client.py`
- Mock Gemini HTTP call — assert `complete()` returns string
- Assert `LLMError` raised on HTTP 429 / timeout
- Assert model is read from env var

### `tests/test_hedge_engine.py`
- Feed fixture `poly2.json` + `polytraders.json`
- Assert `parse_exposure()` returns dict with required keys
- Assert `score_markets()` returns exactly 8 results sorted by `correlation_score` desc
- Assert enrichment correctly joins Kelly data by slug
- Assert `cross_signal: true` only when slug match AND hedge_side matches Kelly outcome

### `tests/test_api.py` (extend existing)
- POST `/api/hedge-session` with mocked `run_hedge_session`
- Assert 200 response shape matches spec
- Assert 422 on missing `exposure` field
- Assert rate limit applies (slowapi, same 30/min rule)

---

## 8. Cost Model

| Call | Tokens in | Tokens out | Cost (Gemini Flash free) |
|---|---|---|---|
| Stage 1 (extraction) | ~150 | ~80 | Free |
| Stage 2 (scoring 85 markets) | ~2,800 | ~600 | Free |
| **Per session** | **~3,000** | **~680** | **Free** |

Free tier: 15 requests/min, 1M tokens/day. A user running 10 hedge sessions/day = ~37k tokens — well within limits.

**Upgrade path:** Set `GEMINI_MODEL=gemini-1.5-pro` or `ANTHROPIC_API_KEY` + update `llm_client.py` — zero other changes.

---

## 9. Files Changed / Created

| File | Action |
|---|---|
| `backend/llm_client.py` | Create |
| `backend/adapters/hedge_engine.py` | Create |
| `backend/server.py` | Add 1 endpoint |
| `frontend/src/tabs/Hedge.jsx` | Create |
| `frontend/src/api.js` | Add `postHedgeSession` |
| `frontend/src/App.jsx` | Add Hedge tab to nav |
| `tests/test_llm_client.py` | Create |
| `tests/test_hedge_engine.py` | Create |
| `tests/test_api.py` | Extend |

---

## 10. Out of Scope (this iteration)

- Session history / saving past hedge sessions
- Push notifications when a hedge market moves
- Automated re-run when poly2.json refreshes
- Charging / auth layer (future when monetising)
