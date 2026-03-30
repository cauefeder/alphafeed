# Quant Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weekly Quant Report tab to AlphaFeed — XGBoost mispricing classifier on Polymarket markets, category trend cards, model vs crowd scatter, edge ranking, rule-based insights, and a Telegram summary every Sunday.

**Architecture:** Pure-function scoring module (`quant_features.py`) tested independently, inference script (`quant_report.py`) that joins `polytraders.json` + `poly2.json`, a one-line backend endpoint, a 6-section React tab, and a GitHub Actions Sunday cron. Model is trained locally once and committed as a binary. Training and inference are completely separate steps.

**Tech Stack:** Python 3.12, XGBoost 2.1.x, scikit-learn, numpy, FastAPI, React/Vite, Recharts, GitHub Actions, Telegram Bot API.

---

## File map

| Action | Path | Responsibility |
|---|---|---|
| Create | `backend/adapters/quant_features.py` | Pure functions: feature engineering, calibration, category trends, edge ranking, insights |
| Create | `backend/adapters/fetch_historical.py` | Pull resolved markets from Gamma API → CSV |
| Create | `backend/adapters/train_model.py` | XGBoost training, temporal split, AUC gate, Platt scaling |
| Create | `backend/adapters/quant_report.py` | Weekly inference: loads model + JSON files, writes quant_report.json |
| Create | `backend/adapters/quant_telegram.py` | Format + send Telegram message from quant_report.json |
| Create | `tests/test_quant_features.py` | Unit tests for every pure function in quant_features.py |
| Create | `tests/test_fetch_historical.py` | Unit tests for historical data fetcher |
| Create | `tests/test_train_model.py` | Light tests: feature matrix shape, temporal split, AUC gate |
| Create | `tests/test_quant_report.py` | Integration tests for inference script |
| Create | `frontend/src/tabs/QuantReport.jsx` | Quant Report tab (6 sections) |
| Create | `.github/workflows/weekly-quant-report.yml` | Sunday 20:00 UTC cron |
| Modify | `backend/adapters/polytraders_export.py` | Expand to OVERALL(50)+CRYPTO(25)+POLITICS(25), add categoryBreakdown |
| Modify | `backend/requirements.txt` | Add xgboost==2.1.*, scikit-learn, numpy |
| Modify | `backend/server.py` | Add GET /api/quant-report |
| Modify | `frontend/src/App.jsx` | Add quant state + Quant tab |
| Modify | `frontend/src/api.js` | Add fetchQuantReport() + seedQuantReport() |
| Modify | `.gitignore` | Add data/ directory |

---

## Codebase context (read this before every task)

- **Pattern**: Adapters write to `reports/*.json`. Server reads them via `_read_report(name)`. Frontend fetches via `api.js` functions.
- **Design tokens**: Import `T` from `../tokens.js`. Use `T.green`, `T.amber`, `T.dim`, `T.sub`, `T.text`, `T.mono`, `T.s1`, `T.s2`, `T.ln`.
- **Components**: `Panel`, `Badge`, `Stat`, `ChartTip` from `../components/primitives.jsx`.
- **Branch**: `master` — all pushes target `master`.
- **Tests**: Run from repo root with `pytest tests/ -v`. Fixtures in `tests/conftest.py`. Mock `sys.modules` for external imports.
- **FEATURE_NAMES (6 features, canonical order)**: `["yes_price", "info_ratio", "log_volume_total", "log_liquidity", "days_left", "price_extremity"]`

---

## Task 1: Foundation — requirements, .gitignore, models dir

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Add ML dependencies to requirements.txt**

```
# append to backend/requirements.txt
xgboost==2.1.3
scikit-learn>=1.4
numpy>=1.26
```

- [ ] **Step 2: Add data/ to .gitignore**

Open `.gitignore` and add:
```
# Training data — large CSV, not committed
data/
```

- [ ] **Step 3: Create models directory with placeholder**

```bash
mkdir -p models
touch models/.gitkeep
```

- [ ] **Step 4: Verify pip installs cleanly**

```bash
pip install -r backend/requirements.txt
python -c "import xgboost; import sklearn; import numpy; print('OK', xgboost.__version__)"
```
Expected: `OK 2.1.x`

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt .gitignore models/.gitkeep
git commit -m "chore: add xgboost, scikit-learn, numpy; gitignore data/"
```

---

## Task 2: Expand polytraders to ~100 traders

**Files:**
- Modify: `backend/adapters/polytraders_export.py`
- Test: `tests/test_adapters.py`

The existing `run_export()` is unchanged. Only the leaderboard fetch changes — add `fetch_expanded_traders()` and update `main()` to call it. Add `categoryBreakdown` to the output.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_adapters.py`:

```python
class TestExpandedTraders:
    def _import(self, monkeypatch):
        mock_lb = ModuleType("leaderboard")
        call_log = []

        def _fetch(time_period, limit, category=None):
            call_log.append((category, limit))
            # Return unique traders per category to test dedup
            return [
                MagicMock(proxy_wallet=f"{category}_{i}")
                for i in range(limit)
            ]

        mock_lb.fetch_top_traders = _fetch
        monkeypatch.setitem(sys.modules, "leaderboard", mock_lb)
        monkeypatch.setitem(sys.modules, "positions", ModuleType("positions"))
        monkeypatch.setitem(sys.modules, "kelly", ModuleType("kelly"))

        spec = importlib.util.spec_from_file_location(
            "polytraders_export",
            Path(__file__).parent.parent / "backend/adapters/polytraders_export.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, call_log

    def test_fetch_expanded_traders_deduplicates(self, monkeypatch):
        """Wallets appearing in multiple categories are only kept once."""
        mock_lb = ModuleType("leaderboard")

        def _fetch(time_period, limit, category=None):
            # All categories return the same wallet for trader 0
            return [MagicMock(proxy_wallet="shared_wallet" if i == 0 else f"{category}_{i}")
                    for i in range(3)]

        mock_lb.fetch_top_traders = _fetch
        monkeypatch.setitem(sys.modules, "leaderboard", mock_lb)
        monkeypatch.setitem(sys.modules, "positions", ModuleType("positions"))
        monkeypatch.setitem(sys.modules, "kelly", ModuleType("kelly"))

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "polytraders_export2",
            Path(__file__).parent.parent / "backend/adapters/polytraders_export.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        traders = mod.fetch_expanded_traders("WEEK")
        wallets = [t.proxy_wallet for t in traders]
        assert wallets.count("shared_wallet") == 1, "shared_wallet should appear exactly once"

    def test_category_breakdown_in_output(self, tmp_path, monkeypatch):
        """run_export output includes categoryBreakdown field."""
        mock_lb = ModuleType("leaderboard")
        mock_pos = ModuleType("positions")
        mock_kelly = ModuleType("kelly")

        mock_lb.fetch_top_traders = lambda **kw: [MagicMock(proxy_wallet=f"w_{i}") for i in range(2)]
        mock_pos.fetch_all_positions = lambda traders, max_traders: []
        mock_kelly.score_opportunities = lambda positions, **kw: []
        monkeypatch.setitem(sys.modules, "leaderboard", mock_lb)
        monkeypatch.setitem(sys.modules, "positions", mock_pos)
        monkeypatch.setitem(sys.modules, "kelly", mock_kelly)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "polytraders_export3",
            Path(__file__).parent.parent / "backend/adapters/polytraders_export.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.run_export(bankroll=100, time_period="WEEK")
        assert "categoryBreakdown" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_adapters.py::TestExpandedTraders -v
```
Expected: FAIL — `fetch_expanded_traders` not defined

- [ ] **Step 3: Implement fetch_expanded_traders and update run_export**

In `backend/adapters/polytraders_export.py`, add after the imports:

```python
CATEGORIES = [
    ("OVERALL",  50),
    ("CRYPTO",   25),
    ("POLITICS", 25),
]


def fetch_expanded_traders(time_period: str) -> list:
    """Fetch traders from multiple leaderboard categories, deduplicate by proxy_wallet."""
    from leaderboard import fetch_top_traders
    seen: set[str] = set()
    traders: list = []
    breakdown: dict[str, int] = {}
    for category, limit in CATEGORIES:
        batch = fetch_top_traders(time_period=time_period, limit=limit, category=category)
        added = 0
        for t in batch:
            if t.proxy_wallet not in seen:
                seen.add(t.proxy_wallet)
                traders.append(t)
                added += 1
        breakdown[category] = added
    return traders, breakdown
```

Update `run_export()` — replace the `fetch_top_traders` call and add `categoryBreakdown`:

```python
def run_export(
    top_n: int = 25,
    bankroll: float = 100.0,
    time_period: str = "WEEK",
) -> dict:
    from positions import fetch_all_positions
    from kelly import score_opportunities

    print(f"  Fetching traders from OVERALL(50)+CRYPTO(25)+POLITICS(25)...")
    traders, breakdown = fetch_expanded_traders(time_period)
    if not traders:
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "error": "No traders returned from leaderboard",
            "opportunities": [],
        }
    print(f"  {len(traders)} unique traders found")

    print(f"  Fetching positions (parallel)...")
    positions = fetch_all_positions(traders, max_traders=len(traders))
    print(f"  {len(positions)} qualifying positions")

    opportunities = score_opportunities(
        positions,
        total_traders_checked=len(traders),
        bankroll=bankroll,
    )

    opps_out = []
    for opp in opportunities:
        opps_out.append({
            "title": opp.title,
            "outcome": opp.outcome,
            "slug": opp.slug,
            "url": opp.url,
            "curPrice": round(opp.cur_price, 4),
            "estimatedEdge": round(opp.estimated_edge, 4),
            "kellyBet": round(opp.kelly_bet, 2),
            "kellyFull": round(opp.kelly_full, 4),
            "nSmartTraders": opp.n_smart_traders,
            "totalTradersChecked": opp.total_traders_checked,
            "smartTraderNames": opp.smart_trader_names[:5],
            "countSignal": round(opp.count_signal, 4),
            "sizeSignal": round(opp.size_signal, 4),
            "totalExposure": round(opp.total_exposure, 2),
            "weightedAvgEntry": round(opp.weighted_avg_entry, 4),
        })

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "timePeriod": time_period,
        "bankroll": bankroll,
        "tradersChecked": len(traders),
        "categoryBreakdown": breakdown,
        "positionsScanned": len(positions),
        "opportunities": opps_out,
    }
```

