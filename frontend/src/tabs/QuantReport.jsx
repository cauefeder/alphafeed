import { useState } from "react";
import { T } from "../tokens.js";
import { Panel, Badge, Stat } from "../components/primitives.jsx";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, ReferenceLine, Cell,
} from "recharts";

// ── Helpers ───────────────────────────────────────────────────────────────────

function tierColor(tier) {
  if (tier === "A") return T.green;
  if (tier === "B") return T.amber;
  return T.dim;
}

function edgeColor(label) {
  if (label === "Strong edge" || label === "Good edge") return T.green;
  if (label === "Moderate edge") return T.amber;
  return T.red ?? T.dim;
}

const CAT_EMOJIS = {
  macro: "📊", politics: "🏛️", geopolitics: "🌍", crypto: "🔷",
  stocks: "📈", ai_tech: "🤖", sports: "⚽", other: "◈",
};

const PROB_COLOR = (p) => p >= 0.70 ? T.green : p >= 0.30 ? T.amber : T.dim;

// ── Section 1: Summary strip ──────────────────────────────────────────────────

function SummaryStrip({ report }) {
  const s = report.summary ?? {};
  const contrary = (report.opportunities ?? []).filter(o => o.contraryFlag).length;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 12 }}>
      <Stat label="Week of"           value={report.weekOf ?? "—"}                />
      <Stat label="Markets scored"    value={s.totalScored ?? 0}                  />
      <Stat label="Tier A signals"    value={s.tierA ?? 0}           accent        />
      <Stat label="Contrarian plays"  value={contrary}                             />
      <Stat label="Model AUC"         value={report.modelAuc?.toFixed(3) ?? "—"}  />
    </div>
  );
}

// ── Section 2: Macro Pulse ────────────────────────────────────────────────────

