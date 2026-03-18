/**
 * Data fetchers and seed data generators.
 * All live fetchers return null on failure so callers can fall back to seed data.
 */

// VITE_API_BASE is set per-environment (Vercel env var or .env.local for local dev).
// Falls back to the production Render URL so Vercel works without manual env config.
const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "https://alphafeed-api.onrender.com");

// ── Generic fetch with timeout ────────────────────────────────────────────────

export async function tryFetch(url, timeoutMs = 8000) {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

// ── Live fetchers ─────────────────────────────────────────────────────────────

export async function fetchBtcPrice() {
  const d = await tryFetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT");
  return d ? +d.price : null;
}

export async function fetchKlines() {
  const d = await tryFetch("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=168");
  if (!Array.isArray(d)) return null;
  return d.map(([o,, h, l, c, v]) => ({
    openTime: o,
    hour: new Date(o).getUTCHours(),
    dayOfWeek: new Date(o).getUTCDay(),
    high: +h, low: +l, close: +c, volume: +v,
  }));
}

export async function fetchDvol() {
  const end = Date.now();
  const start = end - 172_800_000; // 48h
  const d = await tryFetch(
    `https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=3600&start_timestamp=${start}&end_timestamp=${end}`
  );
  if (!d?.result?.data) return null;
  return d.result.data.map(([ts, o, h, l, c]) => ({
    timestamp: ts,
    time: new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    hour: new Date(ts).getUTCHours(),
    open: o, high: h, low: l, close: c,
  }));
}

export async function fetchHistVol() {
  const d = await tryFetch("https://www.deribit.com/api/v2/public/get_historical_volatility?currency=BTC");
  if (!d?.result) return null;
  return d.result.map(([ts, v]) => ({ date: new Date(ts).toLocaleDateString(), vol: +v.toFixed(1) }));
}

export async function fetchOptionsBook() {
  const d = await tryFetch(
    "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option"
  );
  if (!d?.result) return null;

  const map = {};
  d.result.forEach(item => {
    if (!item.mark_iv) return;
    const [, expiry,, type] = item.instrument_name.split("-");
    if (!map[expiry]) map[expiry] = [];
    map[expiry].push({ markIv: item.mark_iv, type, oi: item.open_interest || 0, vol: item.volume || 0 });
  });

  return Object.entries(map).map(([expiry, opts]) => {
    const avg = opts.reduce((s, x) => s + x.markIv, 0) / opts.length;
    const calls = opts.filter(x => x.type === "C");
    const puts  = opts.filter(x => x.type === "P");
    return {
      expiry,
      avgIv:  +avg.toFixed(1),
      callIv: +(calls.length ? calls.reduce((s, x) => s + x.markIv, 0) / calls.length : 0).toFixed(1),
      putIv:  +(puts.length  ? puts.reduce((s, x) => s + x.markIv, 0)  / puts.length  : 0).toFixed(1),
      totalOI:  +opts.reduce((s, x) => s + x.oi,  0).toFixed(0),
      totalVol: +opts.reduce((s, x) => s + x.vol, 0).toFixed(0),
      numStrikes: opts.length,
    };
  }).sort((a, b) => a.expiry.localeCompare(b.expiry)).slice(0, 12);
}

/** Backend-enriched Polymarket (includes computed resolvesIn field). */
export async function fetchBackendPolymarket() {
  const d = await tryFetch(`${API_BASE}/api/polymarket`, 12_000);
  return d?.markets ?? null;
}

/** Direct Gamma API fallback — no resolvesIn. */
export async function fetchPolymarketDirect() {
  const d = await tryFetch(
    "https://gamma-api.polymarket.com/markets?closed=false&limit=50&order=volume24hr&ascending=false"
  );
  if (!Array.isArray(d)) return null;

  return d
    .filter(m => m.outcomePrices)
    .map(m => {
      const prices = JSON.parse(m.outcomePrices);
      const yes = +prices[0];
      const no  = +(1 - yes).toFixed(2);
      const spread = m.spread ? +m.spread : +Math.abs(1 - yes - no).toFixed(4);
      const liquidity = m.liquidity || 0;
      const vol24     = m.volume24hr || 0;
      const uncertainty  = +(1 - Math.abs(yes - 0.5) * 2).toFixed(2);
      const liquidityScore = +Math.min(1, liquidity / 200_000).toFixed(2);
      return {
        question: m.question,
        yesPrice: yes, noPrice: no, spread,
        volume24hr: vol24, liquidity,
        uncertainty, liquidityScore,
        edgeScore: +(uncertainty * liquidityScore * (vol24 > 50_000 ? 1 : 0.5)).toFixed(3),
        resolvesIn: null,
      };
    })
    .sort((a, b) => b.edgeScore - a.edgeScore);
}

export async function fetchKellySignals() {
  return tryFetch(`${API_BASE}/api/kelly-signals`, 35_000);
}

export async function fetchSmartMoney() {
  return tryFetch(`${API_BASE}/api/smart-money`, 35_000);
}

export async function fetchMacroReport() {
  return tryFetch(`${API_BASE}/api/macro-report`, 35_000);
}

/** Wake up Render before main data fetches (cold-start can take ~20s on free tier). */
export async function pingBackend() {
  return tryFetch(`${API_BASE}/api/health`, 35_000);
}

// ── Seed data (offline / demo) ────────────────────────────────────────────────

const EMP_RV = [42,39,37,35,33,31,30,34,45,48,50,52,54,60,65,68,66,63,61,60,56,50,45,43];
const EMP_IV = [44,42,41,39,38,37,36,38,46,48,49,50,52,56,60,62,61,59,58,57,55,51,47,45];

export function seedDvol() {
  const now = Date.now();
  return Array.from({ length: 48 }, (_, i) => {
    const ts = now - (47 - i) * 3_600_000;
    const d = new Date(ts);
    const h = d.getUTCHours();
    const boost = h >= 13 && h <= 20 ? 3 : h >= 8 && h <= 12 ? 1.5 : 0;
    const v = 42 + boost + Math.sin(i * 0.7) * 2.5 + (Math.random() - 0.5) * 1.5;
    return {
      timestamp: ts,
      time: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      hour: h,
      open: +(v - 0.4).toFixed(1), high: +(v + 1).toFixed(1),
      low: +(v - 0.8).toFixed(1),  close: +v.toFixed(1),
    };
  });
}

export function seedHourlyVol() {
  return Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    label: `${String(h).padStart(2, "0")}:00`,
    realizedVol: +(EMP_RV[h] + (Math.random() - 0.5) * 6).toFixed(1),
    impliedVol:  +(EMP_IV[h] + (Math.random() - 0.5) * 3).toFixed(1),
    count: Math.floor(5 + Math.random() * 3),
  }));
}