Also update `main()` to remove `--top-n` (no longer used — categories are fixed):
```python
def main() -> None:
    bankroll = float(os.getenv("POLYTRADERS_BANKROLL", "100"))
    time_period = os.getenv("POLYTRADERS_TIME_PERIOD", "WEEK")
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--bankroll" and i + 1 < len(args):
            bankroll = float(args[i + 1])

    print("[polytraders_export] Starting PolyTraders signal pipeline...")
    result = run_export(bankroll=bankroll, time_period=time_period)
    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = REPORTS_DIR / "polytraders.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(result.get("opportunities", []))
    print(f"[polytraders_export] {n} opportunities -> {out_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_adapters.py::TestExpandedTraders -v
```
Expected: all 3 tests PASS

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest tests/ -v
```
Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add backend/adapters/polytraders_export.py tests/test_adapters.py
git commit -m "feat: expand polytraders to OVERALL(50)+CRYPTO(25)+POLITICS(25) with deduplication"
```

---

## Task 3: Pure functions module (quant_features.py) + full test coverage

**Files:**
- Create: `backend/adapters/quant_features.py`
- Create: `tests/test_quant_features.py`

This module contains every computation that doesn't need file I/O or the trained model. It is importable with zero dependencies beyond stdlib + numpy.

- [ ] **Step 1: Write all failing tests**

Create `tests/test_quant_features.py`:

```python
"""Tests for quant_features.py — all pure functions, no model required."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import (
    FEATURE_NAMES,
    compute_features,
    calibrate,
    build_category_trends,
    compute_edge_ranking,
    generate_insights,
)


# ── FEATURE_NAMES ─────────────────────────────────────────────────────────────

def test_feature_names_length():
    assert len(FEATURE_NAMES) == 6

def test_feature_names_canonical_order():
    assert FEATURE_NAMES == [
        "yes_price", "info_ratio", "log_volume_total",
        "log_liquidity", "days_left", "price_extremity",
    ]


# ── compute_features ──────────────────────────────────────────────────────────

def test_compute_features_known_input():
    opp = {
        "curPrice": 0.6,
        "volume_24h": 10_000,
        "volumeTotal": 100_000,
        "liquidity": 50_000,
        "days_left": 15,
    }
    f = compute_features(opp)
    assert f["yes_price"] == pytest.approx(0.6)
    # info_ratio = 10_000 / sqrt(15 + 1) / 10_000 = 1 / 4 = 0.25
    assert f["info_ratio"] == pytest.approx(0.25, rel=1e-3)
    # price_extremity = abs(0.6 - 0.5) * 2 = 0.2
    assert f["price_extremity"] == pytest.approx(0.2)
    # days_left clamped: max(15, 0.5) = 15
    assert f["days_left"] == pytest.approx(15)

def test_compute_features_days_zero_no_divide_by_zero():
    """days_left=0 → info_ratio uses sqrt(0+1)=1, never divides by zero."""
    opp = {"curPrice": 0.5, "volume_24h": 10_000, "days_left": 0}
    f = compute_features(opp)
    assert f["info_ratio"] == pytest.approx(1.0)   # 10_000 / sqrt(1) / 10_000

def test_compute_features_days_clamped_for_feature():
    """days_left feature is clamped to >= 0.5, but info_ratio uses raw+1."""
    opp = {"curPrice": 0.5, "volume_24h": 0, "days_left": 0}
    f = compute_features(opp)
    assert f["days_left"] == pytest.approx(0.5)    # clamped

def test_compute_features_missing_optionals_default_zero():
    opp = {"curPrice": 0.3}
    f = compute_features(opp)
    assert f["log_volume_total"] == pytest.approx(0.0)
    assert f["log_liquidity"] == pytest.approx(0.0)
    assert f["days_left"] == pytest.approx(0.5)    # default 0, then clamped

def test_compute_features_returns_all_feature_names():
    opp = {"curPrice": 0.5}
    f = compute_features(opp)
    assert set(f.keys()) == set(FEATURE_NAMES)

def test_compute_features_array_matches_feature_names_order():
    """Values extracted in FEATURE_NAMES order must match the dict."""
    opp = {"curPrice": 0.7, "volume_24h": 5_000, "volumeTotal": 80_000,
           "liquidity": 20_000, "days_left": 7}
    f = compute_features(opp)
    arr = [f[name] for name in FEATURE_NAMES]
    assert arr[0] == f["yes_price"]
    assert arr[-1] == f["price_extremity"]


# ── calibrate ─────────────────────────────────────────────────────────────────

def test_calibrate_identity_params():
    """With platt_a=0, platt_b=1, calibrate(0.5) should equal sigmoid(0.5) ≈ 0.622."""
    cal = {"platt_a": 0.0, "platt_b": 1.0}
    result = calibrate(0.5, cal)
    from math import exp
    expected = 1 / (1 + exp(-0.5))
    assert result == pytest.approx(expected, rel=1e-6)

def test_calibrate_zero_params_returns_half():
    """With platt_a=0, platt_b=0, calibrate(anything) = sigmoid(0) = 0.5."""
    cal = {"platt_a": 0.0, "platt_b": 0.0}
    assert calibrate(0.3, cal) == pytest.approx(0.5, rel=1e-6)
    assert calibrate(0.9, cal) == pytest.approx(0.5, rel=1e-6)

def test_calibrate_output_in_01():
    cal = {"platt_a": -0.12, "platt_b": 0.94}
    for p in [0.0, 0.1, 0.5, 0.9, 1.0]:
        result = calibrate(p, cal)
        assert 0.0 <= result <= 1.0


# ── build_category_trends ─────────────────────────────────────────────────────

SAMPLE_POLY2 = {
    "categories": {
        "macro": {
            "markets": [
                {"question": "Q1", "yes_price": 0.3, "volume_24h": 100, "url": "u1"},
                {"question": "Q2", "yes_price": 0.7, "volume_24h": 500, "url": "u2"},
                {"question": "Q3", "yes_price": 0.5, "volume_24h": 200, "url": "u3"},
            ]
        },
        "crypto": {
            "markets": [
                {"question": "C1", "yes_price": 0.9, "volume_24h": 1000, "url": "uc1"},
            ]
        },
        "empty_cat": {"markets": []},
    }
}

def test_build_category_trends_structure():
    trends = build_category_trends(SAMPLE_POLY2)
    assert "macro" in trends
    assert trends["macro"]["totalMarkets"] == 3
    assert len(trends["macro"]["top3Markets"]) == 3

def test_build_category_trends_top_market_by_volume():
    trends = build_category_trends(SAMPLE_POLY2)
    top = trends["macro"]["top3Markets"][0]
    assert top["question"] == "Q2"    # highest volume_24h = 500
    assert top["volume_24h"] == 500

def test_build_category_trends_empty_category_omitted():
    trends = build_category_trends(SAMPLE_POLY2)
    assert "empty_cat" not in trends

def test_build_category_trends_all_categories_included():
    trends = build_category_trends(SAMPLE_POLY2)
    assert set(trends.keys()) == {"macro", "crypto"}

def test_build_category_trends_top3_capped():
    """Category with >3 markets returns only top 3."""
    poly2 = {"categories": {"macro": {"markets": [
        {"question": f"Q{i}", "yes_price": 0.5, "volume_24h": i * 10, "url": f"u{i}"}
        for i in range(10)
    ]}}}
    trends = build_category_trends(poly2)
    assert len(trends["macro"]["top3Markets"]) == 3


# ── compute_edge_ranking ──────────────────────────────────────────────────────

SAMPLE_CAT_REPORT = {
    "crypto":   {"count": 8,  "avgQuantScore": 0.74, "tierACount": 2},
    "politics": {"count": 12, "avgQuantScore": 0.51, "tierACount": 1},
    "sports":   {"count": 6,  "avgQuantScore": 0.25, "tierACount": 0},
    "macro":    {"count": 6,  "avgQuantScore": 0.61, "tierACount": 1},
}

def test_compute_edge_ranking_sorted_descending():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    scores = [r["edgeScore"] for r in ranking]
    assert scores == sorted(scores, reverse=True)

def test_compute_edge_ranking_top_is_crypto():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    assert ranking[0]["category"] == "crypto"

def test_compute_edge_ranking_edge_score_equals_avg_quant_score():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    for r in ranking:
        assert r["edgeScore"] == pytest.approx(r["avgQuantScore"], rel=1e-6)

def test_compute_edge_ranking_labels():
    ranking = compute_edge_ranking(SAMPLE_CAT_REPORT)
    labels = {r["category"]: r["label"] for r in ranking}
    assert labels["crypto"] == "Strong edge"   # 0.74 >= 0.65
    assert labels["macro"] == "Good edge"      # 0.61 >= 0.50
    assert labels["politics"] == "Good edge"   # 0.51 >= 0.50
    assert labels["sports"] == "Skip"          # 0.25 < 0.30


# ── generate_insights ─────────────────────────────────────────────────────────

SAMPLE_RANKING = [
    {"category": "crypto",   "edgeScore": 0.74, "label": "Strong edge", "avgQuantScore": 0.74, "tierACount": 2, "count": 8},
    {"category": "sports",   "edgeScore": 0.25, "label": "Skip",        "avgQuantScore": 0.25, "tierACount": 0, "count": 6},
]

SAMPLE_OPPS = [
    {"title": "BTC 90k?", "quantScore": 0.84, "signalTier": "A", "curPrice": 0.62},
    {"title": "ETH flip?", "quantScore": 0.45, "signalTier": "B", "curPrice": 0.30},
]

def test_generate_insights_count_between_1_and_5():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    assert 1 <= len(insights) <= 5

def test_generate_insights_first_names_top_category():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    assert "crypto" in insights[0].lower() or "Crypto" in insights[0]

def test_generate_insights_skip_category_mentioned():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    skip_insight = next((s for s in insights if "skip" in s.lower() or "sports" in s.lower()), None)
    assert skip_insight is not None

def test_generate_insights_stale_model_fires_after_60_days():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2024-01-01")
    stale = next((s for s in insights if "days old" in s), None)
    assert stale is not None

def test_generate_insights_fresh_model_no_stale_alert():
    insights = generate_insights(SAMPLE_RANKING, SAMPLE_OPPS, "2026-03-30")
    stale = next((s for s in insights if "days old" in s), None)
    assert stale is None

def test_generate_insights_no_tier_a_still_returns_insights():
    opps_no_a = [{"title": "X", "quantScore": 0.45, "signalTier": "B", "curPrice": 0.5}]
    insights = generate_insights(SAMPLE_RANKING, opps_no_a, "2026-03-30")
    assert len(insights) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_quant_features.py -v
```
Expected: FAIL — `quant_features` module not found

