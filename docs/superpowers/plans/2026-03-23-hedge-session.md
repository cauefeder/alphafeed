# Hedge Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 🛡️ Hedge tab to AlphaFeed where users describe real-world exposure and receive a ranked list of Polymarket bets that pay out in their worst-case scenario.

**Architecture:** Two-stage Gemini Flash pipeline — Stage 1 extracts structured exposure from free text (skipped if both `asset` and `risk_type` supplied), Stage 2 scores all 85 cached poly2.json markets for correlation, backend enriches matched markets with Kelly/smart-money data from polytraders.json via slug join + direction normalization.

**Tech Stack:** Python 3.11, FastAPI, Gemini Flash API (free tier via stdlib urllib), React 18, Vite, existing slowapi rate limiter, pytest + unittest.mock.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/llm_client.py` | Create | Gemini HTTP call, fence stripping, JSON retry, LLMError |
| `backend/adapters/hedge_engine.py` | Create | parse_exposure, _flatten_markets, score_markets, _enrich, run_hedge_session |
| `backend/server.py` | Modify | POST /api/hedge-session endpoint + POST to CORS allow_methods |
| `frontend/src/api.js` | Modify | postHedgeSession (POST, 60s timeout) |
| `frontend/src/tabs/Hedge.jsx` | Create | Exposure input, parsed card, hedge list |
| `frontend/src/App.jsx` | Modify | Add Hedge tab to TABS array + render |
| `tests/test_llm_client.py` | Create | Unit tests for llm_client |
| `tests/test_hedge_engine.py` | Create | Unit tests for hedge_engine |
| `tests/test_api.py` | Modify | Integration tests for POST /api/hedge-session |

---

## Task 1: LLM Client — Tests

**Files:**
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Create the test file**

```python
# tests/test_llm_client.py
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
import llm_client
from llm_client import LLMError, complete


def _mock_response(text: str, status: int = 200):
    """Build a fake urllib response object."""
    body = json.dumps({
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }).encode()
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = body
    mock.status = status
    return mock


def test_complete_returns_string(monkeypatch):
    payload = json.dumps({"result": "ok"})
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
        result = complete("test prompt")
    assert result == payload


def test_complete_strips_markdown_fences(monkeypatch):
    raw_json = '{"a": 1}'
    fenced = f"```json\n{raw_json}\n```"
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("urllib.request.urlopen", return_value=_mock_response(fenced)):
        result = complete("test prompt")
    assert result == raw_json
    json.loads(result)  # must be valid JSON


def test_complete_retries_on_bad_json_then_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    call_count = {"n": 0}

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        return _mock_response("not valid json at all")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        try:
            complete("test prompt")
            assert False, "should have raised"
        except LLMError:
            pass
    assert call_count["n"] == 2  # initial + 1 retry


def test_complete_succeeds_on_retry(monkeypatch):
    """First call returns bad JSON; second call (retry) returns valid JSON — must succeed."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    call_count = {"n": 0}
    valid = '{"ok": true}'

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _mock_response("not json")
        return _mock_response(valid)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = complete("test prompt")

    assert result == valid
    assert call_count["n"] == 2


def test_complete_raises_on_429(monkeypatch):
    import urllib.error
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    err = urllib.error.HTTPError(url="", code=429, msg="Too Many Requests", hdrs={}, fp=None)
    with patch("urllib.request.urlopen", side_effect=err):
        try:
            complete("test prompt")
            assert False, "should have raised"
        except LLMError as e:
            assert "429" in str(e)


def test_complete_raises_on_timeout(monkeypatch):
    import socket
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        try:
            complete("test prompt")
            assert False, "should have raised"
        except LLMError as e:
            assert "timed out" in str(e).lower()


def test_model_read_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-model")
    captured_urls = []

    def fake_urlopen(req, timeout=None):
        captured_urls.append(req.full_url)
        return _mock_response('{"ok": true}')

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        complete("prompt")

    assert "gemini-custom-model" in captured_urls[0]
```

- [ ] **Step 2: Run tests to confirm they all fail (module does not exist yet)**

```bash
cd backend && python -m pytest ../tests/test_llm_client.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'llm_client'`

---

## Task 2: LLM Client — Implementation

**Files:**
- Create: `backend/llm_client.py`

- [ ] **Step 1: Create the implementation**

```python
# backend/llm_client.py
"""
Thin LLM abstraction — wraps Gemini Flash (free tier) via stdlib urllib.
Swap model: set GEMINI_MODEL env var.
Swap provider: replace the _call() function body.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class LLMError(Exception):
    pass


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers that Gemini often adds."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return text


