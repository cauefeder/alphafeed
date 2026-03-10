import {
  AreaChart, Area, BarChart, Bar, ComposedChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell,
} from "recharts";
import { T } from "../tokens.js";
import { SESSIONS } from "../math.js";
import { Panel, ChartTip } from "../components/primitives.jsx";

export function VolCurveTab({ hourlyVol, weekdayVol, histVol, nowUTC, srcKlines, srcHistVol }) {
  return (
    <div>
      <Panel title="Intraday Realized Volatility" sub="7-day hourly log-return σ, annualized · purple = DVOL implied" live={srcKlines === "live"} delay="d1">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={hourlyVol} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={T.ln} />
            <XAxis dataKey="label" tick={{ fill: T.sub, fontSize: 10 }} />
            <YAxis tick={{ fill: T.dim, fontSize: 10 }} />
            <Tooltip content={<ChartTip />} />
            <ReferenceLine
              x={`${String(nowUTC).padStart(2, "0")}:00`}
              stroke={T.green} strokeDasharray="3 3" strokeOpacity={.5}
              label={{ value: "NOW", fill: T.green, fontSize: 8, opacity: .7 }}
            />
            <Bar dataKey="realizedVol" name="Realized %" radius={[5, 5, 0, 0]}>
              {hourlyVol.map((d, i) => {
                const sess = SESSIONS.find(s => d.hour >= s.s && d.hour <= s.e) ?? SESSIONS[4];
                return <Cell key={i} fill={sess.c + "aa"} />;
              })}
            </Bar>
            <Line type="monotone" dataKey="impliedVol" name="Implied (DVOL)" stroke="#a78bfa" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginTop: 12 }}>
          {SESSIONS.map(s => (
            <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 9, color: T.dim }}>
              <span style={{ width: 8, height: 8, borderRadius: 3, backgroundColor: s.c, opacity: .7 }} />
              {s.name}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 14, borderRadius: 12, padding: 14, background: "rgba(251,191,36,.03)", border: "1px solid rgba(251,191,36,.08)" }}>
          <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
            <span style={{ color: T.amber, fontWeight: 700 }}>Straddle signal: </span>
            Where bars exceed the purple line → realized beats implied → vol is cheap →{" "}
            <span style={{ color: T.green, fontWeight: 700 }}>BUY straddle</span>.
            NY Open (13–16 UTC) consistently peaks.
          </p>
        </div>
      </Panel>

      <Panel title="Day-of-Week Volatility" sub="Which days produce the biggest BTC moves?" live={srcKlines === "live"} delay="d2">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={weekdayVol} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={T.ln} />
            <XAxis dataKey="day" tick={{ fill: T.sub, fontSize: 11 }} />
            <YAxis tick={{ fill: T.dim, fontSize: 10 }} />
            <Tooltip content={<ChartTip />} />
            <Bar dataKey="vol" name="Ann Vol %" radius={[5, 5, 0, 0]}>
              {weekdayVol.map((d, i) => (
                <Cell key={i} fill={d.vol > 65 ? T.amber : d.vol > 45 ? "#a78bfa" : T.dim} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="Historical Realized Volatility" sub="15-day series from Deribit" live={srcHistVol === "live"} delay="d3">
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={histVol} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="hg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#6366f1" stopOpacity={.2} />
                <stop offset="100%" stopColor="#6366f1" stopOpacity={0}  />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={T.ln} />
            <XAxis dataKey="date" tick={{ fill: T.dim, fontSize: 9 }} interval={2} />
            <YAxis tick={{ fill: T.dim, fontSize: 9 }} />
            <Tooltip content={<ChartTip />} />
            <Area type="monotone" dataKey="vol" name="HV %" stroke="#818cf8" fill="url(#hg)" strokeWidth={1.5} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}
