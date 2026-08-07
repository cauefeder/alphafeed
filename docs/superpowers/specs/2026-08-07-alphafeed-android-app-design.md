# AlphaFeed Android App — Design Spec

**Date:** 2026-08-07
**Status:** Design approved (visual + product), pending spec review → implementation plan
**Related:** the AlphaFeed backend (`backend/server.py`, `reports/quant_report.json`), win-prob model spec (2026-08-05).

---

## 1. Product

A consumer, **freemium** Android app whose one job is **"Today's Best Bets"** — the staked sports
point-market value bets, ranked by expected ROI, each with the calibrated win probability. Aimed
at sports/prediction-market bettors who want an effortless daily read of where the edge is.

**Visual direction:** "Bold Sport" — high-contrast dark cards, a confidence color-stripe
(green = strong, amber = value), large EV numbers, league badges. Committed dark theme.

**Non-negotiable positioning (Google Play policy):** informational **analytics only**. The app
never accepts, places, or deep-links to a wager. No "bet now" button, no bookmaker links. This is
the single biggest approval risk and is designed around from day one.

---

## 2. Screens & navigation

Bottom nav: **Bets · Feed · Record · More**.

| Screen | Content | Free vs Pro |
|---|---|---|
| **Bets** (home) | Today's board: value bets ranked by expected ROI; each card = market · EV · win% · price · league · confidence stripe | Free: **top 3** + ad rows · Pro: **full board** |
| **Bet detail** (tap) | Edge bar (model win% vs market-implied price), payout/confidence stats, plain-language reasons (smart money, market type, timing, fair value), disclaimer. Actions: **Track**, **Share** (no wager action) | Free for the 3 visible bets |
| **Feed** | Telegram-style chronological signal stream (new bet, line moved, resolved ✓) | Free: view · Pro: **push alerts** |
| **Track Record** | 90-day ROI, hit rate, resolved count, model performance — the proof that drives upgrades | **Pro** (free sees a teaser + paywall) |
| **More** | Settings, Go Pro, restore purchases, disclaimers, privacy, about | — |

Paywall appears at three natural friction points: locked rows on Bets, the alerts toggle on Feed,
the Record tab.

---

## 3. Architecture

Single-activity Jetpack Compose, MVVM, matching the existing BTCTrendApp stack.

- **UI:** Compose + Material3, `NavHost` with a bottom `NavigationBar`. One composable screen per
  destination; stateless composables fed by `StateFlow<UiState>`.
- **ViewModel:** one per screen (`BetsViewModel`, `BetDetailViewModel`, `FeedViewModel`,
  `RecordViewModel`), exposes `StateFlow` (`Loading | Content | Error | Offline`).
- **Repository layer:**
  - `BetsRepository` — fetch + cache the board.
  - `TrackRecordRepository`, `FeedRepository` (Phase 2).
  - `BillingRepository` — `isPro: StateFlow<Boolean>` (Play Billing).
  - `ConsentRepository` — UMP ad-consent state.
- **Network:** Retrofit 2.11 + `retrofit2-kotlinx-serialization-converter` + OkHttp, base URL
  `https://alphafeed-api.onrender.com`. OkHttp disk cache for stale-while-revalidate.
- **Persistence:** Room (`BetEntity`, `RecordSnapshotEntity`) for offline-first open; DataStore for
  prefs (theme, consent, seen-onboarding).
- **DI:** lightweight manual `AppContainer` (or Hilt if the team prefers) — one place wiring
  Retrofit, Room, repositories.
- **Package:** `com.omnp.alphafeed` · **Module location:** new `alphafeed-android/` project
  (sibling to the backend), its own Gradle build.

---

## 4. Data flow & API

Phase 1 uses only the **existing** backend:
- `GET /api/quant-report` → the board. Fields already emitted per opportunity: `title`, `curPrice`,
  `expectedValue`, `winProbEst`, `qSource`, `betEligible`, `kellyBet`, `category`, `days_left`,
  `betDirection`, plus `smartTraderNames`/`countSignal` for the detail reasons.
  - The app shows **`betEligible == true`** bets (the staked book), already ranked by EV server-side.