def _call(prompt: str) -> str:
    """Single HTTP call to Gemini. Returns raw response text."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise LLMError(f"HTTP {exc.code}: {exc.reason}")
    except TimeoutError as exc:
        raise LLMError(f"Request timed out: {exc}")
    return data["candidates"][0]["content"]["parts"][0]["text"]


def complete(prompt: str) -> str:
    """
    Call the LLM, strip markdown fences, validate JSON.
    Retries once with explicit JSON instruction if first parse fails.
    Raises LLMError on HTTP error, timeout, or two parse failures.
    """
    text = _strip_fences(_call(prompt))
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Retry with explicit JSON-only instruction
    retry_prompt = prompt + "\n\nCRITICAL: Return ONLY raw JSON. No markdown fences, no code blocks, no explanation."
    text = _strip_fences(_call(retry_prompt))
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError as exc:
        raise LLMError(f"Failed to parse JSON from LLM after retry: {exc}") from exc
```

- [ ] **Step 2: Run tests — all must pass**

```bash
cd backend && python -m pytest ../tests/test_llm_client.py -v
```

Expected: `6 passed`

- [ ] **Step 3: Commit**

```bash
cd "d:/OMNP - Quant/Projetos/AlphaFeed"
git add backend/llm_client.py tests/test_llm_client.py
git commit -m "feat: add llm_client with Gemini Flash, fence stripping, JSON retry"
```

---

## Task 3: Hedge Engine — Flatten + Parse Exposure Tests

**Files:**
- Create: `tests/test_hedge_engine.py` (partial — flatten + parse_exposure only)
- Create: `tests/fixtures/poly2_fixture.json`
- Create: `tests/fixtures/polytraders_fixture.json`

- [ ] **Step 1: Create fixture files**

`tests/fixtures/poly2_fixture.json`:
```json
{
  "generatedAt": "2026-03-23T00:00:00+00:00",
  "totalMarkets": 3,
  "categories": {
    "crypto": {
      "name": "Crypto & Digital Assets",
      "emoji": "₿",
      "count": 2,
      "markets": [
        {
          "question": "Will Bitcoin reach $90,000 in March?",
          "slug": "will-bitcoin-reach-90000-in-march",
          "url": "https://polymarket.com/event/will-bitcoin-reach-90000-in-march",
          "yes_price": 0.04,
          "volume_24h": 578852.0,
          "volume_total": 1000000.0,
          "liquidity": 50000.0,
          "days_left": 14.0
        },
        {
          "question": "Will Bitcoin dip to $65,000 in March?",
          "slug": "will-bitcoin-dip-to-65000-in-march",
          "url": "https://polymarket.com/event/will-bitcoin-dip-to-65000-in-march",
          "yes_price": 0.25,
          "volume_24h": 512750.0,
          "volume_total": 900000.0,
          "liquidity": 40000.0,
          "days_left": 14.0
        }
      ]
    },
    "macro": {
      "name": "Macroeconomics",
      "emoji": "📊",
      "count": 1,
      "markets": [
        {
          "question": "Will the Fed decrease interest rates in March?",
          "slug": "will-the-fed-decrease-interest-rates-march",
          "url": "https://polymarket.com/event/will-the-fed-decrease-interest-rates-march",
          "yes_price": 0.01,
          "volume_24h": 12000000.0,
          "volume_total": 77000000.0,
          "liquidity": 800000.0,
          "days_left": 0.0
        }
      ]
    }
  }
}
```

`tests/fixtures/polytraders_fixture.json`:
```json
{
  "generatedAt": "2026-03-23T00:00:00+00:00",
  "timePeriod": "WEEK",
  "bankroll": 100.0,
  "tradersChecked": 25,
  "positionsScanned": 10,
  "opportunities": [
    {
      "title": "Will Bitcoin dip to $65,000 in March?",
      "outcome": "Yes",
      "slug": "will-bitcoin-dip-to-65000-in-march",
      "url": "https://polymarket.com/event/will-bitcoin-dip-to-65000-in-march",
      "curPrice": 0.25,
      "estimatedEdge": 0.07,
      "kellyBet": 3.5,
      "kellyFull": 0.14,
      "nSmartTraders": 3,
      "totalTradersChecked": 25,
      "smartTraderNames": ["trader1", "trader2", "trader3"],
      "countSignal": 0.12,
      "sizeSignal": 1.0,
      "totalExposure": 78465.0,
      "weightedAvgEntry": 0.22
    },
    {
      "title": "Stars vs. Wild",
      "outcome": "Stars",
      "slug": "nhl-dal-min-2026-03-21",
      "url": "https://polymarket.com/event/nhl-dal-min-2026-03-21",
      "curPrice": 0.55,
      "estimatedEdge": 0.07,
      "kellyBet": 3.7,
      "kellyFull": 0.15,
      "nSmartTraders": 2,
      "totalTradersChecked": 25,
      "smartTraderNames": ["trader1", "trader2"],
      "countSignal": 0.08,
      "sizeSignal": 1.0,
      "totalExposure": 88547.0,
      "weightedAvgEntry": 0.55
    }
  ]
}
```

- [ ] **Step 2: Write flatten + parse_exposure tests**

```python
# tests/test_hedge_engine.py
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

FIXTURES = Path(__file__).parent / "fixtures"
POLY2_FIXTURE = json.loads((FIXTURES / "poly2_fixture.json").read_text())
PT_FIXTURE = json.loads((FIXTURES / "polytraders_fixture.json").read_text())
KELLY_OPPS = PT_FIXTURE["opportunities"]

# ── _flatten_markets ───────────────────────────────────────────────────────────

def test_flatten_markets_returns_flat_list():
    from adapters.hedge_engine import _flatten_markets
    with patch("adapters.hedge_engine._load_poly2", return_value=POLY2_FIXTURE):
        markets = _flatten_markets()
    assert len(markets) == 3  # 2 crypto + 1 macro


def test_flatten_markets_required_fields():
    from adapters.hedge_engine import _flatten_markets
    with patch("adapters.hedge_engine._load_poly2", return_value=POLY2_FIXTURE):
        markets = _flatten_markets()
    for m in markets:
        assert "slug" in m
        assert "question" in m
        assert "yes_price" in m
        assert "volume_24h" in m
        assert "days_left" in m
        # Must NOT contain extra fields
        assert "volume_total" not in m
        assert "liquidity" not in m


# ── parse_exposure ─────────────────────────────────────────────────────────────

def test_parse_exposure_short_circuit_skips_llm():
    """When asset + risk_type both supplied, Stage 1 LLM is NOT called."""
    from adapters.hedge_engine import parse_exposure
    call_count = {"n": 0}

    def fake_complete(prompt):
        call_count["n"] += 1
        return '{"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "test"}'

    with patch("adapters.hedge_engine.llm_complete", side_effect=fake_complete):
        result = parse_exposure("I hold BTC", asset="BTC", risk_type="risk-off")

    assert call_count["n"] == 0  # short-circuit: LLM not called
    assert result["asset"] == "BTC"
    assert result["risk_type"] == "risk-off"
    assert result["direction"] == "long"
    assert result["scenario"] == "I hold BTC"


def test_parse_exposure_calls_llm_when_fields_missing():
    from adapters.hedge_engine import parse_exposure
    llm_response = '{"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "tariff shock"}'

    with patch("adapters.hedge_engine.llm_complete", return_value=llm_response) as mock_llm:
        result = parse_exposure("I hold 2 BTC, worried about tariffs", asset="", risk_type="")

    mock_llm.assert_called_once()
    assert result["asset"] == "BTC"
    assert result["direction"] == "long"
    assert result["scenario"] == "tariff shock"


def test_parse_exposure_returns_required_keys():
    from adapters.hedge_engine import parse_exposure
    llm_response = '{"asset": "tech stocks", "direction": "long", "risk_type": "recession", "scenario": "GDP shrinks"}'

    with patch("adapters.hedge_engine.llm_complete", return_value=llm_response):
        result = parse_exposure("I work in tech", asset=None, risk_type=None)

    for key in ("asset", "direction", "risk_type", "scenario"):
        assert key in result
```

- [ ] **Step 3: Run — confirm fail**

```bash
cd backend && python -m pytest ../tests/test_hedge_engine.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'adapters.hedge_engine'`

---

## Task 4: Hedge Engine — score_markets + _enrich Tests

**Files:**
- Modify: `tests/test_hedge_engine.py` (append)

- [ ] **Step 1: Append score_markets + enrich tests**

```python
# Append to tests/test_hedge_engine.py

# ── score_markets ──────────────────────────────────────────────────────────────

EXPOSURE = {"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "tariff shock drives BTC down"}

STAGE2_RESPONSE = json.dumps([
    {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 8.5, "narrative": "Pays out directly if BTC crashes."},
    {"slug": "will-the-fed-decrease-interest-rates-march", "hedge_side": "NO", "correlation_score": 5.0, "narrative": "Fed on hold signals risk-off."},
    {"slug": "will-bitcoin-reach-90000-in-march", "hedge_side": "NO", "correlation_score": 7.0, "narrative": "BTC won't reach ATH in a crash."},
])

FLAT_MARKETS = [
    {"slug": "will-bitcoin-dip-to-65000-in-march", "question": "Will Bitcoin dip to $65,000?", "yes_price": 0.25, "volume_24h": 512750.0, "days_left": 14.0},
    {"slug": "will-the-fed-decrease-interest-rates-march", "question": "Will the Fed cut rates?", "yes_price": 0.01, "volume_24h": 12000000.0, "days_left": 0.0},
    {"slug": "will-bitcoin-reach-90000-in-march", "question": "Will Bitcoin reach $90K?", "yes_price": 0.04, "volume_24h": 578852.0, "days_left": 14.0},
]


def test_score_markets_returns_at_most_8():
    from adapters.hedge_engine import score_markets
    # Build 10 items in LLM response
    many = [{"slug": f"slug-{i}", "hedge_side": "YES", "correlation_score": float(10 - i), "narrative": "x"} for i in range(10)]
    markets = [{"slug": f"slug-{i}", "question": f"Q{i}", "yes_price": 0.5, "volume_24h": 1000.0, "days_left": 5.0} for i in range(10)]
    with patch("adapters.hedge_engine.llm_complete", return_value=json.dumps(many)):
        results = score_markets(EXPOSURE, markets, [])
    assert len(results) <= 8


def test_score_markets_sorted_by_correlation_descending():
    from adapters.hedge_engine import score_markets
    with patch("adapters.hedge_engine.llm_complete", return_value=STAGE2_RESPONSE):
        results = score_markets(EXPOSURE, FLAT_MARKETS, [])
    scores = [r["correlation_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_score_markets_filters_below_threshold():
    from adapters.hedge_engine import score_markets
    low_score = json.dumps([
        {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 1.5, "narrative": "weak"},
    ])
    with patch("adapters.hedge_engine.llm_complete", return_value=low_score):
        results = score_markets(EXPOSURE, FLAT_MARKETS, [])
    assert len(results) == 0


def test_score_markets_skips_malformed_items():
    from adapters.hedge_engine import score_markets
    malformed = json.dumps([
        {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES"},  # missing correlation_score
        {"slug": "will-bitcoin-reach-90000-in-march", "hedge_side": "NO", "correlation_score": 7.0, "narrative": "valid"},
    ])
    with patch("adapters.hedge_engine.llm_complete", return_value=malformed):
        results = score_markets(EXPOSURE, FLAT_MARKETS, [])
    assert len(results) == 1
    assert results[0]["slug"] == "will-bitcoin-reach-90000-in-march"


# ── _enrich (cross_signal) ─────────────────────────────────────────────────────

def test_enrich_sets_kelly_data_on_slug_match():
    from adapters.hedge_engine import _enrich
    result = {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 8.5, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["kelly_bet"] == 3.5
    assert enriched["smart_money_exposure"] == 78465.0


def test_enrich_cross_signal_true_when_slug_match_and_direction_match():
    from adapters.hedge_engine import _enrich
    # Kelly outcome is "Yes" → normalized to "YES" → matches hedge_side "YES"
    result = {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "YES", "correlation_score": 8.5, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["cross_signal"] is True


def test_enrich_cross_signal_false_when_direction_mismatch():
    from adapters.hedge_engine import _enrich
    # hedge_side NO but Kelly outcome is "Yes" → mismatch
    result = {"slug": "will-bitcoin-dip-to-65000-in-march", "hedge_side": "NO", "correlation_score": 8.5, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["cross_signal"] is False


def test_enrich_cross_signal_false_when_no_slug_match():
    from adapters.hedge_engine import _enrich
    result = {"slug": "nonexistent-slug", "hedge_side": "YES", "correlation_score": 5.0, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)
    assert enriched["cross_signal"] is False
    assert enriched["kelly_bet"] is None
    assert enriched["smart_money_exposure"] is None


def test_enrich_normalizes_named_outcome_to_yes():
    from adapters.hedge_engine import _enrich
    # "Stars" is a named outcome → normalized to YES; uses the NHL fixture entry
    result = {"slug": "nhl-dal-min-2026-03-21", "hedge_side": "YES", "correlation_score": 6.0, "narrative": "x"}
    enriched = _enrich(result, KELLY_OPPS)  # KELLY_OPPS fixture has outcome="Stars" for this slug
    assert enriched["cross_signal"] is True


def test_score_markets_propagates_enrichment_fields():
    """score_markets must include kelly_bet, smart_money_exposure, cross_signal in its returned items."""
    from adapters.hedge_engine import score_markets
    with patch("adapters.hedge_engine.llm_complete", return_value=STAGE2_RESPONSE):
        results = score_markets(EXPOSURE, FLAT_MARKETS, KELLY_OPPS)
    btc_result = next((r for r in results if r["slug"] == "will-bitcoin-dip-to-65000-in-march"), None)
    assert btc_result is not None
    assert btc_result["kelly_bet"] == 3.5
    assert btc_result["smart_money_exposure"] == 78465.0
    assert btc_result["cross_signal"] is True  # Kelly outcome "Yes" == hedge_side "YES"
```

- [ ] **Step 2: Run — confirm fail**

```bash
cd backend && python -m pytest ../tests/test_hedge_engine.py -v 2>&1 | head -20
```

Expected: still `ModuleNotFoundError` (implementation not yet written)

---

## Task 5: Hedge Engine — Implementation

**Files:**
- Create: `backend/adapters/hedge_engine.py`

- [ ] **Step 1: Create the implementation**

```python
# backend/adapters/hedge_engine.py
"""
Hedge Session pipeline.

