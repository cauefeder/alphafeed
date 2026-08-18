# AlphaFeed Android App — Phase 1 (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A shippable freemium Android MVP — "Today's Best Bets" board + bet detail, free/Pro gating, AdMob, Play Billing subscription, offline cache — running against the **existing** live API (`https://alphafeed-api.onrender.com`).

**Architecture:** Single-activity Jetpack Compose (Material3, Bold Sport dark theme), MVVM with per-screen ViewModels exposing `StateFlow<UiState>`, a repository layer over Retrofit + Room cache, manual DI (`AppContainer`). Pure logic (DTO parsing, edge math, gating, VM state, billing entitlement) is TDD'd; Compose screens get a `@Preview` + one smoke UI test.

**Tech stack:** Kotlin, Compose BOM 2024.09.03, Material3, Navigation-Compose, Retrofit 2.11 + kotlinx.serialization, OkHttp, Room, Play Billing (`billing-ktx`), AdMob (`play-services-ads`) + UMP consent, JUnit4 + kotlinx-coroutines-test + Turbine, Robolectric (JVM Compose/UI-less VM tests). minSdk 26, targetSdk 35, JVM 17.

**Spec:** `docs/superpowers/specs/2026-08-07-alphafeed-android-app-design.md`

**Conventions:**
- New project dir: `alphafeed-android/` (sibling to the backend). Package `com.omnp.alphafeed`.
- Build needs **Java 17** (Android Studio JBR). Unit tests: `./gradlew :app:testDebugUnitTest`. Build: `./gradlew :app:assembleDebug`.
- Commit after each green task. TDD: failing test → watch fail → minimal code → pass → commit.
- Defaults chosen: manual DI · Pro `pro_monthly` $6.99/mo, 7-day trial · Record = Pro-gated teaser in Phase 1 · store name "AlphaFeed: Sports Value Analytics".

---

## File structure

```
alphafeed-android/
├── settings.gradle.kts, build.gradle.kts, gradle.properties, gradle/wrapper/…
└── app/
    ├── build.gradle.kts, proguard-rules.pro
    └── src/
        ├── main/AndroidManifest.xml
        ├── main/java/com/omnp/alphafeed/
        │   ├── AlphaFeedApp.kt            # Application, builds AppContainer
        │   ├── MainActivity.kt            # single activity, sets Compose content
        │   ├── di/AppContainer.kt         # manual DI
        │   ├── data/remote/AlphaFeedApi.kt + dto/QuantReportDto.kt
        │   ├── data/BetsRepository.kt
        │   ├── data/cache/{AppDatabase,BetDao,BetEntity}.kt
        │   ├── data/billing/BillingRepository.kt
        │   ├── domain/model/Bet.kt
        │   ├── domain/EdgeCalc.kt
        │   ├── domain/BoardGating.kt
        │   └── ui/
        │       ├── theme/{Color,Type,Theme}.kt   # Bold Sport
        │       ├── nav/AlphaFeedNav.kt
        │       ├── components/{BetCard,EdgeBar,ConfidenceStripe,LockedRow,AdRow}.kt
        │       ├── bets/{BetsViewModel,BetsScreen}.kt
        │       ├── detail/{BetDetailViewModel,BetDetailScreen}.kt
        │       ├── feed/FeedScreen.kt · record/RecordScreen.kt · more/MoreScreen.kt
        │       └── paywall/PaywallSheet.kt
        ├── test/java/com/omnp/alphafeed/…    # JVM unit tests (Robolectric where needed)
        └── androidTest/java/com/omnp/alphafeed/…  # Compose UI smoke tests
```

Each task below produces a self-contained, committable change.

---

## Task 1: Scaffold the Gradle project (builds an empty Compose app)

**Files:** create `settings.gradle.kts`, root `build.gradle.kts`, `gradle.properties`, `gradle/libs.versions.toml`, `app/build.gradle.kts`, `app/src/main/AndroidManifest.xml`, `MainActivity.kt`, `AlphaFeedApp.kt`, a placeholder theme, and the Gradle wrapper.

