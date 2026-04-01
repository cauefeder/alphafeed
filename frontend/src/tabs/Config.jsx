import { T } from "../tokens.js";
import { Panel, Dot, LiveBadge, SeedBadge } from "../components/primitives.jsx";

const API_SOURCES = [
  { name: "Binance Price",   ep: "api.binance.com/api/v3/ticker/price",                    desc: "Real-time BTC/USDT spot price",          key: "price"   },
  { name: "Binance Klines",  ep: "api.binance.com/api/v3/klines",                          desc: "7d hourly candles → realized vol",       key: "klines"  },
  { name: "Deribit DVOL",    ep: "deribit.com/api/v2/public/get_volatility_index_data",    desc: "48h implied vol index (hourly)",         key: "dvol"    },
  { name: "Deribit HV",      ep: "deribit.com/api/v2/public/get_historical_volatility",    desc: "15d annualized realized vol",            key: "histVol" },
  { name: "Deribit Options", ep: "deribit.com/api/v2/public/get_book_summary_by_currency", desc: "Full BTC options chain",                 key: "book"    },
  { name: "Polymarket",      ep: "gamma-api.polymarket.com/markets (via /api/polymarket)", desc: "Markets + resolvesIn enrichment",        key: "poly"    },
  { name: "Alpha Signals",   ep: "alphafeed.onrender.com/api/kelly-signals",               desc: "~90 smart money traders — Kelly signals refreshed twice daily", key: "alpha"   },
];


export function ConfigTab({ src }) {
  return (
    <div>
      <Panel title="Data Source Status" sub="Live sources attempt real-time fetch; others fall back to seed data" delay="d1">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {API_SOURCES.map((a, i) => {
            const live = src[a.key] === "live";
            return (
              <div key={i} className={`fade-up d${Math.min(i + 1, 6)}`} style={{
                display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px", borderRadius: 12,
                background: live ? "rgba(52,211,153,.025)" : "rgba(16,16,20,.6)",
                border: `1px solid ${live ? "rgba(52,211,153,.14)" : T.ln}`,
              }}>
                <div style={{ marginTop: 2 }}><Dot ok={live} /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: T.sub }}>{a.name}</span>
                    {live ? <LiveBadge /> : <SeedBadge />}
                  </div>
                  <p style={{ fontSize: 10, color: T.dim, margin: "2px 0 0" }}>{a.desc}</p>
                  <code style={{ fontSize: 9, display: "block", marginTop: 2, color: T.ln2, fontFamily: T.mono }}>{a.ep}</code>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

    </div>
  );
}
