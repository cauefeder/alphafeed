# Quant Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weekly quantitative intelligence report to AlphaFeed — a separate tab that scores live Polymarket opportunities using an XGBoost classifier trained on historical resolved markets, expanding trader coverage from 25 to ~100, with results pushed to Telegram every Sunday.

**Architecture:** Three independent sub-systems built in sequence. Sub-system 1 expands the existing trader pipeline. Sub-system 2 adds a local training script and a weekly inference cron. Sub-system 3 pushes a summary to Telegram. All computation runs in GitHub Actions (free). Render serves static JSON. No LLM, no paid APIs.

**Tech Stack:** Python 3.12, XGBoost, scikit-learn, numpy, FastAPI, React/Vite, GitHub Actions, Telegram Bot API.

---

## Scope boundaries

- The **Quant tab is completely separate** from the existing Alpha (Kelly signals) tab. No mixing of data, components, or endpoints.
- The XGBoost model is trained **locally once**, validated rigorously, and committed as `models/xgboost_model.pkl`. The weekly cron only runs inference.
- Overfitting is prevented through: temporal train/val/test split, cross-validation, feature importance review, and held-out test AUC gate (must exceed 0.60 to pass).
- The Polymarket public API provides ~50,000+ resolved markets going back to 2021 — this is the primary training corpus.

---

## File structure

### New files
| Path | Responsibility |
|---|---|
| `backend/adapters/fetch_historical.py` | Pull resolved Polymarket markets for training data |
| `backend/adapters/train_model.py` | Train XGBoost, validate, save pkl + calibration params |
| `backend/adapters/quant_report.py` | Weekly inference: load model, score live opps, write JSON |
| `backend/adapters/quant_telegram.py` | Format and send weekly Telegram summary |
| `models/xgboost_model.pkl` | Committed trained model (binary, ~500KB) |
| `models/calibration_params.json` | Platt scaling a/b params + feature stats |
| `models/training_metrics.json` | AUC, precision, recall, confusion matrix from last train run |
| `reports/quant_report.json` | Weekly scored opportunities (served by API) |
| `frontend/src/tabs/QuantReport.jsx` | Quant tab: summary strip, category chart, scored table |
| `tests/test_quant_report.py` | Unit tests for scoring engine |
| `tests/test_fetch_historical.py` | Unit tests for historical data fetcher |
| `.github/workflows/weekly-quant-report.yml` | Sunday 20:00 UTC cron |

### Modified files
| Path | Change |
|---|---|
| `backend/adapters/polytraders_export.py` | Expand to OVERALL(50) + CRYPTO(25) + POLITICS(25), deduplicate |
| `backend/requirements.txt` | Add xgboost, scikit-learn, numpy |
| `backend/server.py` | Add GET /api/quant-report endpoint |
| `frontend/src/App.jsx` | Add QuantReport tab (between Alpha and Macro) |
| `frontend/src/api.js` | Add fetchQuantReport() |

---

## Sub-system 1: Expand trader coverage

### Design

Fetch three leaderboards in parallel, deduplicate by `proxy_wallet`, keep up to 100 unique traders. The existing `run_export()` function receives a `traders` list and is unchanged. Only the leaderboard fetch changes.

```python
# polytraders_export.py addition
CATEGORIES = [
    ("OVERALL",  50),
    ("CRYPTO",   25),
    ("POLITICS", 25),
]

def fetch_expanded_traders(time_period: str) -> list:
    """Fetch traders from multiple leaderboard categories, deduplicate by wallet."""
    seen: set[str] = set()
    traders: list = []
    for category, limit in CATEGORIES:
        batch = fetch_top_traders(time_period=time_period, limit=limit, category=category)
        for t in batch:
            if t.proxy_wallet not in seen:
                seen.add(t.proxy_wallet)
                traders.append(t)
    return traders
```

The polytraders.json report gains a `categoryBreakdown` field:
```json
{
  "tradersChecked": 87,
  "categoryBreakdown": {"OVERALL": 50, "CRYPTO": 18, "POLITICS": 14},
  ...
}
```

---

## Sub-system 2: XGBoost training pipeline

### 2a. Historical data fetch (`fetch_historical.py`)

Pulls resolved markets from `https://gamma-api.polymarket.com/markets?closed=true` using pagination. For each market, captures a feature snapshot representing what was knowable ~7-14 days before resolution (uses market data at face value — no time-travel).

**Fields captured per market:**
- `question`, `slug`, `category` (inferred from tags)
- `outcomePrices` at fetch time (crowd probability)
- `volume24hr`, `volumeTotal`, `liquidity`
- `endDate` (to compute `days_left` at time of snapshot)
- `outcome` (YES/NO — the label)

Saves to `data/historical_markets.csv` (gitignored). Fetches ~8,000–15,000 resolved markets in ~10 minutes.