- [ ] **Step 1:** Create the Gradle wrapper (copy from the existing BTCTrendApp so versions match):
  `cp -r "/d/BTCTrendapp/btc-trend-app/btc-trend-app/gradle" alphafeed-android/ && cp "/d/BTCTrendapp/btc-trend-app/btc-trend-app/gradlew"* alphafeed-android/`
- [ ] **Step 2:** Write `app/build.gradle.kts` mirroring BTCTrendApp's plugins/versions (kotlin.android, kotlin.plugin.compose, kotlin.plugin.serialization; compose BOM 2024.09.03; activity-compose, material3, navigation-compose, lifecycle-viewmodel-compose, retrofit 2.11 + kotlinx-serialization-converter, kotlinx-serialization-json, okhttp), and ADD: `androidx.room:room-runtime`/`room-ktx` + `room-compiler` (ksp), `com.android.billingclient:billing-ktx:7.x`, `com.google.android.gms:play-services-ads:23.x`, `com.google.android.ump:user-messaging-platform:3.x`. Test deps: `junit`, `kotlinx-coroutines-test`, `app.cash.turbine:turbine`, `org.robolectric:robolectric`, `androidx.compose.ui:ui-test-junit4`. Set `applicationId="com.omnp.alphafeed"`, minSdk 26, targetSdk 35, jvmTarget 17, `buildFeatures{ compose=true; buildConfig=true }`.
- [ ] **Step 3:** `AndroidManifest.xml`: INTERNET permission; `com.google.android.gms.permission.AD_ID`; AdMob `<meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" .../>` (test app id `ca-app-pub-3940256099942544~3347511713`); `AlphaFeedApp` as `android:name`; single `MainActivity` (exported, LAUNCHER).
- [ ] **Step 4:** Minimal `AlphaFeedApp : Application`, `MainActivity` with `setContent { AlphaFeedTheme { Surface { Text("AlphaFeed") } } }`, placeholder `ui/theme/Theme.kt`.
- [ ] **Step 5:** Build: `cd alphafeed-android && ./gradlew :app:assembleDebug` → expect **BUILD SUCCESSFUL**.
- [ ] **Step 6:** Commit: `git init` (if new repo) or add under the backend repo; `git add alphafeed-android && git commit -m "chore(android): scaffold compose app"`.

> If `assembleDebug` can't run (no Android SDK on this machine), report BLOCKED — the toolchain must be present; do not fake success.

---

## Task 2: Bold Sport theme

**Files:** `ui/theme/{Color,Type,Theme}.kt`.

- [ ] **Step 1:** Define the palette as Compose `Color`s from the approved direction: bg `#0D1016`, surface `#161A22`, line `#1C222C`, onSurface `#EEF1F8`, secondaryText `#98A2B4`, **semantic** green `#22C55E` / amber `#F59E0B` / blue `#4F8CFF` (semantic, not the M3 accent). Build a dark `ColorScheme` (committed dark theme). `Type.kt`: Material3 typography with tight display weights; a `tabularNums` `TextStyle` for numbers.
- [ ] **Step 2:** `AlphaFeedTheme { MaterialTheme(colorScheme = DarkColors, typography = …, content) }`.
- [ ] **Step 3:** Build + a `@Preview` composable showing a swatch. Commit: `feat(android): bold sport theme`.

(No unit test — visual. Verified by build + preview.)

---

## Task 3: Quant-report DTOs + JSON parsing (TDD)

**Files:** `data/remote/dto/QuantReportDto.kt`; test `test/…/QuantReportDtoTest.kt`. Add a fixture `test/resources/quant_report_sample.json` (trim a real response to 2 opportunities).

