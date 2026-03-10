import { AreaChart, Area, ComposedChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { T } from "../tokens.js";
import { Stat, Panel, ChartTip } from "../components/primitives.jsx";
import { PolyTable } from "../components/PolyTable.jsx";

export function OverviewTab({ btcPrice, dvolData, polyMarkets, hourlyVol, nowUTC, sess, srcPrice, srcDvol, srcPoly }) {
  const curDVOL = dvolData.length ? dvolData[dvolData.length - 1]?.close : null;
  const curHV   = hourlyVol?.find(h => h.hour === nowUTC);

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10, marginBottom: 14 }}>
        <Stat label="BTC / USD"  value={`$${btcPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} sub={srcPrice === "live" ? "Binance spot" : "Seed"} delay="d1" />
        <Stat label="DVOL"       value={curDVOL ? `${curDVOL.toFixed(1)}%` : "—"} sub="30d implied vol" accent={curDVOL > 60} delay="d2" />
        <Stat label="Session"    value={sess?.name ?? "—"} sub={`${String(nowUTC).padStart(2, "0")}:00 UTC`} delay="d3" />
        <Stat label="Hourly RV"  value={curHV ? `${curHV.realizedVol}%` : "—"} sub="Annualized" delay="d4" />
        <Stat label="Poly Opps"  value={polyMarkets.filter(p => p.edgeScore > .3).length} sub={`of ${polyMarkets.length}`} accent delay="d5" />
      </div>

      <Panel title="DVOL Index — 48 Hours" sub="Deribit BTC implied volatility index · hourly" live={srcDvol === "live"} delay="d2">
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={dvolData.slice(-48)} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="dg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor={T.amber} stopOpacity={.15} />
                <stop offset="100%" stopColor={T.amber} stopOpacity={0}   />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={T.ln} />
            <XAxis dataKey="time" tick={{ fill: T.dim, fontSize: 9 }} interval={5} />
            <YAxis tick={{ fill: T.dim, fontSize: 9 }} domain={["auto", "auto"]} />
            <Tooltip content={<ChartTip />} />
            <Area type="monotone" dataKey="close" name="DVOL" stroke={T.amber} fill="url(#dg)" strokeWidth={1.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="Top Polymarket Opportunities" sub="Ranked by edge score · Resolves column shows days until resolution" live={srcPoly === "live"} delay="d3">
        <PolyTable markets={polyMarkets} limit={8} compact />
      </Panel>
    </div>
  );
}
