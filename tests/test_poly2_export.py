"""TDD coverage for poly2_export.

Tests drive the refactor: _classify is decomposed into _parse_market_info,
_passes_quality_filter, _match_category, _search_text. CATEGORIES is moved
to poly2_categories.py. _fetch_markets gains an injectable session for
testability without HTTP.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import requests

from backend.adapters import poly2_export
from backend.adapters.poly2_export import (
    _classify,
    _fetch_markets,
    _match_category,
    _parse_market_info,
    _passes_quality_filter,
    _search_text,
)
from backend.adapters.poly2_categories import CATEGORIES


NOW = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)


def _raw(
    *,
    question: str = "Will BTC hit $100K?",
    slug: str = "btc-100k",
    group: str = "",
    volume_24h: float = 5000.0,
    volume_total: float = 1_000_000.0,
    liquidity: float = 10_000.0,
    end_in_days: float | None = 30.0,
    yes_price: float | None = 0.45,
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "question": question,
        "slug": slug,
        "groupItemTitle": group,
        "volume24hr": volume_24h,
        "volume": volume_total,
        "liquidityClob": liquidity,
    }
    if end_in_days is not None:
        end_dt = NOW + timedelta(days=end_in_days)
        raw["endDate"] = end_dt.isoformat().replace("+00:00", "Z")
    if yes_price is not None:
        raw["outcomePrices"] = json.dumps([str(yes_price), str(1 - yes_price)])
    return raw


# ---------- _search_text ----------


def test_search_text_lowercases_and_concatenates() -> None:
    raw = {"question": "BTC Hit 100K?", "groupItemTitle": "Crypto Bets", "slug": "btc-100k"}
    text = _search_text(raw)
    assert "btc hit 100k?" in text
    assert "crypto bets" in text
    assert "btc-100k" in text
    assert text == text.lower()


def test_search_text_handles_missing_fields() -> None:
    assert _search_text({}) == "  "  # empty question, group, slug


# ---------- _parse_market_info ----------


def test_parse_market_info_basic() -> None:
    info = _parse_market_info(_raw(volume_24h=1234.7, yes_price=0.62), now=NOW)
    assert info["question"] == "Will BTC hit $100K?"
    assert info["slug"] == "btc-100k"
    assert info["url"] == "https://polymarket.com/event/btc-100k"
    assert info["yes_price"] == 0.62
    assert info["volume_24h"] == 1235.0  # rounded to 0 places
    assert info["days_left"] == 30.0


def test_parse_market_info_missing_yes_price_is_none() -> None:
    info = _parse_market_info(_raw(yes_price=None), now=NOW)
    assert info["yes_price"] is None


def test_parse_market_info_malformed_outcome_prices_is_none() -> None:
    raw = _raw()
    raw["outcomePrices"] = "not-json"
    info = _parse_market_info(raw, now=NOW)
    assert info["yes_price"] is None


def test_parse_market_info_no_end_date_gives_none_days_left() -> None:
    info = _parse_market_info(_raw(end_in_days=None), now=NOW)
    assert info["days_left"] is None


def test_parse_market_info_no_slug_gives_default_url() -> None:
    raw = _raw(slug="")
    info = _parse_market_info(raw, now=NOW)
    assert info["url"] == "https://polymarket.com"


# ---------- _passes_quality_filter ----------


def test_quality_excludes_low_volume() -> None:
    info = _parse_market_info(_raw(volume_24h=50.0), now=NOW)
    assert _passes_quality_filter(info) is False


def test_quality_accepts_at_threshold() -> None:
    info = _parse_market_info(_raw(volume_24h=100.0), now=NOW)
    assert _passes_quality_filter(info) is True


def test_quality_excludes_expired() -> None:
    info = _parse_market_info(_raw(end_in_days=-3.0), now=NOW)
    assert _passes_quality_filter(info) is False


def test_quality_accepts_no_end_date() -> None:
    info = _parse_market_info(_raw(end_in_days=None), now=NOW)
    assert _passes_quality_filter(info) is True


# ---------- _match_category ----------


_MINI_CATS = {
    "crypto": {"name": "Crypto", "emoji": "B", "keywords": ["bitcoin", "btc"]},
    "macro": {"name": "Macro", "emoji": "M", "keywords": ["fed", "cpi"]},
}


def test_match_category_first_keyword_wins() -> None:
    # 'btc' matches crypto, 'cpi' matches macro; crypto comes first in dict
    assert _match_category("btc cpi", _MINI_CATS) == "crypto"


def test_match_category_no_match_returns_none() -> None:
    assert _match_category("random text", _MINI_CATS) is None


def test_match_category_real_categories_btc_question() -> None:
    text = "will btc hit $100k?"
    assert _match_category(text, CATEGORIES) == "crypto"


# ---------- _classify ----------


def test_classify_excludes_low_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    classified, top = _classify(
        [_raw(question="btc moon", volume_24h=10.0)],
        now=NOW,
    )
    assert all(len(v) == 0 for v in classified.values())
    assert top == []


def test_classify_routes_to_correct_category() -> None:
    raws = [_raw(question="will fed cut rates?", slug="fed-cut")]
    classified, _ = _classify(raws, now=NOW)
    assert len(classified["macro"]) == 1
    assert sum(len(v) for v in classified.values()) == 1


def test_classify_sorts_by_volume_desc() -> None:
    raws = [
        _raw(question="btc-1", slug="btc-1", volume_24h=1000.0),
        _raw(question="btc-2", slug="btc-2", volume_24h=5000.0),
        _raw(question="btc-3", slug="btc-3", volume_24h=3000.0),
    ]
    classified, _ = _classify(raws, now=NOW)
    crypto_volumes = [m["volume_24h"] for m in classified["crypto"]]
    assert crypto_volumes == [5000.0, 3000.0, 1000.0]


def test_classify_caps_at_15_per_category() -> None:
    raws = [
        _raw(question=f"btc-{i}", slug=f"btc-{i}", volume_24h=1000.0 + i)
        for i in range(20)
    ]
    classified, _ = _classify(raws, now=NOW)
    assert len(classified["crypto"]) == 15


def test_classify_top_volume_dedups_by_question() -> None:
    # Two markets with identical questions but different slugs — top should
    # contain the question once.
    raws = [
        _raw(question="dup-q", slug="a", volume_24h=2000.0),
        _raw(question="dup-q", slug="b", volume_24h=1000.0),
        _raw(question="other", slug="c", volume_24h=500.0),
    ]
    # Force into crypto by including 'btc' in question
    for r in raws:
        r["question"] = "btc " + r["question"]
    classified, top = _classify(raws, now=NOW)
    questions = [m["question"] for m in top]
    assert questions.count("btc dup-q") == 1


def test_classify_top_volume_capped_at_20() -> None:
    raws = [
        _raw(question=f"btc-{i}", slug=f"btc-{i}", volume_24h=1000.0 + i)
        for i in range(30)
    ]
    classified, top = _classify(raws, now=NOW)
    assert len(top) <= 20


def test_classify_empty_input() -> None:
    classified, top = _classify([], now=NOW)
    assert all(len(v) == 0 for v in classified.values())
    assert top == []


# ---------- _fetch_markets ----------


class _StubResponse:
    def __init__(self, payload: list[dict[str, Any]] | Exception, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self) -> list[dict[str, Any]]:
        assert not isinstance(self._payload, Exception)
        return self._payload


class _StubSession:
    def __init__(self, pages_data: list[list[dict[str, Any]] | Exception]) -> None:
        self._pages = list(pages_data)
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> _StubResponse:
        self.calls.append({"url": url, "params": params})
        item = self._pages.pop(0)
        if isinstance(item, Exception):
            raise item
        return _StubResponse(item)


def test_fetch_markets_paginates_until_empty() -> None:
    sess = _StubSession([
        [{"slug": "a"}, {"slug": "b"}],
        [{"slug": "c"}],
        [],  # empty → stop
        [{"slug": "should-not-be-fetched"}],
    ])
    markets = _fetch_markets(pages=4, session=sess, sleep_s=0.0)
    slugs = [m["slug"] for m in markets]
    assert slugs == ["a", "b", "c"]
    assert len(sess.calls) == 3  # stopped on empty third page


def test_fetch_markets_paginates_offset_advances() -> None:
    sess = _StubSession([
        [{"slug": "a"}],
        [{"slug": "b"}],
        [],
    ])
    _fetch_markets(pages=3, session=sess, sleep_s=0.0)
    offsets = [c["params"]["offset"] for c in sess.calls]
    assert offsets == [0, 100, 200]


def test_fetch_markets_swallows_http_error() -> None:
    sess = _StubSession([
        [{"slug": "a"}],
        requests.HTTPError("boom"),
    ])
    markets = _fetch_markets(pages=2, session=sess, sleep_s=0.0)
    # First page survives; HTTPError breaks the loop
    assert [m["slug"] for m in markets] == ["a"]


# ---------- end-to-end run_export with stub session ----------


def test_run_export_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    raws = [_raw(question="will fed cut rates in 2026?", slug="fed-2026", volume_24h=2000.0)]
    sess = _StubSession([raws, []])

    def fake_fetch(pages: int = 8) -> list[dict[str, Any]]:
        return _fetch_markets(pages=pages, session=sess, sleep_s=0.0)

    monkeypatch.setattr(poly2_export, "_fetch_markets", fake_fetch)

    result = poly2_export.run_export(pages=2)
    assert result["totalMarkets"] == 1
    assert result["categories"]["macro"]["count"] == 1
    assert result["topVolume"][0]["slug"] == "fed-2026"
