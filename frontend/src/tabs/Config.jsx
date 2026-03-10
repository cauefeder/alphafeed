import { T } from "../tokens.js";
import { Panel, Dot, LiveBadge, SeedBadge } from "../components/primitives.jsx";

const API_SOURCES = [
  { name: "Binance Price",   ep: "api.binance.com/api/v3/ticker/price",                    desc: "Real-time BTC/USDT spot price",          key: "price"   },
  { name: "Binance Klines",  ep: "api.binance.com/api/v3/klines",                          desc: "7d hourly candles → realized vol",       key: "klines"  },
  { name: "Deribit DVOL",    ep: "deribit.com/api/v2/public/get_volatility_index_data",    desc: "48h implied vol index (hourly)",         key: "dvol"    },
  { name: "Deribit HV",      ep: "deribit.com/api/v2/public/get_historical_volatility",    desc: "15d annualized realized vol",            key: "histVol" },
  { name: "Deribit Options", ep: "deribit.com/api/v2/public/get_book_summary_by_currency", desc: "Full BTC options chain",                 key: "book"    },
  { name: "Polymarket",      ep: "gamma-api.polymarket.com/markets (via /api/polymarket)", desc: "Markets + resolvesIn enrichment",        key: "poly"    },
  { name: "Alpha Signals",   ep: "localhost:8000/api/kelly-signals + /api/smart-money",    desc: "PolyTraders + HedgePoly signals",        key: "alpha"   },
];

const QUICK_START_STEPS = [
  {
    n: "1", label: "Backend",
    cmds:     ["cd backend && pip install -r requirements.txt", "uvicorn server:app --reload --port 8000"],
    comments: ["# Install deps", "# Start API server"],
  },
  {
    n: "2", label: "Alpha Signals (optional)",
    cmds:     ["python backend/adapters/polytraders_export.py", "python backend/adapters/hedgepoly_export.py"],
    comments: ["# Run once to populate reports/*.json", ""],
  },
  {
    n: "3", label: "Frontend",
    cmds:     ["cd frontend && npm install && npm run dev"],
    comments: ["# Visit http://localhost:3000"],
  },
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

      <Panel title="Quick Start" sub="Get Alpha Feed running locally in 3 steps" delay="d2">
        <div style={{ display: "flex", flexDirection: "column", gap: 16, fontSize: 11, color: T.sub }}>
          {QUICK_START_STEPS.map(step => (
            <div key={step.n}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".09em", color: T.dim, marginBottom: 8 }}>
                {step.n}. {step.label}
              </div>
              <div style={{ borderRadius: 12, padding: 14, overflowX: "auto", background: "rgba(0,0,0,.5)", border: `1px solid ${T.ln}`, fontFamily: T.mono, fontSize: 10 }}>
                {step.cmds.map((cmd, i) => (
                  <div key={i}>
                    {step.comments[i] && <div style={{ color: T.dim }}>{step.comments[i]}</div>}
                    <div style={{ color: T.green }}>{cmd}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <p>All APIs are <strong style={{ color: T.green }}>free, no auth required</strong>. Deribit APIs may require a VPN in some regions.</p>
        </div>
      </Panel>
    </div>
  );
}