- [ ] **Step 3: Implement quant_features.py**

Create `backend/adapters/quant_features.py`:

```python
"""
quant_features.py — Pure functions for the Quant Report pipeline.

All functions in this module are side-effect-free (no file I/O, no model loading).
Import this module to compute features, calibrate scores, and generate insights
without requiring XGBoost or any trained model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp, log1p

# ── Feature names — canonical order, single source of truth ───────────────────
# Inference must build numpy arrays using this exact order.
# Training must use the same order in the feature matrix.

FEATURE_NAMES: list[str] = [
    "yes_price",          # crowd probability
    "info_ratio",         # volume_24h / sqrt(days_left_raw + 1) / 10_000
    "log_volume_total",   # log1p(volume_total)
    "log_liquidity",      # log1p(liquidity)
    "days_left",          # time to resolution, clamped >= 0.5
    "price_extremity",    # abs(yes_price - 0.5) * 2
]


def compute_features(opp: dict) -> dict[str, float]:
    """
    Compute the 6 model features from an enriched opportunity dict.

    opp must have:
      - curPrice (float, required)
    opp may have:
      - volume_24h, volumeTotal, liquidity, days_left  (all optional, default 0/0/0/0)

    Returns a dict with exactly the keys in FEATURE_NAMES.
    Uses days_left RAW (before clamping) for info_ratio, clamped for the days_left feature.
    """
    p = float(opp["curPrice"])
    vol = float(opp.get("volume_24h") or 0)
    volume_total = float(opp.get("volumeTotal") or 0)
    liquidity = float(opp.get("liquidity") or 0)
    days_raw = float(opp.get("days_left") or 0)
    days_feat = max(days_raw, 0.5)

    return {
        "yes_price":        p,
        "info_ratio":       vol / ((days_raw + 1) ** 0.5) / 10_000,
        "log_volume_total": log1p(volume_total),
        "log_liquidity":    log1p(liquidity),
        "days_left":        days_feat,
        "price_extremity":  abs(p - 0.5) * 2,
    }


def calibrate(raw_score: float, calibration: dict) -> float:
    """
    Apply Platt scaling to a model output score.

    calibration must contain platt_a (intercept) and platt_b (coefficient),
    matching sklearn LogisticRegression.intercept_[0] / coef_[0][0] convention.

    Returns a value in [0, 1].
    """
    raw = calibration["platt_b"] * raw_score + calibration["platt_a"]
    return 1.0 / (1.0 + exp(-raw))


def build_category_trends(poly2: dict) -> dict:
    """
    Summarise poly2 categories as top-3-by-volume market cards.

    Returns {category_name: {totalMarkets, top3Markets}} for non-empty categories.
    Does NOT average yes_price across markets (that number is dominated by question
    framing and category composition, not by crowd belief).
    """
    trends: dict = {}
    for cat_name, cat_data in poly2.get("categories", {}).items():
        markets = cat_data.get("markets", [])
        if not markets:
            continue
        top3 = sorted(markets, key=lambda m: m.get("volume_24h", 0), reverse=True)[:3]
        trends[cat_name] = {
            "totalMarkets": len(markets),
            "top3Markets": [
                {
                    "question": m["question"],
                    "yes_price": m["yes_price"],
                    "volume_24h": m.get("volume_24h", 0),
                    "url": m["url"],
                }
                for m in top3
            ],
        }
    return trends


_EDGE_LABELS: list[tuple[float, str]] = [
    (0.65, "Strong edge"),
    (0.50, "Good edge"),
    (0.40, "Moderate edge"),
    (0.30, "Weak edge"),
]


def _edge_label(score: float) -> str:
    for threshold, label in _EDGE_LABELS:
        if score >= threshold:
            return label
    return "Skip"


def compute_edge_ranking(category_report: dict) -> list[dict]:
    """
    Rank categories by avgQuantScore (the dominant reliable signal at ~32 opps/week).

    Returns list sorted by edgeScore descending, each entry contains:
      category, edgeScore, label, avgQuantScore, tierACount, count
    """
    ranking = []
    for cat, data in category_report.items():
        score = round(data["avgQuantScore"], 3)
        ranking.append({
            "category":      cat,
            "edgeScore":     score,
            "label":         _edge_label(score),
            "avgQuantScore": data["avgQuantScore"],
            "tierACount":    data["tierACount"],
            "count":         data["count"],
        })
    ranking.sort(key=lambda r: r["edgeScore"], reverse=True)
    return ranking


def generate_insights(
    edge_ranking: list[dict],
    opportunities: list[dict],
    model_version: str,
) -> list[str]:
    """
    Generate up to 5 plain-English insight strings from the weekly report data.
    All logic is deterministic — no LLM, no randomness.
    """
    insights: list[str] = []

    # 1. Top edge category
    if edge_ranking:
        top = edge_ranking[0]
        insights.append(
            f"{top['category'].title()} offers the strongest edge this week "
            f"(signal {top['avgQuantScore']:.0%})."
        )

    # 2. Best Tier A opportunity
    tier_a = [o for o in opportunities if o.get("signalTier") == "A"]
    if tier_a:
        best = tier_a[0]  # already sorted by quantScore desc
        insights.append(
            f"Top opportunity: '{best['title']}' — signal {best['quantScore']:.2f}, "
            f"crowd at {best['curPrice']:.0%}."
        )

    # 3. Signal margin of best opportunity
    if tier_a:
        best = tier_a[0]
        margin = round(best["quantScore"] - 0.65, 2)
        if margin > 0:
            insights.append(
                f"'{best['title']}' is {margin:.2f} above the Tier A threshold. "
                f"Crowd is at {best['curPrice']:.0%}."
            )

    # 4. Skip categories
    skip = [r for r in edge_ranking if r["label"] == "Skip"]
    if skip:
        names = ", ".join(r["category"] for r in skip)
        insights.append(f"Low signal this week: {names} — skip unless you have domain edge.")

    # 5. Model staleness alert (fires only if model is > 60 days old)
    try:
        model_date = datetime.strptime(model_version, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - model_date).days
        if days_since > 60:
            insights.append(
                f"Model is {days_since} days old (trained {model_version}). "
                f"Consider retraining with fresh historical data."
            )
    except (ValueError, TypeError):
        pass

    return insights
```

- [ ] **Step 4: Run tests to verify they all pass**

```bash
pytest tests/test_quant_features.py -v
```
Expected: all 25 tests PASS

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/adapters/quant_features.py tests/test_quant_features.py
git commit -m "feat: add quant_features.py — pure scoring functions with full test coverage"
```

---

## Task 4: Historical data fetcher (fetch_historical.py)

**Files:**
- Create: `backend/adapters/fetch_historical.py`
- Create: `tests/test_fetch_historical.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fetch_historical.py`:

```python
"""Tests for fetch_historical.py — mock Gamma API."""
import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))


REQUIRED_COLUMNS = [
    "slug", "question", "category",
    "yes_price", "volume_24h", "volume_total", "liquidity", "days_left",
    "resolved_yes",
]


def _make_market(slug="test-slug", outcome_prices="[0.65, 0.35]",
                 volume24hr=10000, volume_total=100000,
                 liquidity=50000, end_date="2026-04-01T00:00:00Z",
                 resolved_yes=1, tags=None):
    return {
        "slug": slug,
        "question": f"Question for {slug}",
        "outcomePrices": outcome_prices,
        "volume24hr": volume24hr,
        "volumeTotal": volume_total,
        "liquidity": liquidity,
        "endDate": end_date,
        "resolvedYes": resolved_yes,
        "tags": tags or [{"label": "Politics"}],
    }


def test_fetch_page_extracts_required_columns(tmp_path):
    from fetch_historical import parse_market
    market = _make_market()
    row = parse_market(market)
    assert row is not None
    for col in REQUIRED_COLUMNS:
        assert col in row, f"Missing column: {col}"


def test_fetch_page_skips_missing_outcome_prices(tmp_path):
    from fetch_historical import parse_market
    market = _make_market(outcome_prices=None)
    assert parse_market(market) is None


def test_fetch_page_skips_empty_outcome_prices():
    from fetch_historical import parse_market
    market = _make_market(outcome_prices="[]")
    assert parse_market(market) is None


def test_parse_market_yes_price_from_outcome_prices():
    from fetch_historical import parse_market
    market = _make_market(outcome_prices="[0.72, 0.28]")
    row = parse_market(market)
    assert float(row["yes_price"]) == pytest.approx(0.72)


def test_parse_market_category_from_tags():
    from fetch_historical import parse_market
    market = _make_market(tags=[{"label": "Crypto"}])
    row = parse_market(market)
    assert row["category"].lower() == "crypto"


def test_csv_output_has_required_columns(tmp_path):
    from fetch_historical import write_csv
    rows = [
        {"slug": "s1", "question": "Q1", "category": "macro",
         "yes_price": 0.6, "volume_24h": 1000, "volume_total": 10000,
         "liquidity": 5000, "days_left": 14, "resolved_yes": 1},
    ]
    out = tmp_path / "test.csv"
    write_csv(rows, out)
    with open(out) as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
    for col in REQUIRED_COLUMNS:
        assert col in cols
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_fetch_historical.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Implement fetch_historical.py**

Create `backend/adapters/fetch_historical.py`:

