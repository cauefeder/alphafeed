import { T } from "../tokens.js";
import { Badge } from "./primitives.jsx";
import { formatResolvesIn, resolvesColor } from "../math.js";

// ── Signal-strength dots (Unc. column) ───────────────────────────────────────

function SignalDots({ value }) {
  const filled = Math.round((value ?? 0) * 5);
  const col = value > 0.65 ? T.green : value > 0.38 ? T.amber : T.red;
  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 3, justifyContent: "flex-end" }}
      title={`Uncertainty: ${Math.round((value ?? 0) * 100)}%`}
    >
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} style={{
          display: "inline-block", width: 5, height: 5, borderRadius: "50%",
          background: i <= filled ? col : "rgba(35,35,42,.7)",
          boxShadow: i <= filled ? `0 0 4px ${col}80` : "none",
          transition: "background .2s",
        }} />
      ))}
    </div>
  );
}

// ── Table cell helpers ────────────────────────────────────────────────────────

function TH({ children, right = false }) {
  return (
    <th style={{
      padding: "10px 12px", fontSize: 9, fontWeight: 700,
      textTransform: "uppercase", letterSpacing: ".08em",
      color: T.dim, textAlign: right ? "right" : "left",
    }}>{children}</th>
  );
}

function TD({ children, right = false, mono = false, color, truncate = false }) {
  return (
    <td style={{
      padding: "10px 12px", textAlign: right ? "right" : "left",
      fontFamily: mono ? T.mono : undefined, color: color ?? T.sub,
    }}>
      {truncate
        ? <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{children}</span>
        : children}
    </td>
  );
}

// ── Main table ────────────────────────────────────────────────────────────────

export function PolyTable({ markets, limit = 8, compact = false }) {
  return (
    <div style={{ overflowX: "auto", margin: "0 -4px" }}>
      <table style={{ width: "100%", fontSize: 11, tableLayout: "fixed" }}>
        <colgroup>
          <col style={{ width: compact ? "42%" : "36%" }} />
          <col style={{ width: "7%" }} />
          {!compact && <col style={{ width: "7%" }} />}
          {!compact && <col style={{ width: "7%" }} />}
          {!compact && <col style={{ width: "9%" }} />}
          <col style={{ width: "10%" }} />
          <col style={{ width: "10%" }} />
          <col style={{ width: "9%" }} />
          <col style={{ width: compact ? "14%" : "10%" }} />
        </colgroup>
        <thead>
          <tr style={{ borderBottom: `1px solid ${T.ln}` }}>
            <TH>Market</TH>
            <TH right>Yes</TH>
            {!compact && <TH right>No</TH>}
            {!compact && <TH right>Spread</TH>}
            {!compact && <TH right>Unc.</TH>}
            <TH right>24h Vol</TH>
            <TH right>Liq.</TH>
            <TH right>Resolves</TH>
            <TH right>Edge</TH>
          </tr>
        </thead>
        <tbody>
          {markets.slice(0, limit).map((m, i) => (
            <tr key={i} style={{ borderBottom: `1px solid rgba(28,28,36,.5)` }}>
              <TD color={T.sub} truncate>{m.question?.slice(0, compact ? 48 : 56)}</TD>
              <TD right mono color={T.green}>{(m.yesPrice * 100).toFixed(0)}¢</TD>
              {!compact && <TD right mono color={T.red}>{(m.noPrice * 100).toFixed(0)}¢</TD>}
              {!compact && <TD right mono color={T.dim}>{(m.spread * 100).toFixed(1)}¢</TD>}
              {!compact && (
                <td style={{ padding: "10px 12px", textAlign: "right" }}>
                  <SignalDots value={m.uncertainty} />
                </td>
              )}
              <TD right mono color={T.dim}>
                ${m.volume24hr >= 1e3 ? `${(m.volume24hr / 1e3).toFixed(0)}k` : m.volume24hr}
              </TD>
              <TD right mono color={T.dim}>
                ${m.liquidity >= 1e3 ? `${(m.liquidity / 1e3).toFixed(0)}k` : m.liquidity}
              </TD>
              <TD right mono color={resolvesColor(m.resolvesIn, T)}>
                {formatResolvesIn(m.resolvesIn)}
              </TD>
              <td style={{ padding: "10px 12px", textAlign: "right" }}>
                <Badge color={m.edgeScore > .5 ? "green" : m.edgeScore > .2 ? "amber" : "zinc"}>
                  {m.edgeScore.toFixed(compact ? 2 : 3)}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