- `GET /api/health` → freshness banner ("updated 2h ago").
- `GET /api/smart-money` → enrich the detail's "N of M traders" reason.

Phase 2 needs **new backend endpoints** (documented as dependencies, not built here):
- `GET /api/track-record` — resolved-bet history, hit rate, ROI-over-time from `signal_tracker.db`.
- `GET /api/feed` — recent signal events (new/moved/resolved).
- **FCM sender** — the scheduler POSTs to Firebase when a new bet emits; app subscribes to a topic
  (Pro devices only).

**Client edge computation** (detail bar): model win% = `winProbEst`; market-implied = `curPrice`;
gap = the value. No new math — read straight from the payload.

---

## 5. Monetization

- **Ads (free tier): Google AdMob** (`play-services-ads`). Banner rows interleaved in the Bets
  list (not on detail); optional interstitial only on a deliberate, infrequent transition to stay
  within policy. **UMP consent SDK** gates personalized ads (GDPR/US). No ads for Pro.
- **Pro: Google Play Billing Library** (`billing-ktx`). One auto-renewing subscription
  `pro_monthly` (~$6.99) with an intro free trial. `BillingRepository` queries purchases on
  launch, exposes `isPro`, handles purchase + `acknowledgePurchase` + restore. Digital entitlement
  → **must** use Play Billing (no external payment).
- **Entitlement source of truth:** Play Billing on-device for v1 (tied to Google account, syncs via
  Play). Optional server-side receipt verification later.

---

## 6. Free/Pro gating

Gate in the ViewModel from `isPro`:
- Bets: `if (!isPro) board.take(3)` + insert ad rows + a "locked" CTA row.
- Feed: alerts toggle disabled → paywall.
- Record: whole screen behind paywall (teaser stats blurred).
- v1 gating is **client-side** (the board data is public API). Acceptable for launch; a later
  server-side gate (return 3 for unentitled) can harden it. Noted, not built.

---

## 7. Compliance & store readiness

- **Gambling policy:** analytics-only positioning; no wager/bookmaker actions; prominent
  "informational only · not betting/financial advice · does not accept wagers" on onboarding +
  every detail; **18+** content rating.
- **Required:** privacy policy URL, Data Safety form (ads SDK + FCM data), content rating
  questionnaire, target API 35, Play App Signing, AAB.
- **Account hurdle:** a personal Play developer account (post-2023) needs a 20-tester / 14-day
  closed test before production — schedule it.

---

## 8. Offline & resilience

- Room-cached last board renders instantly on cold start; a background refresh updates it.
- Render `Offline` state (cached data + "showing last update") when the network/Render cold-start
  fails; never a blank error.
- Handle Render free-tier cold starts (first request may take ~30 s) with a skeleton loader + retry.

---

## 9. Testing

- Unit: ViewModel state reduction (loading/content/error/offline); free/Pro gating logic
  (`take(3)` vs full); edge-bar math mapping; JSON deserialization of a sample `/api/quant-report`.
- Repository: cache-then-network; offline fallback.
- Billing: `isPro` transitions via a fake billing client.
- Compose UI tests: board renders cards; locked row shows paywall; detail shows disclaimer.

---

## 10. Phasing (each phase ships a working app)

- **Phase 1 — MVP (standalone against the live API):** Bets board + detail, offline cache,
  free/Pro gating, AdMob + consent, Play Billing subscription, compliance/onboarding, More/settings.
- **Phase 2 — engagement:** `/api/track-record` + Record screen; `/api/feed` + Feed; FCM push
  alerts (backend sender + Pro topic).

The implementation plan (next) will cover **Phase 1** end-to-end; Phase 2 gets its own plan once the
backend endpoints are scoped.

---

## 11. Risks & open questions

- **Play gambling review** is the top risk — mitigated by analytics-only positioning; may still
  need appeal/clarification. Consider a neutral store name (e.g., "AlphaFeed: Sports Value
  Analytics") over anything implying a sportsbook.
- **Client-side gating** is bypassable — accepted for v1.
- **Render cold starts** affect first-open latency — mitigated by cache + skeleton.
- **Open:** DI choice (manual vs Hilt), exact Pro price/trial length, whether Record ships in
  Phase 1 as a static snapshot or waits for Phase 2's endpoint.
