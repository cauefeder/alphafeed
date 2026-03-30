"""
quant_telegram.py — Send weekly Quant Report summary to Telegram.

Usage:
  python backend/adapters/quant_telegram.py

Env vars:
  TELEGRAM_BOT_TOKEN  (required)
  TELEGRAM_CHAT_ID    (required)
  QUANT_REPORT_PATH   (optional, default reports/quant_report.json)
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent.parent

REPORT_PATH = REPO_ROOT / os.environ.get("QUANT_REPORT_PATH", "reports/quant_report.json")

LABEL_EMOJI = {
    "Strong edge":   "🟢",
    "Good edge":     "🟢",
    "Moderate edge": "🟡",
    "Weak edge":     "🔴",
    "Skip":          "🔴",
}


def format_message(report: dict) -> str:
    """Format report dict as Telegram HTML message (≤ 4096 chars)."""
    week = report.get("weekOf", "?")
    summary = report.get("summary", {})
    n_scored = summary.get("totalScored", 0)
    model_auc = report.get("modelAuc", 0)

    lines: list = [
        f"📊 <b>Weekly Quant Report</b> — Week of {week}",
        "",
    ]

    # Macro Pulse
    trends = report.get("categoryTrends", {})
    if trends:
        lines.append("🌍 <b>Market Pulse</b>")
        for cat, data in list(trends.items())[:4]:
            top_list = data.get("top3Markets") or []
            top = top_list[0] if top_list else None
            total = data.get("totalMarkets", 0)
            if top:
                pct = round(top["yes_price"] * 100)
                q = top["question"][:50]
                url = top.get("url", "")
                link = f'<a href="{url}">{q}…</a>' if url else q
                lines.append(f"• {cat.title()}: {total} mkts · top: {link} ({pct}%)")
            else:
                lines.append(f"• {cat.title()}: {total} markets")
        lines.append("")

    # Edge Ranking
    ranking = report.get("edgeRanking", [])
    if ranking:
        lines.append("🏆 <b>Edge Ranking</b>")
        for i, r in enumerate(ranking[:5], 1):
            emoji = LABEL_EMOJI.get(r["label"], "⬜")
            lines.append(
                f"{i}. {emoji} {r['category'].title()} — "
                f"signal {r['avgQuantScore']:.0%} · {r['tierACount']} Tier A"
            )
        lines.append("")

    # Tier A signals
    tier_a_opps = [o for o in report.get("opportunities", []) if o.get("signalTier") == "A"]
    if tier_a_opps:
        lines.append(f"🟢 <b>Tier A signals ({len(tier_a_opps)})</b>")
        for opp in tier_a_opps[:4]:
            title = opp.get("title", "?")[:45]
            score = opp.get("quantScore", 0)
            crowd = round((opp.get("curPrice") or 0) * 100)
            url = opp.get("url", "")
            link = f'<a href="{url}">{title}</a>' if url else title
            lines.append(f"• {link} — signal {score:.2f} | crowd {crowd}%")
        lines.append("")

    # Tier B highlights
    tier_b_opps = [o for o in report.get("opportunities", []) if o.get("signalTier") == "B"]
    if tier_b_opps:
        lines.append("🟡 <b>Tier B highlights</b>")
        for opp in tier_b_opps[:3]:
            title = opp.get("title", "?")[:40]
            score = opp.get("quantScore", 0)
            url = opp.get("url", "")
            link = f'<a href="{url}">{title}</a>' if url else title
            lines.append(f"• {link} — signal {score:.2f}")
        lines.append("")

    # Insights
    insights = report.get("insights", [])
    if insights:
        lines.append("💡 <b>Conclusions</b>")
        for s in insights[:3]:
            lines.append(f"• {s}")
        lines.append("")

    lines.append(f"{n_scored} markets scored · Model AUC {model_auc:.2f} · Not financial advice")

    msg = "\n".join(lines)
    if len(msg) > 4096:
        msg = msg[:4090] + "\n…"
    return msg


def send_message(token: str, chat_id: str, text: str) -> None:
    """Send HTML message via Telegram Bot API (stdlib only)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        status = resp.getcode()
        if status != 200:
            raise RuntimeError(f"Telegram API returned {status}")


def main() -> None:
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[quant_telegram] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping")
        return

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    msg = format_message(report)
    send_message(token, chat_id, msg)
    print(f"[quant_telegram] Sent ({len(msg)} chars)")


if __name__ == "__main__":
    main()
