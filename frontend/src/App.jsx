import { useState, useEffect, useCallback } from "react";
import { T } from "./tokens.js";
import { globalCss } from "./styles.js";
import { getSession, calcRealizedVol, calcWeekdayVol } from "./math.js";
import {
  fetchBtcPrice, fetchKlines, fetchDvol, fetchHistVol, fetchOptionsBook,
  fetchBackendPolymarket, fetchPolymarketDirect, fetchKellySignals, fetchSmartMoney, fetchMacroReport,
  pingBackend,
  seedDvol, seedHourlyVol, seedWeekdayVol, seedHistVol, seedVolSurface,
  seedPolymarket, seedKellySignals, seedSmartMoney, seedMacroReport, EMP_IV,
} from "./api.js";
import { Dot, LiveBadge, SeedBadge } from "./components/primitives.jsx";
import { OverviewTab }      from "./tabs/Overview.jsx";
import { VolCurveTab }      from "./tabs/VolCurve.jsx";
import { TermStructureTab } from "./tabs/TermStructure.jsx";
import { PolymarketTab }    from "./tabs/Polymarket.jsx";
import { AlphaTab }         from "./tabs/Alpha.jsx";
import { HedgeTab }         from "./tabs/Hedge.jsx";
import { MacroReportTab }   from "./tabs/MacroReport.jsx";
import { BankrollTab }      from "./tabs/Bankroll.jsx";
import { ConfigTab }        from "./tabs/Config.jsx";

const TABS = [
  { id: "overview",   label: "Overview",    icon: "◉" },
  { id: "volatility", label: "Vol Curve",   icon: "◆" },
  { id: "options",    label: "Term Struct", icon: "▣" },
  { id: "polymarket", label: "Polymarket",  icon: "◈" },
  { id: "alpha",      label: "Alpha",       icon: "★" },
  { id: "hedge",      label: "Hedge",       icon: "🛡️" },
  { id: "macro",      label: "Macro",       icon: "🌐" },
  { id: "bankroll",   label: "Bankroll",    icon: "⚡" },
  { id: "apis",       label: "Config",      icon: "⚙" },
];