Stages:
  1. parse_exposure  — extract structured exposure from user text (Stage 1 LLM)
  2. _flatten_markets — flatten poly2.json categories into a single list
  3. score_markets   — Stage 2 LLM scores markets for correlation, filters, enriches
  4. run_hedge_session — orchestrates all stages, loads cached JSON files
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# llm_client lives one directory up (backend/), add to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent))
import llm_client
from llm_client import LLMError

# Re-export so tests can patch via 'adapters.hedge_engine.llm_complete'
llm_complete = llm_client.complete

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"

# ── File loaders (patchable in tests) ─────────────────────────────────────────

def _load_poly2() -> dict:
    return json.loads((REPORTS_DIR / "poly2.json").read_text(encoding="utf-8"))


def _load_polytraders() -> dict:
    return json.loads((REPORTS_DIR / "polytraders.json").read_text(encoding="utf-8"))


# ── Stage helpers ──────────────────────────────────────────────────────────────

def _flatten_markets() -> list[dict]:
    """Flatten poly2.json categories into a single condensed list for the LLM."""
    data = _load_poly2()
    out = []
    for cat in data.get("categories", {}).values():
        for m in cat.get("markets", []):
            out.append({
                "slug":       m["slug"],
                "question":   m["question"],
                "yes_price":  m["yes_price"],
                "volume_24h": m["volume_24h"],
                "days_left":  m["days_left"],
            })
    return out