function MacroPulse({ categoryTrends }) {
  const entries = Object.entries(categoryTrends ?? {});
  if (!entries.length) return null;
  return (
    <Panel title="Market Pulse — Top Markets by Category" delay="d1">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
        {entries.map(([cat, data]) => (
          <div key={cat} style={{ background: T.s2, border: `1px solid ${T.ln}`, borderRadius: 12, padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <span>{CAT_EMOJIS[cat] ?? "◈"}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: T.text, textTransform: "capitalize" }}>{cat}</span>
              <span style={{ fontSize: 10, color: T.dim, marginLeft: "auto" }}>{data.totalMarkets} markets</span>
            </div>
            {(data.top3Markets ?? []).map((m, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 7 }}>
                <span style={{
                  flexShrink: 0, minWidth: 36, padding: "2px 5px", borderRadius: 99, fontSize: 9,
                  fontFamily: T.mono, textAlign: "center",
                  color: PROB_COLOR(m.yes_price),
                  background: `${PROB_COLOR(m.yes_price)}15`,
                  border: `1px solid ${PROB_COLOR(m.yes_price)}30`,
                }}>
                  {(m.yes_price * 100).toFixed(0)}%
                </span>
                <a href={m.url} target="_blank" rel="noreferrer" style={{
                  fontSize: 10, color: T.sub, textDecoration: "none", lineHeight: 1.4,
                  display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
                }}>
                  {m.question}
                </a>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ── Section 3: Signal vs Crowd Scatter ────────────────────────────────────────

function SignalScatter({ opportunities }) {
  if (!opportunities?.length) return null;
  const dots = opportunities.map(o => ({
    x: o.curPrice ?? 0,
    y: o.quantScore ?? 0,
    convergent: o.convergentScore ?? 0,
    contrary: o.contraryFlag ?? false,
    tier: o.signalTier,
    title: o.title,
  }));
  return (
    <Panel title="Signal vs Crowd — Model Score vs Crowd Probability"
           sub="Dots above 0.65 line are Tier A. Dot size reflects convergent score (quant × smart-money count). Stars are contrarian plays."
           delay="d2">
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 8, right: 24, bottom: 20, left: 0 }}>
          <CartesianGrid stroke={T.ln} strokeDasharray="3 3" />
          <XAxis dataKey="x" type="number" domain={[0, 1]} tickCount={6}
                 tickFormatter={v => `${(v * 100).toFixed(0)}%`}
                 label={{ value: "Crowd Prob", position: "insideBottom", offset: -10, fontSize: 10, fill: T.dim }} />
          <YAxis dataKey="y" type="number" domain={[0, 1]} tickCount={6}
                 tickFormatter={v => v.toFixed(2)}
                 label={{ value: "Signal", angle: -90, position: "insideLeft", fontSize: 10, fill: T.dim }} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0]?.payload;
              return (
                <div style={{ background: "#06060aF7", border: `1px solid ${T.ln}`, borderRadius: 10, padding: "8px 12px" }}>
                  <div style={{ fontSize: 10, color: T.sub, marginBottom: 4 }}>{d?.title?.slice(0, 55)}</div>
                  <div style={{ fontSize: 11, fontFamily: T.mono, color: tierColor(d?.tier) }}>
                    Tier {d?.tier} · signal {d?.y?.toFixed(3)} · crowd {(d?.x * 100)?.toFixed(0)}%
                  </div>
                  <div style={{ fontSize: 10, color: T.dim, marginTop: 3 }}>
                    convergent {d?.convergent?.toFixed(4)}
                    {d?.contrary && " · ⚡ contrarian"}
                  </div>
                </div>
              );
            }}
          />
          <ReferenceLine y={0.65} stroke={T.green} strokeDasharray="4 4"
                         label={{ value: "Tier A ≥ 0.65", position: "right", fontSize: 9, fill: T.green }} />
          <Scatter data={dots} fill={T.amber}>
            {dots.map((d, i) => (
              <Cell key={i}
                fill={d.contrary ? (T.red ?? T.dim) : tierColor(d.tier)}
                fillOpacity={d.contrary ? 1.0 : 0.8}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </Panel>
  );
}

// ── Section 4: Category bar chart ─────────────────────────────────────────────

function CategoryComparison({ categoryReport }) {
  const cats = Object.entries(categoryReport ?? {});
  if (!cats.length) return null;
  const data = cats
    .sort((a, b) => b[1].avgQuantScore - a[1].avgQuantScore)
    .map(([cat, d]) => ({
      name: `${CAT_EMOJIS[cat] ?? "◈"} ${cat}`,
      "Model Signal": +(d.avgQuantScore * 100).toFixed(1),
      "Tier A": d.tierACount,
    }));
  return (
    <Panel title="Category Signal Strength" sub="Avg model signal per category — scored opportunities only" delay="d3">
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 36)}>
        <BarChart data={data} layout="vertical" margin={{ left: 80, right: 16 }}>
          <CartesianGrid stroke={T.ln} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickFormatter={v => `${v}%`}
                 tick={{ fontSize: 10, fill: T.dim }} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: T.sub }} width={80} />
          <Tooltip formatter={(v, name) => [name === "Model Signal" ? `${v}%` : v, name]}
                   contentStyle={{ background: "#06060a", border: `1px solid ${T.ln}`, borderRadius: 10, fontSize: 10 }} />
          <Bar dataKey="Model Signal" fill={T.green} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  );
}

// ── Section 5: Edge ranking + insights ────────────────────────────────────────

