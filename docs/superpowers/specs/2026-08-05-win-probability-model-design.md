# Empirical Win-Probability Model — Design Spec

**Date:** 2026-08-05
**Status:** Approved (design), pending implementation plan
**Related:** `docs/top5-accuracy-report-2026-07-28.md` (accuracy analysis + focus filter + EV ranking)

---

## 1. Problem & motivation

The dashboard now ranks the staked book by expected value, `EV = q/price − 1 − cost`,
but `q` comes from a **hardcoded 3-bucket lookup** (`focus_win_prob`) derived by hand from the
forward-test. We want a principled, self-updating win probability for **every** scored
opportunity so EV is trustworthy across the whole table, not just the focus book.

The original ask was "fix the model calibration." A diagnostic on the 1,518 resolved
alphafeed signals showed that is not viable:

| Test | Result | Meaning |
|---|---|---|
| AUC(raw XGBoost score → market resolution) | **0.45** | below 0.5 — anti-predictive |
| AUC(model − price residual → resolution) | 0.52 | model adds ~nothing over price |
| Brier(model P(YES)) vs Brier(price) | **0.467 vs 0.373** | model probs worse than the raw price |
| AUC(cheap price → bet wins) | **0.61** | price is the real signal |

Isotonic/Platt calibration can only re-map a **monotonic** signal; at AUC ≈ 0.5 there is nothing
to calibrate — it collapses to the base rate, which is exactly what the current `α=0` shrinkage
already does. So the deliverable is **not** calibrating the dead XGBoost model. It is a **new,
small, well-calibrated empirical model** trained on the features that actually predict.

**Caveat carried into the design:** all diagnostics ride on the 42.5%-resolved sample (54.8%
NO_MATCH). AUC(price → resolution) = 0.377 on this sample is itself anti-predictive, partly the
smart-money edge (we only log markets where smart money bets against the crowd) and partly
selection bias we cannot yet separate. The model inherits this bias; it is documented, not fixed
here (the user chose the model over fixing measurement first).

---

## 2. Goals / non-goals

**Goals**
- A per-opportunity win probability `q ∈ (0,1)` for **all** scored opportunities.
- Fit from `signal_tracker.db` resolved outcomes; **scheduled auto-refit** with a **validation
  gate** that refuses to promote a bad fit.
- Replace `focus_win_prob` in the EV computation; keep it as a fallback.
- Interpretable (readable coefficients), calibrated, robust on a small/biased sample.

**Non-goals (v1)**
- Fixing the NO_MATCH measurement gap (separate track).
- Retraining or re-enabling the XGBoost model; `quantScore` stays only as a legacy display value,
  fully out of the EV/staking path.
- Per-prediction confidence intervals or coverage flags (noted as future work).
- Changing staking policy (flat 2%) or eligibility (sports point-markets, 0.15–0.45).

---

## 3. Architecture & components

Each unit has one purpose, a defined interface, and is independently testable.

### 3.1 `backend/adapters/win_prob.py` (new library)
Pure model logic. No I/O beyond artifact load/save helpers.

- `FEATURES: list[str]` — canonical feature order.
- `featurize(opp: dict) -> dict[str, float]` — extract features from an opportunity dict **or** a
  `signal_tracker` row (both provide price, slug, days_left, liquidity, category). One code path
  so training and inference featurize identically.
- `class WinProbModel`
  - `WinProbModel.load(path) -> WinProbModel` (classmethod)
  - `.predict(opp: dict) -> float` — returns `q` clipped to `[0.02, 0.98]`.
  - `.to_dict()` / `WinProbModel.from_dict()` — artifact (de)serialization.
- `fit(rows: list[dict]) -> tuple[dict, dict]` — returns `(params, metrics)`. L2 logistic
  regression on standardized features, walk-forward validation, optional isotonic recalibration
  of the OOS predictions.
- `passes_gate(metrics: dict) -> bool`.

### 3.2 `backend/adapters/fit_win_prob.py` (new script)
Orchestration + I/O. Run by the refresh pipeline.

1. Read resolved alphafeed signals from `signal_tracker.db` (`outcome in ('WIN','LOSS')`).
2. `params, metrics = fit(rows)`.
3. If `passes_gate(metrics)`: **atomically** write `models/win_prob_model.json`.
   Else: leave the existing artifact untouched, log the reason, exit non-zero-but-tolerated so
   the workflow's failure alert can fire without breaking the report run.
4. Print a one-line summary (n_train, Brier vs baseline, ECE, gate result).

### 3.3 `models/win_prob_model.json` (new artifact)
Versioned. Regenerated and committed by the refresh pipeline (like `reports/*.json`).
```json
{
  "fit_date": "2026-08-05T12:00:00Z",
  "model_type": "logistic_l2+isotonic",
  "features": ["price", "is_point_market", "same_day", "log_liquidity", "cat_sports", "..."],
  "standardizer": {"mean": [...], "std": [...]},
  "coefficients": [...], "intercept": 0.0,
  "isotonic": {"x": [...], "y": [...]},   // optional
  "clip": [0.02, 0.98],
  "validation": {"n_train": 1300, "brier": 0.21, "brier_price_baseline": 0.235,
                 "ece": 0.04, "auc": 0.63, "folds": 5},
  "gate_passed": true
}
```

### 3.4 `backend/adapters/quant_report.py` (change)
- Load `WinProbModel` once per report build.
- Per opportunity: `q = model.predict(featurize(opp))`; `EV = expected_value(q, curPrice)`.
- Emit `winProbEst`, `expectedValue`, and new `qSource ∈ {model, lookup, price}`.
- Fallback: if the artifact is missing / older than a staleness bound / `gate_passed=false`,
  use `focus_win_prob` for eligible bets and price-implied `q=price` for the rest; set `qSource`
  accordingly. The system must never hard-break on a missing model.