```
python backend/adapters/fetch_historical.py --pages 150 --output data/historical_markets.csv
```

### 2b. Model training (`train_model.py`)

**Feature engineering:**
```python
features = [
    "yes_price",                          # raw crowd probability
    "calibrated_prob",                    # logit(yes_price) * b + a (fit on data)
    "info_ratio",                         # volume_24h / sqrt(days_left + 1)
    "log_volume_total",                   # log1p(volume_total)
    "log_liquidity",                      # log1p(liquidity)
    "days_left",                          # time to resolution
    "is_longshot",                        # yes_price < 0.20 (binary)
    "is_favorite",                        # yes_price > 0.80 (binary)
    "price_extremity",                    # |yes_price - 0.5| * 2 (0=uncertain, 1=decided)
]
```

**Label definition:**
```python
# crowd was wrong: market said <0.5 but resolved YES, or >=0.5 but resolved NO
label = int((resolved_yes == 1) != (yes_price >= 0.5))
```

**Overfitting prevention — mandatory gates:**

1. **Temporal split** (not random): oldest 70% → train, next 15% → validation, newest 15% → test. This prevents leakage from future market patterns contaminating training.

2. **Cross-validation**: 5-fold TimeSeriesSplit on training set. Report mean ± std AUC.

3. **Regularisation**: XGBoost params include `max_depth=4`, `min_child_weight=10`, `subsample=0.8`, `colsample_bytree=0.8`, `reg_alpha=0.1`, `reg_lambda=1.0`. These are conservative defaults to prevent overfitting on small feature sets.

4. **Feature importance check**: Print SHAP values after training. Flag if any single feature explains >60% of variance (signals overfitting to one variable).

5. **Held-out test gate**: If test AUC < 0.58, training script exits with an error and refuses to save the model. The gate is intentionally low — prediction markets are hard to beat. A 0.58 AUC means the model is adding real signal.

**Training output:**
```
python backend/adapters/train_model.py --data data/historical_markets.csv

[train_model] 11,420 resolved markets loaded
[train_model] Train: 7,994  Val: 1,713  Test: 1,713
[train_model] CV AUC (5-fold): 0.634 ± 0.018
[train_model] Validation AUC: 0.641
[train_model] Test AUC: 0.628  ← PASS (threshold: 0.58)
[train_model] Feature importance:
               info_ratio        0.31
               yes_price         0.24
               calibrated_prob   0.18
               log_liquidity     0.12
               days_left         0.09
               is_longshot       0.04
               ...
[train_model] Model saved → models/xgboost_model.pkl
[train_model] Calibration saved → models/calibration_params.json
[train_model] Metrics saved → models/training_metrics.json
```

---

## Sub-system 2c: Weekly inference (`quant_report.py`)

Runs in GitHub Actions every Sunday. Loads committed model, scores all current opportunities from `polytraders.json`.

**Scoring per opportunity:**
```python
def score_opportunity(opp: dict, model, calibration: dict) -> dict:
    p = opp["curPrice"]
    vol = opp["volume_24h"]           # from poly2 enrichment
    days = max(opp.get("days_left") or 14, 0.5)

    features = {
        "yes_price": p,
        "calibrated_prob": calibrate(p, calibration),
        "info_ratio": vol / (days ** 0.5) / 10_000,
        "log_volume_total": log1p(opp.get("volumeTotal", 0)),
        "log_liquidity": log1p(opp.get("liquidity", 0)),
        "days_left": days,
        "is_longshot": int(p < 0.20),
        "is_favorite": int(p > 0.80),
        "price_extremity": abs(p - 0.5) * 2,
    }

    quant_score = float(model.predict_proba([list(features.values())])[0][1])
    tier = "A" if quant_score >= 0.65 else "B" if quant_score >= 0.40 else "C"

    return {**opp, "quantScore": quant_score, "signalTier": tier,
            "calibratedProb": features["calibrated_prob"],
            "infoRatio": round(features["info_ratio"], 3)}
```

**Output** (`reports/quant_report.json`):
```json
{
  "generatedAt": "2026-03-30T20:00:00Z",
  "weekOf": "2026-03-30",
  "modelVersion": "1.0",
  "modelAuc": 0.628,
  "summary": {
    "totalScored": 32,
    "tierA": 4,
    "tierB": 11,
    "tierC": 17,
    "topCategory": "crypto",
    "topCategoryAvgScore": 0.74
  },
  "opportunities": [
    {
      "slug": "btc-90k",
      "title": "Will BTC hit $90K by April?",
      "quantScore": 0.84,
      "signalTier": "A",
      "calibratedProb": 0.68,
      "infoRatio": 0.51,
      "curPrice": 0.62,
      "kellyBet": 4.20,
      "nSmartTraders": 8,
      "totalExposure": 42000,
      "url": "https://polymarket.com/event/btc-90k"
    }
  ],
  "categoryReport": {
    "crypto":   {"count": 8,  "avgQuantScore": 0.74, "tierACcount": 2},
    "politics": {"count": 12, "avgQuantScore": 0.51, "tierACount": 1},
    "sports":   {"count": 6,  "avgQuantScore": 0.38, "tierACount": 0},
    "macro":    {"count": 6,  "avgQuantScore": 0.61, "tierACount": 1}
  }
}
```