function EdgeRankingAndInsights({ edgeRanking, insights }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 700, color: T.text }}>
          Edge Ranking — Where to Focus
        </h3>
        {(edgeRanking ?? []).map((r, i) => (
          <div key={r.category} style={{
            display: "flex", alignItems: "center", gap: 8, padding: "8px 0",
            borderBottom: i < edgeRanking.length - 1 ? `1px solid ${T.ln}` : "none",
          }}>
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.dim, width: 14 }}>{i + 1}</span>
            <span style={{
              padding: "2px 7px", borderRadius: 99, fontSize: 9, fontFamily: T.mono,
              color: edgeColor(r.label), background: `${edgeColor(r.label)}12`,
              border: `1px solid ${edgeColor(r.label)}25`,
            }}>{r.label}</span>
            <span style={{ fontSize: 11, color: T.text, textTransform: "capitalize", flex: 1 }}>
              {CAT_EMOJIS[r.category] ?? ""} {r.category}
            </span>
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.green }}>{(r.edgeScore * 100).toFixed(0)}%</span>
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.dim }}>{r.tierACount}A/{r.count}</span>
          </div>
        ))}
        {!edgeRanking?.length && (
          <div style={{ fontSize: 11, color: T.dim, padding: "16px 0" }}>No scored opportunities</div>
        )}
      </div>
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 700, color: T.text }}>
          Weekly Conclusions
        </h3>
        {(insights ?? []).length ? (
          <ol style={{ margin: 0, padding: "0 0 0 16px" }}>
            {insights.map((s, i) => (
              <li key={i} style={{ fontSize: 11, color: T.sub, lineHeight: 1.6, marginBottom: 8 }}>{s}</li>
            ))}
          </ol>
        ) : (
          <div style={{ fontSize: 11, color: T.dim }}>No insights generated.</div>
        )}
      </div>
    </div>
  );
}

// ── Section 6: Contrarian plays callout ───────────────────────────────────────