- Ranking unchanged (by `expectedValue`).

### 3.5 Pipeline (change)
Run `fit_win_prob.py` **before** `quant_report.py` so the report uses the fresh model:
- `.github/workflows/refresh-reports.yml`: add a step before "Run quant_report", and add the
  artifact to the commit step.
- `scheduler.py` `ALPHAFEED_ADAPTERS`: add a `fit_win_prob` entry before the quant-report entry.

### 3.6 Frontend (minimal change)
`frontend/src/tabs/QuantReport.jsx`: the **Exp. ROI** column already exists; extend its tooltip
to show `qSource` and the est. win prob. No new columns.

---

## 4. The model

- **Label:** `y = 1` iff the bet on the opportunity's side won (`outcome == 'WIN'`) — this is
  exactly P(our bet wins), what EV consumes.
- **Features** (per opportunity, at log/score time):
  - `price` — entry/cur price of the bet side (dominant predictor).
  - `is_point_market` — spread/total/handicap slug (0/1).
  - `same_day` — `days_left < 1` (0/1).
  - `log_liquidity` — `log1p(liquidity)`.
  - `category` — one-hot (sports, politics, crypto, geopolitics, macro, other).
- **Estimator:** `sklearn` L2 logistic regression on standardized continuous features. ~6–8
  parameters on n≈1,500 → regularization controls overfitting. Output clipped to `[0.02, 0.98]`.
- **Optional calibration layer:** isotonic regression fit on the concatenated walk-forward OOS
  predictions, applied to `predict` output, to guarantee calibration. Included only if it
  improves OOS ECE without worsening Brier.

---

## 5. Validation & promotion gate

- **Walk-forward**, expanding-window, time-ordered by `created_at` (same style as
  `backtest/run_backtest.py`), default 5 folds.
- **Metrics** on concatenated OOS predictions: Brier, ECE (10-bin), AUC, and the **price-baseline
  Brier** (`q = price`) on the same rows.
- **Promote a new fit only if ALL hold:**
  1. `n_train ≥ 300`
  2. `brier ≤ brier_price_baseline` (must beat naively using the price)
  3. `ece ≤ 0.06`
- **On failure:** do not overwrite the artifact; keep the last good one; log + fire the workflow's
  existing Telegram failure alert.
- **Cold start** (no artifact yet): `quant_report` falls back to `focus_win_prob` / price.

Thresholds are constants at the top of `win_prob.py`, tunable in one place.

---

## 6. Data flow

```
signal_tracker.db (resolved alphafeed signals)
    → fit_win_prob.py → fit() → passes_gate?
        yes → models/win_prob_model.json   (committed by pipeline)
        no  → keep previous artifact + alert
    → quant_report.py loads artifact → q per opp → EV → reports/quant_report.json
    → backend serves JSON → frontend Exp. ROI column
```

---

## 7. Error handling

| Condition | Behavior |
|---|---|
| Artifact missing / unparseable | Fallback to `focus_win_prob` / price; `qSource` reflects it |
| Artifact `gate_passed=false` or stale (> N days) | Same fallback; log a warning |
| `fit` raises / too few rows | Script exits tolerated-nonzero, artifact untouched, alert fires |
| `predict` gets an opp missing a feature | `featurize` supplies documented defaults (e.g. liquidity 0) |
| `price <= 0` | EV returns 0.0 (existing guard) |

---

## 8. Testing

- **Unit (`win_prob.py`):** `featurize` maps opp→vector in canonical order with correct defaults;
  `predict` returns (0,1) and is **monotonically decreasing in price** holding others fixed;
  `to_dict`/`from_dict` round-trip; `fit` is deterministic under a fixed seed; `passes_gate`
  accepts a good metrics dict and rejects on each failing condition.
- **Unit (`fit_win_prob.py`):** writes the artifact only when the gate passes; on gate failure the
  previous artifact is byte-for-byte unchanged; write is atomic (temp + rename).
- **Integration (`quant_report.py`):** uses model `q` when the artifact is present; falls back and
  sets `qSource` when absent/failed; `expectedValue` is recomputed from the model `q`.
- Full suite must stay green (currently 230 passed).

---

## 9. Success criteria

1. Scheduled auto-refit produces a **calibrated** model (OOS ECE ≤ 0.06) that **beats the
   price-Brier baseline**, gated and deterministic.
2. `quant_report` ranks and displays EV from the model `q`, with safe fallback and `qSource`
   transparency.
3. No regression: eligibility, staking, and ranking-by-EV behavior unchanged except that `q` is
   now model-derived.

---

## 10. Risks & open questions

- **Selection/NO_MATCH bias (known):** the model learns from a biased 42.5% sample; on-price
  anti-prediction may not generalize. Mitigation: the gate's price-baseline comparison, and a
  documented caveat. Revisit after the measurement track lands.
- **Small cheap-price buckets** (n≈30–33 below 0.25): predictions there are high-variance;
  L2 + clipping bound the damage, but headline EVs on ultra-cheap bets stay optimistic.
- **Feature leakage:** features must be values known at score time (price, slug, days_left,
  liquidity) — no post-resolution fields. Enforced by the shared `featurize`.
- **Open:** exact staleness bound for fallback (proposed: 7 days) and whether to keep the isotonic
  layer — both decided empirically during implementation from the first fit's metrics.
