import { T } from "../tokens.js";
import { Panel, Badge } from "../components/primitives.jsx";

export function AlphaTab({ kellySignals, smartMoney, srcAlpha }) {
  const kellyLive = srcAlpha === "live" && !!kellySignals.generatedAt;
  const smartLive = srcAlpha === "live" && !!smartMoney.generatedAt;

  return (
    <div>
      <Panel
        title="Kelly Opportunities — Smart Money Consensus"
        sub={kellySignals.generatedAt
          ? `Last run: ${new Date(kellySignals.generatedAt).toLocaleString()} · ${kellySignals.tradersChecked ?? "?"} traders · ${kellySignals.positionsScanned ?? "?"} positions`
          : "Run backend/adapters/polytraders_export.py to populate"}
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

      <Panel
        title="Smart Money Signals — HedgePoly Consensus"
        sub={smartMoney.generatedAt
          ? `Last run: ${new Date(smartMoney.generatedAt).toLocaleString()} · ${smartMoney.signalCount ?? smartMoney.signals?.length ?? 0} signals`
          : "Run backend/adapters/hedgepoly_export.py to populate"}
        live={smartLive}
        delay="d2"
      >
        {smartMoney.signals?.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${T.ln}`, color: T.dim }}>
                  {["Market", "Side", "Traders", "Confidence", "YES $", "NO $"].map((h, i) => (
                    <th key={h} style={{ padding: "9px 10px", fontWeight: 600, textAlign: i === 0 ? "left" : "right" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {smartMoney.signals.slice(0, 12).map((sig, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid rgba(28,28,36,.5)` }}>
                    <td style={{ padding: "9px 10px", maxWidth: 280, color: T.sub }}>
                      {sig.url
                        ? <a href={sig.url} target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "none", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sig.question?.slice(0, 55)}</a>
                        : <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sig.question?.slice(0, 55)}</span>}
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right" }}>
                      <Badge color={sig.side === "YES" ? "green" : "red"}>{sig.side}</Badge>
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>{sig.traderCount}</td>
                    <td style={{ padding: "9px 10px", textAlign: "right" }}>
                      <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <div style={{ width: 40, height: 4, borderRadius: 2, overflow: "hidden", background: T.ln }}>
                          <div style={{
                            height: "100%", borderRadius: 2,
                            width: `${(sig.confidence ?? 0) * 100}%`,
                            background: sig.side === "YES"
                              ? `linear-gradient(90deg,${T.green},#10b981)`
                              : `linear-gradient(90deg,${T.red},#ef4444)`,
                          }} />
                        </div>
                        <span style={{ fontFamily: T.mono, fontSize: 10, color: T.sub }}>{((sig.confidence ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.green }}>
                      ${sig.yesValue >= 1e3 ? `${(sig.yesValue / 1e3).toFixed(0)}k` : sig.yesValue?.toFixed(0) ?? "—"}
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.red }}>
                      ${sig.noValue >= 1e3 ? `${(sig.noValue / 1e3).toFixed(0)}k` : sig.noValue?.toFixed(0) ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: "32px 0", textAlign: "center", fontSize: 11, color: T.dim }}>
            No signals — run <code style={{ color: T.green }}>python backend/adapters/hedgepoly_export.py</code>
          </div>
        )}
      </Panel>

      <div className="fade-up d3" style={{ borderRadius: 14, padding: 16, background: "rgba(52,211,153,.02)", border: `1px solid rgba(52,211,153,.08)` }}>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
          <span style={{ color: T.green, fontWeight: 700 }}>How this works: </span>
          Kelly Opportunities track the top 25 Polymarket traders by weekly PnL and find markets where ≥2 agree.
          Smart Money Signals aggregate HedgePoly consensus by USD exposure direction.
          Both use the public Polymarket leaderboard. Refresh via the adapter scripts or schedule as a cron job.
        </p>
      </div>
    </div>
  );
}
