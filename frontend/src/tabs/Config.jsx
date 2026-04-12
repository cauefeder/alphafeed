import { T } from "../tokens.js";
import { Panel, Dot, LiveBadge, SeedBadge } from "../components/primitives.jsx";

const API_SOURCES = [
  { name: "Binance Price",   ep: "api.binance.com/api/v3/ticker/price",                    desc: "Real-time BTC/USDT spot price",          key: "price",   reportKey: null       },
  { name: "Binance Klines",  ep: "api.binance.com/api/v3/klines",                          desc: "7d hourly candles → realized vol",       key: "klines",  reportKey: null       },
  { name: "Deribit DVOL",    ep: "deribit.com/api/v2/public/get_volatility_index_data",    desc: "48h implied vol index (hourly)",         key: "dvol",    reportKey: null       },
  { name: "Deribit HV",      ep: "deribit.com/api/v2/public/get_historical_volatility",    desc: "15d annualized realized vol",            key: "histVol", reportKey: null       },
  { name: "Deribit Options", ep: "deribit.com/api/v2/public/get_book_summary_by_currency", desc: "Full BTC options chain",                 key: "book",    reportKey: null       },
  { name: "Polymarket",      ep: "gamma-api.polymarket.com/markets (via /api/polymarket)", desc: "Markets + resolvesIn enrichment",        key: "poly",    reportKey: null       },
  { name: "Kelly Signals",   ep: "reports/polytraders.json → /api/kelly-signals",          desc: "Smart money traders — refreshes 08:00 & 20:00 UTC", key: "alpha", reportKey: "polytraders" },
  { name: "Smart Money",     ep: "reports/hedgepoly.json → /api/smart-money",              desc: "HedgePoly signals — refreshes 08:00 & 20:00 UTC",   key: "alpha", reportKey: "hedgepoly"   },
  { name: "Macro Report",    ep: "reports/poly2.json → /api/macro-report",                 desc: "Macro categories — refreshes 08:00 & 20:00 UTC",    key: "macro", reportKey: "poly2"       },
  { name: "Quant Report",    ep: "reports/quant_report.json → /api/quant-report",          desc: "XGBoost scores — refreshes 08:00 & 20:00 UTC",      key: "quant", reportKey: "quant_report"},
];

function StaleBadge() {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase",
      padding: "2px 6px", borderRadius: 99,
      background: "rgba(251,191,36,.12)", color: "#fbbf24",
      border: "1px solid rgba(251,191,36,.25)",
    }}>Stale</span>
  );
}

function MissingBadge() {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase",
      padding: "2px 6px", borderRadius: 99,
      background: "rgba(239,68,68,.12)", color: "#ef4444",
      border: "1px solid rgba(239,68,68,.25)",
    }}>Missing</span>
  );
}

export function ConfigTab({ src, health }) {
  return (
    <div>
      <Panel title="Data Source Status" sub="Live sources attempt real-time fetch; report sources refresh via GitHub Actions cron" delay="d1">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {API_SOURCES.map((a, i) => {
            const live = src[a.key] === "live";
            const rh = health && a.reportKey ? health[a.reportKey] : null;
            const isStale = rh?.status === "stale";
            const isMissing = rh?.status === "missing";
            const ageLabel = rh?.age_hours != null ? `${rh.age_hours}h ago` : null;

            return (
              <div key={i} className={`fade-up d${Math.min(i + 1, 6)}`} style={{
                display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px", borderRadius: 12,
                background: isStale || isMissing
                  ? "rgba(251,191,36,.03)"
                  : live ? "rgba(52,211,153,.025)" : "rgba(16,16,20,.6)",
                border: `1px solid ${isStale || isMissing ? "rgba(251,191,36,.18)" : live ? "rgba(52,211,153,.14)" : T.ln}`,
              }}>
                <div style={{ marginTop: 2 }}><Dot ok={live && !isStale && !isMissing} /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: T.sub }}>{a.name}</span>
                    {isMissing ? <MissingBadge /> : isStale ? <StaleBadge /> : live ? <LiveBadge /> : <SeedBadge />}
                    {ageLabel && !isMissing && (
                      <span style={{ fontSize: 9, color: isStale ? "#fbbf24" : T.dim, fontFamily: T.mono }}>
                        updated {ageLabel}
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: 10, color: T.dim, margin: "2px 0 0" }}>{a.desc}</p>
                  <code style={{ fontSize: 9, display: "block", marginTop: 2, color: T.ln2, fontFamily: T.mono }}>{a.ep}</code>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      {health && Object.values(health).some(r => r.status === "stale" || r.status === "missing") && (
        <div className="fade-up d3" style={{ borderRadius: 14, padding: 14, background: "rgba(251,191,36,.04)", border: "1px solid rgba(251,191,36,.18)", marginTop: 8 }}>
          <p style={{ fontSize: 11, color: "#fbbf24", margin: 0 }}>
            One or more report files are stale or missing. GitHub Actions refreshes them at 08:00 and 20:00 UTC.
            You can trigger a manual run from the{" "}
            <a href="https://github.com/cauefeder/alphafeed/actions/workflows/refresh-reports.yml"
               target="_blank" rel="noreferrer" style={{ color: "#fbbf24" }}>
              Actions tab
            </a>.
          </p>
        </div>
      )}
    </div>
  );
}