export function seedWeekdayVol() {
  const days = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
  const vols = [30, 55, 58, 64, 60, 68, 34];
  return days.map((day, i) => ({
    day,
    vol: vols[i] + Math.floor((Math.random() - 0.5) * 5),
    avgMove: +(vols[i] * 0.012 + (Math.random() - 0.5) * 0.2).toFixed(2),
  }));
}

export function seedHistVol() {
  return Array.from({ length: 15 }, (_, i) => {
    const d = new Date(Date.now() - (14 - i) * 86_400_000);
    return { date: d.toLocaleDateString(), vol: +(40 + Math.sin(i * 0.5) * 6 + (Math.random() - 0.5) * 3).toFixed(1) };
  });
}

export function seedVolSurface() {
  const expiries = ["8MAR26","9MAR26","14MAR26","21MAR26","28MAR26","4APR26","25APR26","27JUN26","26SEP26","26DEC26"];
  return expiries.map((expiry, i) => {
    const base = 38 + i * 1.4 + (Math.random() - 0.5) * 2;
    return {
      expiry,
      avgIv:  +base.toFixed(1),
      callIv: +(base - 1.2 + (Math.random() - 0.5) * 1.5).toFixed(1),
      putIv:  +(base + 1.8 + (Math.random() - 0.5) * 1.5).toFixed(1),
      totalOI:  +(500  + Math.random() * 4000).toFixed(0),
      totalVol: +(10   + Math.random() * 200).toFixed(0),
      numStrikes: Math.floor(20 + Math.random() * 40),
    };
  });
}

