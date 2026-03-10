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
          <span style={{ color: T.green, fontWeight: 700 }}>Model integration: </span>
          Feed your model's P(yes) per market. Edge = modelProb − yesPrice.
          Kelly: f* = (p·(1/price) − 1) / ((1/price) − 1).
          Cap 5% per position. Resolves column shows days remaining — prefer markets with &gt;7d for limit order execution.
        </p>
      </div>
    </div>
  );
}
