# AlphaFeed — Play Store Listing & Submission Pack

Copy-paste-ready listing text, Data Safety answers, content-rating notes, and the release checklist.
Positioning is deliberately **analytics-only** to pass Google Play's real-money-gambling policy.

---

## Store listing

**App name (30 char max):**
`AlphaFeed: Value Analytics`

**Short description (80 char max):**
`Data-driven value analytics for sports & prediction markets. Informational only.`

**Full description (≤4000 char):**
```
AlphaFeed is an informational analytics tool for sports and prediction markets. It surfaces where
the models see value — ranked by expected ROI, with a calibrated win-probability estimate, the
market price, and a plain-language read of why.

WHAT YOU GET
• Today's Edge — the day's value opportunities, ranked by expected return
• The edge, visualized — model win% vs the market's implied price, side by side
• Why it's flagged — smart-money signal, market type, timing, and fair-value gap
• Clean, fast, made for effortless reading

FREE
• The top opportunities each day
• Full analytics on each one

PRO (optional subscription)
• The complete daily board
• Ad-free
• New-signal alerts
• Track record: hit rate and ROI over time

IMPORTANT — READ THIS
AlphaFeed is INFORMATIONAL ANALYTICS ONLY. It is not betting advice and not financial advice. The
app does NOT accept, place, or facilitate any wager, and it does not connect to any sportsbook or
handle any bets or money for gambling. Nothing here is a recommendation to place a wager. Markets
are risky and uncertain; past model performance does not guarantee future results. For adults 18+.

Questions: cauefeder@gmail.com
Privacy policy: <YOUR_HOSTED_PRIVACY_URL>
```

**Category:** Sports (or Finance) · **Tags:** analytics, sports, statistics
**Contact email:** cauefeder@gmail.com
**Privacy policy URL:** _host `privacy-policy.md` as HTML and paste the URL here (see hosting note)_

**Graphics needed (you provide/generate):**
- App icon 512×512 PNG
- Feature graphic 1024×500 PNG
- ≥2 phone screenshots (use the Free board, a bet detail, and the paywall)

---

## Data Safety form (Play Console answers)

- **Does your app collect or share user data?** Yes (via the ads SDK on the free tier).
- **Data types:**
  - **Device or other IDs** — *Advertising ID*. Collected + shared (AdMob). Purpose: **Advertising/marketing**, **Analytics**. Not user-provided; used by a third-party SDK.
  - **App activity** (ad interactions) — collected by AdMob for ads/analytics.
  - **Purchase history** — entitlement only, via Google Play Billing (Google-processed).
- **You do NOT collect:** name, email, location (precise), contacts, photos, files, messages,
  health, financial account info. No account/login.
- **Is data encrypted in transit?** Yes (HTTPS).
- **Can users request deletion?** No account exists; users clear local data via Clear Data / uninstall
  and reset their Advertising ID in Android settings.
- **Committed to the Play Families policy?** App is 18+, not designed for children.

*(These answers describe the FREE build with AdMob. If you ship a no-ads build, the ad-related
answers drop out.)*

---

## Content rating (IARC questionnaire)
- Category: **Reference / News / Utility** with **simulated gambling / gambling references** = **Yes**
  (the app discusses betting markets). Expect a **Mature 17+ / 18+** rating. Do **not** claim it
  facilitates real gambling (it doesn't) — that would trigger the restricted real-money-gambling flow.
- Target age: **18+**. Set "Ads present: Yes" (free tier).

---

## Gambling-policy guardrails (the #1 rejection risk)
Google Play restricts real-money gambling apps to licensed operators in approved countries. AlphaFeed
is **not** a gambling app — keep it that way in the review's eyes:
- ✅ Analytics/informational only; prominent "does not accept wagers / not advice / 18+" (in-app
  onboarding + every detail screen — already implemented).
- ✅ **No** "bet now" button, **no** deep links to sportsbooks, **no** odds-to-cash flow.
- ✅ Store copy uses "analytics / informational", never "betting tips/picks to win".
- If rejected, appeal citing the analytics-only positioning and the in-app disclaimers.

---

## Pre-submission checklist
- [ ] Host `privacy-policy.md` (get a public URL) → paste into listing + Data Safety.
- [ ] Replace **AdMob test IDs** with real ad-unit IDs; add `app-ads.txt` on your domain; set up the
      AdSense payment/tax profile.
- [ ] Create the **`pro_monthly`** subscription (price + free trial) in Play Console; set up the
      merchant/payments profile. Turn OFF the `FORCE_PRO` test path for production (it defaults off).
- [ ] Bump `versionCode`/`versionName` per release.
- [ ] Upload the **AAB** (`AlphaFeed-release.aab`) to an internal-test track first; enroll in Play
      App Signing; complete Data Safety + content rating; then closed → production.
- [ ] Back up the upload keystore + `keystore.properties` (losing them blocks updates).
