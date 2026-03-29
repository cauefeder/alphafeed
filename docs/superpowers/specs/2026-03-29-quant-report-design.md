# Quant Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weekly quantitative intelligence report to AlphaFeed — a separate tab that scores live Polymarket opportunities using an XGBoost classifier trained on historical resolved markets, expanding trader coverage from 25 to ~100, with macro/politics trend charts, a model vs crowd scatter plot, and auto-generated insights pushed to Telegram every Sunday.

**Architecture:** Three independent sub-systems built in sequence. Sub-system 1 expands the existing trader pipeline. Sub-system 2 adds a local training script and a weekly inference cron (reads both `polytraders.json` and `poly2.json`). Sub-system 3 pushes a rich summary to Telegram. All computation runs in GitHub Actions (free). Render serves static JSON. No LLM, no paid APIs.

**Tech Stack:** Python 3.12, XGBoost, scikit-learn, numpy, FastAPI, React/Vite, GitHub Actions, Telegram Bot API.

**Branch:** The AlphaFeed repo's default branch is `master`. All `git push` commands in this spec target `master`.

---

## Scope boundaries

- The **Quant tab is completely separate** from the existing Alpha (Kelly signals) tab. No mixing of data, components, or endpoints.
- The XGBoost model is trained **locally once**, validated rigorously, and committed as `models/xgboost_model.pkl`. The weekly cron only runs inference.
- Overfitting is prevented through: temporal train/val/test split, cross-validation, feature importance review, and held-out test AUC gate (must exceed 0.58 to pass).
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
| `models/calibration_params.json` | Platt scaling a/b params + feature order list |
| `models/training_metrics.json` | AUC, precision, recall, confusion matrix, modelVersion (date string) |
| `reports/quant_report.json` | Weekly scored opportunities (served by API) |
| `frontend/src/tabs/QuantReport.jsx` | Quant tab: summary strip, category chart, scored table |
| `tests/test_quant_report.py` | Unit tests for scoring engine |
| `tests/test_fetch_historical.py` | Unit tests for historical data fetcher |
| `tests/test_train_model.py` | Light tests for training pipeline (split, AUC gate) |
| `.github/workflows/weekly-quant-report.yml` | Sunday 20:00 UTC cron |

### Modified files
| Path | Change |
|---|---|
| `backend/adapters/polytraders_export.py` | Expand to OVERALL(50) + CRYPTO(25) + POLITICS(25), deduplicate |
| `backend/requirements.txt` | Add xgboost==2.1.*, scikit-learn, numpy (XGBoost pkl files are version-sensitive — pin the version to match the training environment) |
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

**Feature engineering — 8 training features (canonical order):**
```python
FEATURE_NAMES = [
    "yes_price",          # raw crowd probability
    "info_ratio",         # volume_24h / sqrt(days_left + 1) / 10_000
    "log_volume_total",   # log1p(volume_total)
    "log_liquidity",      # log1p(liquidity)
    "days_left",          # time to resolution (clamped to >= 0.5 at inference)
    "is_longshot",        # int(yes_price < 0.20)
    "is_favorite",        # int(yes_price > 0.80)
    "price_extremity",    # abs(yes_price - 0.5) * 2  (0=uncertain, 1=decided)
]

# info_ratio formula — identical in training AND inference:
# info_ratio = volume_24h / sqrt(days_left + 1) / 10_000
# The +1 is applied to the RAW days_left before clamping,
# so training (days_left=0 → sqrt(1)) and inference agree.
```

`FEATURE_NAMES` is the single source of truth for column order. All data frames and inference arrays must be constructed from this list explicitly — never from dict insertion order.

> **Note on `calibrated_prob`:** Platt scaling (a/b) is fit on the model's *output* probabilities against the validation set labels *after* training. It is **not** a training input feature. The `calibratedProb` field in the inference output is computed post-prediction using these params as an output annotation, not as a model input.

**What the model predicts:** `quantScore` is the model's confidence that the crowd is wrong (mispricing confidence), not the probability that YES resolves. `calibratedProb` is Platt-scaled `quantScore` — also a mispricing confidence, not an outcome probability. The UI and Telegram message should label it "mispricing confidence" or "signal strength", not "win probability."

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