def _normalize_outcome(outcome: str) -> str:
    """Map Kelly outcome to YES/NO for direction-match comparison."""
    lo = outcome.lower().strip()
    if lo == "yes":
        return "YES"
    if lo == "no":
        return "NO"
    return "YES"  # named outcomes (team, person) = betting that entity wins = YES


def _enrich(result: dict, kelly_opps: list[dict]) -> dict:
    """
    Join a scored hedge result to polytraders.json by slug.
    Sets kelly_bet, smart_money_exposure, cross_signal.
    """
    slug = result["slug"]
    match = next((k for k in kelly_opps if k.get("slug") == slug), None)

    result["kelly_bet"] = None
    result["smart_money_exposure"] = None
    result["cross_signal"] = False

    if match:
        result["kelly_bet"] = match.get("kellyBet")
        result["smart_money_exposure"] = match.get("totalExposure")
        kelly_direction = _normalize_outcome(match.get("outcome", ""))
        result["cross_signal"] = kelly_direction == result["hedge_side"]

    return result


# ── Stage 1: Exposure extraction ───────────────────────────────────────────────

def parse_exposure(text: str, asset: Optional[str], risk_type: Optional[str]) -> dict:
    """
    Extract { asset, direction, risk_type, scenario } from user text.
    Short-circuit: if both asset and risk_type are non-empty, skip LLM call.
    """
    if asset and risk_type:
        return {
            "asset":     asset,
            "direction": "long",
            "risk_type": risk_type,
            "scenario":  text,
        }

    prompt = f"""Extract the financial exposure from this description. Return JSON only.

User description: "{text}"

Return this exact JSON structure:
{{
  "asset": "the primary asset (e.g. BTC, S&P500, tech stocks)",
  "direction": "long or short",
  "risk_type": "one of: risk-off, rate-hike, recession, geopolitical, crypto-crash, tech-selloff, other",
  "scenario": "one sentence describing the worst case scenario"
}}"""
    raw = llm_complete(prompt)
    return json.loads(raw)