export function seedPolymarket() {
  const markets = [
    { q: "Will Bitcoin exceed $80K by March 31?",          v: 285e3, l: 180e3 },
    { q: "Fed rate cut at March FOMC meeting?",            v: 420e3, l: 310e3 },
    { q: "Will BTC drop below $60K in March?",             v: 195e3, l: 120e3 },
    { q: "US GDP growth above 3% in Q1 2026?",             v: 175e3, l: 140e3 },
    { q: "Will Iran conflict escalate to US involvement?", v: 350e3, l: 220e3 },
    { q: "BTC dominance above 60% end of March?",          v: 68e3,  l: 45e3  },
    { q: "CPI below 2.5% for February?",                   v: 210e3, l: 155e3 },
    { q: "Morgan Stanley BTC custody live by April?",      v: 42e3,  l: 28e3  },
    { q: "Kraken Fed access boosts BTC above $75K?",       v: 31e3,  l: 19e3  },
    { q: "S&P 500 recovers above 5500 before April 1?",    v: 390e3, l: 275e3 },
    { q: "Oil exceeds $85/barrel in March?",               v: 82e3,  l: 55e3  },
    { q: "Ethereum Pectra upgrade live by March 31?",      v: 120e3, l: 78e3  },
  ];
  return markets.map(({ q, v, l }) => {
    const yes = +(.15 + Math.random() * .7).toFixed(2);
    const no  = +(1 - yes).toFixed(2);
    const spread       = +(.005 + Math.random() * .03).toFixed(4);
    const uncertainty  = +(1 - Math.abs(yes - .5) * 2).toFixed(2);
    const liquidityScore = +Math.min(1, l / 2e5).toFixed(2);
    return {
      question: q,
      yesPrice: yes, noPrice: no, spread,
      volume24hr: v, liquidity: l,
      uncertainty, liquidityScore,
      edgeScore: +(uncertainty * liquidityScore * (v > 5e4 ? 1 : 0.5)).toFixed(3),
      resolvesIn: Math.round(1 + Math.random() * 59),
    };
  }).sort((a, b) => b.edgeScore - a.edgeScore);
}

export function seedKellySignals() {
  return {
    generatedAt: null,
    opportunities: [
      {
        title: "Will BTC exceed $80K by March 31?", outcome: "Yes",
        curPrice: 0.62, estimatedEdge: 0.048, kellyBet: 2.10,
        nSmartTraders: 4, totalTradersChecked: 25,
        smartTraderNames: ["alpha_whale","quant_99","poly_god"],
        totalExposure: 18400, weightedAvgEntry: 0.58, url: "https://polymarket.com",
      },
      {
        title: "Fed rate cut at March FOMC?", outcome: "Yes",
        curPrice: 0.38, estimatedEdge: 0.033, kellyBet: 1.25,
        nSmartTraders: 3, totalTradersChecked: 25,
        smartTraderNames: ["macro_edge","poly_god"],
        totalExposure: 9200, weightedAvgEntry: 0.35, url: "https://polymarket.com",
      },
    ],
  };
}

export function seedSmartMoney() {
  return {
    generatedAt: null,
    signals: [
      { question: "Will Bitcoin exceed $80K by March 31?", side: "YES", traderCount: 5, confidence: 0.82, yesValue: 22000, noValue: 4800, totalValue: 26800, url: "https://polymarket.com" },
      { question: "Fed rate cut at March FOMC meeting?",   side: "YES", traderCount: 3, confidence: 0.71, yesValue: 14200, noValue: 5800, totalValue: 20000, url: "https://polymarket.com" },
      { question: "Ethereum Pectra upgrade by March 31?",  side: "NO",  traderCount: 2, confidence: 0.67, yesValue: 3100,  noValue: 6400, totalValue: 9500,  url: "https://polymarket.com" },
    ],
  };
}

export function seedMacroReport() {
  return {
    generatedAt: null,
    totalMarkets: 0,
    categories: {},
    topVolume: [],
  };
}

export { EMP_IV }; // used by App to merge DVOL implied vol into hourly buckets