**Platt scaling fit (after training):**
After the model passes the AUC gate, fit logistic regression on the validation set:
```python
from sklearn.linear_model import LogisticRegression
platt = LogisticRegression()
platt.fit(model.predict_proba(X_val)[:, 1].reshape(-1, 1), y_val)
platt_a = float(platt.intercept_[0])
platt_b = float(platt.coef_[0][0])
```
`platt_a` and `platt_b` are saved in `calibration_params.json`.

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
               log_liquidity     0.12
               days_left         0.09
               is_longshot       0.04
               ...
[train_model] Platt scaling fit on validation set: a=-0.12, b=0.94
[train_model] Model saved → models/xgboost_model.pkl
[train_model] Calibration saved → models/calibration_params.json
[train_model] Metrics saved → models/training_metrics.json
```

**`calibration_params.json` schema:**
```json
{
  "platt_a": -0.12,
  "platt_b": 0.94,
  "feature_names": [
    "yes_price", "info_ratio", "log_volume_total", "log_liquidity",
    "days_left", "is_longshot", "is_favorite", "price_extremity"
  ]
}
```

- `platt_a` / `platt_b`: Platt scaling intercept and coefficient, fit on validation set outputs.
- `feature_names`: Canonical ordered list used during training. Inference must construct numpy arrays using this exact order.

**`training_metrics.json` schema:**
```json
{
  "modelVersion": "2026-03-30",
  "trainedAt": "2026-03-30T14:22:00Z",
  "nSamples": 11420,
  "cvAuc": 0.634,
  "cvAucStd": 0.018,
  "valAuc": 0.641,
  "testAuc": 0.628,
  "aucGatePassed": true,
  "featureImportance": {
    "info_ratio": 0.31,
    "yes_price": 0.24,
    "log_liquidity": 0.12,
    "days_left": 0.09,
    "is_longshot": 0.04,
    "log_volume_total": 0.04,
    "is_favorite": 0.03,
    "price_extremity": 0.13
  }
}
```

- `modelVersion`: Date string (YYYY-MM-DD) of the training run. Read by `quant_report.py` and written into the output JSON.
- `testAuc` and `modelVersion` are the two fields consumed by inference.

---

## Sub-system 2c: Weekly inference (`quant_report.py`)

Runs in GitHub Actions every Sunday. Invoked as:
```
python backend/adapters/quant_report.py
```
All paths are relative to repo root. Hardcoded constants (no CLI flags needed for weekly cron):
```python
POLYTRADERS_PATH = "reports/polytraders.json"
POLY2_PATH       = "reports/poly2.json"
MODEL_PATH       = "models/xgboost_model.pkl"
CALIBRATION_PATH = "models/calibration_params.json"
METRICS_PATH     = "models/training_metrics.json"
OUTPUT_PATH      = "reports/quant_report.json"
```

Both `reports/polytraders.json` and `reports/poly2.json` are kept fresh by the existing `refresh-reports.yml` daily cron. The quant report reads the most recently committed versions. Also reads `modelVersion` and `testAuc` from `models/training_metrics.json`, and computes `categoryTrends` from all poly2 categories (independent of which opportunities are scored).

**Actual field schemas (confirmed from live files):**

`polytraders.json` opportunity fields: `slug`, `title`, `curPrice`, `kellyBet`, `nSmartTraders`, `totalExposure`, `url`, etc.
`poly2.json` markets (nested under `categories.<name>.markets`): `slug`, `yes_price`, `volume_24h`, `volume_total`, `liquidity`, `days_left`.

**Merge strategy:** `quant_report.py` builds a lookup `poly2_by_slug: dict[str, dict]` from all poly2 markets across all categories. For each polytraders opportunity, look up its `slug` in `poly2_by_slug` to get volume and liquidity data. If a slug has no poly2 match, the opportunity is still scored but with `volume_24h=0`, `volume_total=0`, `liquidity=0`, `days_left=14` (all optional fields).

**Field mapping:**
- `curPrice` → from `polytraders.json` opportunity (required, skip with warning if absent)
- `volume_24h` → from poly2 match (optional, default `0`)
- `volumeTotal` → `volume_total` from poly2 (note: poly2 uses `volume_total`, not `volumeTotal`)
- `liquidity` → from poly2 match (optional, default `0`)
- `days_left` → from poly2 match (optional, default `14`)
- `kellyBet` → from `polytraders.json` opportunity (pass-through, `null` if absent)

**Missing required fields:** If `curPrice` is absent from a polytraders opportunity, skip it and log a warning. The iterator (not `score_opportunity`) handles the skip:
```python
for opp in polytraders["opportunities"]:
    if "curPrice" not in opp:
        logging.warning("Skipping opportunity missing curPrice: %s", opp.get("slug"))
        continue
    poly2_data = poly2_by_slug.get(opp["slug"], {})
    enriched = {**opp, **poly2_data, "volumeTotal": poly2_data.get("volume_total", 0)}
    scored.append(score_opportunity(enriched, model, calibration))
