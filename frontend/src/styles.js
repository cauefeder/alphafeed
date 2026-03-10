import { T } from "./tokens.js";

/**
 * Global CSS injected via <style> in App.jsx.
 * Class names used here are referenced directly in component inline styles
 * and className attributes — keep them in sync.
 */
export const globalCss = `
  *, *::before, *::after { box-sizing: border-box; }
  body { margin: 0; color-scheme: dark; background: ${T.bg}; }

  @keyframes fadeUp  { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
  @keyframes glow    { 0%,100%{box-shadow:0 0 12px rgba(52,211,153,.22),0 0 32px rgba(52,211,153,.07)} 50%{box-shadow:0 0 22px rgba(52,211,153,.4),0 0 52px rgba(52,211,153,.13)} }
  @keyframes shimmer { from{background-position:-200% 0} to{background-position:200% 0} }
  @keyframes scan    { from{top:-2px} to{top:100%} }

  .fade-up { animation: fadeUp .38s cubic-bezier(.22,1,.36,1) both; }
  .d1{animation-delay:.04s}.d2{animation-delay:.08s}.d3{animation-delay:.12s}
  .d4{animation-delay:.16s}.d5{animation-delay:.20s}.d6{animation-delay:.24s}
  .glow-pulse { animation: glow 3.5s ease-in-out infinite; }

  /* ── Cards / Panels ── */
  .card {
    background: ${T.s1};
    border: 1px solid ${T.ln};
    border-radius: 18px;
    box-shadow: 0 2px 16px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.022);
    position: relative; overflow: hidden;
  }
  .card::before {
    content:''; position:absolute; left:0; width:100%; height:1px;
    background: linear-gradient(90deg,transparent 10%,rgba(52,211,153,.06) 50%,transparent 90%);
    animation: scan 14s linear infinite; z-index:1; pointer-events:none;
  }

  /* ── Metric / stat cards ── */
  .mcard {
    background: ${T.s2}; border: 1px solid ${T.ln};
    border-radius: 14px; padding: 16px 18px;
    flex: 1 1 130px; min-width: 120px;
    transition: border-color .18s, transform .18s;
  }
  .mcard:hover { border-color: rgba(52,211,153,.2); transform: translateY(-1px); }
  .mcard.warn  { border-color: rgba(241,113,113,.25); }
  .mcard.hero  {
    background: linear-gradient(140deg,rgba(52,211,153,.07),rgba(52,211,153,.02));
    border-color: rgba(52,211,153,.22);
    box-shadow: 0 0 40px rgba(52,211,153,.07);
    flex: 1 1 100%; min-width: unset; padding: 22px 24px; border-radius: 16px;
  }
  .shimmer-text {
    background: linear-gradient(90deg,${T.green} 0%,#86efac 45%,${T.green} 100%);
    background-size: 200% auto;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    animation: shimmer 4s linear infinite;
  }

  /* ── Tab buttons ── */
  .tab-btn {
    padding: 9px 18px; border-radius: 10px; cursor: pointer;
    border: 1px solid transparent; background: transparent;
    color: ${T.sub}; font-size: 11px; font-weight: 700;
    font-family: ${T.sans}; letter-spacing: .04em;
    display: flex; align-items: center; gap: 6px;
    transition: all .15s; white-space: nowrap;
  }
  .tab-btn:hover { background: ${T.s2}; border-color: ${T.ln2}; color: ${T.text}; }
  .tab-btn.on {
    background: rgba(52,211,153,.07); border-color: rgba(52,211,153,.3);
    color: ${T.green}; box-shadow: 0 0 0 3px rgba(52,211,153,.06);
  }

  /* ── Inputs (bankroll tab) ── */
  input[type=number] {
    -webkit-appearance:none; -moz-appearance:textfield; appearance:textfield;
    background:transparent!important; border:none; outline:none;
    color:${T.text}; width:100%;
    font-family:${T.mono}; font-size:14px; font-weight:500; padding:10px 0;
  }
  input[type=number]::-webkit-inner-spin-button,
  input[type=number]::-webkit-outer-spin-button { -webkit-appearance:none; }
  .inp {
    display:flex; align-items:center; background:${T.s0};
    border:1px solid ${T.ln2}; border-radius:10px; padding:0 13px;
    transition: border-color .15s, box-shadow .15s;
  }
  .inp:focus-within { border-color:rgba(52,211,153,.35); box-shadow:0 0 0 3px rgba(52,211,153,.07); }

  /* ── Kelly fraction buttons ── */
  .kbtn {
    flex:1; padding:10px 6px; border-radius:10px;
    border:1px solid ${T.ln2}; background:${T.s2};
    color:${T.sub}; font-size:11px; font-weight:700;
    cursor:pointer; transition:all .15s; font-family:${T.sans}; line-height:1.25;
  }
  .kbtn:hover { border-color:rgba(52,211,153,.3); color:${T.green}; background:${T.s3}; }
  .kbtn.on {
    background:rgba(52,211,153,.08); border-color:rgba(52,211,153,.4);
    color:${T.green}; box-shadow:0 0 0 3px rgba(52,211,153,.06),inset 0 1px 0 rgba(52,211,153,.1);
  }

  /* ── Allocation bars ── */
  .bar-track { height:5px; background:${T.ln}; border-radius:3px; overflow:hidden; }
  .bar-fill   { height:5px; border-radius:3px; transition:width .45s cubic-bezier(.4,0,.2,1); }

  /* ── Live / Seed badges ── */
  .badge-live { background:rgba(52,211,153,.09); border:1px solid rgba(52,211,153,.22); color:#6ee7b7; }
  .badge-seed { background:rgba(30,30,38,.8);    border:1px solid rgba(42,42,52,.8);    color:${T.dim}; }

  /* ── Refresh button ── */
  .btn-refresh {
    background:${T.s2}; border:1px solid ${T.ln2}; color:${T.dim};
    border-radius:10px; padding:7px 18px; font-size:10px;
    font-family:${T.mono}; letter-spacing:.1em; text-transform:uppercase;
    cursor:pointer; transition:all .18s; box-shadow:0 1px 4px rgba(0,0,0,.4);
  }
  .btn-refresh:hover:not(:disabled) {
    border-color:rgba(52,211,153,.32); color:${T.green};
    box-shadow:0 0 0 3px rgba(52,211,153,.06),0 1px 4px rgba(0,0,0,.4);
  }
  .btn-refresh:disabled { opacity:.28; cursor:default; }

  /* ── Tables ── */
  table { border-collapse:collapse; }
  table thead tr  { background:rgba(255,255,255,.016); }
  table tbody tr  { transition:background .1s; }
  table tbody tr:hover { background:rgba(52,211,153,.028); }

  /* ── Section divider (bankroll) ── */
  .sdiv { display:flex; align-items:center; gap:12px; margin:20px 0 14px; }
  .sdiv-ln  { flex:1; height:1px; background:${T.ln}; }
  .sdiv-lbl { font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:.1em; color:${T.dim}; white-space:nowrap; }

  /* ── Rule rows (bankroll) ── */
  .rule-row {
    display:flex; align-items:center; gap:14px; padding:11px 14px;
    border-radius:10px; background:rgba(255,255,255,.018); border:1px solid ${T.ln};
  }

  /* ── Day pills (bankroll) ── */
  .dpill { flex:1 1 62px; text-align:center; padding:12px 4px; border-radius:10px; border:1px solid ${T.ln}; background:transparent; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar       { width:3px; height:3px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:rgba(50,50,60,.5); border-radius:99px; }
`;