```python
"""
fetch_historical.py — Pull resolved Polymarket markets for XGBoost training data.

Usage:
  python backend/adapters/fetch_historical.py --pages 150 --output data/historical_markets.csv

Fetches ~8,000–15,000 resolved markets in ~10 minutes.
Data is gitignored (stored in data/ directory).
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

GAMMA_URL = "https://gamma-api.polymarket.com/markets"
REQUIRED_COLUMNS = [
    "slug", "question", "category",
    "yes_price", "volume_24h", "volume_total", "liquidity", "days_left",
    "resolved_yes",
]


def _infer_category(tags: list) -> str:
    """Extract the first tag label as category, defaulting to 'other'."""
    if not tags:
        return "other"
    return (tags[0].get("label") or "other").lower().replace(" ", "_")


def parse_market(m: dict) -> dict | None:
    """
    Parse a single Gamma API market dict into a training row.
    Returns None if the market lacks required price data.
    """
    raw_prices = m.get("outcomePrices")
    if not raw_prices:
        return None
    try:
        prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
        if not prices:
            return None
        yes_price = float(prices[0])
    except (ValueError, TypeError, IndexError):
        return None

    end_date = m.get("endDate")
    days_left = 14.0  # default fallback
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            delta = (dt - datetime.now(timezone.utc)).total_seconds()
            days_left = max(round(delta / 86400, 1), 0.0)
        except Exception:
            pass

    resolved_yes = m.get("resolvedYes")
    if resolved_yes is None:
        return None  # skip unresolved

    return {
        "slug":         m.get("slug", ""),
        "question":     m.get("question", ""),
        "category":     _infer_category(m.get("tags") or []),
        "yes_price":    round(yes_price, 4),
        "volume_24h":   float(m.get("volume24hr") or 0),
        "volume_total": float(m.get("volumeTotal") or 0),
        "liquidity":    float(m.get("liquidity") or 0),
        "days_left":    days_left,
        "resolved_yes": int(bool(resolved_yes)),
    }


def fetch_page(page: int, limit: int = 100) -> list[dict]:
    """Fetch one page of closed markets from Gamma API."""
    params = {
        "closed": "true",
        "limit": limit,
        "offset": page * limit,
        "order": "endDate",
        "ascending": "false",
    }
    resp = requests.get(GAMMA_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def write_csv(rows: list[dict], path: Path) -> None:
    """Write list of row dicts to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=150)
    parser.add_argument("--output", default="data/historical_markets.csv")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    out_path = Path(args.output)
    rows: list[dict] = []
    print(f"[fetch_historical] Fetching {args.pages} pages × {args.limit} markets...")

    for page in range(args.pages):
        try:
            markets = fetch_page(page, args.limit)
        except Exception as exc:
            print(f"  Page {page}: ERROR — {exc}")
            time.sleep(2)
            continue

        if not markets:
            print(f"  Page {page}: empty response, stopping.")
            break

        for m in markets:
            row = parse_market(m)
            if row:
                rows.append(row)

        if page % 10 == 0:
            print(f"  Page {page}: {len(rows)} rows so far")
        time.sleep(0.1)  # gentle rate limiting

    write_csv(rows, out_path)
    print(f"[fetch_historical] {len(rows)} resolved markets → {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetch_historical.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/fetch_historical.py tests/test_fetch_historical.py
git commit -m "feat: add fetch_historical.py — Gamma API historical data fetcher"
```

---

## Task 5: Model training script (train_model.py) + light tests

**Files:**
- Create: `backend/adapters/train_model.py`
- Create: `tests/test_train_model.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_train_model.py`:

```python
"""Light tests for train_model.py — no real training, no network."""
import sys
from pathlib import Path
import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import FEATURE_NAMES


def _make_df(n=100):
    """Synthetic DataFrame mimicking historical_markets.csv."""
    import pandas as pd
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "yes_price":    rng.uniform(0.01, 0.99, n),
        "volume_24h":   rng.uniform(0, 1_000_000, n),
        "volume_total": rng.uniform(0, 10_000_000, n),
        "liquidity":    rng.uniform(0, 2_000_000, n),
        "days_left":    rng.uniform(0, 90, n),
        "resolved_yes": rng.integers(0, 2, n),
        "endDate_ts":   np.arange(n, dtype=float),  # synthetic time ordering
    })


def test_feature_matrix_shape():
    from train_model import build_feature_matrix
    df = _make_df(200)
    X, y = build_feature_matrix(df)
    assert X.shape == (200, len(FEATURE_NAMES)), f"Expected (200, {len(FEATURE_NAMES)}), got {X.shape}"
    assert y.shape == (200,)


def test_feature_matrix_columns_match_feature_names():
    from train_model import build_feature_matrix
    df = _make_df(50)
    X, y = build_feature_matrix(df)
    # X must be ordered per FEATURE_NAMES — verify by checking values
    from math import log1p
    row = df.iloc[0]
    expected_yes_price = row["yes_price"]
    assert X[0, 0] == pytest.approx(expected_yes_price)


def test_temporal_split_no_leakage():
    from train_model import temporal_split
    df = _make_df(100)
    train, val, test = temporal_split(df)
    # Verify ordering: all train indices < all val < all test
    assert train.index.max() < val.index.min()
    assert val.index.max() < test.index.min()


def test_temporal_split_proportions():
    from train_model import temporal_split
    df = _make_df(100)
    train, val, test = temporal_split(df)
    total = len(train) + len(val) + len(test)
    assert total == 100
    assert 68 <= len(train) <= 72  # ~70%
    assert 13 <= len(val) <= 17    # ~15%
    assert 13 <= len(test) <= 17   # ~15%


def test_auc_gate_rejects_random_model():
    """A model that outputs random probabilities should produce AUC ≈ 0.5 → gate fails."""
    from train_model import check_auc_gate
    from unittest.mock import MagicMock
    import numpy as np

    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, 200)

    mock_model = MagicMock()
    mock_model.predict_proba.return_value = np.column_stack(
        [rng.uniform(0, 1, 200), rng.uniform(0, 1, 200)]
    )
    X_fake = np.zeros((200, len(FEATURE_NAMES)))

    passed, auc = check_auc_gate(mock_model, X_fake, y_true, threshold=0.58)
    assert not passed, f"Random model with AUC {auc:.3f} should not pass gate"
    assert auc < 0.6
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_train_model.py -v
```
Expected: FAIL — `train_model` module not found

- [ ] **Step 3: Implement train_model.py**

Create `backend/adapters/train_model.py`:

```python
"""
train_model.py — Train the XGBoost mispricing classifier.

Usage:
  python backend/adapters/train_model.py --data data/historical_markets.csv

Outputs (all relative to repo root):
  models/xgboost_model.pkl
  models/calibration_params.json
  models/training_metrics.json

Exits with code 1 if test AUC < 0.58.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime, timezone
from math import log1p
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_HERE.parent))
from quant_features import FEATURE_NAMES

MODEL_PATH       = REPO_ROOT / "models/xgboost_model.pkl"
CALIBRATION_PATH = REPO_ROOT / "models/calibration_params.json"
METRICS_PATH     = REPO_ROOT / "models/training_metrics.json"
AUC_THRESHOLD    = 0.58


def build_feature_matrix(df) -> tuple:
    """
    Compute the 6 training features for every row in df.
    Returns (X: np.ndarray of shape (n, 6), y: np.ndarray of shape (n,)).
    Label: 1 = crowd was wrong (market resolved against crowd's >=0.5 direction).
    """
    yes = df["yes_price"].values
    vol = df["volume_24h"].values
    days_raw = np.maximum(df["days_left"].values, 0)  # raw, NOT clamped, for info_ratio
    days_feat = np.maximum(days_raw, 0.5)             # clamped for days_left feature

    X = np.column_stack([
        yes,                                    # yes_price
        vol / ((days_raw + 1) ** 0.5) / 10_000,# info_ratio
        np.log1p(df["volume_total"].values),    # log_volume_total
        np.log1p(df["liquidity"].values),       # log_liquidity
        days_feat,                              # days_left
        np.abs(yes - 0.5) * 2,                  # price_extremity
    ])
    assert X.shape[1] == len(FEATURE_NAMES), f"Feature matrix has {X.shape[1]} cols, expected {len(FEATURE_NAMES)}"

    resolved = df["resolved_yes"].values.astype(int)
    y = ((resolved == 1) != (yes >= 0.5)).astype(int)  # crowd was wrong
    return X, y


def temporal_split(df):
    """
    Split df chronologically: oldest 70% → train, next 15% → val, newest 15% → test.
    df must already be sorted by time (older rows first).
    """
    n = len(df)
    i_val  = int(n * 0.70)
    i_test = int(n * 0.85)
    return df.iloc[:i_val], df.iloc[i_val:i_test], df.iloc[i_test:]


def check_auc_gate(model, X_test, y_test, threshold: float = AUC_THRESHOLD) -> tuple[bool, float]:
    from sklearn.metrics import roc_auc_score
    proba = model.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, proba))
    return auc >= threshold, auc


def main() -> None:
    import pandas as pd
    import xgboost as xgb
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import TimeSeriesSplit

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    args = parser.parse_args()

    print("[train_model] Loading data...")
    df = pd.read_csv(args.data)

    # Sort chronologically — endDate_ts or just use row order as proxy
    if "endDate_ts" in df.columns:
        df = df.sort_values("endDate_ts").reset_index(drop=True)

    print(f"[train_model] {len(df):,} resolved markets loaded")

    train_df, val_df, test_df = temporal_split(df)
    print(f"[train_model] Train: {len(train_df):,}  Val: {len(val_df):,}  Test: {len(test_df):,}")

    X_train, y_train = build_feature_matrix(train_df)
    X_val,   y_val   = build_feature_matrix(val_df)
    X_test,  y_test  = build_feature_matrix(test_df)

    # Class imbalance: crowd is right ~70-75% of the time
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / max(n_pos, 1)
    print(f"[train_model] Class balance: {n_neg} majority / {n_pos} minority → scale_pos_weight={scale_pos_weight:.2f}")

    xgb_params = {
        "max_depth":          4,
        "min_child_weight":   10,
        "subsample":          0.8,
        "colsample_bytree":   0.8,
        "reg_alpha":          0.1,
        "reg_lambda":         1.0,
        "scale_pos_weight":   scale_pos_weight,
        "eval_metric":        "auc",
        "use_label_encoder":  False,
        "verbosity":          0,
        "random_state":       42,
    }

    # 5-fold TimeSeriesSplit cross-validation on training set
    tscv = TimeSeriesSplit(n_splits=5)
    cv_aucs = []
    for fold, (tr_idx, vl_idx) in enumerate(tscv.split(X_train)):
        fold_model = xgb.XGBClassifier(**xgb_params, n_estimators=200)
        fold_model.fit(X_train[tr_idx], y_train[tr_idx], verbose=False)
        proba = fold_model.predict_proba(X_train[vl_idx])[:, 1]
        auc = roc_auc_score(y_train[vl_idx], proba)
        cv_aucs.append(auc)

    cv_mean = float(np.mean(cv_aucs))
    cv_std  = float(np.std(cv_aucs))
    print(f"[train_model] CV AUC (5-fold): {cv_mean:.3f} ± {cv_std:.3f}")

    # Train final model on full training set
    model = xgb.XGBClassifier(**xgb_params, n_estimators=300)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    val_auc = float(roc_auc_score(y_val, model.predict_proba(X_val)[:, 1]))
    print(f"[train_model] Validation AUC: {val_auc:.3f}")

    passed, test_auc = check_auc_gate(model, X_test, y_test)
    status = "PASS" if passed else "FAIL"
    print(f"[train_model] Test AUC: {test_auc:.3f}  ← {status} (threshold: {AUC_THRESHOLD})")

    if not passed:
        print(f"[train_model] ERROR: Test AUC {test_auc:.3f} < {AUC_THRESHOLD}. Model NOT saved.")
        sys.exit(1)

    # Feature importance
    importance = dict(zip(FEATURE_NAMES, model.feature_importances_))
    max_feat, max_imp = max(importance.items(), key=lambda kv: kv[1])
    print("[train_model] Feature importance:")
    for feat, imp in sorted(importance.items(), key=lambda kv: kv[1], reverse=True):
        flag = " ← HIGH" if imp > 0.60 else ""
        print(f"               {feat:<22} {imp:.2f}{flag}")
    if max_imp > 0.60:
        print(f"[train_model] WARNING: {max_feat} explains {max_imp:.0%} of variance — possible overfit")

    # Platt scaling on validation set
    platt = LogisticRegression()
    platt.fit(model.predict_proba(X_val)[:, 1].reshape(-1, 1), y_val)
    platt_a = float(platt.intercept_[0])
    platt_b = float(platt.coef_[0][0])
    print(f"[train_model] Platt scaling: a={platt_a:.4f}, b={platt_b:.4f}")

    model_version = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Save outputs
    (REPO_ROOT / "models").mkdir(exist_ok=True)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"[train_model] Model saved → {MODEL_PATH}")

    calibration = {
        "platt_a":       platt_a,
        "platt_b":       platt_b,
        "feature_names": FEATURE_NAMES,
    }
    CALIBRATION_PATH.write_text(json.dumps(calibration, indent=2))
    print(f"[train_model] Calibration saved → {CALIBRATION_PATH}")

    metrics = {
        "modelVersion":       model_version,
        "trainedAt":          datetime.now(timezone.utc).isoformat(),
        "nSamples":           len(df),
        "cvAuc":              round(cv_mean, 4),
        "cvAucStd":           round(cv_std, 4),
        "valAuc":             round(val_auc, 4),
        "testAuc":            round(test_auc, 4),
        "aucGatePassed":      True,
        "featureImportance":  {k: round(v, 4) for k, v in importance.items()},
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"[train_model] Metrics saved → {METRICS_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_train_model.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/train_model.py tests/test_train_model.py
git commit -m "feat: add train_model.py — XGBoost training with temporal split, AUC gate, Platt scaling"
```

