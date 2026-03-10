/**
 * Pure math and formatting utilities — no React, no side-effects.
 * All functions are exported individually for tree-shaking.
 */

// ── Trading sessions ──────────────────────────────────────────────────────────

export const SESSIONS = [
  { name: "Asia",      s: 0,  e: 7,  c: "#d97706" },
  { name: "London",    s: 8,  e: 12, c: "#2563eb" },
  { name: "NY Open",   s: 13, e: 16, c: "#dc2626" },
  { name: "NY PM",     s: 17, e: 21, c: "#ea580c" },
  { name: "Dead Zone", s: 22, e: 23, c: "#404040" },
];

export function getSession(hour) {
  return SESSIONS.find(s => hour >= s.s && hour <= s.e) ?? SESSIONS[4];
}

// ── Volatility ────────────────────────────────────────────────────────────────

/**
 * Compute hourly realized volatility from 1-hour klines.
 * Returns 24-element array (one per UTC hour) with annualized vol %.
 */
export function calcRealizedVol(klines) {
  if (!klines || klines.length < 2) return null;

  const buckets = {};
  klines.forEach((x, i) => {
    if (!i) return;
    const lr = Math.log(x.close / klines[i - 1].close);
    if (!buckets[x.hour]) buckets[x.hour] = [];
    buckets[x.hour].push(lr);
  });

  return Array.from({ length: 24 }, (_, h) => {
    const r = buckets[h] ?? [];
    if (r.length < 2) return { hour: h, label: `${String(h).padStart(2, "0")}:00`, realizedVol: 0, impliedVol: null, count: 0 };
    const mean = r.reduce((s, x) => s + x, 0) / r.length;
    const variance = r.reduce((s, x) => s + (x - mean) ** 2, 0) / (r.length - 1);
    return {
      hour: h,
      label: `${String(h).padStart(2, "0")}:00`,
      realizedVol: +(Math.sqrt(variance) * Math.sqrt(8760) * 100).toFixed(1),
      impliedVol: null,
      count: r.length,
    };
  });
}

/**
 * Compute day-of-week realized volatility from 1-hour klines.
 */
export function calcWeekdayVol(klines) {
  if (!klines || klines.length < 2) return null;

  const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const buckets = {};
  klines.forEach((x, i) => {
    if (!i) return;
    const lr = Math.log(x.close / klines[i - 1].close);
    if (!buckets[x.dayOfWeek]) buckets[x.dayOfWeek] = [];
    buckets[x.dayOfWeek].push(lr);
  });

  return Array.from({ length: 7 }, (_, d) => {
    const r = buckets[d] ?? [];
    if (r.length < 2) return { day: DAY_NAMES[d], vol: 0 };
    const mean = r.reduce((s, x) => s + x, 0) / r.length;
    const variance = r.reduce((s, x) => s + (x - mean) ** 2, 0) / (r.length - 1);
    return { day: DAY_NAMES[d], vol: +(Math.sqrt(variance) * Math.sqrt(8760) * 100).toFixed(0) };
  });
}

// ── Kelly / Bankroll math ─────────────────────────────────────────────────────

export const KELLY_FRACTIONS = [
  { label: "¼ Kelly", long: "Quarter Kelly", sub: "Safest",       value: 0.25 },
  { label: "½ Kelly", long: "Half Kelly",    sub: "Recommended",  value: 0.5  },
  { label: "¾ Kelly", long: "Three-Quarter", sub: "Moderate",     value: 0.75 },
  { label: "1 Kelly", long: "Full Kelly",    sub: "Aggressive",   value: 1.0  },
];

export function kellyFraction(winRate, avgWin, avgLoss) {
  if (avgLoss === 0) return 0;
  const b = avgWin / avgLoss, p = winRate / 100, q = 1 - p;
  return Math.max(0, (b * p - q) / b);
}

export function expectedValue(winRate, avgWin, avgLoss) {
  const p = winRate / 100;
  return p * avgWin - (1 - p) * avgLoss;
}

export function maxDrawdown(kellyMult, fullKelly) {
  const f = kellyMult * fullKelly;
  return f <= 0 ? 0 : Math.min(0.95, f * 3.5 * 1.05);
}

// ── Formatters ────────────────────────────────────────────────────────────────

export function formatDollars(n)   { return "$" + Math.round(n).toLocaleString("en-US"); }
export function formatPct(n)       { return (n * 100).toFixed(1) + "%"; }

export function formatResolvesIn(days) {
  if (days === null || days === undefined) return "—";
  if (days === 0)    return "<1d";
  if (days > 365)    return ">1yr";
  return days < 10   ? `${days.toFixed(1)}d` : `${Math.round(days)}d`;
}

export function resolvesColor(days, T) {
  if (days === null || days === undefined) return T.dim;
  if (days < 3)  return T.red;
  if (days < 7)  return T.amber;
  if (days < 30) return T.sub;
  return T.dim;
}