# ── Stage 2: Market scoring ────────────────────────────────────────────────────

def score_markets(exposure: dict, markets: list[dict], kelly_opps: list[dict]) -> list[dict]:
    """
    Call Stage 2 LLM to score each market for hedge correlation.
    Filters to correlation_score >= 2.0, returns at most 8 sorted descending.
    Enriches each result with Kelly data.
    """
    market_lines = "\n".join(
        f'{m["slug"]} | {m["question"]} | yes_price={m["yes_price"]:.2f} | '
        f'vol24h=${m["volume_24h"]:,.0f} | days_left={m["days_left"]:.0f}d'
        for m in markets
    )

    prompt = f"""You are a hedge analyst. A user has the following financial exposure:
Asset: {exposure["asset"]}
Direction: {exposure["direction"]}
Risk type: {exposure["risk_type"]}
Worst case scenario: {exposure["scenario"]}

Find Polymarket prediction markets below that would PAY OUT if the worst case scenario happens.
These are HEDGES — a YES or NO bet that profits if the bad scenario occurs.

Markets:
{market_lines}

Return a JSON array of up to 8 markets where correlation_score >= 2.0, sorted by correlation_score descending.
Each item must have exactly these fields:
[
  {{
    "slug": "exact slug from the market list above",
    "hedge_side": "YES or NO",
    "correlation_score": <number 0-10>,
    "narrative": "<2 sentences: how this pays out if the worst case happens>"
  }}
]

Return ONLY the JSON array. No markdown, no explanation."""

    raw = llm_complete(prompt)
    items = json.loads(raw)

    results = []
    for item in items:
        try:
            score = float(item["correlation_score"])
            if score < 2.0:
                continue
            enriched = _enrich({
                "slug":              item["slug"],
                "hedge_side":        item["hedge_side"],
                "correlation_score": score,
                "narrative":         item["narrative"],
            }, kelly_opps)
            # Add market metadata from original list
            market_meta = next((m for m in markets if m["slug"] == item["slug"]), {})
            enriched["question"]   = market_meta.get("question", "")
            enriched["yes_price"]  = market_meta.get("yes_price")
            enriched["volume_24h"] = market_meta.get("volume_24h")
            enriched["days_left"]  = market_meta.get("days_left")
            enriched["url"]        = f"https://polymarket.com/event/{item['slug']}"
            results.append(enriched)
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed items

    results.sort(key=lambda x: x["correlation_score"], reverse=True)
    return results[:8]


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run_hedge_session(text: str, asset: Optional[str], risk_type: Optional[str]) -> dict:
    """Full pipeline: parse → flatten → score → return."""
    exposure = parse_exposure(text, asset, risk_type)
    markets = _flatten_markets()
    kelly_opps = _load_polytraders().get("opportunities", [])
    hedges = score_markets(exposure, markets, kelly_opps)
    return {"exposure_parsed": exposure, "hedges": hedges}