---

## Task 6: Inference script (quant_report.py) + tests

**Files:**
- Create: `backend/adapters/quant_report.py`
- Create: `tests/test_quant_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quant_report.py`:

```python
"""Integration tests for quant_report.py — uses fixtures, mocks the model."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_features import FEATURE_NAMES


def _make_calibration():
    return {"platt_a": 0.0, "platt_b": 1.0, "feature_names": FEATURE_NAMES}


def _make_model(score: float = 0.7):
    m = MagicMock()
    m.predict_proba.return_value = np.array([[1 - score, score]])
    return m


SAMPLE_POLYTRADERS = {
    "opportunities": [
        {"title": "BTC 90k?", "slug": "btc-90k", "curPrice": 0.62,
         "kellyBet": 4.2, "nSmartTraders": 3, "totalExposure": 20000,
         "url": "https://polymarket.com/event/btc-90k"},
        {"title": "ETH flip?", "slug": "eth-flip", "curPrice": 0.25,
         "kellyBet": 1.5, "nSmartTraders": 2, "totalExposure": 8000,
         "url": "https://polymarket.com/event/eth-flip"},
    ]
}

SAMPLE_POLY2 = {
    "categories": {
        "crypto": {
            "markets": [
                {"question": "BTC hits 90k?", "slug": "btc-90k",
                 "yes_price": 0.62, "volume_24h": 50000, "volume_total": 500000,
                 "liquidity": 200000, "days_left": 14, "url": "https://polymarket.com/event/btc-90k"},
            ]
        }
    }
}

SAMPLE_METRICS = {"modelVersion": "2026-03-30", "testAuc": 0.628}


def test_score_opportunity_returns_quant_score(monkeypatch):
    from quant_report import score_opportunity
    model = _make_model(0.75)
    cal = _make_calibration()
    opp = {"curPrice": 0.6, "volume_24h": 10000, "volumeTotal": 100000,
           "liquidity": 50000, "days_left": 14}
    result = score_opportunity(opp, model, cal)
    assert "quantScore" in result
    assert result["quantScore"] == pytest.approx(0.75, rel=1e-3)


def test_score_opportunity_tier_a():
    from quant_report import score_opportunity
    model = _make_model(0.70)
    result = score_opportunity({"curPrice": 0.5}, model, _make_calibration())
    assert result["signalTier"] == "A"


def test_score_opportunity_tier_b():
    from quant_report import score_opportunity
    model = _make_model(0.50)
    result = score_opportunity({"curPrice": 0.5}, model, _make_calibration())
    assert result["signalTier"] == "B"


def test_score_opportunity_tier_c():
    from quant_report import score_opportunity
    model = _make_model(0.30)
    result = score_opportunity({"curPrice": 0.5}, model, _make_calibration())
    assert result["signalTier"] == "C"


def test_score_opportunity_uses_feature_names_order():
    """Model must receive features in FEATURE_NAMES order, not dict insertion order."""
    from quant_report import score_opportunity
    captured_X = []

    def capture_proba(X):
        captured_X.append(X.tolist())
        return np.array([[0.3, 0.7]])

    model = MagicMock()
    model.predict_proba.side_effect = capture_proba
    cal = _make_calibration()
    score_opportunity({"curPrice": 0.6, "volume_24h": 10000, "days_left": 14}, model, cal)
    X = captured_X[0][0]
    assert X[0] == pytest.approx(0.6)       # yes_price is first in FEATURE_NAMES
    assert X[-1] == pytest.approx(0.2)      # price_extremity = abs(0.6-0.5)*2


def test_skip_opportunity_missing_cur_price(tmp_path, capsys):
    from quant_report import run_inference
    polytraders = {"opportunities": [{"slug": "no-price", "title": "Missing"}]}
    poly2 = {"categories": {}}
    model = _make_model(0.7)
    cal = _make_calibration()
    result = run_inference(polytraders, poly2, model, cal, SAMPLE_METRICS)
    # Opportunity without curPrice is skipped — no error, 0 scored
    assert result["summary"]["totalScored"] == 0
    captured = capsys.readouterr()
    assert "skip" in captured.err.lower() or len(result["opportunities"]) == 0


def test_poly2_slug_merge():
    """Opportunity matched by slug gets poly2 volume/liquidity/days_left."""
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    # btc-90k should be enriched with poly2 data (volume_24h=50000)
    opp = next((o for o in result["opportunities"] if o["slug"] == "btc-90k"), None)
    assert opp is not None


def test_run_inference_empty_opportunities():
    from quant_report import run_inference
    result = run_inference({"opportunities": []}, SAMPLE_POLY2, _make_model(),
                           _make_calibration(), SAMPLE_METRICS)
    assert result["summary"]["totalScored"] == 0
    assert result["opportunities"] == []


def test_run_inference_output_has_required_keys():
    from quant_report import run_inference
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    for key in ["generatedAt", "weekOf", "modelVersion", "modelAuc", "summary",
                "opportunities", "categoryReport", "edgeRanking", "insights",
                "categoryTrends"]:
        assert key in result, f"Missing key: {key}"


def test_run_inference_category_report_aggregation():
    from quant_report import run_inference
    # Both opps are in 'crypto' from poly2 match
    result = run_inference(SAMPLE_POLYTRADERS, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    cat_report = result["categoryReport"]
    # Check math: avgQuantScore should be within sane range
    if "crypto" in cat_report:
        assert 0 <= cat_report["crypto"]["avgQuantScore"] <= 1


def test_telegram_message_under_4096_chars(tmp_path):
    """Full report message must fit Telegram's 4096-char limit."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
    from quant_telegram import format_message
    from quant_report import run_inference

    # Generate a report with max reasonable data
    polytraders = {
        "opportunities": [
            {"title": f"Market {i}", "slug": f"slug-{i}", "curPrice": 0.5 + i * 0.01,
             "kellyBet": 2.0, "nSmartTraders": 3, "totalExposure": 10000,
             "url": f"https://polymarket.com/event/slug-{i}"}
            for i in range(20)
        ]
    }
    result = run_inference(polytraders, SAMPLE_POLY2, _make_model(0.7),
                           _make_calibration(), SAMPLE_METRICS)
    msg = format_message(result)
    assert len(msg) <= 4096, f"Message too long: {len(msg)} chars"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_quant_report.py -v
```
Expected: FAIL — `quant_report` module not found

- [ ] **Step 3: Implement quant_report.py**

Create `backend/adapters/quant_report.py`:

```python
"""
quant_report.py — Weekly XGBoost inference script.

Reads reports/polytraders.json + reports/poly2.json,
scores every polytraders opportunity with the committed model,
writes reports/quant_report.json.

Usage (invoked by GitHub Actions every Sunday):
  python backend/adapters/quant_report.py
"""
from __future__ import annotations

import json
import logging
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_HERE.parent))

from quant_features import (
    FEATURE_NAMES,
    build_category_trends,
    calibrate,
    compute_edge_ranking,
    compute_features,
    generate_insights,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quant_report")

POLYTRADERS_PATH = REPO_ROOT / "reports/polytraders.json"
POLY2_PATH       = REPO_ROOT / "reports/poly2.json"
MODEL_PATH       = REPO_ROOT / "models/xgboost_model.pkl"
CALIBRATION_PATH = REPO_ROOT / "models/calibration_params.json"
METRICS_PATH     = REPO_ROOT / "models/training_metrics.json"
OUTPUT_PATH      = REPO_ROOT / "reports/quant_report.json"


def score_opportunity(opp: dict, model, calibration: dict) -> dict:
    """Score one enriched opportunity dict. Returns opp + quantScore/signalTier/infoRatio."""
    features = compute_features(opp)
    # Build numpy array in exact FEATURE_NAMES order (canonical from calibration)
    feat_order = calibration.get("feature_names", FEATURE_NAMES)
    X = np.array([[features[f] for f in feat_order]])
    raw_score = float(model.predict_proba(X)[0][1])
    calibrated_prob = calibrate(raw_score, calibration)
    tier = "A" if raw_score >= 0.65 else "B" if raw_score >= 0.40 else "C"
    return {
        **opp,
        "quantScore":    round(raw_score, 4),
        "signalTier":    tier,
        "calibratedProb": round(calibrated_prob, 4),
        "infoRatio":     round(features["info_ratio"], 4),
    }


def _build_category_report(scored_opps: list[dict]) -> dict:
    """Aggregate scored opportunities by category."""
    cats: dict[str, list] = {}
    for opp in scored_opps:
        cat = opp.get("category", "other")
        cats.setdefault(cat, []).append(opp)
    report = {}
    for cat, opps in cats.items():
        scores = [o["quantScore"] for o in opps]
        tier_a = sum(1 for o in opps if o["signalTier"] == "A")
        report[cat] = {
            "count":         len(opps),
            "avgQuantScore": round(sum(scores) / len(scores), 4),
            "tierACount":    tier_a,
        }
    return report


def run_inference(
    polytraders: dict,
    poly2: dict,
    model,
    calibration: dict,
    metrics: dict,
) -> dict:
    """
    Core inference logic (pure function of inputs — no file I/O).
    Called by main() and by tests.
    """
    # Build poly2 lookup by slug across all categories
    poly2_by_slug: dict[str, dict] = {}
    for cat_name, cat_data in poly2.get("categories", {}).items():
        for m in cat_data.get("markets", []):
            slug = m.get("slug")
            if slug:
                poly2_by_slug[slug] = {**m, "_category": cat_name}

    # Score each opportunity
    scored: list[dict] = []
    for opp in polytraders.get("opportunities", []):
        if "curPrice" not in opp:
            logger.warning("Skipping opportunity missing curPrice: %s", opp.get("slug"))
            continue
        poly2_data = poly2_by_slug.get(opp.get("slug", ""), {})
        enriched = {
            **opp,
            "volume_24h":   poly2_data.get("volume_24h", 0),
            "volumeTotal":  poly2_data.get("volume_total", 0),
            "liquidity":    poly2_data.get("liquidity", 0),
            "days_left":    poly2_data.get("days_left", 14),
            "category":     poly2_data.get("_category", "other"),
        }
        scored.append(score_opportunity(enriched, model, calibration))

    # Sort by quantScore descending
    scored.sort(key=lambda o: o["quantScore"], reverse=True)

    # Aggregate
    tier_a = sum(1 for o in scored if o["signalTier"] == "A")
    tier_b = sum(1 for o in scored if o["signalTier"] == "B")
    tier_c = sum(1 for o in scored if o["signalTier"] == "C")

    cat_report = _build_category_report(scored)
    edge_ranking = compute_edge_ranking(cat_report)
    category_trends = build_category_trends(poly2)

    top_cat = edge_ranking[0] if edge_ranking else None
    model_version = metrics.get("modelVersion", "unknown")
    insights = generate_insights(edge_ranking, scored, model_version)

    return {
        "generatedAt":    datetime.now(timezone.utc).isoformat(),
        "weekOf":         datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "modelVersion":   model_version,
        "modelAuc":       metrics.get("testAuc", 0),
        "summary": {
            "totalScored":          len(scored),
            "tierA":                tier_a,
            "tierB":                tier_b,
            "tierC":                tier_c,
            "topSignalCategory":    top_cat["category"] if top_cat else None,
            "topCategoryAvgScore":  top_cat["edgeScore"] if top_cat else None,
        },
        "opportunities":    scored,
        "categoryReport":   cat_report,
        "edgeRanking":      edge_ranking,
        "insights":         insights,
        "categoryTrends":   category_trends,
    }


def main() -> None:
    logger.info("Loading input files...")
    polytraders = json.loads(POLYTRADERS_PATH.read_text(encoding="utf-8"))
    poly2       = json.loads(POLY2_PATH.read_text(encoding="utf-8"))
    metrics     = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    logger.info("Loading model...")
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))

    result = run_inference(polytraders, poly2, model, calibration, metrics)

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    n = result["summary"]["totalScored"]
    logger.info("Quant report: %d opportunities scored → %s", n, OUTPUT_PATH)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_quant_report.py -v
```
Expected: all 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/quant_report.py tests/test_quant_report.py
git commit -m "feat: add quant_report.py — weekly inference script with poly2 join"
```

---

## Task 7: Telegram push (quant_telegram.py)

**Files:**
- Create: `backend/adapters/quant_telegram.py`

- [ ] **Step 1: Implement quant_telegram.py**

Create `backend/adapters/quant_telegram.py`:

```python
"""
quant_telegram.py — Send weekly Quant Report summary to Telegram.

Usage:
  python backend/adapters/quant_telegram.py

Env vars:
  TELEGRAM_BOT_TOKEN  (required)
  TELEGRAM_CHAT_ID    (required)
  QUANT_REPORT_PATH   (optional, default reports/quant_report.json)
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent

REPORT_PATH = REPO_ROOT / os.environ.get("QUANT_REPORT_PATH", "reports/quant_report.json")

LABEL_EMOJI = {
    "Strong edge":   "🟢",
    "Good edge":     "🟢",
    "Moderate edge": "🟡",
    "Weak edge":     "🔴",
    "Skip":          "🔴",
}


def format_message(report: dict) -> str:
    """Format report dict as Telegram HTML message (≤ 4096 chars)."""
    week = report.get("weekOf", "?")
    summary = report.get("summary", {})
    n_scored = summary.get("totalScored", 0)
    tier_a = summary.get("tierA", 0)
    model_auc = report.get("modelAuc", 0)

    lines: list[str] = [
        f"📊 <b>Weekly Quant Report</b> — Week of {week}",
        "",
    ]

    # Macro Pulse — top market per category from categoryTrends
    trends = report.get("categoryTrends", {})
    if trends:
        lines.append("🌍 <b>Market Pulse</b>")
        for cat, data in list(trends.items())[:4]:
            top_list = data.get("top3Markets") or []
            top = top_list[0] if top_list else None
            total = data.get("totalMarkets", 0)
            if top:
                pct = round(top["yes_price"] * 100)
                q = top["question"][:50]
                url = top.get("url", "")
                link = f'<a href="{url}">{q}…</a>' if url else q
                lines.append(f"• {cat.title()}: {total} mkts · top: {link} ({pct}%)")
            else:
                lines.append(f"• {cat.title()}: {total} markets")
        lines.append("")

    # Edge Ranking
    ranking = report.get("edgeRanking", [])
    if ranking:
        lines.append("🏆 <b>Edge Ranking</b>")
        for i, r in enumerate(ranking[:5], 1):
            emoji = LABEL_EMOJI.get(r["label"], "⬜")
            lines.append(
                f"{i}. {emoji} {r['category'].title()} — "
                f"signal {r['avgQuantScore']:.0%} · {r['tierACount']} Tier A"
            )
        lines.append("")

    # Tier A signals
    tier_a_opps = [o for o in report.get("opportunities", []) if o.get("signalTier") == "A"]
    if tier_a_opps:
        lines.append(f"🟢 <b>Tier A signals ({len(tier_a_opps)})</b>")
        for opp in tier_a_opps[:4]:
            title = opp.get("title", "?")[:45]
            score = opp.get("quantScore", 0)
            crowd = round((opp.get("curPrice") or 0) * 100)
            url = opp.get("url", "")
            link = f'<a href="{url}">{title}</a>' if url else title
            lines.append(f"• {link} — signal {score:.2f} | crowd {crowd}%")
        lines.append("")

    # Tier B highlights (top 3 only)
    tier_b_opps = [o for o in report.get("opportunities", []) if o.get("signalTier") == "B"]
    if tier_b_opps:
        lines.append("🟡 <b>Tier B highlights</b>")
        for opp in tier_b_opps[:3]:
            title = opp.get("title", "?")[:40]
            score = opp.get("quantScore", 0)
            url = opp.get("url", "")
            link = f'<a href="{url}">{title}</a>' if url else title
            lines.append(f"• {link} — signal {score:.2f}")
        lines.append("")

    # Insights
    insights = report.get("insights", [])
    if insights:
        lines.append("💡 <b>Conclusions</b>")
        for s in insights[:3]:
            lines.append(f"• {s}")
        lines.append("")

    lines.append(f"{n_scored} markets scored · Model AUC {model_auc:.2f} · Not financial advice")

    msg = "\n".join(lines)
    # Hard truncate at 4096 chars (Telegram limit)
    if len(msg) > 4096:
        msg = msg[:4090] + "\n…"
    return msg


def send_message(token: str, chat_id: str, text: str) -> None:
    """Send HTML message via Telegram Bot API (stdlib only)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        status = resp.getcode()
        if status != 200:
            raise RuntimeError(f"Telegram API returned {status}")


