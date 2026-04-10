import { T } from "../tokens.js";
import { Panel } from "../components/primitives.jsx";

const CAT_ORDER = ["macro", "geopolitics", "crypto", "stocks", "ai_tech", "politics"];

function fmt(vol) {
  if (vol >= 1e6) return `$${(vol / 1e6).toFixed(1)}M`;
  if (vol >= 1e3) return `$${(vol / 1e3).toFixed(0)}K`;
  return `$${vol}`;
}

function PriceBar({ price }) {
  if (price == null) return <span style={{ color: T.dim, fontFamily: T.mono }}>—</span>;
  const pct = Math.round(price * 100);
  const color = pct >= 70 ? T.green : pct <= 30 ? T.red : T.amber;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 44, height: 4, borderRadius: 2, overflow: "hidden", background: T.ln }}>
        <div style={{ height: "100%", borderRadius: 2, width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontFamily: T.mono, fontSize: 10, color, minWidth: 28, textAlign: "right" }}>{pct}%</span>
    </div>
  );
}

function TextSummary({ topVolume, categories }) {
  if (!topVolume?.length) return null;

  // Pick top 5 unique by volume
  const top5 = topVolume.slice(0, 5);

  // Find dominant category by total vol
  const catVols = CAT_ORDER.map(cat => {
    const info = categories?.[cat];
    if (!info?.markets?.length) return null;
    const total = info.markets.reduce((s, m) => s + (m.volume_24h || 0), 0);
    return { name: info.name, emoji: info.emoji, total, count: info.count };
  }).filter(Boolean).sort((a, b) => b.total - a.total);

  const dominant = catVols[0];

  // Markets close to resolving (< 3 days)
  const urgent = topVolume.filter(m => m.days_left != null && m.days_left < 3 && m.days_left >= 0);

  // High conviction (price > 80% or < 20%)
  const highConv = topVolume.filter(m => m.yes_price != null && (m.yes_price > 0.80 || m.yes_price < 0.20));

  return (
    <div style={{
      marginBottom: 24, padding: 16, borderRadius: 12,
      background: "rgba(52,211,153,.03)", border: `1px solid rgba(52,211,153,.10)`,
      lineHeight: 1.75, fontSize: 11, color: T.sub,
    }}>
      <div style={{ fontWeight: 700, color: T.green, marginBottom: 8, fontSize: 12 }}>
        Market Intelligence Summary
      </div>

      {/* Top volume line */}
      <p style={{ margin: "0 0 8px" }}>
        The highest-activity market today is{" "}
        <a href={top5[0].url} target="_blank" rel="noreferrer"
          style={{ color: T.text, fontWeight: 600, textDecoration: "none" }}>
          "{top5[0].question.slice(0, 70)}{top5[0].question.length > 70 ? "…" : ""}"
        </a>
        {" "}with <span style={{ color: T.amber, fontFamily: T.mono }}>{fmt(top5[0].volume_24h)}</span> in 24h volume
        at a{" "}
        <span style={{ color: top5[0].yes_price > 0.5 ? T.green : T.red, fontFamily: T.mono }}>
          {top5[0].yes_price != null ? `${Math.round(top5[0].yes_price * 100)}%` : "?"}
        </span>
        {" "}YES probability.
      </p>

      {/* Top 2-5 volume */}
      {top5.length > 1 && (
        <p style={{ margin: "0 0 8px" }}>
          Other high-volume markets include{" "}
          {top5.slice(1).map((m, i, arr) => (
            <span key={i}>
              <a href={m.url} target="_blank" rel="noreferrer"
                style={{ color: T.sub, textDecoration: "none" }}>
                "{m.question.slice(0, 50)}{m.question.length > 50 ? "…" : ""}"
              </a>
              {" "}(<span style={{ fontFamily: T.mono, color: T.amber }}>{fmt(m.volume_24h)}</span>,{" "}
              <span style={{ fontFamily: T.mono, color: m.yes_price > 0.5 ? T.green : T.red }}>
                {m.yes_price != null ? `${Math.round(m.yes_price * 100)}%` : "?"}
              </span> YES)
              {i < arr.length - 1 ? "; " : "."}
            </span>
          ))}
        </p>
      )}

      {/* Dominant category */}
      {dominant && (
        <p style={{ margin: "0 0 8px" }}>
          {dominant.emoji} <strong style={{ color: T.text }}>{dominant.name}</strong> is the most active sector
          with {dominant.count} markets tracked and{" "}
          <span style={{ fontFamily: T.mono, color: T.amber }}>{fmt(dominant.total)}</span> total 24h volume.
        </p>
      )}

      {/* Urgent markets */}
      {urgent.length > 0 && (
        <p style={{ margin: "0 0 8px" }}>
          <span style={{ color: T.red, fontWeight: 600 }}>⚑ Resolving soon:</span>{" "}
          {urgent.slice(0, 3).map((m, i, arr) => (
            <span key={i}>
              <a href={m.url} target="_blank" rel="noreferrer" style={{ color: T.sub, textDecoration: "none" }}>
                "{m.question.slice(0, 45)}{m.question.length > 45 ? "…" : ""}"
              </a>
              {" "}in <span style={{ fontFamily: T.mono }}>{m.days_left?.toFixed(1)}d</span>
              {i < arr.length - 1 ? "; " : "."}
            </span>
          ))}
        </p>
      )}

      {/* High conviction */}
      {highConv.length > 0 && (
        <p style={{ margin: 0 }}>
          <span style={{ color: T.green, fontWeight: 600 }}>High conviction signals</span>
          {" "}(crowd &gt;80% or &lt;20%):{" "}
          {highConv.slice(0, 3).map((m, i, arr) => (
            <span key={i}>
              <a href={m.url} target="_blank" rel="noreferrer" style={{ color: T.sub, textDecoration: "none" }}>
                "{m.question.slice(0, 45)}{m.question.length > 45 ? "…" : ""}"
              </a>
              {" "}at <span style={{ fontFamily: T.mono, color: m.yes_price > 0.5 ? T.green : T.red }}>
                {Math.round(m.yes_price * 100)}%
              </span>
              {i < arr.length - 1 ? "; " : "."}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

function CategoryCard({ cat }) {
  if (!cat.markets.length) return null;
  return (
    <div className="fade-up" style={{
      borderRadius: 14, border: `1px solid ${T.ln}`,
      background: "rgba(18,18,26,.6)", marginBottom: 20, overflow: "hidden",
    }}>
      <div style={{
        padding: "12px 16px", borderBottom: `1px solid ${T.ln}`,
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <span style={{ fontSize: 16 }}>{cat.emoji}</span>
        <div>
          <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>{cat.name}</span>
          <span style={{ marginLeft: 8, fontSize: 10, color: T.dim }}>{cat.count} market{cat.count !== 1 ? "s" : ""}</span>
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${T.ln}`, color: T.dim }}>
              {["Market", "YES Prob", "24h Vol", "Total Vol", "Resolves"].map((h, i) => (
                <th key={h} style={{ padding: "8px 12px", fontWeight: 600, textAlign: i === 0 ? "left" : "right" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cat.markets.slice(0, 10).map((m, i) => (
              <tr key={i} style={{ borderBottom: `1px solid rgba(28,28,36,.4)` }}>
                <td style={{ padding: "8px 12px", maxWidth: 300, color: T.sub }}>
                  {m.url
                    ? <a href={m.url} target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "none", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.question}</a>
                    : <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.question}</span>}
                </td>
                <td style={{ padding: "8px 12px" }}>
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <PriceBar price={m.yes_price} />
                  </div>
                </td>
                <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: T.mono, color: T.text }}>
                  {fmt(m.volume_24h)}
                </td>
                <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>
                  {fmt(m.volume_total)}
                </td>
                <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: T.mono, color: T.dim }}>
                  {m.days_left != null ? `${m.days_left}d` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function MacroReportTab({ macroReport, srcMacro }) {
  const live = srcMacro === "live" && !!macroReport?.generatedAt;
  const cats = macroReport?.categories ?? {};
  const topVolume = macroReport?.topVolume ?? [];
  const hasData = macroReport?.totalMarkets > 0;

  return (
    <div>
      <Panel
        title="Polymarket Macro Intelligence"
        sub={macroReport?.generatedAt
          ? `Last run: ${new Date(macroReport.generatedAt).toLocaleString()} · ${macroReport.totalMarkets ?? 0} markets classified`
          : "Run backend/adapters/poly2_export.py to populate"}
        live={live}
        delay="d1"
      >
        {!hasData ? (
          <div style={{ padding: "32px 0", textAlign: "center", fontSize: 11, color: T.dim }}>
            No data — run <code style={{ color: T.green }}>python backend/adapters/poly2_export.py</code>
          </div>
        ) : (
          <>
            {/* AI-style text summary */}
            <TextSummary topVolume={topVolume} categories={cats} />

            {/* Top volume strip */}
            {topVolume.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 10, color: T.dim, fontWeight: 600, letterSpacing: ".12em", textTransform: "uppercase", marginBottom: 10 }}>
                  Top Volume (24h)
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {topVolume.slice(0, 6).map((m, i) => (
                    <a key={i} href={m.url} target="_blank" rel="noreferrer" style={{
                      textDecoration: "none", display: "flex", flexDirection: "column", gap: 4,
                      padding: "10px 14px", borderRadius: 10, background: "rgba(52,211,153,.04)",
                      border: `1px solid rgba(52,211,153,.12)`, minWidth: 180, flex: "1 1 180px", maxWidth: 260,
                    }}>
                      <span style={{ fontSize: 10, color: T.sub, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {m.question.slice(0, 55)}
                      </span>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontFamily: T.mono, fontSize: 11, color: T.green, fontWeight: 700 }}>
                          {m.yes_price != null ? `${Math.round(m.yes_price * 100)}%` : "—"}
                        </span>
                        <span style={{ fontFamily: T.mono, fontSize: 10, color: T.dim }}>
                          {fmt(m.volume_24h)} vol
                        </span>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Category tables */}
            {CAT_ORDER.map(cat => cats[cat] && cats[cat].count > 0
              ? <CategoryCard key={cat} cat={cats[cat]} />
              : null
            )}
          </>
        )}
      </Panel>

      <div className="fade-up d3" style={{ borderRadius: 14, padding: 16, background: "rgba(52,211,153,.02)", border: `1px solid rgba(52,211,153,.08)` }}>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
          <span style={{ color: T.green, fontWeight: 700 }}>How this works: </span>
          Fetches ~800 Polymarket markets and classifies them into 6 macro categories: Macroeconomics, Geopolitics, Crypto, Stocks, AI/Tech, and Politics.
          YES probability reflects the crowd's real-money estimate.{" "}
          <strong style={{ color: T.text }}>Resolves</strong> = days until market settles — high-volume markets close to resolution carry the strongest signal.
          Data refreshes at 08:00 and 20:00 UTC via GitHub Actions.
        </p>
      </div>
    </div>
  );
}