```

**Scoring per opportunity:**
```python
def score_opportunity(opp: dict, model, calibration: dict) -> dict:
    p = opp["curPrice"]
    vol = opp.get("volume_24h") or 0
    days_raw = opp.get("days_left") or 0  # raw for info_ratio formula
    days_feat = max(days_raw, 0.5)         # clamped for days_left feature only

    # info_ratio uses days_raw + 1 to match the training formula exactly
    feature_values = {
        "yes_price": p,
        "info_ratio": vol / ((days_raw + 1) ** 0.5) / 10_000,
        "log_volume_total": log1p(opp.get("volumeTotal") or 0),
        "log_liquidity": log1p(opp.get("liquidity") or 0),
        "days_left": days_feat,
        "is_longshot": int(p < 0.20),
        "is_favorite": int(p > 0.80),
        "price_extremity": abs(p - 0.5) * 2,
    }

    # Build array using calibration's canonical feature order — never dict insertion order
    feature_names = calibration["feature_names"]
    X = np.array([[feature_values[f] for f in feature_names]])

    raw_score = float(model.predict_proba(X)[0][1])
    calibrated = calibrate(raw_score, calibration)  # Platt scaling on model output
    tier = "A" if raw_score >= 0.65 else "B" if raw_score >= 0.40 else "C"

    return {**opp, "quantScore": raw_score, "signalTier": tier,
            "calibratedProb": round(calibrated, 3),
            "infoRatio": round(feature_values["info_ratio"], 3)}
```

**`categoryTrends` computation (from poly2.json, all categories):**
```python
def build_category_trends(poly2: dict) -> dict:
    """Summarise poly2 categories — crowd probability pulse, independent of scored opps."""
    trends = {}
    for cat_name, cat_data in poly2.get("categories", {}).items():
        markets = cat_data.get("markets", [])
        if not markets:
            continue
        avg_prob = sum(m["yes_price"] for m in markets) / len(markets)
        top = max(markets, key=lambda m: m.get("volume_24h", 0))
        trends[cat_name] = {
            "totalMarkets": len(markets),
            "avgCrowdProb": round(avg_prob, 3),
            "topMarket": {
                "question": top["question"],
                "yes_price": top["yes_price"],
                "volume_24h": top.get("volume_24h", 0),
                "url": top["url"],
            },
        }
    return trends
```

This runs regardless of whether any polytraders opportunities matched — it gives the full macro/politics pulse even if smart-money coverage is thin in a category.

**Category edge ranking (`edgeRanking`) computation:**

Each category in `categoryReport` (scored opportunities only) gets an `edgeScore`:

```python
def compute_edge_score(cat: dict, trend: dict) -> float:
    """
    Edge score = weighted combination of three signals:
      1. avg model signal (0.5 weight)  — how much mispricing the model detects
      2. crowd uncertainty (0.3 weight) — how far avg crowd prob is from 0.5 (inverted)
                                          closer to 0.5 = more uncertain = more edge potential
      3. Tier A density (0.2 weight)    — tierACount / count (fraction of top signals)
    """
    model_signal   = cat["avgQuantScore"]                       # 0–1
    crowd_prob     = trend.get("avgCrowdProb", 0.5) if trend else 0.5
    uncertainty    = 1.0 - abs(crowd_prob - 0.5) * 2           # 0=decided, 1=max uncertain
    tier_a_density = cat["tierACount"] / max(cat["count"], 1)  # 0–1

    return round(0.5 * model_signal + 0.3 * uncertainty + 0.2 * tier_a_density, 3)