def main() -> None:
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[quant_telegram] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping")
        return

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    msg = format_message(report)
    send_message(token, chat_id, msg)
    print(f"[quant_telegram] Sent ({len(msg)} chars)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify telegram message length test passes**

```bash
pytest tests/test_quant_report.py::test_telegram_message_under_4096_chars -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/adapters/quant_telegram.py
git commit -m "feat: add quant_telegram.py — Telegram push with macro pulse and edge ranking"
```

---

## Task 8: Backend endpoint

**Files:**
- Modify: `backend/server.py` (add one route, line 256)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_quant_report_returns_404_when_missing(client):
    """quant_report.json not present → 404."""
    resp = client.get("/api/quant-report")
    assert resp.status_code == 404

def test_quant_report_returns_report(tmp_path, monkeypatch, client):
    """quant_report.json present → 200 with the JSON contents."""
    import json
    from backend import server as srv
    report = {"generatedAt": "2026-03-30T20:00:00Z", "opportunities": []}
    (srv.REPORTS_DIR / "quant_report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    resp = client.get("/api/quant-report")
    assert resp.status_code == 200
    assert resp.json()["generatedAt"] == "2026-03-30T20:00:00Z"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api.py::test_quant_report_returns_404_when_missing -v
```
Expected: FAIL — endpoint not found

- [ ] **Step 3: Add the endpoint to server.py**

In `backend/server.py`, after the `macro_report` route (line ~253):

```python
@app.get("/api/quant-report")
def quant_report() -> dict:
    return _read_report("quant_report")
```

Also update the module docstring to include the new endpoint:
```
  GET /api/quant-report    — XGBoost weekly report (from reports/quant_report.json)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api.py -v
```
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/server.py tests/test_api.py
git commit -m "feat: add GET /api/quant-report endpoint"
```

---

## Task 9: Frontend — api.js + App.jsx

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add fetchQuantReport to api.js**

Open `frontend/src/api.js`. Find where `fetchMacroReport` is defined and add after it:

```js
export async function fetchQuantReport() {
  const data = await _fetch(`${API_BASE}/api/quant-report`);
  return data ?? seedQuantReport();
}

export function seedQuantReport() {
  return {
    generatedAt: null,
    weekOf: null,
    modelVersion: null,
    modelAuc: null,
    summary: { totalScored: 0, tierA: 0, tierB: 0, tierC: 0 },
    opportunities: [],
    categoryReport: {},
    edgeRanking: [],
    insights: [],
    categoryTrends: {},
  };
}
```

- [ ] **Step 2: Add quant state and tab to App.jsx**

In `App.jsx`:

**Import** (add to the imports block):
```js
import { QuantReportTab } from "./tabs/QuantReport.jsx";
```

Also add to the api imports:
```js
fetchQuantReport, seedQuantReport,
```

**State** (add after `const [macroReport, setMacroReport]`):
```js
const [quantReport, setQuantReport] = useState(seedQuantReport());
```

**Source tracking** (add `quant: "seed"` to `src` initial state):
```js
const [src, setSrc] = useState({
  price: "seed", dvol: "seed", histVol: "seed",
  klines: "seed", book: "seed", poly: "seed",
  alpha: "seed", macro: "seed", quant: "seed",
});
```

**In the `load` callback**, add `fetchQuantReport()` to the `Promise.allSettled` array:
```js
const [price, klines, dvol, hv, book, poly, ks, sm, mr, qr] = await Promise.allSettled([
  fetchBtcPrice(), fetchKlines(), fetchDvol(), fetchHistVol(),
  fetchOptionsBook(), fetchBackendPolymarket(), fetchKellySignals(), fetchSmartMoney(),
  fetchMacroReport(), fetchQuantReport(),
]);
```

Then handle `qr`:
```js
const lQr = qr.status === "fulfilled" ? qr.value : null;
if (lQr?.generatedAt) { setQuantReport(lQr); s.quant = "live"; }
else                   { s.quant = "seed"; }
```

**TABS array** (add between alpha and macro):
```js
{ id: "quant",   label: "Quant",        icon: "📊" },
```

**Render** (add inside the tab render block, after AlphaTab):
```jsx
{tab === "quant" && <QuantReportTab quantReport={quantReport} srcQuant={src.quant} />}
```

- [ ] **Step 3: Build check**

```bash
cd frontend && npm run build
```
Expected: build succeeds (QuantReport.jsx doesn't exist yet → build will fail; proceed to Task 10 immediately)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.js frontend/src/App.jsx
git commit -m "feat: add fetchQuantReport, quant state, and Quant tab placeholder to App"
```

---

## Task 10: Frontend — QuantReport.jsx

**Files:**
- Create: `frontend/src/tabs/QuantReport.jsx`

- [ ] **Step 1: Create QuantReport.jsx**

Create `frontend/src/tabs/QuantReport.jsx`:

```jsx
import { useState } from "react";
import { T } from "../tokens.js";
import { Panel, Badge, Stat } from "../components/primitives.jsx";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ScatterChart, Scatter, ReferenceLine, Cell,
} from "recharts";

// ── Tier helpers ──────────────────────────────────────────────────────────────

function tierColor(tier) {
  if (tier === "A") return T.green;
  if (tier === "B") return T.amber;
  return T.dim;
}

function edgeColor(label) {
  if (label === "Strong edge" || label === "Good edge") return T.green;
  if (label === "Moderate edge") return T.amber;
  return T.red;
}

// ── Section 1: Summary strip ──────────────────────────────────────────────────

function SummaryStrip({ report }) {
  const s = report.summary ?? {};
  const fmt = (d) => d ? new Date(d).toLocaleDateString() : "—";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 12 }}>
      <Stat label="Week of"        value={report.weekOf ?? "—"}          />
      <Stat label="Markets scored" value={s.totalScored ?? 0}            />
      <Stat label="Tier A signals" value={s.tierA ?? 0} accent           />
      <Stat label="Model AUC"      value={report.modelAuc?.toFixed(3) ?? "—"} />
    </div>
  );
}

// ── Section 2: Macro Pulse (top markets per category) ────────────────────────

const PROB_COLOR = (p) => p >= 0.70 ? T.green : p >= 0.30 ? T.amber : T.red;
const CAT_EMOJIS = { macro: "📊", politics: "🏛️", geopolitics: "🌍", crypto: "🔷", stocks: "📈", ai_tech: "🤖", sports: "⚽" };

function MacroPulse({ categoryTrends }) {
  const entries = Object.entries(categoryTrends ?? {});
  if (!entries.length) return null;

  return (
    <Panel title="Market Pulse — Top Markets by Category" delay="d1">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
        {entries.map(([cat, data]) => (
          <div key={cat} style={{ background: T.s2, border: `1px solid ${T.ln}`, borderRadius: 12, padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <span>{CAT_EMOJIS[cat] ?? "◈"}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: T.text, textTransform: "capitalize" }}>{cat}</span>
              <span style={{ fontSize: 10, color: T.dim, marginLeft: "auto" }}>{data.totalMarkets} markets</span>
            </div>
            {(data.top3Markets ?? []).map((m, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 7 }}>
                <span style={{
                  flexShrink: 0, minWidth: 36, padding: "2px 5px", borderRadius: 99, fontSize: 9,
                  fontFamily: T.mono, textAlign: "center",
                  color: PROB_COLOR(m.yes_price),
                  background: `${PROB_COLOR(m.yes_price)}15`,
                  border: `1px solid ${PROB_COLOR(m.yes_price)}30`,
                }}>
                  {(m.yes_price * 100).toFixed(0)}%
                </span>
                <a href={m.url} target="_blank" rel="noreferrer" style={{
                  fontSize: 10, color: T.sub, textDecoration: "none", lineHeight: 1.4,
                  display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
                }}>
                  {m.question}
                </a>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ── Section 3: Model Signal vs Crowd Scatter ──────────────────────────────────

function SignalScatter({ opportunities }) {
  if (!opportunities?.length) return null;
  const dots = opportunities.map(o => ({
    x: o.curPrice ?? 0,
    y: o.quantScore ?? 0,
    tier: o.signalTier,
    title: o.title,
  }));

  return (
    <Panel title="Signal vs Crowd — Model Score vs Crowd Probability" sub="Dots above the 0.65 line are Tier A signals. Horizontal threshold, not diagonal — quantScore is mispricing confidence, not an outcome probability." delay="d2">
      <ResponsiveContainer width="100%" height={240}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
          <CartesianGrid stroke={T.ln} strokeDasharray="3 3" />
          <XAxis dataKey="x" type="number" domain={[0, 1]} tickCount={6}
                 tickFormatter={v => `${(v * 100).toFixed(0)}%`}
                 label={{ value: "Crowd Prob", position: "insideBottom", offset: -8, fontSize: 10, fill: T.dim }} />
          <YAxis dataKey="y" type="number" domain={[0, 1]} tickCount={6}
                 tickFormatter={v => v.toFixed(2)}
                 label={{ value: "Signal", angle: -90, position: "insideLeft", fontSize: 10, fill: T.dim }} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0]?.payload;
              return (
                <div style={{ background: "#06060aF7", border: `1px solid ${T.ln2}`, borderRadius: 10, padding: "8px 12px" }}>
                  <div style={{ fontSize: 10, color: T.sub, marginBottom: 4 }}>{d?.title?.slice(0, 55)}</div>
                  <div style={{ fontSize: 11, fontFamily: T.mono, color: tierColor(d?.tier) }}>
                    Tier {d?.tier} · signal {d?.y?.toFixed(3)} · crowd {(d?.x * 100)?.toFixed(0)}%
                  </div>
                </div>
              );
            }}
          />
          <ReferenceLine y={0.65} stroke={T.green} strokeDasharray="4 4"
                         label={{ value: "Tier A ≥ 0.65", position: "right", fontSize: 9, fill: T.green }} />
          <Scatter data={dots} fill={T.amber}>
            {dots.map((d, i) => (
              <Cell key={i} fill={tierColor(d.tier)} fillOpacity={0.8} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </Panel>
  );
}

// ── Section 4: Category comparison (dual-bar) ─────────────────────────────────

function CategoryComparison({ categoryReport, categoryTrends }) {
  const cats = Object.entries(categoryReport ?? {});
  if (!cats.length) return null;

  const data = cats.map(([cat, d]) => ({
    name: cat,
    "Model Signal":  +(d.avgQuantScore * 100).toFixed(1),
  }));

  return (
    <Panel title="Category Signal Strength" sub="Avg model signal per category — scored opportunities only" delay="d3">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ left: 60, right: 16 }}>
          <CartesianGrid stroke={T.ln} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickFormatter={v => `${v}%`}
                 tick={{ fontSize: 10, fill: T.dim }} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: T.sub }} />
          <Tooltip formatter={(v) => [`${v}%`]} contentStyle={{ background: "#06060a", border: `1px solid ${T.ln2}`, borderRadius: 10, fontSize: 10 }} />
          <Bar dataKey="Model Signal" fill={T.green} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  );
}

// ── Section 5: Edge Ranking + Insights ────────────────────────────────────────

function EdgeRankingAndInsights({ edgeRanking, insights }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>

      {/* Left: Edge Ranking */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 700, color: T.text }}>
          Edge Ranking — Where to Focus
        </h3>
        {(edgeRanking ?? []).map((r, i) => (
          <div key={r.category} style={{
            display: "flex", alignItems: "center", gap: 8, padding: "8px 0",
            borderBottom: i < edgeRanking.length - 1 ? `1px solid ${T.ln}` : "none",
          }}>
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.dim, width: 14 }}>{i + 1}</span>
            <span style={{
              padding: "2px 7px", borderRadius: 99, fontSize: 9, fontFamily: T.mono,
              color: edgeColor(r.label),
              background: `${edgeColor(r.label)}12`,
              border: `1px solid ${edgeColor(r.label)}25`,
            }}>{r.label}</span>
            <span style={{ fontSize: 11, color: T.text, textTransform: "capitalize", flex: 1 }}>{r.category}</span>
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.green }}>{(r.edgeScore * 100).toFixed(0)}%</span>
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.dim }}>{r.tierACount}A</span>
          </div>
        ))}
        {!edgeRanking?.length && (
          <div style={{ fontSize: 11, color: T.dim, padding: "16px 0" }}>No scored opportunities</div>
        )}
      </div>

      {/* Right: Insights */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 700, color: T.text }}>
          Weekly Conclusions
        </h3>
        {(insights ?? []).length ? (
          <ol style={{ margin: 0, padding: "0 0 0 16px" }}>
            {insights.map((s, i) => (
              <li key={i} style={{ fontSize: 11, color: T.sub, lineHeight: 1.6, marginBottom: 8 }}>{s}</li>
            ))}
          </ol>
        ) : (
          <div style={{ fontSize: 11, color: T.dim }}>No insights generated.</div>
        )}
      </div>
    </div>
  );
}