- [ ] **Step 1 — failing test:**
```kotlin
class QuantReportDtoTest {
  private val json = Json { ignoreUnknownKeys = true }
  @Test fun parses_opportunities_with_new_fields() {
    val txt = javaClass.classLoader!!.getResource("quant_report_sample.json")!!.readText()
    val dto = json.decodeFromString<QuantReportDto>(txt)
    val o = dto.opportunities.first()
    assertEquals("Red Sox −1.5", o.title)
    assertEquals(0.30, o.curPrice!!, 1e-6)
    assertTrue(o.expectedValue!! > 0)
    assertEquals("model", o.qSource)
    assertNotNull(o.winProbEst)
    assertTrue(o.betEligible == true)
  }
}
```
- [ ] **Step 2:** Run `./gradlew :app:testDebugUnitTest --tests "*QuantReportDtoTest*"` → FAIL (class missing).
- [ ] **Step 3:** Implement `@Serializable data class QuantReportDto(val generatedAt: String? = null, val opportunities: List<OpportunityDto> = emptyList())` and `OpportunityDto` with nullable fields: `title, slug, url, curPrice, expectedValue, winProbEst, qSource, betEligible, kellyBet, betDirection, category, days_left (@SerialName), estimatedEdge, countSignal, smartTraderNames: List<String>? , nSmartTraders, totalTradersChecked`. Use `@SerialName` where JSON keys differ.
- [ ] **Step 4:** PASS. **Step 5:** commit `feat(android): quant-report DTOs`.

---

## Task 4: Domain model + mapping (TDD)

**Files:** `domain/model/Bet.kt`; test `BetMapperTest.kt`.

- [ ] **Step 1 — failing test:** map an `OpportunityDto` → `Bet` with derived, non-null, display-ready fields:
```kotlin
@Test fun maps_dto_to_display_bet() {
  val bet = OpportunityDto(title="Red Sox −1.5", curPrice=0.30, expectedValue=0.47,
                           winProbEst=0.53, category="sports", days_left=0.5,
                           betEligible=true, url="…").toBet()
  assertEquals("Red Sox −1.5", bet.market)
  assertEquals(47, bet.evPercent)          // rounded %
  assertEquals(53, bet.winPercent)
  assertEquals(30, bet.priceCents)
  assertEquals(Confidence.STRONG, bet.confidence)  // ev>=0.4 STRONG else VALUE
  assertEquals("MLB", bet.leagueLabel)     // sports slug -> league label; fallback "SPORTS"
}
```
- [ ] **Step 2:** FAIL. **Step 3:** implement `data class Bet(...)`, `enum Confidence { STRONG, VALUE }`, and `OpportunityDto.toBet()` (round percents, cents = price*100, confidence from EV threshold, league from slug prefix mapping mlb/nba/nhl/etc → uppercase label). **Step 4:** PASS. **Step 5:** commit.

---

## Task 5: EdgeCalc — the detail bar math (TDD)

**Files:** `domain/EdgeCalc.kt`; test `EdgeCalcTest.kt`.

- [ ] **Step 1 — failing test:**
```kotlin
@Test fun edge_is_model_win_minus_market_price() {
  val e = EdgeCalc.of(winProb = 0.53, price = 0.33)
  assertEquals(53, e.modelWinPct); assertEquals(33, e.marketPct)
  assertEquals(20, e.gapPct)                     // the value
  assertEquals(3.0, e.payoutX, 0.05)             // 1/price
  assertEquals(50, e.fairValueCents)             // round(winProb*100)
}
@Test fun clamps_and_handles_zero_price() { assertEquals(0.0, EdgeCalc.of(0.5,0.0).payoutX) }
```
- [ ] **Step 2:** FAIL. **Step 3:** implement `EdgeCalc.of(winProb, price) -> Edge(modelWinPct, marketPct, gapPct, payoutX, fairValueCents)`. **Step 4:** PASS. **Step 5:** commit.

---

## Task 6: BoardGating — free vs Pro (TDD)

**Files:** `domain/BoardGating.kt`; test `BoardGatingTest.kt`.

