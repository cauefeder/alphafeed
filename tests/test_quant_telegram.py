"""Coverage for quant_telegram: format_message branches, send_message HTTP
stub, main() env-guard + happy path. No real Telegram network calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend/adapters"))
from quant_telegram import format_message, main, send_message


# ---------- format_message ----------


def _report(**overrides: object) -> dict:
    base: dict = {
        "weekOf": "2026-06-05",
        "summary": {"totalScored": 12},
        "modelAuc": 0.62,
        "categoryTrends": {},
        "edgeRanking": [],
        "opportunities": [],
        "insights": [],
    }
    base.update(overrides)
    return base


def test_format_message_minimum_report() -> None:
    msg = format_message(_report())
    assert "Weekly Quant Report" in msg
    assert "Week of 2026-06-05" in msg
    assert "12 markets scored" in msg
    assert "Model AUC 0.62" in msg


def test_format_message_trends_with_no_top_market_falls_back_to_count() -> None:
    msg = format_message(_report(categoryTrends={
        "macro": {"top3Markets": [], "totalMarkets": 7},
    }))
    # The "no top" branch shows only the count
    assert "Macro: 7 markets" in msg


def test_format_message_tier_b_section() -> None:
    msg = format_message(_report(opportunities=[
        {"title": "tier-B-test", "signalTier": "B", "quantScore": 0.41,
         "curPrice": 0.4, "url": "https://x/y"},
    ]))
    assert "Tier B highlights" in msg
    assert "tier-B-test" in msg


def test_format_message_truncates_at_4096() -> None:
    huge = _report(insights=["x" * 5000])
    msg = format_message(huge)
    assert len(msg) <= 4096


# ---------- send_message ----------


def _make_response(status: int = 200):
    """Fake urlopen return — supports `with resp as r: r.getcode()`."""
    resp = MagicMock()
    resp.getcode.return_value = status
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


def test_send_message_posts_payload_to_correct_url() -> None:
    with patch("quant_telegram.urllib.request.urlopen", return_value=_make_response(200)) as up:
        send_message("BOTTOK", "12345", "hello")
    req = up.call_args[0][0]
    assert "/botBOTTOK/sendMessage" in req.full_url
    payload = json.loads(req.data.decode())
    assert payload["chat_id"] == "12345"
    assert payload["text"] == "hello"
    assert payload["parse_mode"] == "HTML"


def test_send_message_raises_on_non_200() -> None:
    with patch("quant_telegram.urllib.request.urlopen", return_value=_make_response(429)):
        with pytest.raises(RuntimeError, match="429"):
            send_message("BOTTOK", "12345", "hi")


# ---------- main ----------


def test_main_no_credentials_returns_silently(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    main()
    out = capsys.readouterr().out
    assert "skipping" in out


def test_main_happy_path_reads_report_and_sends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "quant_report.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOTTOK")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr("quant_telegram.REPORT_PATH", report_path)

    with patch("quant_telegram.send_message") as send:
        main()
    send.assert_called_once()
    token, chat, text = send.call_args[0]
    assert token == "BOTTOK"
    assert chat == "12345"
    assert "Weekly Quant Report" in text