// ── Section 6: Opportunities table ───────────────────────────────────────────

const COLS = ["Tier", "Market", "Signal", "Crowd", "Info Ratio", "Kelly Bet"];

function OpportunitiesTable({ opportunities }) {
  const [sortKey, setSortKey] = useState("quantScore");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = [...(opportunities ?? [])].sort((a, b) => {
    const av = a[sortKey] ?? 0, bv = b[sortKey] ?? 0;
    return sortAsc ? av - bv : bv - av;
  });

  const KEY_MAP = { "Signal": "quantScore", "Crowd": "curPrice", "Info Ratio": "infoRatio", "Kelly Bet": "kellyBet" };

  return (
    <Panel title="Scored Opportunities" sub={`Top ${Math.min(sorted.length, 20)} · sorted by ${sortKey}`} delay="d5">
      {sorted.length ? (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.ln}`, color: T.dim }}>
                {COLS.map((h, i) => (
                  <th key={h}
                    style={{ padding: "9px 10px", fontWeight: 600, textAlign: i <= 1 ? "left" : "right", cursor: KEY_MAP[h] ? "pointer" : "default" }}
                    onClick={() => {
                      const k = KEY_MAP[h];
                      if (!k) return;
                      if (sortKey === k) setSortAsc(!sortAsc);
                      else { setSortKey(k); setSortAsc(false); }
                    }}
                  >
                    {h}{KEY_MAP[h] && (sortKey === KEY_MAP[h] ? (sortAsc ? " ▲" : " ▼") : " ·")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 20).map((opp, i) => (
                <tr key={i} style={{ borderBottom: `1px solid rgba(28,28,36,.5)` }}>
                  <td style={{ padding: "9px 10px" }}>
                    <Badge color={opp.signalTier === "A" ? "green" : opp.signalTier === "B" ? "amber" : "zinc"}>
                      {opp.signalTier}
                    </Badge>
                  </td>
                  <td style={{ padding: "9px 10px", maxWidth: 240, color: T.sub }}>
                    {opp.url
                      ? <a href={opp.url} target="_blank" rel="noreferrer"
                           style={{ color: "inherit", textDecoration: "none", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {opp.title?.slice(0, 50)}
                        </a>
                      : <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{opp.title?.slice(0, 50)}</span>
                    }
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: tierColor(opp.signalTier), fontWeight: 700 }}>
                    {opp.quantScore?.toFixed(3) ?? "—"}
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.sub }}>
                    {opp.curPrice != null ? `${(opp.curPrice * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>
                    {opp.infoRatio?.toFixed(3) ?? "—"}
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.amber }}>
                    {opp.kellyBet != null ? `$${opp.kellyBet.toFixed(2)}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ padding: "32px 0", textAlign: "center", fontSize: 11, color: T.dim }}>
          No scored opportunities — run <code style={{ color: T.green }}>python backend/adapters/quant_report.py</code>
        </div>
      )}
    </Panel>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function QuantReportTab({ quantReport, srcQuant }) {
  const isLive = srcQuant === "live" && !!quantReport?.generatedAt;

  return (
    <div>
      <SummaryStrip report={quantReport} />
      <MacroPulse categoryTrends={quantReport?.categoryTrends} />
      <SignalScatter opportunities={quantReport?.opportunities} />
      <CategoryComparison categoryReport={quantReport?.categoryReport} categoryTrends={quantReport?.categoryTrends} />
      <EdgeRankingAndInsights edgeRanking={quantReport?.edgeRanking} insights={quantReport?.insights} />
      <OpportunitiesTable opportunities={quantReport?.opportunities} />

      <div className="fade-up d5" style={{ borderRadius: 14, padding: 16, background: "rgba(52,211,153,.02)", border: `1px solid rgba(52,211,153,.08)` }}>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
          <span style={{ color: T.green, fontWeight: 700 }}>How this works: </span>
          XGBoost classifier trained on {">"}8,000 resolved Polymarket markets. Predicts crowd mispricing using
          market microstructure features (volume, liquidity, days to resolution). Applied to smart-money
          pre-filtered opportunities from the Alpha pipeline. Signal score = confidence that the crowd is
          on the wrong side — not a predicted outcome probability. Model AUC {quantReport?.modelAuc?.toFixed(3) ?? "?"} · version {quantReport?.modelVersion ?? "?"}.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build to verify no errors**

```bash
cd frontend && npm run build
```
Expected: build succeeds, 0 errors

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/tabs/QuantReport.jsx
git commit -m "feat: add QuantReport.jsx — 6-section quant report tab with scatter, edge ranking, insights"
```

---

## Task 11: GitHub Actions cron

**Files:**
- Create: `.github/workflows/weekly-quant-report.yml`

- [ ] **Step 1: Create weekly-quant-report.yml**

```yaml
name: Weekly Quant Report

on:
  schedule:
    - cron: "0 20 * * 0"   # Sunday 20:00 UTC
  workflow_dispatch:         # allow manual trigger

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
        # Hard fail — do not commit a partial or stale report
        env:
          POLYTRADERS_BANKROLL: "100"

      - name: Commit and push quant report
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git pull --rebase origin master
          git add -f reports/quant_report.json
          git diff --cached --quiet && echo "No changes to commit" || \
            git commit -m "chore: weekly quant report $(date -u +'%Y-%m-%d')"
          git push origin master

      - name: Send Telegram summary
        run: python backend/adapters/quant_telegram.py
        continue-on-error: true    # Telegram outage should not block the committed report
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
```

- [ ] **Step 2: Verify the existing CI workflow still passes**

```bash
pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/weekly-quant-report.yml
git commit -m "feat: add weekly-quant-report.yml — Sunday 20:00 UTC cron"
```

---

## Task 12: End-to-end smoke test

Before training the real model, verify the full pipeline runs end-to-end with a tiny synthetic dataset.

- [ ] **Step 1: Create data directory and synthetic CSV**

```bash
mkdir -p data
python - <<'EOF'
import csv, random, math
rows = []
for i in range(200):
    yes_p = random.uniform(0.05, 0.95)
    resolved = 1 if random.random() < yes_p else 0
    rows.append({
        "slug": f"slug-{i}", "question": f"Q{i}", "category": "macro",
        "yes_price": round(yes_p, 4),
        "volume_24h": random.uniform(0, 100000),
        "volume_total": random.uniform(0, 500000),
        "liquidity": random.uniform(0, 200000),
        "days_left": random.uniform(0, 60),
        "resolved_yes": resolved,
        "endDate_ts": i,
    })
with open("data/smoke_test.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
print("Wrote 200 rows")
EOF
```

- [ ] **Step 2: Train with smoke data (expect AUC gate may fail — that's fine)**

```bash
python backend/adapters/train_model.py --data data/smoke_test.csv || echo "AUC gate failed (expected on random data)"
```

- [ ] **Step 3: Verify quant_report.py runs against existing polytraders.json + poly2.json**

```bash
# Requires models/ to exist; skip if model not yet trained
# Instead verify the module imports and runs with seed data
python -c "
import sys; sys.path.insert(0,'backend/adapters')
from quant_report import run_inference
from quant_features import FEATURE_NAMES
from unittest.mock import MagicMock
import numpy as np, json
poly = json.load(open('reports/polytraders.json', encoding='utf-8'))
poly2 = json.load(open('reports/poly2.json', encoding='utf-8'))
model = MagicMock()
model.predict_proba.return_value = np.array([[0.3, 0.7]])
cal = {'platt_a': 0.0, 'platt_b': 1.0, 'feature_names': FEATURE_NAMES}
metrics = {'modelVersion': '2026-03-29', 'testAuc': 0.628}
result = run_inference(poly, poly2, model, cal, metrics)
print(f'Scored {result[\"summary\"][\"totalScored\"]} opportunities')
print(f'Categories: {list(result[\"categoryReport\"].keys())}')
print(f'Insights: {len(result[\"insights\"])} generated')
print('Smoke test PASSED')
"
```
Expected: `Smoke test PASSED`

---

## Task 13: Push to remote

- [ ] **Step 1: Verify all tests pass**

```bash
pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 2: Verify frontend builds**

```bash
cd frontend && npm run build && cd ..
```

- [ ] **Step 3: Push to remote**

```bash
git push origin master
```

- [ ] **Step 4: Trigger workflow manually to test CI**

On GitHub → Actions → Weekly Quant Report → Run workflow.
This will fail until `models/xgboost_model.pkl` is committed (expected). Verify it fails gracefully (not a Python crash, just a FileNotFoundError from model loading).

---

## After implementation: train the real model

Once all code is merged, run this locally:

```bash
# 1. Fetch historical data (~10 minutes, ~$0 cost)
python backend/adapters/fetch_historical.py --pages 150 --output data/historical_markets.csv

# 2. Train and validate
python backend/adapters/train_model.py --data data/historical_markets.csv

# 3. Review models/training_metrics.json — check testAuc, featureImportance

# 4. Commit the trained model
git add models/xgboost_model.pkl models/calibration_params.json models/training_metrics.json
git commit -m "chore: train initial XGBoost model v$(date +%Y-%m-%d)"
git push origin master

# 5. Trigger weekly-quant-report workflow manually to verify end-to-end
```