- [ ] **Step 1 — failing test:**
```kotlin
@Test fun free_shows_top_three_then_locked() {
  val board = (1..8).map { fakeBet(evPercent = 50 - it) }   // already EV-ranked
  val rows = BoardGating.rows(board, isPro = false)
  assertEquals(3, rows.count { it is Row.BetRow })
  assertTrue(rows.any { it is Row.LockedRow && (it as Row.LockedRow).remaining == 5 })
}
@Test fun pro_shows_all_no_lock() {
  val rows = BoardGating.rows((1..8).map { fakeBet() }, isPro = true)
  assertEquals(8, rows.count { it is Row.BetRow })
  assertTrue(rows.none { it is Row.LockedRow })
}
@Test fun free_inserts_ad_row_after_top_bets() {
  val rows = BoardGating.rows((1..8).map { fakeBet() }, isPro = false)
  assertTrue(rows.any { it is Row.AdRow })      // exactly one ad slot for free
}
```
- [ ] **Step 2:** FAIL. **Step 3:** implement a `sealed interface Row { BetRow; AdRow; LockedRow(remaining) }` and `BoardGating.rows(board, isPro)`: Pro → all BetRows; free → first 3 BetRows + one AdRow + LockedRow(board.size-3). **Step 4:** PASS. **Step 5:** commit.

---

## Task 7: Room cache (TDD, Robolectric)

**Files:** `data/cache/{BetEntity,BetDao,AppDatabase}.kt`; test `BetDaoTest.kt` (Robolectric, in-memory DB).

- [ ] **Step 1 — failing test:** insert a list, replace-on-refresh, read back ordered:
```kotlin
@RunWith(RobolectricTestRunner::class)
class BetDaoTest {
  @Test fun replace_and_read() = runTest {
    val db = Room.inMemoryDatabaseBuilder(ctx, AppDatabase::class.java).allowMainThreadQueries().build()
    db.betDao().replaceAll(listOf(betEntity("a", 47), betEntity("b", 40)))
    assertEquals(2, db.betDao().getAll().size)
    db.betDao().replaceAll(listOf(betEntity("c", 30)))   // refresh clears old
    assertEquals(listOf("c"), db.betDao().getAll().map { it.id })
  }
}
```
- [ ] **Step 2:** FAIL. **Step 3:** `@Entity BetEntity`, `@Dao BetDao { @Query getAll; @Transaction replaceAll = delete()+insert() }`, `@Database AppDatabase`. **Step 4:** PASS. **Step 5:** commit.

---

## Task 8: Retrofit API + BetsRepository (cache-then-network, TDD)

**Files:** `data/remote/AlphaFeedApi.kt`, `data/BetsRepository.kt`; test `BetsRepositoryTest.kt` with a fake api + in-memory dao.

- [ ] **Step 1 — failing test:** repository emits cached first, then network; on network error falls back to cache with an `offline` flag:
```kotlin
@Test fun emits_cache_then_network() = runTest {
  val repo = BetsRepository(FakeApi(ok = listOf(dto("a"))), dao, json)
  repo.refresh()
  assertEquals(listOf("a"), dao.getAll().map { it.id })
}
@Test fun network_error_keeps_cache_and_flags_offline() = runTest {
  dao.replaceAll(listOf(betEntity("cached")))
  val result = BetsRepository(FakeApi(error = IOException()), dao, json).load()
  assertTrue(result.isOffline); assertEquals(listOf("cached"), result.bets.map { it.id })
}
```
- [ ] **Step 2:** FAIL. **Step 3:** `interface AlphaFeedApi { @GET("api/quant-report") suspend fun quantReport(): QuantReportDto; @GET("api/health") … }`. `BetsRepository.load(): BoardResult(bets, isOffline, updatedAt)` — read cache, try network (map DTO→Bet, keep `betEligible==true`, sort by EV desc), write cache; on failure return cache + `isOffline=true`. **Step 4:** PASS. **Step 5:** commit.