```

- [ ] **Step 2: Run all hedge engine tests — all must pass**

```bash
cd backend && python -m pytest ../tests/test_hedge_engine.py -v
```

Expected: `14 passed`

- [ ] **Step 3: Commit**

```bash
cd "d:/OMNP - Quant/Projetos/AlphaFeed"
git add backend/adapters/hedge_engine.py tests/test_hedge_engine.py tests/fixtures/
git commit -m "feat: add hedge_engine — two-stage LLM pipeline with Kelly enrichment"
```

---

## Task 6: API Endpoint Tests + Implementation

**Files:**
- Modify: `tests/test_api.py` (append hedge session tests)
- Modify: `backend/server.py` (add endpoint + CORS)

- [ ] **Step 1: Append to test_api.py**

```python
# Append to tests/test_api.py

from unittest.mock import patch
from llm_client import LLMError

MOCK_HEDGE_RESPONSE = {
    "exposure_parsed": {"asset": "BTC", "direction": "long", "risk_type": "risk-off", "scenario": "crash"},
    "hedges": [
        {
            "question": "Will BTC dip to $65K?", "url": "https://polymarket.com/event/x",
            "slug": "btc-65k", "hedge_side": "YES", "correlation_score": 8.5,
            "narrative": "Pays out if BTC crashes.", "yes_price": 0.25,
            "volume_24h": 512750.0, "days_left": 14.0,
            "kelly_bet": 3.5, "smart_money_exposure": 78465.0, "cross_signal": True,
        }
    ],
}


def test_hedge_session_200(client):
    with patch("server.run_hedge_session", return_value=MOCK_HEDGE_RESPONSE):
        resp = client.post("/api/hedge-session", json={"exposure": "I hold BTC"})
    assert resp.status_code == 200
    body = resp.json()
    assert "exposure_parsed" in body
    assert "hedges" in body
    assert body["hedges"][0]["cross_signal"] is True


def test_hedge_session_422_on_missing_exposure(client):
    resp = client.post("/api/hedge-session", json={"asset": "BTC"})
    assert resp.status_code == 422


def test_hedge_session_504_on_llm_error(client):
    with patch("server.run_hedge_session", side_effect=LLMError("timeout")):
        resp = client.post("/api/hedge-session", json={"exposure": "I hold BTC"})
    assert resp.status_code == 504


def test_hedge_session_rate_limited(client):
    """POST /api/hedge-session shares the 30/minute rate limit."""
    # Hit the endpoint 31 times — the 31st should be rate-limited (429)
    with patch("server.run_hedge_session", return_value=MOCK_HEDGE_RESPONSE):
        responses = [client.post("/api/hedge-session", json={"exposure": "test"}) for _ in range(31)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes


def test_hedge_session_cors_allows_post(client):
    # Use "*" wildcard origin (server default when ALLOWED_ORIGINS not set in test env)
    resp = client.options(
        "/api/hedge-session",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    # CORSMiddleware returns 200 for preflight if origin + method are allowed
    assert resp.status_code == 200
```

- [ ] **Step 2: Run — confirm new tests fail**

```bash
cd backend && python -m pytest ../tests/test_api.py -k "hedge" -v 2>&1 | head -20
```

Expected: `404` or `AttributeError` (endpoint not yet defined)

- [ ] **Step 3: Update server.py — CORS + endpoint**

In `server.py`, make two changes:

**Change 1** — Update CORS `allow_methods`:
```python
# Find this line:
    allow_methods=["GET"],
# Replace with:
    allow_methods=["GET", "POST"],
```

**Change 2** — Add after existing imports, add the import:
```python
from adapters.hedge_engine import run_hedge_session
from llm_client import LLMError
from pydantic import BaseModel
```

**Change 3** — Add the request model and endpoint before the last line of the file:
```python
class HedgeRequest(BaseModel):
    exposure: str
    asset: str = ""
    risk_type: str = ""


@app.post("/api/hedge-session")
@limiter.limit("30/minute")
async def hedge_session(request: Request, body: HedgeRequest):
    try:
        result = run_hedge_session(body.exposure, body.asset or None, body.risk_type or None)
    except LLMError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    return result
```

- [ ] **Step 4: Run all API tests — all must pass**

```bash
cd backend && python -m pytest ../tests/test_api.py -v
```

Expected: all pass (including existing tests)

- [ ] **Step 5: Commit**

```bash
cd "d:/OMNP - Quant/Projetos/AlphaFeed"
git add backend/server.py tests/test_api.py
git commit -m "feat: add POST /api/hedge-session endpoint with CORS + 504 on LLMError"
```

---

## Task 7: Frontend — api.js + Hedge.jsx + App.jsx

**Files:**
- Modify: `frontend/src/api.js`
- Create: `frontend/src/tabs/Hedge.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add postHedgeSession to api.js**

Append to `frontend/src/api.js` (before the closing `export { EMP_IV }` line):

```js
export async function postHedgeSession({ exposure, asset, riskType }) {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60_000); // 60s — LLM pipeline
    const res = await fetch(`${API_BASE}/api/hedge-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exposure, asset: asset || "", risk_type: riskType || "" }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}