```

`edgeRanking` is an ordered list of categories sorted by `edgeScore` descending:
```json
"edgeRanking": [
  {"category": "crypto",      "edgeScore": 0.71, "label": "Strong edge",   "avgQuantScore": 0.74, "avgCrowdProb": 0.61, "tierACount": 2},
  {"category": "macro",       "edgeScore": 0.62, "label": "Good edge",     "avgQuantScore": 0.61, "avgCrowdProb": 0.38, "tierACount": 1},
  {"category": "politics",    "edgeScore": 0.55, "label": "Moderate edge", "avgQuantScore": 0.51, "avgCrowdProb": 0.52, "tierACount": 1},
  {"category": "geopolitics", "edgeScore": 0.41, "label": "Weak edge",     "avgQuantScore": 0.44, "avgCrowdProb": 0.41, "tierACount": 0},
  {"category": "sports",      "edgeScore": 0.34, "label": "Skip",          "avgQuantScore": 0.38, "avgCrowdProb": 0.55, "tierACount": 0}
]
```

Label thresholds: `edgeScore >= 0.65` → "Strong edge", `>= 0.50` → "Good edge", `>= 0.40` → "Moderate edge", `>= 0.30` → "Weak edge", `< 0.30` → "Skip".

**Insights generation (rule-based, no LLM):**

`insights` is a list of up to 5 plain-English strings derived deterministically from the data:

```python
def generate_insights(edge_ranking, category_report, category_trends, opportunities) -> list[str]:
    insights = []

    # 1. Top edge category
    top = edge_ranking[0]
    insights.append(
        f"{top['category'].title()} offers the strongest edge this week "
        f"(model signal {top['avgQuantScore']:.0%}, crowd at {top['avgCrowdProb']:.0%})."
    )

    # 2. Tier A spotlight (best single opportunity)
    tier_a = [o for o in opportunities if o["signalTier"] == "A"]
    if tier_a:
        best = tier_a[0]  # already sorted by quantScore desc
        insights.append(
            f"Top opportunity: '{best['title']}' — model signal {best['quantScore']:.2f}, "
            f"crowd at {best['curPrice']:.0%}, adj. prob {best['calibratedProb']:.0%}."
        )

    # 3. Largest crowd-model divergence
    divergent = max(
        edge_ranking,
        key=lambda r: abs(r["avgQuantScore"] - r["avgCrowdProb"])
    )
    delta = divergent["avgQuantScore"] - divergent["avgCrowdProb"]
    direction = "underpriced" if delta > 0 else "overpriced"
    insights.append(
        f"{divergent['category'].title()} shows the largest crowd-model gap "
        f"({abs(delta):.0%} {direction} by crowd)."
    )

    # 4. Skip recommendation
    skip = [r for r in edge_ranking if r["label"] == "Skip"]
    if skip:
        names = ", ".join(r["category"] for r in skip)
        insights.append(f"Low signal this week: {names} — skip unless you have domain edge.")

    # 5. Market uncertainty note
    most_uncertain = min(category_trends.items(), key=lambda kv: abs(kv[1]["avgCrowdProb"] - 0.5))
    cat, data = most_uncertain
    insights.append(
        f"{cat.title()} is the most uncertain category (crowd avg {data['avgCrowdProb']:.0%}) "
        f"— high uncertainty can mean opportunity or noise."
    )

    return insights
