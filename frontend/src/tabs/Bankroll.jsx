import { useState, useMemo } from "react";
import { T } from "../tokens.js";
import { KELLY_FRACTIONS, kellyFraction, expectedValue, maxDrawdown, formatDollars, formatPct } from "../math.js";
import { Divider, StepLabel } from "../components/primitives.jsx";

// ── Local sub-components ──────────────────────────────────────────────────────

function BInput({ label, value, onChange, suffix, prefix, min = 0, max, step = 1, hint }) {
  return (
    <div style={{ marginBottom: 13 }}>
      <label style={{ display: "block", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".09em", color: T.sub, marginBottom: 5 }}>
        {label}
      </label>
      <div className="inp">
        {prefix && <span style={{ color: T.green, fontSize: 13, marginRight: 8, fontWeight: 700, fontFamily: T.mono }}>{prefix}</span>}
        <input type="number" value={value} onChange={e => onChange(Number(e.target.value))} min={min} max={max} step={step} />
        {suffix && <span style={{ color: T.dim, fontSize: 12, marginLeft: 8 }}>{suffix}</span>}
      </div>
      {hint && <div style={{ fontSize: 10, color: T.dim, marginTop: 4, paddingLeft: 2 }}>{hint}</div>}
    </div>
  );
}

function BCard({ label, value, sub, color = T.blue, warn = false, hero = false }) {
  return (
    <div className={`mcard${warn ? " warn" : ""}${hero ? " hero" : ""}`}>
      <div style={{ fontSize: 10, color: T.sub, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: hero ? 10 : 6 }}>{label}</div>
      <div style={{ fontSize: hero ? 34 : 20, fontWeight: 800, fontFamily: T.mono, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: T.dim, marginTop: hero ? 10 : 6, lineHeight: 1.5 }}>{sub}</div>}
    </div>
  );
}