function ContrarianPlays({ opportunities }) {
  const plays = (opportunities ?? [])
    .filter(o => o.contraryFlag)
    .sort((a, b) => b.countSignal - a.countSignal);
  if (!plays.length) return null;
  return (
    <Panel
      title="Contrarian Plays — Crowd Certain, Smart Money Disagrees"
      sub="Crowd confidence is high (low quantScore) but >10% of tracked traders are positioned against it"
      delay="d4"
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 8 }}>
        {plays.map((opp, i) => (
          <div key={i} style={{
            background: T.s2, border: `1px solid ${(T.red ?? T.dim)}30`,
            borderRadius: 10, padding: "12px 14px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: T.red ?? T.dim }}>⚡</span>
              <span style={{ fontFamily: T.mono, fontSize: 10, color: T.red ?? T.dim }}>
                {(opp.countSignal * 100).toFixed(0)}% of traders
              </span>
              <span style={{ marginLeft: "auto", fontFamily: T.mono, fontSize: 10, color: T.dim }}>
                crowd {(opp.curPrice * 100).toFixed(0)}%
              </span>
            </div>
            {opp.url
              ? <a href={opp.url} target="_blank" rel="noreferrer"
                   style={{ fontSize: 11, color: T.sub, textDecoration: "none", lineHeight: 1.5, display: "block" }}>
                  {opp.title?.slice(0, 70)}
                </a>
              : <span style={{ fontSize: 11, color: T.sub }}>{opp.title?.slice(0, 70)}</span>
            }
            <div style={{ marginTop: 6, display: "flex", gap: 10 }}>
              <span style={{ fontSize: 10, color: T.dim }}>
                kelly ${opp.kellyBet?.toFixed(1)}
              </span>
              <span style={{ fontSize: 10, color: T.dim, textTransform: "capitalize" }}>
                {CAT_EMOJIS[opp.category] ?? ""} {opp.category}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ── Section 7: Opportunities table ───────────────────────────────────────────

const COLS = [
  { label: "Tier",       key: null },
  { label: "Market",     key: null },
  { label: "Signal",     key: "quantScore" },
  { label: "Convergent", key: "convergentScore" },
  { label: "Crowd",      key: "curPrice" },
  { label: "Info Ratio", key: "infoRatio" },
  { label: "Kelly Bet",  key: "kellyBet" },
];

function OpportunitiesTable({ opportunities }) {
  const [sortKey, setSortKey] = useState("convergentScore");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = [...(opportunities ?? [])].sort((a, b) => {
    const av = a[sortKey] ?? 0, bv = b[sortKey] ?? 0;
    return sortAsc ? av - bv : bv - av;
  });

  const handleHeaderClick = (key) => {
    if (!key) return;
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  return (
    <Panel title="Scored Opportunities"
           sub={`${Math.min(sorted.length, 20)} shown · sorted by convergent score by default · click column to sort`}
           delay="d5">
      {sorted.length ? (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.ln}`, color: T.dim }}>
                {COLS.map((col, i) => (
                  <th key={col.label}
                    style={{
                      padding: "9px 10px", fontWeight: 600,
                      textAlign: i <= 1 ? "left" : "right",
                      cursor: col.key ? "pointer" : "default",
                      color: col.key && sortKey === col.key ? T.text : T.dim,
                    }}
                    onClick={() => handleHeaderClick(col.key)}
                  >
                    {col.label}
                    {col.key && (sortKey === col.key ? (sortAsc ? " ▲" : " ▼") : " ·")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 20).map((opp, i) => (
                <tr key={i} style={{
                  borderBottom: `1px solid rgba(28,28,36,.5)`,
                  background: opp.contraryFlag ? `${(T.red ?? T.dim)}08` : "transparent",
                }}>
                  <td style={{ padding: "9px 10px" }}>
                    <Badge color={opp.signalTier === "A" ? "green" : opp.signalTier === "B" ? "amber" : "zinc"}>
                      {opp.signalTier}
                    </Badge>
                  </td>
                  <td style={{ padding: "9px 10px", maxWidth: 220, color: T.sub }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      {opp.contraryFlag && (
                        <span title="Contrarian play" style={{ fontSize: 10, color: T.red ?? T.dim, flexShrink: 0 }}>⚡</span>
                      )}
                      {opp.url
                        ? <a href={opp.url} target="_blank" rel="noreferrer"
                             style={{ color: "inherit", textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
                            {opp.title?.slice(0, 48)}
                          </a>
                        : <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>{opp.title?.slice(0, 48)}</span>
                      }
                    </div>
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: tierColor(opp.signalTier) }}>
                    {opp.quantScore?.toFixed(3) ?? "—"}
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.green }}>
                    {opp.convergentScore != null ? opp.convergentScore.toFixed(4) : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.sub }}>
                    {opp.curPrice != null ? `${(opp.curPrice * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>
                    {opp.infoRatio?.toFixed(3) ?? "—"}
                  </td>
                  <td style={{ padding: "9px 10px", textAlign: "right", fontFamily: T.mono, color: T.amber }}>
                    {opp.kellyBet != null ? `$${opp.kellyBet.toFixed(2)}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ padding: "32px 0", textAlign: "center", fontSize: 11, color: T.dim }}>
          No scored opportunities — run{" "}
          <code style={{ color: T.green }}>python backend/adapters/quant_report.py</code>
        </div>
      )}
    </Panel>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function QuantReportTab({ quantReport, srcQuant }) {
  return (
    <div>
      <SummaryStrip report={quantReport} />
      <MacroPulse categoryTrends={quantReport?.categoryTrends} />
      <SignalScatter opportunities={quantReport?.opportunities} />
      <CategoryComparison categoryReport={quantReport?.categoryReport} />
      <EdgeRankingAndInsights edgeRanking={quantReport?.edgeRanking} insights={quantReport?.insights} />
      <ContrarianPlays opportunities={quantReport?.opportunities} />
      <OpportunitiesTable opportunities={quantReport?.opportunities} />

      <div className="fade-up d5" style={{ borderRadius: 14, padding: 16, background: "rgba(52,211,153,.02)", border: "1px solid rgba(52,211,153,.08)" }}>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
          <span style={{ color: T.green, fontWeight: 700 }}>How this works: </span>
          XGBoost classifier trained on 5,000+ resolved Polymarket markets predicts crowd mispricing
          probability from price, volume, and liquidity features.{" "}
          <strong style={{ color: T.text }}>Convergent score</strong> = model signal &times; fraction of
          smart traders positioned there — the best combined signal.{" "}
          <strong style={{ color: T.red ?? T.dim }}>Contrarian plays</strong> mark markets where the
          crowd is confident but smart money disagrees.
          {quantReport?.modelAuc && ` Model AUC ${quantReport.modelAuc.toFixed(3)}`}
          {quantReport?.modelVersion && ` · trained ${quantReport.modelVersion}`}.
        </p>
      </div>
    </div>
  );
}