```

Sample output:
```json
"insights": [
  "Crypto offers the strongest edge this week (model signal 74%, crowd at 61%).",
  "Top opportunity: 'Will BTC hit $90K by April?' — model signal 0.84, crowd at 62%, adj. prob 68%.",
  "Macro shows the largest crowd-model gap (23% underpriced by crowd).",
  "Low signal this week: sports — skip unless you have domain edge.",
  "Macro is the most uncertain category (crowd avg 38%) — high uncertainty can mean opportunity or noise."
]
```

The `calibrate(p, calibration)` function applies Platt scaling to the model's output probability.
`platt_b` is the coefficient of the raw model score, `platt_a` is the intercept (matching sklearn's `LogisticRegression` convention from training):
```python
def calibrate(p: float, calibration: dict) -> float:
    """Apply Platt scaling: sigmoid(platt_b * p + platt_a)."""
    from math import exp
    raw = calibration["platt_b"] * p + calibration["platt_a"]
    return 1 / (1 + exp(-raw))
```

**Output** (`reports/quant_report.json`):
```json
{
  "generatedAt": "2026-03-30T20:00:00Z",
  "weekOf": "2026-03-30",
  "modelVersion": "2026-03-30",
  "modelAuc": 0.628,
  "summary": {
    "totalScored": 32,
    "tierA": 4,
    "tierB": 11,
    "tierC": 17,
    "topSignalCategory": "crypto",
    "topCategoryAvgScore": 0.74,
    "mostUncertainCategory": "macro",
    "mostUncertainAvgPrice": 0.38
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
      "url": "https://polymarket.com/event/btc-90k",
      "category": "crypto"
    }
  ],
  "categoryReport": {
    "crypto":      {"count": 8,  "avgQuantScore": 0.74, "tierACount": 2},
    "politics":    {"count": 12, "avgQuantScore": 0.51, "tierACount": 1},
    "sports":      {"count": 6,  "avgQuantScore": 0.38, "tierACount": 0},
    "macro":       {"count": 6,  "avgQuantScore": 0.61, "tierACount": 1},
    "geopolitics": {"count": 4,  "avgQuantScore": 0.44, "tierACount": 0}
  },
  "edgeRanking": [
    {"category": "crypto",   "edgeScore": 0.71, "label": "Strong edge",   "avgQuantScore": 0.74, "avgCrowdProb": 0.61, "tierACount": 2},
    {"category": "macro",    "edgeScore": 0.62, "label": "Good edge",     "avgQuantScore": 0.61, "avgCrowdProb": 0.38, "tierACount": 1},
    {"category": "politics", "edgeScore": 0.55, "label": "Moderate edge", "avgQuantScore": 0.51, "avgCrowdProb": 0.52, "tierACount": 1},
    {"category": "sports",   "edgeScore": 0.34, "label": "Skip",          "avgQuantScore": 0.38, "avgCrowdProb": 0.55, "tierACount": 0}
  ],
  "insights": [
    "Crypto offers the strongest edge this week (model signal 74%, crowd at 61%).",
    "Top opportunity: 'Will BTC hit $90K by April?' — model signal 0.84, crowd at 62%, adj. prob 68%.",
    "Macro shows the largest crowd-model gap (23% underpriced by crowd).",
    "Low signal this week: sports — skip unless you have domain edge.",
    "Macro is the most uncertain category (crowd avg 38%) — high uncertainty can mean opportunity or noise."
  ],
  "categoryTrends": {
    "macro": {
      "totalMarkets": 42,
      "avgCrowdProb": 0.38,
      "topMarket": {
        "question": "Will the Fed cut rates by 50bps in April?",
        "yes_price": 0.005,
        "volume_24h": 835103,
        "url": "https://polymarket.com/event/..."
      }
    },
    "politics": {
      "totalMarkets": 55,
      "avgCrowdProb": 0.52,
      "topMarket": { "question": "...", "yes_price": 0.71, "volume_24h": 240000, "url": "..." }
    },
    "geopolitics": {
      "totalMarkets": 28,
      "avgCrowdProb": 0.41,
      "topMarket": { "question": "...", "yes_price": 0.44, "volume_24h": 180000, "url": "..." }
    },
    "crypto":  { "totalMarkets": 31, "avgCrowdProb": 0.61, "topMarket": { "..." : "..." } },
    "stocks":  { "totalMarkets": 18, "avgCrowdProb": 0.55, "topMarket": { "..." : "..." } },
    "ai_tech": { "totalMarkets": 12, "avgCrowdProb": 0.48, "topMarket": { "..." : "..." } }
  }
}
```

---

## Sub-system 3: Telegram push (`quant_telegram.py`)

Sends after `quant_report.json` is committed to the repo. Uses same `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` env vars as the existing Kelly bot. Single message, ~30 lines of HTML.

**Message format:**
```
📊 <b>Weekly Quant Report</b> — Week of Mar 30