function StratPanel({ title, icon, params, setParams, activeDays, color }) {
  const fk  = kellyFraction(params.wr, params.aw, params.al);
  const ev  = expectedValue(params.wr, params.aw, params.al);
  const wev = ev * params.tpd * activeDays;

  return (
    <div style={{
      background: T.s1, borderRadius: 18, padding: 22, flex: "1 1 290px", minWidth: 270,
      border: `1px solid ${color}1c`, boxShadow: `inset 0 0 0 1px ${color}08`,
    }}>
      <div style={{ height: 2, borderRadius: 2, marginBottom: 18, background: `linear-gradient(90deg,${color},${color}00)` }} />
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 10, fontSize: 16,
          background: `${color}12`, border: `1px solid ${color}22`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>{icon}</div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>{title}</div>
          <div style={{ fontSize: 10, color: T.dim, marginTop: 1 }}>{activeDays} active days / week</div>
        </div>
        <span style={{
          marginLeft: "auto", fontSize: 10, padding: "3px 9px", borderRadius: 99, fontWeight: 700, letterSpacing: ".05em",
          background: ev > 0 ? "rgba(52,211,153,.1)" : "rgba(241,113,113,.1)",
          color: ev > 0 ? T.green : T.red,
          border: `1px solid ${ev > 0 ? "rgba(52,211,153,.25)" : "rgba(241,113,113,.25)"}`,
        }}>{ev > 0 ? "EDGE +" : "NO EDGE"}</span>
      </div>

      <BInput label="Win Rate"            value={params.wr}  onChange={v => setParams({ ...params, wr: v })}  suffix="%" min={1} max={99} step={0.5} />
      <BInput label="Avg Win / trade"     value={params.aw}  onChange={v => setParams({ ...params, aw: v })}  prefix="$" min={1} />
      <BInput label="Avg Loss / trade"    value={params.al}  onChange={v => setParams({ ...params, al: v })}  prefix="$" min={1} />
      <BInput label="Trades / active day" value={params.tpd} onChange={v => setParams({ ...params, tpd: v })} min={1} max={50} hint={`${params.tpd * activeDays} trades / week`} />

      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 16,
        padding: 14, borderRadius: 12, background: `${color}08`, border: `1px solid ${color}14`,
      }}>
        {[
          { lbl: "Full Kelly", val: formatPct(fk),                         col: color },
          { lbl: "EV / Trade", val: ev > 0 ? `+${formatDollars(ev)}` : formatDollars(ev), col: ev > 0 ? T.green : T.red },
          { lbl: "Weekly EV",  val: wev > 0 ? `+${formatDollars(wev)}` : formatDollars(wev), col: wev > 0 ? T.green : T.red },
        ].map(m => (
          <div key={m.lbl} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 9, color: T.dim, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 4 }}>{m.lbl}</div>
            <div style={{ fontSize: 13, fontWeight: 800, fontFamily: T.mono, color: m.col }}>{m.val}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function BankrollTab() {
  const [kIdx,    setKIdx]    = useState(1);
  const [target,  setTarget]  = useState(150);
  const [reserve, setReserve] = useState(25);
  const [poly, setPoly] = useState({ wr: 58, aw: 120, al: 100, tpd: 3 });
  const [btc,  setBtc]  = useState({ wr: 55, aw: 200, al: 150, tpd: 2 });

  const km = KELLY_FRACTIONS[kIdx].value;

  const R = useMemo(() => {
    const pfk = kellyFraction(poly.wr, poly.aw, poly.al);
    const bfk = kellyFraction(btc.wr,  btc.aw,  btc.al);
    const pk  = pfk * km, bk = bfk * km;
    const pev = expectedValue(poly.wr, poly.aw, poly.al);
    const bev = expectedValue(btc.wr,  btc.aw,  btc.al);
    const pwt = poly.tpd * 2, bwt = btc.tpd * 2;
    const pwev = pev * pwt, bwev = bev * bwt, twev = pwev + bwev, wtgt = target * 4;

    let pn = 0, bn = 0;
    if (pk > 0 && pev > 0) { const sh = pwev > 0 ? pwev / Math.max(twev, 1) : .5; pn = Math.max(0, (wtgt * sh) / (pk * (pev / poly.al) * pwt || 1)); }
    if (bk > 0 && bev > 0) { const sh = bwev > 0 ? bwev / Math.max(twev, 1) : .5; bn = Math.max(0, (wtgt * sh) / (bk * (bev / btc.al)  * bwt || 1)); }

    const w   = pn + bn, rf = reserve / 100, tot = w / (1 - rf);
    const pa  = tot > 0 ? pn / w : .5;
    const ept = (pev + bev) / 2, rt = ept > 0 ? Math.ceil(w * .15 / ept) : Infinity;
    const rw  = rt / ((pwt + bwt) || 1);

    return {
      tot: Math.round(tot), w: Math.round(w), res: Math.round(tot * rf),
      pn: Math.round(pn), bn: Math.round(bn),
      pp: Math.round(pk * pn), bp: Math.round(bk * bn),
      pa, ba: 1 - pa, pk, bk,
      pdd: maxDrawdown(km, pfk), bdd: maxDrawdown(km, bfk),
      wtgt, twev: Math.round(twev),
      ruin: km <= .5 ? "Very Low" : km <= .75 ? "Moderate" : "High",
      rw: rw.toFixed(1),
    };
  }, [poly, btc, km, target, reserve]);

  const bmax = Math.max(R.pn, R.bn, 1);
  const emet = R.twev >= R.wtgt;

  return (
    <div style={{ paddingTop: 4 }}>
      {/* Step 1 — Global Config */}
      <div className="card fade-up d1" style={{ padding: 24, marginBottom: 12 }}>
        <StepLabel n={1} label="Global Configuration" color={T.sub} />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
          <div style={{ flex: "1 1 160px" }}>
            <BInput label="Daily Profit Target" value={target} onChange={setTarget} prefix="$" min={10} hint={`Weekly target: ${formatDollars(target * 4)}`} />
          </div>
          <div style={{ flex: "1 1 160px" }}>
            <BInput label="Drawdown Reserve" value={reserve} onChange={setReserve} suffix="%" min={10} max={50} hint="Locked safety buffer — never traded" />
          </div>
          <div style={{ flex: "2 1 300px" }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".09em", color: T.sub, marginBottom: 8 }}>Kelly Fraction</div>
            <div style={{ display: "flex", gap: 6 }}>
              {KELLY_FRACTIONS.map((k, i) => (
                <button key={i} className={`kbtn${i === kIdx ? " on" : ""}`} onClick={() => setKIdx(i)}>
                  {k.label}
                  <div style={{ fontSize: 9, opacity: .5, marginTop: 3, fontWeight: 500 }}>{k.sub}</div>
                </button>
              ))}
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: T.dim }}>
              Using <span style={{ color: T.green, fontWeight: 700 }}>{KELLY_FRACTIONS[kIdx].long}</span> —
              bets {KELLY_FRACTIONS[kIdx].value * 100}% of the theoretically optimal Kelly stake.
              {km === 1 && <span style={{ color: T.amber }}> High variance — use with caution.</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Step 2 — Strategy Parameters */}
      <div className="card fade-up d2" style={{ padding: 24, marginBottom: 12 }}>
        <StepLabel n={2} label="Strategy Parameters" color={T.blue} />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          <StratPanel title="Polymarket"    icon="🎯" params={poly} setParams={setPoly} activeDays={2} color={T.blue} />
          <StratPanel title="BTC Volatility" icon="₿" params={btc}  setParams={setBtc}  activeDays={2} color={T.amber} />
        </div>
      </div>

      {/* Step 3 — Recommended Bankroll */}
      <div className="card fade-up d3" style={{ padding: 24, marginBottom: 12, borderColor: "rgba(52,211,153,.18)" }}>
        <StepLabel n={3} label="Recommended Bankroll" color={T.green} />

        <div className="mcard hero" style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 10, color: T.sub, textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 10 }}>Total Capital Required</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 18, flexWrap: "wrap" }}>
            <div style={{ fontSize: 38, fontWeight: 900, fontFamily: T.mono, color: T.green, lineHeight: 1 }}>{formatDollars(R.tot)}</div>
            <div style={{ display: "flex", gap: 18 }}>
              <span style={{ fontSize: 12, color: T.sub }}>Working <span style={{ color: T.text, fontWeight: 700, fontFamily: T.mono }}>{formatDollars(R.w)}</span></span>
              <span style={{ fontSize: 12, color: T.sub }}>Reserve <span style={{ color: T.dim, fontWeight: 700, fontFamily: T.mono }}>{formatDollars(R.res)}</span></span>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <BCard label="Weekly Target" value={formatDollars(R.wtgt)} sub={`${formatDollars(target)} / day × 4 active days`} color={T.blue} />
          <BCard
            label="Expected Weekly EV"
            value={R.twev >= 0 ? `+${formatDollars(R.twev)}` : formatDollars(R.twev)}
            sub={emet ? "✓ On track to meet target" : "⚠ Below target — adjust inputs or increase bankroll"}
            color={emet ? T.green : T.amber} warn={!emet}
          />
        </div>

        <Divider label="Capital Allocation" />
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            { label: "Polymarket",       icon: "🎯", amount: R.pn,  pct: R.pa,         color: T.blue,  fixed: false },
            { label: "BTC Volatility",   icon: "₿",  amount: R.bn,  pct: R.ba,         color: T.amber, fixed: false },
            { label: "Drawdown Reserve", icon: "🛡",  amount: R.res, pct: reserve / 100, color: T.dim,   fixed: true  },
          ].map((row, i) => (
            <div key={i}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
                <span style={{ fontSize: 12, color: row.color, fontWeight: 600 }}>{row.icon} {row.label}</span>
                <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                  <span style={{ fontSize: 13, fontWeight: 700, fontFamily: T.mono, color: T.text }}>{formatDollars(row.amount)}</span>
                  <span style={{ fontSize: 11, color: T.dim, fontFamily: T.mono, minWidth: 34, textAlign: "right" }}>{(row.pct * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{
                  width: row.fixed ? `${reserve}%` : `${(row.amount / bmax) * 100}%`,
                  background: `linear-gradient(90deg,${row.color},${row.color}44)`,
                }} />
              </div>
            </div>
          ))}
        </div>

        <Divider label="Position Sizing per Trade" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <BCard label="Polymarket Position" value={formatDollars(R.pp)} sub={`${formatPct(R.pk)} of Polymarket bankroll`} color={T.blue} />
          <BCard label="BTC Position"        value={formatDollars(R.bp)} sub={`${formatPct(R.bk)} of BTC bankroll`}        color={T.amber} />
        </div>

        <Divider label="Risk Analysis" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <BCard label="Ruin Risk"         value={R.ruin}           sub={KELLY_FRACTIONS[kIdx].long}  color={R.ruin === "Very Low" ? T.green : R.ruin === "Moderate" ? T.amber : T.red} warn={R.ruin === "High"} />
          <BCard label="Poly Max Drawdown" value={formatPct(R.pdd)} sub="Estimated worst case"         color={T.blue} />
          <BCard label="BTC Max Drawdown"  value={formatPct(R.bdd)} sub="Estimated worst case"         color={T.amber} />
          <BCard label="Recovery Time"     value={`~${R.rw}w`}      sub="After 15% drawdown"           color={T.purple} />
        </div>
      </div>

      {/* Schedule + Rules */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
        <div className="card fade-up d4" style={{ flex: "1 1 280px", padding: 22 }}>
          <div style={{ fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".1em", color: T.sub, marginBottom: 14 }}>📅 Weekly Schedule</div>
          <div style={{ display: "flex", gap: 5 }}>
            {[
              { d: "Mon", k: null },
              { d: "Tue", k: null },
              { d: "Wed", k: "btc" },
              { d: "Thu", k: null },
              { d: "Fri", k: "btc" },
              { d: "Sat", k: "poly" },
              { d: "Sun", k: "poly" },
            ].map(({ d, k }) => {
              const col  = k === "poly" ? T.blue : k === "btc" ? T.amber : null;
              const icon = k === "poly" ? `🎯×${poly.tpd}` : k === "btc" ? `₿×${btc.tpd}` : "–";
              return (
                <div key={d} className="dpill" style={{ background: col ? `${col}08` : "transparent", borderColor: col ? `${col}22` : T.ln }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: col ?? T.dim }}>{d}</div>
                  <div style={{ fontSize: 9, color: col ?? T.ln, marginTop: 5, lineHeight: 1.3 }}>{icon}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card fade-up d5" style={{ flex: "1 1 280px", padding: 22, borderColor: "rgba(241,113,113,.12)" }}>
          <div style={{ fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".1em", color: T.red, marginBottom: 14 }}>🚨 Drawdown Rules</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {[
              { lvl: "10% DD",  act: "Reduce to ¼-Kelly sizing",               col: T.amber },
              { lvl: "15% DD",  act: "Halve position sizes · review assumptions", col: T.amber },
              { lvl: "25% DD",  act: "Stop trading — re-evaluate models",        col: T.red   },
              { lvl: "Monthly", act: "Rebalance allocations between strategies",  col: T.blue  },
            ].map((r, i) => (
              <div key={i} className="rule-row" style={{ borderLeft: `3px solid ${r.col}` }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: r.col, minWidth: 62, fontFamily: T.mono }}>{r.lvl}</span>
                <span style={{ fontSize: 11, color: T.text }}>{r.act}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ textAlign: "center", padding: "12px 0 4px", fontSize: 10, color: T.dim }}>
        Adjust parameters above — all outputs update live · Fractional Kelly with drawdown reserve · Not financial advice
      </div>
    </div>
  );
}