```

- [ ] **Step 2: Create Hedge.jsx**

```jsx
// frontend/src/tabs/Hedge.jsx
import { useState } from "react";
import { T } from "../tokens.js";
import { postHedgeSession } from "../api.js";

const RISK_TYPES = [
  { value: "",            label: "Select risk type (optional)" },
  { value: "risk-off",    label: "Risk-off / Market crash" },
  { value: "rate-hike",   label: "Rate hike" },
  { value: "recession",   label: "Recession" },
  { value: "geopolitical",label: "Geopolitical conflict" },
  { value: "crypto-crash",label: "Crypto crash" },
  { value: "tech-selloff",label: "Tech selloff" },
  { value: "other",       label: "Other" },
];

function CorrBadge({ score }) {
  const color = score >= 7 ? T.green : score >= 4 ? "#f59e0b" : T.dim;
  return (
    <span style={{ fontFamily: T.mono, fontSize: 11, color, fontWeight: 700,
      background: color + "18", padding: "2px 7px", borderRadius: 6 }}>
      {score.toFixed(1)} corr
    </span>
  );
}

function HedgeCard({ h }) {
  const [open, setOpen] = useState(false);
  const sideColor = h.hedge_side === "YES" ? T.green : "#f87171";
  return (
    <div style={{ background: T.card, border: `1px solid ${T.ln}`, borderRadius: 10, padding: "14px 16px", marginBottom: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <CorrBadge score={h.correlation_score} />
        <span style={{ fontSize: 11, fontWeight: 700, color: sideColor,
          background: sideColor + "20", padding: "2px 8px", borderRadius: 5 }}>
          {h.hedge_side}
        </span>
        {h.cross_signal && (
          <span title="Smart money + LLM agree" style={{ fontSize: 11, color: "#fbbf24" }}>⭐ cross-signal</span>
        )}
        <a href={h.url} target="_blank" rel="noopener noreferrer"
          style={{ color: T.text, fontWeight: 600, fontSize: 13, textDecoration: "none", flex: 1 }}>
          {h.question}
        </a>
      </div>

      <div style={{ display: "flex", gap: 20, marginTop: 10, flexWrap: "wrap", fontSize: 11, color: T.dim, fontFamily: T.mono }}>
        <span>YES {h.yes_price != null ? (h.yes_price * 100).toFixed(0) + "¢" : "—"}</span>
        <span>${h.volume_24h != null ? (h.volume_24h / 1000).toFixed(0) + "k" : "—"} vol</span>
        <span>{h.days_left != null ? h.days_left + "d" : "—"} left</span>
        {h.kelly_bet != null && <span style={{ color: "#fbbf24" }}>Kelly ${h.kelly_bet.toFixed(2)}</span>}
        {h.smart_money_exposure != null && <span>${(h.smart_money_exposure / 1000).toFixed(0)}k smart $</span>}
      </div>

      <button onClick={() => setOpen(o => !o)}
        style={{ marginTop: 8, background: "none", border: "none", cursor: "pointer",
          color: T.dim, fontSize: 11, padding: 0 }}>
        {open ? "▲ hide" : "▼ show analysis"}
      </button>
      {open && (
        <p style={{ marginTop: 8, fontSize: 12, color: T.dim, lineHeight: 1.6 }}>{h.narrative}</p>
      )}
    </div>
  );
}

export function HedgeTab() {
  const [exposure, setExposure] = useState("");
  const [asset, setAsset] = useState("");
  const [riskType, setRiskType] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | results | error
  const [result, setResult] = useState(null);

  async function handleRun() {
    if (!exposure.trim()) return;
    setStatus("loading");
    setResult(null);
    const data = await postHedgeSession({ exposure, asset, riskType });
    if (!data) { setStatus("error"); return; }
    setResult(data);
    setStatus("results");
  }

  const inp = {
    background: T.card, border: `1px solid ${T.ln}`, borderRadius: 8,
    color: T.text, fontSize: 13, padding: "8px 12px", width: "100%", boxSizing: "border-box",
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      {/* Input */}
      <div style={{ background: T.card, border: `1px solid ${T.ln}`, borderRadius: 12, padding: 20, marginBottom: 16 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color: T.text }}>🛡️ Hedge Session</h2>
        <p style={{ margin: "0 0 14px", fontSize: 11, color: T.dim }}>
          Describe your exposure. The system finds Polymarket bets that pay out in your worst case.
        </p>
        <textarea value={exposure} onChange={e => setExposure(e.target.value)} rows={3}
          placeholder='e.g. "I hold 2 BTC and I am worried about a tariff-driven risk-off event crashing crypto markets"'
          style={{ ...inp, resize: "vertical", marginBottom: 10 }} />
        <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
          <input value={asset} onChange={e => setAsset(e.target.value)}
            placeholder="Asset (optional, e.g. BTC)"
            style={{ ...inp, flex: 1, minWidth: 140 }} />
          <select value={riskType} onChange={e => setRiskType(e.target.value)}
            style={{ ...inp, flex: 1, minWidth: 200 }}>
            {RISK_TYPES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        <button onClick={handleRun} disabled={status === "loading" || !exposure.trim()}
          style={{ background: T.green, color: "#000", border: "none", borderRadius: 8,
            padding: "9px 20px", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
          {status === "loading" ? "Analysing your exposure…" : "Run Hedge"}
        </button>
      </div>

      {/* Parsed exposure card */}
      {status === "results" && result?.exposure_parsed && (
        <div style={{ background: T.card, border: `1px solid ${T.ln}`, borderRadius: 10,
          padding: "12px 16px", marginBottom: 16, fontSize: 12 }}>
          <span style={{ color: T.dim }}>Analysed as: </span>
          <strong style={{ color: T.text }}>{result.exposure_parsed.asset}</strong>
          <span style={{ color: T.dim }}> · {result.exposure_parsed.direction} · {result.exposure_parsed.risk_type}</span>
          <p style={{ margin: "6px 0 0", color: T.dim, fontStyle: "italic" }}>{result.exposure_parsed.scenario}</p>
        </div>
      )}

      {/* Hedge list */}
      {status === "results" && result?.hedges?.length > 0 && (
        <div>
          <p style={{ fontSize: 11, color: T.dim, marginBottom: 10 }}>
            {result.hedges.length} hedge{result.hedges.length !== 1 ? "s" : ""} found — sorted by correlation
          </p>
          {result.hedges.map(h => <HedgeCard key={h.slug} h={h} />)}
        </div>
      )}

      {status === "results" && result?.hedges?.length === 0 && (
        <p style={{ color: T.dim, fontSize: 13, textAlign: "center", padding: 40 }}>
          No hedges found with sufficient correlation. Try broadening your description.
        </p>
      )}

      {status === "error" && (
        <p style={{ color: "#f87171", fontSize: 13, textAlign: "center", padding: 40 }}>
          Failed to fetch hedges — backend may be starting up (free tier). Wait 30s and try again.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add Hedge tab to App.jsx**

In `App.jsx`, make two edits:

**Edit 1** — Add import after `AlphaTab` import:
```js
import { HedgeTab }         from "./tabs/Hedge.jsx";
```

**Edit 2** — Add to TABS array after the `alpha` entry:
```js
  { id: "hedge",      label: "Hedge",       icon: "🛡️" },
```

**Edit 3** — Add render in the content section after the `alpha` line:
```jsx
        {tab === "hedge"      && <HedgeTab />}
```

- [ ] **Step 4: Smoke test locally**

```bash
# Terminal 1
cd "d:/OMNP - Quant/Projetos/AlphaFeed/backend"
python -m uvicorn server:app --port 8000

# Terminal 2
cd "d:/OMNP - Quant/Projetos/AlphaFeed/frontend"
npm run dev
```

Open `http://localhost:3000`, click **🛡️ Hedge** tab.
Enter: `"I hold BTC and worry about a global recession"`, click **Run Hedge**.
Verify: parsed exposure card appears + hedge list loads within 30s.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && python -m pytest ../tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd "d:/OMNP - Quant/Projetos/AlphaFeed"
git add frontend/src/api.js frontend/src/tabs/Hedge.jsx frontend/src/App.jsx
git commit -m "feat: add Hedge tab — LLM-powered exposure hedge finder with Kelly enrichment"
```

---

## Task 8: Deploy to Production

- [ ] **Step 1: Push to GitHub (triggers Render + Vercel auto-deploy)**

```bash
cd "d:/OMNP - Quant/Projetos/AlphaFeed"
git push origin main
```

- [ ] **Step 2: Verify Render has GEMINI_API_KEY set**

In Render dashboard → alphafeed-api → Environment:
- `GEMINI_API_KEY` = your Gemini API key
- `GEMINI_MODEL` = `gemini-2.0-flash` (default)

- [ ] **Step 3: Smoke test production**

```bash
curl -s -X POST https://alphafeed-api.onrender.com/api/hedge-session \
  -H "Content-Type: application/json" \
  -d '{"exposure": "I hold BTC and worry about recession", "asset": "BTC", "risk_type": "recession"}' \
  | python -c "import json,sys; d=json.load(sys.stdin); print(len(d['hedges']), 'hedges found')"
```

Expected: `N hedges found` (N between 1-8)

- [ ] **Step 4: Final commit if any prod fixes needed**

```bash
git add -A && git commit -m "fix: production hedge session adjustments"
git push origin main
```

---

## Done ✓

Full feature delivered:
- `llm_client.py` — swappable LLM abstraction, fence stripping, retry
- `hedge_engine.py` — two-stage pipeline, enrichment, cross-signal
- `POST /api/hedge-session` — rate limited, 504 on LLM failure
- `🛡️ Hedge` tab — input → parsed card → ranked hedge list
- Full TDD coverage: 20+ tests across 3 test files