🌍 <b>Macro Pulse</b>
• Macro: avg crowd 38% · 42 markets · top: <a href="...">Fed cut 50bps?</a> (0.5%)
• Politics: avg crowd 52% · 55 markets · top: <a href="...">Trump approval?</a> (71%)
• Geopolitics: avg crowd 41% · 28 markets
• Crypto: avg crowd 61% · 31 markets

🏆 <b>Edge Ranking this week</b>
1. 🟢 Crypto — edge 0.71 (signal 74% vs crowd 61%) · 2 Tier A
2. 🟢 Macro — edge 0.62 (signal 61% vs crowd 38%) · 1 Tier A
3. 🟡 Politics — edge 0.55 · 1 Tier A
4. 🔴 Sports — Skip (signal 0.38)

🟢 <b>Tier A signals (4)</b>
• <a href="...">BTC hits $90K?</a> — signal 0.84 | crowd→adj: 62%→68% | info: 0.51
• <a href="...">Fed rate cut?</a> — signal 0.79 | crowd→adj: 38%→44% | info: 0.38

🟡 <b>Tier B highlights</b>
• <a href="...">ETH flippening?</a> — signal 0.55 | crowd: 22%

💡 <b>Conclusions</b>
• Crypto offers the strongest edge (model 74%, crowd 61%).
• Macro shows the largest crowd-model gap (23% underpriced by crowd).
• Skip sports unless you have domain edge.

32 markets scored · Model AUC 0.63 · Not financial advice
```

Uses stdlib `urllib.request` — no extra dependencies. Tier B entries capped at top 3. Insights capped at top 3. Total message stays under Telegram's 4096-char limit.

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

Five sections, no shared components with Alpha tab. All charts use existing Recharts dependency.

### Section 1: Summary strip
Four stat pills in a row: `Week of`, `Markets scored`, `Tier A signals`, `Model AUC`. Tiny and non-intrusive.

### Section 2: Macro & Politics Pulse (category crowd probability chart — option B)
Horizontal bar chart, one bar per poly2 category (`macro`, `politics`, `geopolitics`, `crypto`, `stocks`, `ai_tech`). Bar length = `avgCrowdProb` (0–100%). Each bar shows the category name, market count, and the top market question as a tooltip. Colour scale: blue=cold/uncertain (near 50%), amber=leaning, green=strong consensus.

This answers: "What does the crowd collectively believe across themes this week?"

### Section 3: Model Signal vs Crowd Scatter (option C)
Scatter plot. Each dot is one scored opportunity:
- X axis: `curPrice` (crowd probability, 0–1)
- Y axis: `quantScore` (model mispricing signal, 0–1)
- Dot colour: tier A=green, B=amber, C=dim
- Hover tooltip: market title + signal tier + adj. prob

Reference diagonal line (y = x) drawn in dim colour — dots above the line are where the model sees more signal than the crowd price suggests. This is the key insight view.

### Section 4: Category signal comparison (dual-bar)
Side-by-side grouped bars per category: one bar for `avgCrowdProb` (crowd), one for `avgQuantScore` (model signal). Shows where the model diverges from consensus.

Only shown for categories that have at least one scored opportunity (i.e., categories in `categoryReport`, not all of `categoryTrends`).

### Section 5: Edge Ranking + Insights
Two sub-sections side by side (on desktop, stacked on mobile):

**Left — Edge Ranking table:**
| Rank | Category | Edge Score | Label badge | Model Signal | Crowd Prob | Tier A |
Sorted by `edgeScore` descending. Label badge colours: "Strong edge"=green, "Good edge"=teal, "Moderate edge"=amber, "Weak edge"=dim, "Skip"=red. This is the direct answer to "where should I focus my capital this week?"

**Right — Insights panel:**
Numbered list of the 5 auto-generated insight strings from `insights[]`. Plain text, no formatting. Small header: "Weekly Conclusions".

### Section 6: Opportunities table
Columns: Tier badge, Market title (linked), Signal Score, Adj. Prob, Crowd Prob, Info Ratio, Kelly Bet. Default sort: Signal Score descending. Top 20 rows shown. `kellyBet` shows "—" if null.

Signal tier badge colours: A = `T.green`, B = `T.amber`, C = `T.dim`. Matches existing design tokens.

Column label clarification: `calibratedProb` is displayed as "Adj. Prob" (mispricing confidence), `curPrice` as "Crowd Prob". The scatter plot tooltip clarifies these meanings on hover.

---

## Sub-system 6: GitHub Actions cron

New file `.github/workflows/weekly-quant-report.yml`:
```yaml
name: Weekly Quant Report