export default function AlphaFeed() {
  const [tab, setTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [src, setSrc] = useState({
    price: "seed", dvol: "seed", histVol: "seed",
    klines: "seed", book: "seed", poly: "seed", alpha: "seed", macro: "seed",
  });

  const [btcPrice,    setBtcPrice]    = useState(67340);
  const [dvolData,    setDvolData]    = useState([]);
  const [hourlyVol,   setHourlyVol]   = useState([]);
  const [weekdayVol,  setWeekdayVol]  = useState([]);
  const [histVol,     setHistVol]     = useState([]);
  const [volSurface,  setVolSurface]  = useState([]);
  const [polyMarkets, setPolyMarkets] = useState([]);
  const [kellySignals,setKellySignals]= useState(seedKellySignals());
  const [smartMoney,  setSmartMoney]  = useState(seedSmartMoney());
  const [macroReport, setMacroReport] = useState(seedMacroReport());

  const load = useCallback(async () => {
    setLoading(true);
    const s = { ...src };

    // Wake up Render backend (free tier sleeps after 15 min of inactivity)
    await pingBackend();

    const [price, klines, dvol, hv, book, poly, ks, sm, mr] = await Promise.allSettled([
      fetchBtcPrice(), fetchKlines(), fetchDvol(), fetchHistVol(),
      fetchOptionsBook(), fetchBackendPolymarket(), fetchKellySignals(), fetchSmartMoney(),
      fetchMacroReport(),
    ]);

    const lPrice = price.status === "fulfilled" ? price.value : null;
    if (lPrice) { setBtcPrice(lPrice); s.price = "live"; }
    else         { setBtcPrice(67340 + Math.floor((Math.random() - .5) * 800)); s.price = "seed"; }

    const lKlines = klines.status === "fulfilled" ? klines.value : null;
    if (lKlines) {
      const rv = calcRealizedVol(lKlines), wv = calcWeekdayVol(lKlines);
      if (rv) setHourlyVol(rv);
      if (wv) setWeekdayVol(wv);
      s.klines = "live";
    } else {
      setHourlyVol(seedHourlyVol());
      setWeekdayVol(seedWeekdayVol());
      s.klines = "seed";
    }

    const lDvol = dvol.status === "fulfilled" ? dvol.value : null;
    if (lDvol) { setDvolData(lDvol); s.dvol = "live"; }
    else        { setDvolData(seedDvol()); s.dvol = "seed"; }

    const lHv = hv.status === "fulfilled" ? hv.value : null;
    if (lHv) { setHistVol(lHv); s.histVol = "live"; }
    else      { setHistVol(seedHistVol()); s.histVol = "seed"; }

    const lBook = book.status === "fulfilled" ? book.value : null;
    if (lBook) { setVolSurface(lBook); s.book = "live"; }
    else        { setVolSurface(seedVolSurface()); s.book = "seed"; }

    const lPoly = poly.status === "fulfilled" ? poly.value : null;
    if (lPoly && Array.isArray(lPoly)) {
      setPolyMarkets(lPoly); s.poly = "live";
    } else {
      const direct = await fetchPolymarketDirect();
      if (direct) { setPolyMarkets(direct); s.poly = "live"; }
      else         { setPolyMarkets(seedPolymarket()); s.poly = "seed"; }
    }

    const lKs = ks.status === "fulfilled" ? ks.value : null;
    if (lKs?.opportunities) { setKellySignals(lKs); s.alpha = "live"; }

    const lSm = sm.status === "fulfilled" ? sm.value : null;
    if (lSm?.signals) { setSmartMoney(lSm); if (s.alpha !== "live") s.alpha = "live"; }

    const lMr = mr.status === "fulfilled" ? mr.value : null;
    if (lMr?.categories) { setMacroReport(lMr); s.macro = "live"; }

    // Merge DVOL implied vol into hourly buckets
    setHourlyVol(prev => prev.map(h => {
      const dvArr  = lDvol ?? [];
      const match  = dvArr.filter(d => d.hour === h.hour);
      const avg    = match.length
        ? match.reduce((a, d) => a + d.close, 0) / match.length
        : (s.klines === "seed" ? EMP_IV[h.hour] : null);
      return { ...h, impliedVol: avg ? +avg.toFixed(1) : h.impliedVol };
    }));

    setSrc(s);
    setLastUpdate(new Date());
    setLoading(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  const nowUTC = new Date().getUTCHours();
  const sess   = getSession(nowUTC);
  const liveN  = Object.values(src).filter(s => s === "live").length;
  const total  = Object.keys(src).length;

  return (
    <div style={{ minHeight: "100vh", background: T.bg, color: T.text, fontFamily: T.sans, colorScheme: "dark" }}>
      <style>{globalCss}</style>

      {/* Header */}
      <header className="fade-up" style={{ borderBottom: `1px solid ${T.ln}` }}>
        <div style={{ maxWidth: 1140, margin: "0 auto", padding: "14px 20px", display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div className="glow-pulse" style={{
              width: 36, height: 36, borderRadius: 12, flexShrink: 0, overflow: "hidden",
              boxShadow: "0 0 18px rgba(52,211,153,.22)",
            }}>
              <img src="/logo.png" alt="Alpha Feed" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: 15, fontWeight: 800, letterSpacing: "-.02em", color: T.text }}>
                Alpha <span style={{ color: T.green }}>Feed</span>
              </h1>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                {["Deribit", "Binance", "Polymarket", "Smart Money"].map((s, i, a) => (
                  <span key={s} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: ".18em", color: T.dim }}>{s}</span>
                    {i < a.length - 1 && <span style={{ color: "#1c1c24" }}>·</span>}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 11 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: T.dim }}>
              <Dot ok={liveN > 0} />
              <span style={{ fontFamily: T.mono, fontSize: 10 }}>{liveN}/{total} live</span>
            </div>
            <span style={{ color: T.ln }}>|</span>
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.dim }}>{lastUpdate ? lastUpdate.toLocaleTimeString() : "—"}</span>
            <button onClick={load} disabled={loading} className="btn-refresh">{loading ? "Loading…" : "Refresh"}</button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <nav style={{ borderBottom: `1px solid ${T.ln}` }}>
        <div style={{ maxWidth: 1140, margin: "0 auto", padding: "8px 20px", display: "flex", gap: 4, overflowX: "auto" }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`tab-btn${tab === t.id ? " on" : ""}`}>
              <span style={{ fontSize: 8, opacity: .6 }}>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main style={{ maxWidth: 1140, margin: "0 auto", padding: "20px" }}>
        {tab === "overview"   && <OverviewTab      btcPrice={btcPrice} dvolData={dvolData} polyMarkets={polyMarkets} nowUTC={nowUTC} sess={sess} hourlyVol={hourlyVol} srcPrice={src.price} srcDvol={src.dvol} srcPoly={src.poly} />}
        {tab === "volatility" && <VolCurveTab      hourlyVol={hourlyVol} weekdayVol={weekdayVol} histVol={histVol} nowUTC={nowUTC} srcKlines={src.klines} srcHistVol={src.histVol} />}
        {tab === "options"    && <TermStructureTab volSurface={volSurface} srcBook={src.book} />}
        {tab === "polymarket" && <PolymarketTab    polyAnalysis={polyMarkets} srcPoly={src.poly} />}
        {tab === "alpha"      && <AlphaTab         kellySignals={kellySignals} srcAlpha={src.alpha} />}
        {tab === "hedge"      && <HedgeTab />}
        {tab === "macro"      && <MacroReportTab   macroReport={macroReport} srcMacro={src.macro} />}
        {tab === "bankroll"   && <BankrollTab />}
        {tab === "apis"       && <ConfigTab        src={src} />}
      </main>

      {/* Footer */}
      <footer style={{ borderTop: `1px solid ${T.ln}`, marginTop: 8 }}>
        <div style={{ maxWidth: 1140, margin: "0 auto", padding: "12px 20px", display: "flex", flexWrap: "wrap", justifyContent: "space-between", fontSize: 9, color: T.dim }}>
          <span>Alpha Feed · {liveN > 0 ? `${liveN}/${total} live` : "Seed mode"} · Free APIs · Not financial advice</span>
          <span style={{ fontFamily: T.mono }}>{lastUpdate ? lastUpdate.toLocaleTimeString() : ""}</span>
        </div>
      </footer>
    </div>
  );
}
