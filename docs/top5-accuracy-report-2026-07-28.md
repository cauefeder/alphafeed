# AlphaFeed — Top-Ranked Bet Accuracy Report

**Date:** 2026-07-28 · **Author:** automated analysis
**Sources:** `signal_tracker.db` (6,341 signals; alphafeed = 3,562), `backtest/report.md`,
`backtest/diagnostics.json`, live `reports/quant_report.json`.

---

## TL;DR

**The system's top-ranked bets are anti-predictive.** Ranking by edge selects bets that
resolve *worse* than the system's own average, the probability model is inverted in the tails,
and the conviction tiers are backwards. The only reason live P&L is positive is that the
system stopped staking its high-conviction picks and now bets nothing but Tier-C — and even
that survives only on low-price longshot payoffs. Over half of all signals can never be scored.

| Headline metric | Value | Verdict |
|---|---|---|
| Top-5-per-day hit rate (by edge) | **39.5%** | ❌ below baseline |
| Baseline hit rate (all resolved) | 44.0% | — |
| Walk-forward backtest return | **−77.0%** ($100 → $22.98) | ❌ |
| Backtest win rate | 63.5% | ⚠️ high WR, negative P&L |
| Live forward-test P&L (alphafeed) | +$1,030.52 | ⚠️ see caveats |
| Signal measurement coverage | **42.5%** (54.8% NO_MATCH) | ❌ |
| Current live signals rated actionable | **0 of 92** (all Tier-C "Skip") | ⚠️ self-silenced |

---

## 1. The direct question — how accurate are the top-5 ranked bets?

Reconstructed the system's **top-5 picks per day** across 62 days (ranked by `estimated_edge`,
identical result by `net_edge`) and scored their real resolutions:

| Set | WIN | LOSS | NO_MATCH | Hit rate | Net P&L (staked rows) |
|---|---|---|---|---|---|
| **Top-5 / day** | 64 | 98 | 141 | **39.5%** | +$79.30 |
| Baseline (all resolved) | 666 | 848 | — | **44.0%** | — |

**The top-ranked selection is 4.5 pts *worse* than picking at random from the same universe.**
The ranking key is actively harmful.

### Edge deciles are inverted
If the edge score worked, higher deciles would win more. They win **less**:

| net_edge decile | Hit rate |
|---|---|
| 4–5 (edge 0.001–0.012) | **53–55%** ✅ |
| 6 (0.012–0.49) | 37.1% |
| 7 (0.49–0.97) | 35.1% |
| 8 (0.97–0.995) | **32.2%** ❌ |

The highest-"edge" bets are the worst performers. (Edge values near 1.0 are themselves a data
artifact — a real probabilistic edge cannot be 97%.)

---

## 2. Calibration is broken (root cause)

Predicted probability vs. realized win rate on 1,514 resolved alphafeed signals:

| Model says | Actually wins | Gap |
|---|---|---|
| ~0.6% (0.0–0.1 bucket, n=841) | **50.1%** | +49 pts under-confident |
| ~76% (0.7–0.8, n=25) | 20.0% | −56 pts over-confident |
| ~99% (0.9–1.0 bucket, n=481) | **39.1%** | −60 pts over-confident |

The mapping is **non-monotonic and inverted in the tails** — the model's probability output
carries little usable information and is actively misleading where it is most confident. This
is why the recent `α=0` post-hoc shrinkage (commit N3) silences everything: it's a band-aid
over a miscalibrated model, not a fix.

---

## 3. Conviction tiers are backwards

Tiers should rank A > B > C by accuracy. They are reversed:

| Tier | Resolved | Hit rate | Actually staked | P&L |
|---|---|---|---|---|
| A (highest conviction) | 527 | **37.8%** | 0 bets ($0) | $0 |
| B | 83 | 31.3% | 1 bet | −$5 |
| C (lowest) | 894 | **49.1%** | 235 bets | **+$1,035** |
| Skip | 10 | 20.0% | 0 | $0 |

