import { T } from "../tokens.js";
import { Panel } from "../components/primitives.jsx";
import { PolyTable } from "../components/PolyTable.jsx";

export function PolymarketTab({ polyAnalysis, srcPoly }) {
  return (
    <div>
      <Panel
        title="Active Prediction Markets"
        sub={`${polyAnalysis.length} markets · sorted by edge score · Resolves = days until resolution`}
        live={srcPoly === "live"}
        delay="d1"
      >
        <PolyTable markets={polyAnalysis} limit={16} compact={false} />
      </Panel>

      <div className="fade-up d2" style={{ borderRadius: 14, padding: 16, background: "rgba(52,211,153,.02)", border: `1px solid rgba(52,211,153,.08)` }}>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: T.sub, margin: 0 }}>
          <span style={{ color: T.green, fontWeight: 700 }}>How to read this: </span>
          <strong style={{ color: T.text }}>Edge</strong> = how mispriced the market appears based on volume, liquidity, and price extremity — higher is better.{" "}
          <strong style={{ color: T.text }}>Unc. (Uncertainty)</strong> = how far the crowd is from a consensus: 5 green dots means the market is near 50/50 and maximally uncertain, 1 red dot means the crowd is very confident.{" "}
          <strong style={{ color: T.text }}>Resolves</strong> = days until the market settles — prefer &gt;7d for time to execute.
          Markets are sorted by edge score; data refreshes twice daily.
        </p>
      </div>
    </div>
  );
}
