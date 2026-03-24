// frontend/src/tabs/Hedge.jsx
import { useState } from "react";
import { T } from "../tokens.js";
import { postHedgeSession } from "../api.js";

const RISK_TYPES = [
  { value: "",            label: "Select risk type (optional)" },
  { value: "risk-off",    label: "Risk-off / Market crash" },
  { value: "rate-hike",   label: "Rate hike" },
  { value: "recession",   label: "Recession" },
  { value: "geopolitical",label: "Geopolitical conflict" },
  { value: "crypto-crash",label: "Crypto crash" },
  { value: "tech-selloff",label: "Tech selloff" },
  { value: "other",       label: "Other" },
];

function CorrBadge({ score }) {
  const color = score >= 7 ? T.green : score >= 4 ? "#f59e0b" : T.dim;
  return (
    <span style={{ fontFamily: T.mono, fontSize: 11, color, fontWeight: 700,
      background: color + "18", padding: "2px 7px", borderRadius: 6 }}>
      {score.toFixed(1)} corr
    </span>
  );
}

function HedgeCard({ h }) {
  const [open, setOpen] = useState(false);
  const sideColor = h.hedge_side === "YES" ? T.green : "#f87171";
  return (
    <div style={{ background: T.card, border: `1px solid ${T.ln}`, borderRadius: 10, padding: "14px 16px", marginBottom: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <CorrBadge score={h.correlation_score} />
        <span style={{ fontSize: 11, fontWeight: 700, color: sideColor,
          background: sideColor + "20", padding: "2px 8px", borderRadius: 5 }}>
          {h.hedge_side}
        </span>
        {h.cross_signal && (
          <span title="Smart money + LLM agree" style={{ fontSize: 11, color: "#fbbf24" }}>⭐ cross-signal</span>
        )}
        <a href={h.url} target="_blank" rel="noopener noreferrer"
          style={{ color: T.text, fontWeight: 600, fontSize: 13, textDecoration: "none", flex: 1 }}>
          {h.question}
        </a>
      </div>

      <div style={{ display: "flex", gap: 20, marginTop: 10, flexWrap: "wrap", fontSize: 11, color: T.dim, fontFamily: T.mono }}>
        <span>YES {h.yes_price != null ? (h.yes_price * 100).toFixed(0) + "¢" : "—"}</span>
        <span>${h.volume_24h != null ? (h.volume_24h / 1000).toFixed(0) + "k" : "—"} vol</span>
        <span>{h.days_left != null ? h.days_left + "d" : "—"} left</span>
        {h.kelly_bet != null && <span style={{ color: "#fbbf24" }}>Kelly ${h.kelly_bet.toFixed(2)}</span>}
        {h.smart_money_exposure != null && <span>${(h.smart_money_exposure / 1000).toFixed(0)}k smart $</span>}
      </div>

      <button onClick={() => setOpen(o => !o)}
        style={{ marginTop: 8, background: "none", border: "none", cursor: "pointer",
          color: T.dim, fontSize: 11, padding: 0 }}>
        {open ? "▲ hide" : "▼ show analysis"}
      </button>
      {open && (
        <p style={{ marginTop: 8, fontSize: 12, color: T.dim, lineHeight: 1.6 }}>{h.narrative}</p>
      )}
    </div>
  );
}

export function HedgeTab() {
  const [exposure, setExposure] = useState("");
  const [asset, setAsset] = useState("");
  const [riskType, setRiskType] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | results | error
  const [result, setResult] = useState(null);

  async function handleRun() {
    if (!exposure.trim()) return;
    setStatus("loading");
    setResult(null);
    const data = await postHedgeSession({ exposure, asset, riskType });
    if (!data) { setStatus("error"); return; }
    setResult(data);
    setStatus("results");
  }

  const inp = {
    background: T.card, border: `1px solid ${T.ln}`, borderRadius: 8,
    color: T.text, fontSize: 13, padding: "8px 12px", width: "100%", boxSizing: "border-box",
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      {/* Input */}
      <div style={{ background: T.card, border: `1px solid ${T.ln}`, borderRadius: 12, padding: 20, marginBottom: 16 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color: T.text }}>🛡️ Hedge Session</h2>
        <p style={{ margin: "0 0 14px", fontSize: 11, color: T.dim }}>
          Describe your exposure. The system finds Polymarket bets that pay out in your worst case.
        </p>
        <textarea value={exposure} onChange={e => setExposure(e.target.value)} rows={3}
          placeholder='e.g. "I hold 2 BTC and I am worried about a tariff-driven risk-off event crashing crypto markets"'
          style={{ ...inp, resize: "vertical", marginBottom: 10 }} />
        <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
          <input value={asset} onChange={e => setAsset(e.target.value)}
            placeholder="Asset (optional, e.g. BTC)"
            style={{ ...inp, flex: 1, minWidth: 140 }} />
          <select value={riskType} onChange={e => setRiskType(e.target.value)}
            style={{ ...inp, flex: 1, minWidth: 200 }}>
            {RISK_TYPES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        <button onClick={handleRun} disabled={status === "loading" || !exposure.trim()}
          style={{ background: T.green, color: "#000", border: "none", borderRadius: 8,
            padding: "9px 20px", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
          {status === "loading" ? "Analysing your exposure…" : "Run Hedge"}
        </button>
      </div>

      {/* Parsed exposure card */}
      {status === "results" && result?.exposure_parsed && (
        <div style={{ background: T.card, border: `1px solid ${T.ln}`, borderRadius: 10,
          padding: "12px 16px", marginBottom: 16, fontSize: 12 }}>
          <span style={{ color: T.dim }}>Analysed as: </span>
          <strong style={{ color: T.text }}>{result.exposure_parsed.asset}</strong>
          <span style={{ color: T.dim }}> · {result.exposure_parsed.direction} · {result.exposure_parsed.risk_type}</span>
          <p style={{ margin: "6px 0 0", color: T.dim, fontStyle: "italic" }}>{result.exposure_parsed.scenario}</p>
        </div>
      )}

      {/* Hedge list */}
      {status === "results" && result?.hedges?.length > 0 && (
        <div>
          <p style={{ fontSize: 11, color: T.dim, marginBottom: 10 }}>
            {result.hedges.length} hedge{result.hedges.length !== 1 ? "s" : ""} found — sorted by correlation
          </p>
          {result.hedges.map(h => <HedgeCard key={h.slug} h={h} />)}
        </div>
      )}

      {status === "results" && result?.hedges?.length === 0 && (
        <p style={{ color: T.dim, fontSize: 13, textAlign: "center", padding: 40 }}>
          No hedges found with sufficient correlation. Try broadening your description.
        </p>
      )}

      {status === "error" && (
        <p style={{ color: "#f87171", fontSize: 13, textAlign: "center", padding: 40 }}>
          Failed to fetch hedges — backend may be starting up (free tier). Wait 30s and try again.
        </p>
      )}
    </div>
  );
}
