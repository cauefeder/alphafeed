import { T } from "../tokens.js";

// ── Status indicators ─────────────────────────────────────────────────────────

export function Dot({ ok }) {
  return (
    <span style={{
      display: "inline-block", width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
      background: ok ? T.green : T.dim,
      boxShadow: ok ? "0 0 5px rgba(52,211,153,.7)" : "none",
    }} />
  );
}

export function LiveBadge() {
  return <span className="badge-live px-2 py-0.5 rounded-full text-[9px] font-mono tracking-wider uppercase">Live</span>;
}

export function SeedBadge() {
  return <span className="badge-seed px-2 py-0.5 rounded-full text-[9px] font-mono tracking-wider uppercase">Seed</span>;
}

// ── Badge ─────────────────────────────────────────────────────────────────────

const BADGE_STYLES = {
  green:  { color: "#6ee7b7", bg: "rgba(52,211,153,.09)",  border: "rgba(52,211,153,.2)"  },
  red:    { color: "#fca5a5", bg: "rgba(248,113,113,.09)", border: "rgba(248,113,113,.2)" },
  amber:  { color: "#fcd34d", bg: "rgba(251,191,36,.09)",  border: "rgba(251,191,36,.2)"  },
  blue:   { color: "#93c5fd", bg: "rgba(147,197,253,.09)", border: "rgba(147,197,253,.2)" },
  zinc:   { color: T.dim,     bg: "rgba(30,30,38,.6)",     border: T.ln                   },
};

export function Badge({ children, color = "zinc" }) {
  const s = BADGE_STYLES[color] ?? BADGE_STYLES.zinc;
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 99, fontSize: 10, fontFamily: T.mono,
      color: s.color, background: s.bg, border: `1px solid ${s.border}`,
    }}>{children}</span>
  );
}

// ── Panel / Card ──────────────────────────────────────────────────────────────

export function Panel({ title, sub, live, children, delay = "", accent = false }) {
  return (
    <div className={`card fade-up ${delay}`} style={{
      marginBottom: 12, padding: 24,
      ...(accent ? { borderColor: "rgba(52,211,153,.2)", background: `linear-gradient(160deg,rgba(52,211,153,.04),${T.s1} 60%)` } : {}),
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18, gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: T.text, letterSpacing: "-.01em" }}>{title}</h3>
          {sub && <p style={{ margin: "5px 0 0", fontSize: 10, color: T.dim, lineHeight: 1.5 }}>{sub}</p>}
        </div>
        {live !== undefined && (
          <div style={{ flexShrink: 0, paddingTop: 2 }}>{live ? <LiveBadge /> : <SeedBadge />}</div>
        )}
      </div>
      {children}
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────

export function Stat({ label, value, sub, accent, change, delay = "" }) {
  return (
    <div className={`mcard fade-up ${delay}${accent ? " hero" : ""}`}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: ".14em", color: T.dim, marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span className={accent ? "shimmer-text" : ""} style={{
          fontSize: 20, fontWeight: 800, fontFamily: T.mono, letterSpacing: "-.02em",
          color: accent ? undefined : T.text, lineHeight: 1,
        }}>{value}</span>
        {change !== undefined && (
          <span style={{ fontSize: 10, fontFamily: T.mono, color: change >= 0 ? T.green : T.red }}>
            {change >= 0 ? "▲" : "▼"}{Math.abs(change).toFixed(1)}%
          </span>
        )}
      </div>
      {sub && <div style={{ fontSize: 9, marginTop: 6, color: T.dim }}>{sub}</div>}
    </div>
  );
}

// ── Chart tooltip ─────────────────────────────────────────────────────────────

export function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(6,6,10,.97)", border: `1px solid ${T.ln2}`,
      borderRadius: 12, padding: "10px 14px", backdropFilter: "blur(16px)",
    }}>
      <div style={{ fontSize: 10, fontFamily: T.mono, color: T.dim, marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: p.color, boxShadow: `0 0 4px ${p.color}88`, flexShrink: 0 }} />
          <span style={{ color: T.sub }}>{p.name}</span>
          <span style={{ fontFamily: T.mono, color: T.text, marginLeft: "auto", paddingLeft: 12 }}>
            {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Bankroll-specific primitives ──────────────────────────────────────────────

export function Divider({ label }) {
  return (
    <div className="sdiv">
      <div className="sdiv-ln" /><span className="sdiv-lbl">{label}</span><div className="sdiv-ln" />
    </div>
  );
}

export function StepLabel({ n, label, color = T.sub }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <div style={{
        width: 22, height: 22, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 800, fontFamily: T.mono,
        background: `${color}18`, border: `1px solid ${color}28`, color,
      }}>{String(n).padStart(2, "0")}</div>
      <span style={{ fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".1em", color }}>{label}</span>
    </div>
  );
}