---

## Task 9: BillingRepository — isPro entitlement (TDD with fake client)

**Files:** `data/billing/BillingRepository.kt` (wrap `BillingClient` behind a small `BillingClientWrapper` interface so it's fakeable); test `BillingRepositoryTest.kt`.

- [ ] **Step 1 — failing test:**
```kotlin
@Test fun isPro_true_when_active_sub_present() = runTest {
  val repo = BillingRepository(FakeBilling(purchases = listOf(activeSub("pro_monthly"))))
  repo.refresh()
  assertTrue(repo.isPro.value)
}
@Test fun isPro_false_when_no_purchase() = runTest {
  val repo = BillingRepository(FakeBilling(purchases = emptyList())); repo.refresh()
  assertFalse(repo.isPro.value)
}
```
- [ ] **Step 2:** FAIL. **Step 3:** `interface BillingGateway { suspend fun queryPurchases(): List<PurchaseInfo>; suspend fun launchPurchase(activity, productId); … }`; `BillingRepository(gateway)` exposes `val isPro: StateFlow<Boolean>`; `refresh()` sets it from active `pro_monthly` purchases; `purchasePro(activity)`; acknowledges. A real `PlayBillingGateway` implements it against `billing-ktx` (not unit-tested; wired in Task 14). **Step 4:** PASS. **Step 5:** commit.

---

## Task 10: BetsViewModel (state + gating, TDD)

**Files:** `ui/bets/BetsViewModel.kt`; test `BetsViewModelTest.kt` (Turbine).

- [ ] **Step 1 — failing test:** loading → content; content applies gating from an `isPro` flow; error path:
```kotlin
@Test fun free_content_is_gated_to_three() = runTest {
  val vm = BetsViewModel(FakeRepo(board = eightBets()), isProFlow = flowOf(false))
  vm.state.test {
    assertIs<BetsUi.Loading>(awaitItem())
    val c = awaitItem() as BetsUi.Content
    assertEquals(3, c.rows.count { it is Row.BetRow })
    cancelAndIgnoreRemainingEvents()
  }
}
@Test fun offline_flag_surfaces() = runTest { /* FakeRepo(isOffline=true) -> Content.isOffline */ }
```
- [ ] **Step 2:** FAIL. **Step 3:** `sealed interface BetsUi { Loading; Content(rows, isOffline, updatedAt); Error(msg) }`; VM collects repo + `isProFlow`, maps to rows via `BoardGating`, exposes `StateFlow<BetsUi>`; `retry()`. **Step 4:** PASS. **Step 5:** commit.

---

## Task 11: BetDetailViewModel (TDD) + BetDetailScreen (UI)

**Files:** `ui/detail/BetDetailViewModel.kt` (+ test), `ui/detail/BetDetailScreen.kt`, `ui/components/EdgeBar.kt`.

- [ ] **Step 1 — failing VM test:** given a `Bet`, exposes an `Edge` (via EdgeCalc) + the reason strings + disclaimer flag. Assert `edge.gapPct` and that reasons are non-empty plain strings.
- [ ] **Step 2:** FAIL. **Step 3:** implement VM building `DetailUi(bet, edge, reasons, disclaimer)`; reasons derived from fields (smart-money count, point-market, same-day, fair value). **Step 4:** PASS.
- [ ] **Step 5 (UI):** `EdgeBar` composable (fill = win%, marker = price), `BetDetailScreen` rendering hero EV, EdgeBar, stat trio, reasons, disclaimer, and a **Track**/**Share** action row (no wager action). Add `@Preview`. **Step 6:** commit.

---

## Task 12: Navigation + Bets/Feed/Record/More screens

**Files:** `ui/nav/AlphaFeedNav.kt`, `ui/bets/BetsScreen.kt`, `ui/components/{BetCard,ConfidenceStripe,LockedRow,AdRow}.kt`, `ui/feed/FeedScreen.kt`, `ui/record/RecordScreen.kt`, `ui/more/MoreScreen.kt`.

- [ ] **Step 1:** `AlphaFeedNav`: `Scaffold` + `NavigationBar` (Bets · Feed · Record · More) + `NavHost`; Bets → detail route.
- [ ] **Step 2:** `BetsScreen` renders `BetsUi`: `BetCard` per `Row.BetRow` (confidence stripe, market, EV, chips), `AdRow`/`LockedRow` placeholders, offline banner + freshness. `FeedScreen` = static "coming soon / recent signals" placeholder (Phase 2). `RecordScreen` = Pro teaser (blurred stats + Go Pro). `MoreScreen` = Go Pro, restore, disclaimers, privacy, about.
- [ ] **Step 3 (UI smoke test, androidTest):** `BetsScreen` with fake `Content` shows 3 bet cards + a locked row; tapping a card navigates. Run `./gradlew :app:connectedDebugAndroidTest` (needs emulator; if unavailable, keep the test but note it can't run in this env).
- [ ] **Step 4:** commit.

---

## Task 13: PaywallSheet + wire gating to purchase

**Files:** `ui/paywall/PaywallSheet.kt`; wire `LockedRow`, Record, Feed-alerts → open paywall → `BillingRepository.purchasePro(activity)`.

- [ ] **Step 1:** `PaywallSheet` (ModalBottomSheet): value list (full board · no ads · alerts · track record), price "$6.99/mo · 7-day free trial", CTA. On CTA → `purchasePro`. On success (`isPro` flips), gated UI recomposes to unlocked.
- [ ] **Step 2:** UI smoke test: tapping a `LockedRow` shows the sheet. **Step 3:** commit.

---

## Task 14: AdMob + UMP consent (free tier)

**Files:** `ui/ads/AdBanner.kt`, consent init in `MainActivity`, `PlayBillingGateway` real impl, `di/AppContainer.kt` wiring.

- [ ] **Step 1:** Initialize UMP consent + MobileAds in `MainActivity`/`AlphaFeedApp`; `AdBanner` composable (AndroidView `AdView`, **test ad unit** `ca-app-pub-3940256099942544/6300978111`) rendered for `Row.AdRow` only when `!isPro`.
- [ ] **Step 2:** Implement `PlayBillingGateway` against `billing-ktx`; wire everything in `AppContainer` (Retrofit, Room, repositories, billing) built in `AlphaFeedApp`.
- [ ] **Step 3:** Build `./gradlew :app:assembleDebug`; manually verify a test banner shows on free and disappears when `isPro`. (Integration — no unit test.) **Step 4:** commit.

---

## Task 15: Onboarding + compliance + offline polish

**Files:** `ui/onboarding/OnboardingScreen.kt`, string resources, `di/AppContainer` prefs.

- [ ] **Step 1:** First-run onboarding (2–3 slides) ending with the **"informational only · not betting/financial advice · does not accept wagers · 18+"** consent gate stored in DataStore. Disclaimer footer on detail (already) + More.
- [ ] **Step 2:** Offline/skeleton states: skeleton loader for the Render cold-start (~30 s), offline banner using cached data.
- [ ] **Step 3:** Build + run the full unit suite `./gradlew :app:testDebugUnitTest` → all green. **Step 4:** commit.

---

## Final verification (before release prep — separate from execution)

- [ ] `./gradlew :app:testDebugUnitTest` all green; `./gradlew :app:assembleDebug` succeeds.
- [ ] Manual pass on an emulator: board loads (or shows offline cache), gating shows 3 + locked for free, detail renders edge bar + disclaimer, paywall opens, test ads show on free only.
- [ ] Release prep (its own checklist, user-gated, NOT this plan): signing/AAB, real AdMob + Billing product IDs, privacy policy, Data Safety, content rating, 20-tester closed test.

*Phase 2 (Track Record + Feed endpoints + FCM push) is a separate plan once the backend endpoints are scoped.*
