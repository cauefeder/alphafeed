"""
tests/test_adapters.py — Unit tests for the adapter scripts.

These tests mock the upstream project imports so the adapters can be tested
without needing the PolyTraders or HedgePoly directories present.

Run:
    pytest tests/test_adapters.py -v
"""
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_opportunity(**kw):
    opp = MagicMock()
    defaults = dict(
        title="Will BTC hit $100K?", outcome="Yes", slug="btc-100k",
        cur_price=0.62, estimated_edge=0.048, kelly_bet=2.10, kelly_full=0.084,
        n_smart_traders=4, total_traders_checked=25,
        smart_trader_names=["trader_a", "trader_b"],
        count_signal=0.16, size_signal=0.72,
        total_exposure=18400.0, weighted_avg_entry=0.59,
        url="https://polymarket.com/event/btc-100k",
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(opp, k, v)
    return opp


def _make_signal(**kw):
    sig = MagicMock()
    defaults = dict(
        market_slug="btc-100k", question="Will BTC hit $100K?",
        side="YES", yes_value=22000.0, no_value=4800.0,
        total_value=26800.0, trader_count=5, confidence=0.82,
        url="https://polymarket.com/event/btc-100k",
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(sig, k, v)
    return sig


def _make_trader(**kw):
    t = MagicMock()
    defaults = dict(username="alpha_whale", rank=1, pnl=50000.0, proxy_wallet="0xabc")
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(t, k, v)
    return t


def _make_position(**kw):
    p = MagicMock()
    defaults = dict(
        condition_id="cid1", outcome="Yes", cur_price=0.62, avg_price=0.59,
        current_value=5000.0, title="Will BTC hit $100K?", slug="btc-100k",
        proxy_wallet="0xabc", username="alpha_whale", trader_rank=1, trader_pnl=50000.0,
    )
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


# ── PolyTraders adapter ───────────────────────────────────────────────────────

class TestPolytradersExport:
    def _import_adapter(self, monkeypatch, fake_traders, fake_positions, fake_opps):
        """Import the adapter with mocked upstream modules."""
        # Prevent sys.exit if PolyTraders dir doesn't exist
        mock_leaderboard = ModuleType("leaderboard")
        mock_leaderboard.fetch_top_traders = MagicMock(return_value=fake_traders)

        mock_positions = ModuleType("positions")
        mock_positions.fetch_all_positions = MagicMock(return_value=fake_positions)

        mock_kelly = ModuleType("kelly")
        mock_kelly.score_opportunities = MagicMock(return_value=fake_opps)

        # Inject mocks before import
        sys.modules.setdefault("leaderboard", mock_leaderboard)
        sys.modules.setdefault("positions", mock_positions)
        sys.modules.setdefault("kelly", mock_kelly)

        # Patch the path-existence check
        with patch("pathlib.Path.exists", return_value=True):
            import importlib
            # Remove cached module if already imported
            if "backend.adapters.polytraders_export" in sys.modules:
                del sys.modules["backend.adapters.polytraders_export"]
            from backend.adapters import polytraders_export as mod
        return mod, mock_leaderboard, mock_positions, mock_kelly

    def test_run_export_happy_path(self, monkeypatch, tmp_path):
        traders = [_make_trader()]
        positions = [_make_position()]
        opps = [_make_opportunity()]

        mod, lb, pos, kelly = self._import_adapter(monkeypatch, traders, positions, opps)
        monkeypatch.setattr(mod, "POLYTRADERS_DIR", tmp_path)
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

        result = mod.run_export(top_n=25, bankroll=100.0, time_period="WEEK")

        assert "generatedAt" in result
        assert result["tradersChecked"] == 1
        assert result["positionsScanned"] == 1
        assert len(result["opportunities"]) == 1
        opp = result["opportunities"][0]
        assert opp["title"] == "Will BTC hit $100K?"
        assert opp["kellyBet"] == 2.10
        assert opp["nSmartTraders"] == 4

    def test_run_export_no_traders(self, monkeypatch, tmp_path):
        mod, *_ = self._import_adapter(monkeypatch, [], [], [])
        monkeypatch.setattr(mod, "POLYTRADERS_DIR", tmp_path)
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

        result = mod.run_export()
        assert "error" in result
        assert result["opportunities"] == []

    def test_main_writes_json(self, monkeypatch, tmp_path):
        traders = [_make_trader()]
        positions = [_make_position()]
        opps = [_make_opportunity()]

        mod, *_ = self._import_adapter(monkeypatch, traders, positions, opps)
        monkeypatch.setattr(mod, "POLYTRADERS_DIR", tmp_path)
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

        mod.main()

        out_file = tmp_path / "polytraders.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "opportunities" in data


# ── HedgePoly adapter ─────────────────────────────────────────────────────────

class TestHedgepolyExport:
    def _import_adapter(self, monkeypatch, fake_signals):
        mock_sm = ModuleType("smart_money")
        mock_sm.build_smart_money_signals = MagicMock(return_value=fake_signals)
        sys.modules.setdefault("smart_money", mock_sm)

        with patch("pathlib.Path.exists", return_value=True):
            import importlib
            if "backend.adapters.hedgepoly_export" in sys.modules:
                del sys.modules["backend.adapters.hedgepoly_export"]
            from backend.adapters import hedgepoly_export as mod
        return mod, mock_sm

    def test_run_export_happy_path(self, monkeypatch, tmp_path):
        signals = [_make_signal(), _make_signal(side="NO", market_slug="fed-cut")]
        mod, _ = self._import_adapter(monkeypatch, signals)
        monkeypatch.setattr(mod, "HEDGEPOLY_DIR", tmp_path)
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

        result = mod.run_export()

        assert result["signalCount"] == 2
        assert len(result["signals"]) == 2
        assert result["signals"][0]["side"] == "YES"
        assert result["signals"][1]["side"] == "NO"

    def test_run_export_empty_signals(self, monkeypatch, tmp_path):
        mod, _ = self._import_adapter(monkeypatch, [])
        monkeypatch.setattr(mod, "HEDGEPOLY_DIR", tmp_path)
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

        result = mod.run_export()
        assert result["signalCount"] == 0
        assert result["signals"] == []

    def test_main_writes_json(self, monkeypatch, tmp_path):
        signals = [_make_signal()]
        mod, _ = self._import_adapter(monkeypatch, signals)
        monkeypatch.setattr(mod, "HEDGEPOLY_DIR", tmp_path)
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

        mod.main()

        out_file = tmp_path / "hedgepoly.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["signalCount"] == 1
        assert data["signals"][0]["question"] == "Will BTC hit $100K?"
