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

- **Cost:** Free Gemini Flash tier only. Token usage minimised by sending condensed market data per market.
- **No new API calls to Polymarket** — reuses `reports/poly2.json` (85 markets) and `reports/polytraders.json` (Kelly opportunities), both already cached by existing adapters.
- **LLM provider is swappable** — one `llm_client.py` module abstracts the Gemini call. Changing to Claude or a paid model requires editing one env var.
- **TDD** — tests written before implementation for engine logic and API endpoint.

---

## 4. Architecture

```
User Input (free text + optional structured tags)
        │
        ▼
POST /api/hedge-session
        │
   ┌────┴──────────────────────────────────────────────┐
   │  Stage 1 — Exposure Extraction (~150 tok)          │
   │  SKIPPED if both `asset` and `risk_type` supplied  │
   │  Gemini Flash                                      │
   │  Output: { asset, direction, risk_type, scenario } │
   └────┬──────────────────────────────────────────────┘
        │
   ┌────┴──────────────────────────────────────────────┐
   │  Stage 2 — Market Scoring (~3,500-4,000 tok in)   │
   │  Gemini Flash                                      │
   │  Input: structured exposure +                      │
   │    flattened markets (slug, question, yes_price,   │
   │    volume_24h, days_left) — slug included for join │
   │  Output: top ≤8 markets with                       │
   │    slug, correlation_score (0-10), hedge_side,     │
   │    narrative (2 sentences max)                     │
   │  Minimum correlation_score threshold: 2.0          │
   └────┬──────────────────────────────────────────────┘
        │
   Backend enriches with Kelly + smart money
   from polytraders.json (slug join + direction match)
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
- Strips markdown code fences from response (Gemini Flash often wraps JSON in ```json ... ```)
- Calls `json.loads()` on result; if it fails, retries once with an explicit "Return only raw JSON" suffix
- Raises `LLMError` on HTTP 429, timeout, or two consecutive parse failures
- Swappable: changing model requires only env var change

**`backend/adapters/hedge_engine.py`**

**`parse_exposure(text, asset, risk_type) -> dict`**
- Calls Stage 1 LLM to extract `{ asset, direction, risk_type, scenario }`
- Short-circuit: if both `asset` and `risk_type` are non-empty strings, skip Stage 1 and build the dict directly from the supplied values with `direction="long"` as default and `scenario=text`

**`_flatten_markets() -> list[dict]`**
- Reads `reports/poly2.json`
- Flattens nested `data["categories"][cat]["markets"]` into a single list
- Each item includes only: `slug`, `question`, `yes_price`, `volume_24h`, `days_left`

**`score_markets(exposure, markets, kelly_opps) -> list[HedgeResult]`**
- Calls Stage 2 LLM with exposure + flattened markets
- LLM instructed to return JSON array, each item: `{ slug, hedge_side, correlation_score, narrative }`
- Filters results to `correlation_score >= 2.0`; returns at most 8, sorted descending
- Enriches each result via slug join against `kelly_opps` (list from `polytraders.json`)

**`_enrich(result, kelly_opps) -> HedgeResult`**
- Looks up `result["slug"]` in `kelly_opps`
- `kelly_bet` and `smart_money_exposure` populated from match; `null` if no match
- `cross_signal: true` requires **both**: (a) slug match found, AND (b) `result["hedge_side"]` matches Kelly `outcome` direction after normalization
- **Outcome normalization:** Kelly `outcome` is `"Yes"`, `"No"`, or a named outcome (e.g., team name). Normalize to YES/NO: `outcome.lower() == "yes"` → `"YES"`, `outcome.lower() == "no"` → `"NO"`, anything else → `"YES"` (named outcomes mean betting that team wins = YES direction)

**`run_hedge_session(text, asset, risk_type) -> HedgeSessionResult`**
- Orchestrates: `parse_exposure` → `_flatten_markets` → `score_markets`
- Loads `polytraders.json` once, passes `opportunities` list to `score_markets`

### Endpoint (added to `server.py`)

```
POST /api/hedge-session
Content-Type: application/json

Request:
{
  "exposure": "I hold 2 BTC and worry about a tariff-driven risk-off event",
  "asset": "BTC",          // optional — triggers Stage 1 short-circuit with risk_type
  "risk_type": "risk-off"  // optional
}

Response 200:
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
      "narrative": "If your worst case hits...",
      "yes_price": 0.25,
      "volume_24h": 512750,
      "days_left": 14,
      "kelly_bet": 3.5,              // null if not in polytraders.json
      "smart_money_exposure": 78465, // null if not in polytraders.json
      "cross_signal": true           // true only when slug match + direction match
    }
  ]
}