---

## Sub-system 3: Telegram push (`quant_telegram.py`)

Sends after `quant_report.json` is generated. Uses same `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` env vars as the existing Kelly bot. Single message, ~30 lines of HTML.

**Message format:**
```
📊 <b>Weekly Quant Report</b> — Week of Mar 30

🟢 <b>Tier A signals (4)</b>
• <a href="...">BTC hits $90K?</a> — score 0.84 | crowd→cal: 62%→68% | info: 0.51
• <a href="...">Fed rate cut?</a> — score 0.79 | crowd→cal: 38%→44% | info: 0.38
• ...

📈 Strongest category: <b>Crypto</b> (avg 0.74)
⚠️ Sports: low signal (0.38) — skip unless you have domain edge

32 markets scored · Model AUC 0.63 · Not financial advice
```

Uses stdlib `urllib.request` — no extra dependencies.

---

## Sub-system 4: Backend endpoint

Add to `server.py`:
```python
@app.get("/api/quant-report")
def quant_report() -> dict:
    return _read_report("quant_report")
```

One line. Reuses the existing `_read_report()` helper (404 if missing, 500 if corrupt JSON).

---

## Sub-system 5: Frontend tab (`QuantReport.jsx`)

Three sections, no shared components with Alpha tab:

1. **Summary strip** — generatedAt, weekOf, modelAUC badge, tierA count
2. **Category bar chart** — horizontal bars using existing Recharts (already a dep), one bar per category coloured by avgQuantScore
3. **Opportunities table** — columns: Tier badge, Market (linked), Quant Score, Calibrated Prob, Info Ratio, Kelly Bet. Sortable by any column. Top 15 rows shown.

Signal tier badge colours: A = `T.green`, B = `T.amber`, C = `T.dim`. Matches existing design tokens.

---

## Sub-system 6: GitHub Actions cron

New file `.github/workflows/weekly-quant-report.yml`:
```yaml
permissions:
  contents: write

on:
  schedule:
    - cron: "0 20 * * 0"   # Sunday 20:00 UTC
  workflow_dispatch:

steps:
  - checkout
  - python setup
  - pip install -r backend/requirements.txt
  - run quant_report.py        # inference only, model.pkl already committed
  - run quant_telegram.py      # push Telegram message
  - git commit reports/quant_report.json + push
```

---

## Testing strategy

### `test_fetch_historical.py`
- Mock Gamma API, verify pagination and field extraction
- Verify CSV output has required columns
- Verify graceful handling of missing `outcomePrices`

### `test_quant_report.py`
- `test_score_opportunity_features_correct` — verify feature values for known input
- `test_tier_boundaries` — score 0.70 → A, 0.50 → B, 0.30 → C
- `test_model_not_needed_for_feature_engineering` — feature computation is pure functions, no model required
- `test_calibrate_midpoint` — calibrate(0.5) ≈ 0.5 (calibration shouldn't move midpoint)
- `test_generate_report_empty_input` — empty opportunities list → valid JSON with zeroed summary
- `test_category_report_aggregation` — verify avgQuantScore math per category

### `test_train_model.py` (light)
- `test_feature_matrix_shape` — N rows × 9 columns
- `test_temporal_split_no_leakage` — test indices are always newer than val, val newer than train
- `test_auc_gate_rejects_bad_model` — mock model returning random predictions → AUC ≈ 0.50 → exits

---

## Local workflow for model updates

```bash
# 1. Fetch fresh historical data (run once every 2-3 months)
python backend/adapters/fetch_historical.py --pages 150 --output data/historical_markets.csv

# 2. Train and validate
python backend/adapters/train_model.py --data data/historical_markets.csv

# 3. Review output in models/training_metrics.json
# 4. If AUC passes gate and feature importance looks reasonable:
git add models/xgboost_model.pkl models/calibration_params.json models/training_metrics.json
git commit -m "chore: retrain XGBoost model vX.Y"
git push origin master
```

`data/` directory is gitignored. `models/` is committed.

---

## Constraints and non-goals

- **No real-time inference** — model runs weekly, not on every API request
- **No automatic retraining** — always a deliberate local step with human review of metrics
- **No feature store** — features computed fresh each inference run from JSON files
- **No mixing with Alpha tab** — QuantReport.jsx imports nothing from Alpha.jsx and vice versa
- **No paid APIs** — Polymarket Gamma API is free and public
