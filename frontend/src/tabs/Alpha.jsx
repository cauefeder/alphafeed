import { T } from "../tokens.js";
import { Panel, Badge } from "../components/primitives.jsx";

export function AlphaTab({ kellySignals, srcAlpha }) {
  const kellyLive = srcAlpha === "live" && !!kellySignals.generatedAt;

  return (
    <div>
      <Panel
        title="Kelly Opportunities — Smart Money Consensus"
        sub={kellySignals.generatedAt
          ? `Last run: ${new Date(kellySignals.generatedAt).toLocaleString()} · ${kellySignals.tradersChecked ?? "?"} traders · ${kellySignals.positionsScanned ?? "?"} positions · ${kellySignals.opportunities?.length ?? 0} opportunities`
          : "Refreshes at 08:00 and 20:00 UTC via GitHub Actions"}
        live={kellyLive}
        delay="d1"
      >
        {kellySignals.opportunities?.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${T.ln}`, color: T.dim }}>
                  {["Market", "Side", "Price", "Edge", "Kelly Bet", "Traders", "Exposure"].map((h, i) => (
                    <th key={h} style={{ padding: "9px 10px", fontWeight: 600, textAlign: i === 0 ? "left" : "right" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {kellySignals.opportunities.slice(0, 12).map((opp, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid rgba(28,28,36,.5)` }}>
                    <td style={{ padding: "9px 10px", maxWidth: 260, color: T.sub }}>
                      {opp.url
                        ? <a href={opp.url} target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "none", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{opp.title?.slice(0, 52)}</a>
                        : <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{opp.title?.slice(0, 52)}</span>}
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right" }}>
                      <Badge color={opp.outcome?.toLowerCase().startsWith("y") ? "green" : "red"}>{opp.outcome}</Badge>
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.text }}>
                      {opp.curPrice != null ? (opp.curPrice * 100).toFixed(0) + "¢" : "—"}
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.green }}>
                      +{opp.estimatedEdge != null ? (opp.estimatedEdge * 100).toFixed(1) : "?"}pp
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, fontWeight: 700, color: T.amber }}>
                      ${opp.kellyBet?.toFixed(2) ?? "—"}
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>
                      {opp.nSmartTraders ?? "?"}/{opp.totalTradersChecked ?? "?"}
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>
                      ${opp.totalExposure >= 1e3 ? `${(opp.totalExposure / 1e3).toFixed(0)}k` : opp.totalExposure?.toFixed(0) ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: "32px 0", textAlign: "center", fontSize: 11, color: T.dim }}>
            No opportunities — run <code style={{ color: T.green }}>python backend/adapters/polytraders_export.py</code>
          </div>
        )}
      </Panel>

      <div className="fade-up d2" style={{ borderRadius: 14, padding: 16, background: "rgba(52,211,153,.02)", border: `1px solid rgba(52,211,153,.08)` }}>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
          <span style={{ color: T.green, fontWeight: 700 }}>How this works: </span>
          Tracks the top Polymarket traders across Overall, Crypto, and Politics leaderboards by weekly PnL and surfaces markets where ≥2 agree on the same side.
          Edge is estimated using rank-weighted signal strength, mean USD exposure, and entry-price discount.
          <strong style={{ color: T.text }}> Kelly Criterion</strong> with quarter-Kelly sizing caps each bet.
          Data refreshes automatically at 08:00 and 20:00 UTC via GitHub Actions.
        </p>
      </div>
    </div>
  );
}