Tier-A (driven by extreme model confidence) selects the model's *most overconfident, most
wrong* predictions. The system implicitly learned this and stopped staking A/B (0 bet rows) —
so its positive P&L comes entirely from Tier-C.

---

## 4. The one real edge: low price wins, favorites lose

P&L by entry-price bucket (staked rows only):

| Entry price | Hit rate | P&L | # bets |
|---|---|---|---|
| < 0.20 (longshot) | 47.1% | **+$533** | 28 |
| 0.20–0.40 | 59.3% | **+$504** | 103 |
| 0.40–0.60 | 50.2% | +$54 | 82 |
| 0.60–0.80 | 38.6% | −$33 | 15 |
| ≥ 0.80 (heavy favorite) | **23.5%** | −$28 | 8 |

**100% of profit comes from entry price < 0.60**, concentrated below 0.40 (+$1,038 combined).
Heavy favorites are money-losers. This is the only durable, exploitable pattern in the data.

⚠️ **The current live top-2 picks violate this** — AfD "No" @ 0.85 and House-GOP "No" @ 0.865
sit squarely in the 23.5%-hit-rate, negative-P&L heavy-favorite bucket.

---

## 5. Backtest vs. live — why the disagreement

- **Walk-forward backtest:** −77.0% return, 63.5% win rate, max DD −83.4%, Sharpe −1.09,
  AUC 0.674 (but fold-2 = 0.529, near-random). High win rate + big loss = betting favorites
  whose rare losses erase many small wins.
- **Live forward-test:** +$1,030.52. But this is **not** vindication: it excludes the 54.8%
  NO_MATCH signals (selection bias), reflects only Tier-C stakes, and is carried by a handful
  of low-price longshot winners with 1/entry payoffs. The backtest is the more honest estimate
  of the ranking's true quality.

---

## 6. Data quality — you are half-blind

| alphafeed outcome | Count | Share |
|---|---|---|
| Resolved WIN | 666 | 18.7% |
| Resolved LOSS | 848 | 23.8% |
| **NO_MATCH (unscoreable)** | **1,951** | **54.8%** |
| Still open | 97 | 2.7% |

Only **42.5%** of logged signals ever receive a real outcome. NO_MATCH = slug not found at
resolution time (slug rot / archival before the resolver ran / wrong slug captured). Every
metric above is computed on a biased 42.5% sample.

---

## 7. Current live report — state check

- **0 of 92** opportunities are actionable — all Tier-C, `quantScore ≤ 0.062`, every category
  labeled "Skip". `calibratedProb` is pinned to ~0.045–0.048 for every market (the α=0 shrinkage).
  The system is effectively **muted** — which, given sections 1–3, is currently the *safest*
  thing it does.
- **10 of 92** opportunities are already expired (`days_left ≤ 0`) yet still ranked; a past MLB
  game (ATL-CWS, 2026-06-11) shows `days_left = 18.9` → **endDate parsing / staleness bug**.
