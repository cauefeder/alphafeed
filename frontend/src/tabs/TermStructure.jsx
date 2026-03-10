import {
  ComposedChart, Bar, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { T } from "../tokens.js";
import { Panel, Badge, ChartTip } from "../components/primitives.jsx";

export function TermStructureTab({ volSurface, srcBook }) {
  return (
    <div>
      <Panel title="BTC Options IV Term Structure" sub="Average mark IV by expiry · Deribit book summary" live={srcBook === "live"} delay="d1">
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={volSurface} margin={{ top: 10, right: 40, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={T.ln} />
            <XAxis dataKey="expiry" tick={{ fill: T.sub, fontSize: 9 }} angle={-25} textAnchor="end" height={45} />
            <YAxis yAxisId="left"  tick={{ fill: T.dim, fontSize: 9 }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fill: T.ln, fontSize: 9 }} />
            <Tooltip content={<ChartTip />} />
            <Bar  yAxisId="right" dataKey="totalOI" name="Open Interest" fill="rgba(99,102,241,.06)" radius={[4, 4, 0, 0]} />
            <Line yAxisId="left" type="monotone" dataKey="avgIv"  name="Avg IV"  stroke={T.amber} strokeWidth={2.5} dot={{ r: 3.5, fill: T.amber, stroke: T.amber + "44", strokeWidth: 4 }} />
            <Line yAxisId="left" type="monotone" dataKey="callIv" name="Call IV" stroke={T.green} strokeWidth={1} dot={false} strokeDasharray="5 3" strokeOpacity={.6} />
            <Line yAxisId="left" type="monotone" dataKey="putIv"  name="Put IV"  stroke={T.red}   strokeWidth={1} dot={false} strokeDasharray="5 3" strokeOpacity={.6} />
          </ComposedChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="Expiry Detail" delay="d2">
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: 11 }}>
            <thead>
              <tr style={{ color: T.dim, borderBottom: `1px solid ${T.ln}` }}>
                {["Expiry", "Avg IV", "Call", "Put", "Skew", "OI", "Volume"].map((h, i) => (
                  <th key={h} style={{ padding: "9px 10px", fontWeight: 600, textAlign: i === 0 ? "left" : "right" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {volSurface.map((v, i) => {
                const sk = v.putIv - v.callIv;
                return (
                  <tr key={i} style={{ borderBottom: `1px solid rgba(28,28,36,.5)` }}>
                    <td style={{ padding: "9px 10px", fontFamily: T.mono, color: T.sub }}>{v.expiry}</td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.amber }}>{v.avgIv}%</td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.green }}>{v.callIv}%</td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.red }}>{v.putIv}%</td>
                    <td style={{ padding: "9px 10px", textAlign: "right" }}>
                      <Badge color={sk > 5 ? "red" : sk < -5 ? "green" : "zinc"}>{sk > 0 ? "+" : ""}{sk.toFixed(1)}</Badge>
                    </td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>{Number(v.totalOI).toLocaleString()}</td>
                    <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>{Number(v.totalVol).toLocaleString()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="fade-up d3" style={{ borderRadius: 14, padding: 16, background: "rgba(99,102,241,.03)", border: "1px solid rgba(99,102,241,.1)" }}>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
          <span style={{ color: "#818cf8", fontWeight: 700 }}>Reading the curve: </span>
          Upward slope = more vol expected ahead (normal). Flat or inverted = near-term event risk.
          Put IV &gt; Call IV = bearish hedging demand. High-OI expiries act as price magnets.
        </p>
      </div>
    </div>
  );
}