on:
  schedule:
    - cron: "0 20 * * 0"   # Sunday 20:00 UTC
  workflow_dispatch:

permissions:
  contents: write

jobs:
  quant-report:
    name: Generate and push quant report
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r backend/requirements.txt

      - name: Run quant_report (inference)
        run: python backend/adapters/quant_report.py
        continue-on-error: false   # hard fail — no partial reports
        env:
          POLYTRADERS_BANKROLL: "100"

      - name: Commit and push quant report
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git pull --rebase origin master
          git add -f reports/quant_report.json
          git diff --cached --quiet && echo "No changes" || \
            git commit -m "chore: weekly quant report $(date -u +'%Y-%m-%d')"
          git push origin master

      - name: Send Telegram summary
        run: python backend/adapters/quant_telegram.py
        continue-on-error: true    # Telegram down is non-critical after report is committed
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

Note: commit-and-push runs before Telegram so the notification is only sent after the report is durably stored.

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
- `test_calibrate_midpoint` — calibrate(0.5) ≈ 0.5 (calibration shouldn't move midpoint when a≈0, b≈1)
- `test_generate_report_empty_input` — empty opportunities list → valid JSON with zeroed summary
- `test_category_report_aggregation` — verify avgQuantScore math per category
- `test_feature_order_matches_calibration` — `score_opportunity` uses `calibration["feature_names"]` order, not dict insertion order
- `test_info_ratio_days_zero` — days_left=0 → info_ratio uses sqrt(0+1)=1 denominator (no divide-by-zero)
- `test_kelly_bet_passthrough_nullable` — opportunity with no `kellyBet` → output has `"kellyBet": null`
- `test_skip_opportunity_missing_cur_price` — opportunity without `curPrice` is skipped with a warning, not raised; remaining opportunities are still scored
- `test_poly2_slug_merge` — poly2 enrichment lookup by slug; unmatched slug → volume/liquidity defaults to 0
- `test_build_category_trends_structure` — verify `avgCrowdProb` is correctly averaged and `topMarket` is the highest-volume market
- `test_build_category_trends_empty_category` — category with no markets → omitted from output (not keyed with nulls)
- `test_category_trends_independent_of_scored_opps` — `categoryTrends` includes all poly2 categories even when no polytraders opportunities exist
- `test_compute_edge_score_formula` — known inputs produce expected weighted score (0.5×signal + 0.3×uncertainty + 0.2×tier_a_density)
- `test_edge_ranking_sorted_descending` — `edgeRanking` list is sorted by `edgeScore` high→low
- `test_edge_label_thresholds` — scores at 0.65, 0.50, 0.40, 0.30, 0.20 map to correct labels
- `test_generate_insights_count` — always returns between 1 and 5 strings, even with minimal input
- `test_insights_top_category_mentioned` — first insight always names the top-ranked edge category
- `test_telegram_message_length` — Telegram message is always < 4096 chars even with maximum data

### `test_train_model.py` (light)
- `test_feature_matrix_shape` — N rows × 8 columns (matching `FEATURE_NAMES`)
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