- **betDirection ↔ outcome inconsistency** on some rows (e.g. #4 outcome "Yes" but `betDir=NO`).
- Model is `2026-06-16`, scored for `weekOf 2026-08-01` → **6+ weeks stale**.

---

## 8. What to improve — prioritized

1. **Fix calibration before anything else (highest impact).** Per-fold Platt scaling is not
   generalizing (§2). Replace with **isotonic regression on a rolling out-of-sample window**,
   validated by a reliability diagram + held-out Brier. **Gate deployment on monotonic
   calibration**, not just AUC > 0.58. Retire the α=0 shrinkage once calibration is real.

2. **Stop ranking by `estimated_edge`.** It's derived from the miscalibrated probability, so
   it's anti-predictive (§1). Until calibration is fixed, rank on the empirically stable,
   validated features the backtest already identified — `info_ratio`, `log_volume_total`,
   `days_left` — via a simple monotonic score with proper CV.

3. **Close the 54.8% measurement gap (§6).** Capture `condition_id` **and** `token_id` at log
   time (the resolver prefers cid but 55% still miss). Run resolution *before* markets archive.
   Refuse to log already-closed markets. You cannot improve what you cannot measure.

4. **Encode the price edge (§4).** Forbid or heavily penalize bets at entry price ≥ 0.75
   (historically negative-EV). The current top-2 live picks would be filtered out. Consider a
   price-bucket-conditional model.

5. **Re-derive or drop the tiers (§3).** Rebuild A/B/C from *out-of-sample realized hit rate*,
   not raw model confidence — the current mapping is inverted.

6. **Purge stale markets (§7).** Filter `days_left ≤ 0` and `closed` markets before scoring and
   display; fix the endDate parser that lets June games show positive days-left.

7. **Add decay guards.** Auto-retrain on a schedule and auto-disable when rolling OOS AUC < 0.55
   (fold-2 already breached this). Surface model age in the UI.

8. **Honest near-term posture:** stay **paper-only** until calibration + ranking demonstrate
   OOS hit-rate monotonicity. The retired legacy systems (poly −$6,408, poly2 −$1,835,
   modeltelegra −$40,490) confirm the cost of trusting uncalibrated signals live.

---

*All figures reproducible from `signal_tracker.db` and the backtest artifacts as of 2026-07-28.
Live P&L and hit-rate figures are computed on the 42.5% of signals with a real resolution.*

---
---

# Part 2 — Accuracy by Theme, and Where to Focus

Themes assigned by slug classifier (no category is stored in the DB). Alphafeed signals only.

## 9. Per-theme accuracy

| Theme | Resolved | NO_MATCH | Hit% | P&L (staked) | # bets | Avg price |
|---|---|---|---|---|---|---|
| **Sports** | **886** | **20%** | **49.1%** | **+$709** | **205** | 0.50 |
| Other | 120 | 62% | 45.0% | +$47 | 10 | 0.64 |
| Geopolitics | 246 | 64% | 36.2% | +$33 | 3 | 0.57 |
| Crypto | 92 | 68% | 35.9% | +$139 | 9 | 0.71 |
| Politics | 156 | 75% | **27.6%** | +$92 | 7 | 0.57 |
| Economy | 14 | 72% | 85.7% ⚠️ | +$10 | 2 | 0.79 |

**Winner: Sports**, decisively — largest sample, best *measurable* accuracy, most P&L, most staked,
and the lowest NO_MATCH rate (its numbers are the only ones we can actually trust).

Two warnings that change strategy:
- **Economy's 85.7% is a mirage** — n=14 resolved, 2 bets. Statistical noise, not a signal. Ignore it.
- **Politics is the *worst* theme (27.6%)** with 75% NO_MATCH — yet the **current live top-4 picks are
  all politics**. The system is concentrating conviction in its least accurate, least measurable theme.

## 10. Inside Sports — where the accuracy actually lives

**By bet type** — point-based markets beat picking winners:

| Bet type | Resolved | Hit% | P&L |
|---|---|---|---|
| Spread / handicap | 110 | **59.1%** | +$102 |
| Total (O/U) | 178 | **53.9%** | +$132 |
| Moneyline | 584 | 45.7% | +$465 |

**By entry price** — a strong, monotonic edge (this is the real signal):

| Price bucket | Resolved | Hit% | P&L | # bets |
|---|---|---|---|---|
| **< 0.35** | 180 | **63.9%** | **+$697** | 83 |
| 0.35–0.50 | 300 | 51.7% | +$83 | 95 |
| 0.50–0.65 | 209 | 46.9% | −$30 | 11 |
| ≥ 0.65 | 197 | 34.0% | −$41 | 16 |

Cheap bets win far above their implied probability; favorites lose. **Essentially the entire sports
book P&L comes from the < 0.35 bucket.**

**Robustness** — the low-price edge is not one lucky tournament:

| League (price < 0.35) | Resolved | Hit% | P&L |
|---|---|---|---|
| fifwc (Women's WC) | 76 | 65.8% | +$501 |
| mlb | 35 | 54.3% | +$1 |
| nba | 22 | **86.4%** | $0 (unstaked) |
| atp | 9 | 44.4% | +$23 |

The *hit-rate* edge shows up across fifwc, mlb, and nba. But **P&L is fifwc-concentrated, and fifwc
is a finished tournament** — not forward-repeatable. The repeatable, in-season carrier is **MLB**
(54% at low price), plus NBA where the model is accurate (86%) but barely staked — a sizing miss.

**Calibration is still broken even inside sports** (pred 0.8–1.0 → 42% realized; pred 0.0–0.2 → 53%).
Conclusion: **the sports edge is the price/bet-type/smart-money filter, NOT the model's probability.**
Treat the focus as a *rule-based filter*, not a model-score bet.

## 11. The focused strategy

| Filter | Resolved | Hit% | P&L | # bets |
|---|---|---|---|---|
| All sports | 886 | 49.1% | +$709 | 205 |
| **Sports, price < 0.50** | 480 | **56.2%** | **+$780** | 178 |
| Sports, price < 0.35 | 180 | 63.9% | +$697 | 83 |
| Sports, price ≥ 0.65 | 197 | 34.0% | −$41 | 16 |

**Recommended focus: Sports markets, entry price < 0.50.** It captures **110% of the entire
sports P&L** (+$780) at 56% accuracy over 178 bets, purely by cutting the favorite bucket that
bleeds money. Tighten to **< 0.35** for the highest-conviction slice (64%).

### Action list for the focus
1. **Restrict the live book to Sports, price < 0.50** until other themes have a validated edge.
   Prefer **spreads and totals** (54–59% hit) over moneylines.
2. **Hard-block price ≥ 0.65** across all themes — it is negative-EV everywhere (§4, §10).
3. **Kill politics/geopolitics/crypto from the staked book** — 28–36% hit and 64–75% unmeasurable.
   (This also removes the current live top-4.) Keep them display-only until measurable.
4. **Fix NBA sizing** — 86% hit at low price but $0 staked; the Kelly/tier logic is skipping the
   theme where the model is *right*.
5. **Prioritize in-season leagues** (MLB now; NBA/NHL/EPL in season) since fifwc's +$501 won't recur.
6. Revisit once **§8's calibration fix** lands — then re-test whether the model score adds anything
   on top of this price filter.

*Theme figures are slug-classified and computed on resolved sports signals (20% NO_MATCH — the most
trustworthy slice in the dataset).*

---
---

# Part 3 — Focus filter shipped (implementation)

Implemented the focus strategy directly in the scoring pipeline, test-first (TDD).

### Code changes
- **`backend/adapters/quant_features.py`** — added `is_focus_eligible(category, cur_price)`
  and `focus_score(category, cur_price, days_left, point_market)` with tunable constants:
  `FOCUS_THEMES={"sports"}`, `FOCUS_PRICE_MIN=0.15`, `FOCUS_PRICE_MAX=0.45`,
  `FOCUS_SAMEDAY_DAYS=1.0`, `FOCUS_DEEP_VALUE_MAX=0.35`, and priority bonuses.
- **`backend/adapters/quant_report.py`** — `score_opportunity` now sets
  `betEligible = is_focus_eligible(...)` (was the loose `[0.10, 0.90]` range) and emits a new
  `focusScore`; added `_is_point_market(slug)`; `run_inference` now ranks by
  `(focusScore, quantScore)` so validated bets surface to the top-5.
- **Tests:** `tests/test_focus_filter.py` (10) + 5 new cases in `tests/test_quant_report.py`.
  Full suite: **221 passed**.

### Scoring rule (stacked accuracy levers)
`focusScore = 0` unless **sports AND price ∈ [0.15, 0.45)**. For eligible bets:
`1.0 + 0.4·(same-day) + 0.3·(price<0.35 deep value) + 0.15·(spread/total point market)`.
The score deliberately **ignores the model's quantScore** (which was anti-predictive) and
ranks purely on empirically validated drivers.

### Live re-score — before vs. after
Re-ran the adapter on live data. Eligible book shrank from **92 → 14** (all sports).

| Rank | BEFORE (quantScore) — hist. ~23–28% hit | AFTER (focusScore) — hist. ~59–63% hit |
|---|---|---|
| 1 | Politics: AfD "No" @ 0.85 (favorite) | Spread: Tampa Bay Rays −1.5 @ 0.295 (same-day) |
| 2 | Politics: House-GOP "No" @ 0.865 (favorite) | Spread: NY Liberty −2.5 @ 0.335 (same-day) |
| 3 | Politics: House-GOP "Yes" @ 0.135 | Total: Cardinals–Blue Jays O/U @ 0.17 (same-day) |
| 4 | Politics: SC nominee @ 0.61 | Total: Brewers–Angels O/U @ 0.435 (same-day) |
| 5 | Sports: Braves–White Sox O/U @ 0.37 | Total: Twins–Mariners O/U @ 0.385 (same-day) |

The top-5 flipped from **politics favorites** (worst theme, worst price bucket) to **same-day
sports spreads/totals in the validated price band** — the exact profile that historically hit
59–63%. Constants are one-line tunable as new resolutions accumulate.

### Staking enabled (flat 2% on the focus book)

**Correction to §7's premise:** stakes were never $0. Under `SHRINKAGE_ALPHA=0` the
calibrated probability collapses to 0.5, and a flat 0.5 makes *any* price ≠ 0.5 look
mispriced — so `compute_kelly_bet` maxed the 5% cap (**$5**) on the underdog side of **every**
in-range market (~85 of them), including all the non-focus junk. That accidental
"flat-$5-on-everything" is what generated the historical staked P&L, not a deliberate policy.

Replaced it with intentional flat staking:
- **`compute_focus_stake()`** → `FOCUS_FLAT_STAKE_PCT = 0.02` (2% of the $100 reference bankroll).
- `score_opportunity` now stakes **$2 on each focus-eligible bet and $0 on everything else**
  (was $5 on ~85 markets). Direction is kept from `compute_kelly_bet` (the underdog-side
  convention the forward-test hit rates were measured under), so the measured edge stays valid.
- Sizing is deliberately **independent of the model probability** — the report's core finding is
  that that probability can't be trusted, so Kelly-off-the-model is off the table.

Live result: **14 bets × $2 = $28 total exposure** (was ~$425 of phantom exposure across 85
markets). The tracker now logs an honest, intentional forward-test instead of a spurious one.

| | Before | After |
|---|---|---|
| Staked markets | ~85 (every in-range) | 14 (focus-eligible sports) |
| Stake per bet | $5 (5% cap, spurious edge) | $2 (flat 2%, intentional) |
| Total exposure | ~$425 | $28 |
| Sizing basis | broken model prob (0.5 artifact) | flat fraction, prob-independent |

### Note on "more accuracy"
The band was tuned for accuracy, not just inclusion: adding the `≥0.15` floor lifted hit rate
56% → 59% (cuts noisy extreme longshots); the same-day + deep-value + point-market bonuses push
the top of the book toward the 63–64% slices. All levers were **out-of-sample validated** on a
time split before shipping. Remaining ceiling is the broken calibration (§2/§8) — until that's
fixed, this rule-based filter is the accuracy lever; the model score should stay silenced.

---
---

# Part 4 — Signal accuracy test + improvement

Backtested the *exact shipped rule* on the 293 historical resolved sports signals in the focus
band (flat $2 stake), then tested principled refinements with a first/second-half time split.

| Rule variant | n | Hit% | P&L | ROI | 1st half | 2nd half |
|---|---|---|---|---|---|---|
| Shipped (sports 0.15–0.45) | 293 | 59.0% | +$536 | 91% | 64.2% | 56.0% |
| **+ require point market** | 109 | **67.9%** | +$267 | 123% | 80.0% | 59.4% |
| + same-day only | 81 | 63.0% | +$154 | 95% | 62.1% | 63.5% |
| + point AND same-day | 29 | 79.3% | +$88 | 151% | 100% | 70.0% |
| tighten to 0.20–0.40 | 188 | 58.5% | +$354 | 94% | 67.2% | 54.3% |

**Improvement shipped:** require point markets (`FOCUS_REQUIRE_POINT_MARKET=True`). It lifts the
staked book from **59% → 67.9%** hit and holds out-of-sample (both halves beat the moneyline-
inclusive rule). Mechanistically sound — spread/total lines are sharp-set, so smart-money signals
on them are more reliable. Tightening the price band added nothing; same-day is kept as a ranking
bonus (most *stable* slice) rather than a hard gate to preserve volume.

Live effect: staked book **14 → 8 bets** (all spreads/totals), $2 each = **$16 exposure**,
projected ~68% hit. Test suite: **225 passed**. Direction unchanged, so the measured hit rate
transfers to the forward-test.

*Kept as future levers (not shipped, to avoid overfitting small samples): point+same-day (79% but
n=29) and per-league sizing.*

---
---

# Part 5 — Steer by expected value, not accuracy

Q: *"If we copy the most profitable Polymarket traders, why is accuracy so low?"*
A: **Profit comes from payoff, not frequency.** The leaderboard ranks traders by P&L/ROI, and
they make money on mispriced cheap outcomes — a 44% hit rate paid us +$1,031 because winners at
low prices pay 3–7×. Grading that strategy on *accuracy* is the wrong ruler; its edge is EV.

| Entry price | Hit% | Win payoff | ROI/bet |
|---|---|---|---|
| < 0.20 | 64% | ~7.4× | **+381%** |
| 0.20–0.40 | 57% | ~3.3× | +98% |
| 0.40–0.60 | 52% | ~2.2× | +17% |
| 0.60–0.80 | 40% | ~1.5× | −44% |
| ≥ 0.80 | 25% | ~1.2× | −70% |

Low accuracy is only a problem when ROI is *also* negative (the ≥0.60 favorites — where the old
model ranked us). The focus band 0.15–0.45 is the "low accuracy, high ROI" zone.

**Shipped:** the dashboard now leads with an **Exp. ROI** column and the book is **ranked by
expected value**, not focusScore. EV uses the *empirical* win probability (not the broken model
prob): `EV = q/price − 1 − cost`, where `q` is the historical point-market hit rate by price
bucket (73% <0.25, 70% 0.25–0.35, 54% 0.35–0.45). Live ordering:

| Bet | Price | q | **Exp. ROI** | Stake |
|---|---|---|---|---|
| Cardinals–Jays O/U | 0.17 | 73% | **+330%** | $2 |
| Spread: Rays −1.5 | 0.295 | 70% | +135% | $2 |
| Spread: Liberty −2.5 | 0.335 | 70% | +107% | $2 |
| Spread: Blue Jays −1.5 | 0.355 | 54% | +52% | $2 |

`expectedValue` + `winProbEst` are emitted per opportunity; `run_inference` sorts by
`(expectedValue, focusScore, quantScore)`. Test suite: **230 passed**; frontend builds clean.

**Caveat:** `q` is a coarse historical estimate on the 42.5%-resolved sample, and the cheap
buckets are small (n=30–33), so the headline EVs (+300%) are optimistic point estimates — treat
them as *ordering*, not promises. The real fix is still proper calibration (§8).
