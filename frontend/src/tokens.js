/**
 * Design tokens — single source of truth for colours, surfaces, and typography.
 * Import T from this file in every component; never hard-code colour strings.
 */
export const T = {
  bg:     "#040406",
  s0:     "#08080b",   // input backgrounds
  s1:     "#0c0c10",   // panel / section backgrounds
  s2:     "#101014",   // card backgrounds
  s3:     "#161619",   // elevated / hover state
  ln:     "#1c1c24",   // default border
  ln2:    "#252530",   // strong border
  text:   "#dcdce4",
  sub:    "#7a7a8a",
  dim:    "#3c3c48",
  green:  "#34d399",   // brand, positive
  blue:   "#5ac8fa",   // secondary accent
  amber:  "#fbbf24",   // BTC, warnings
  purple: "#bf5af2",   // misc / recovery
  red:    "#f87171",   // negative, risk
  mono:   "'JetBrains Mono','Geist Mono','SF Mono',monospace",
  sans:   "'SF Pro Display',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
};