Response 422: missing `exposure` field
Response 504: LLMError (timeout or repeated parse failure)
```

### CORS update (server.py)

Add `"POST"` to `allow_methods` in `CORSMiddleware`. `"Content-Type"` is already in `allow_headers` — no change needed there.

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
   - Allows user to sanity-check before trusting results

3. **Hedge List** (ranked by `correlation_score` descending)
   - Each card: correlation badge, hedge side (YES/NO pill), question, price, volume, days left
   - Kelly bet + smart money exposure shown where available
   - ⭐ `cross_signal` badge when Kelly smart money also holds this position in the same direction
   - Collapsible narrative paragraph

**States:** `idle` → `loading` (spinner, "Analysing your exposure...") → `results` → `error`

### `api.js` addition

```js
export async function postHedgeSession({ exposure, asset, riskType }) {
  // POST to /api/hedge-session
  // timeout: 60 seconds (LLM calls take 10-20s on free tier)
  // returns parsed JSON or null on error
}
```

Explicitly uses POST method. Timeout set to **60 seconds** (not the default 8s `tryFetch` timeout — LLM two-stage pipeline needs headroom).

---

## 7. Tests (TDD — written before implementation)

### `tests/test_llm_client.py`
- Mock Gemini HTTP — assert `complete()` returns parsed string
- Assert markdown fences stripped before returning (`\`\`\`json ... \`\`\`` → raw JSON string)
- Assert retry on first JSON parse failure, `LLMError` raised on second failure
- Assert `LLMError` raised on HTTP 429
- Assert `LLMError` raised on socket timeout
- Assert model is read from `GEMINI_MODEL` env var

### `tests/test_hedge_engine.py`
- Feed fixture `poly2.json` + `polytraders.json` (real file structure)
- Assert `_flatten_markets()` returns flat list, all items have `slug`, `question`, `yes_price`, `volume_24h`, `days_left`
- Assert `parse_exposure()` returns dict with keys: `asset`, `direction`, `risk_type`, `scenario`
- Assert Stage 1 short-circuit: when `asset` and `risk_type` both provided, `llm_client.complete` is NOT called for Stage 1
- Assert `score_markets()` returns **at most 8** results sorted by `correlation_score` descending
- Assert `score_markets()` filters out results with `correlation_score < 2.0`
- Assert enrichment correctly sets `kelly_bet` and `smart_money_exposure` when slug matches
- Assert `cross_signal: true` only when slug match AND `hedge_side` matches normalized Kelly outcome direction
- Assert `cross_signal: false` when slug matches but directions differ
- Assert `cross_signal: false` when no slug match
- Assert `score_markets()` handles malformed LLM output (missing `correlation_score`) without crashing — skips invalid items

### `tests/test_api.py` (extend existing)
- POST `/api/hedge-session` with mocked `run_hedge_session` — assert 200 response shape
- Assert 422 on missing `exposure` field
- Assert 504 when `run_hedge_session` raises `LLMError`
- Assert rate limit applies (30/min, same as other endpoints)
- Assert CORS allows POST from configured origin

---

## 8. Cost Model

| Call | Tokens in | Tokens out | Notes |
|---|---|---|---|
| Stage 1 (extraction) | ~150 | ~80 | Skipped if asset + risk_type supplied |
| Stage 2 (scoring 85 markets) | ~3,500–4,000 | ~600 | Includes system prompt + output schema |
| **Per session (cold)** | **~4,000** | **~680** | |
| **Per session (warm, both fields supplied)** | **~3,700** | **~600** | Stage 1 skipped |

Free tier: 15 requests/min, 1M tokens/day. 10 sessions/day ≈ 47k tokens — well within limits.

**Upgrade path:** Set `GEMINI_MODEL=gemini-1.5-pro` or add Claude support in `llm_client.py` — zero other changes required.

---

## 9. Files Changed / Created

| File | Action |
|---|---|
| `backend/llm_client.py` | Create |
| `backend/adapters/hedge_engine.py` | Create |
| `backend/server.py` | Add 1 endpoint + POST to CORS allow_methods |
| `frontend/src/tabs/Hedge.jsx` | Create |
| `frontend/src/api.js` | Add `postHedgeSession` (POST, 60s timeout) |
| `frontend/src/App.jsx` | Add Hedge tab to nav |
| `tests/test_llm_client.py` | Create |
| `tests/test_hedge_engine.py` | Create |
| `tests/test_api.py` | Extend |

---

## 10. Out of Scope (this iteration)

- Session history / saving past hedge sessions
- Push notifications when a hedge market moves
- Automated re-run when poly2.json refreshes
- Auth / billing layer (future when monetising)
- Parallel LLM calls across market batches
