"""
Unit tests for the multi-strategy engine.
Run: pytest tests/ -v
"""

from __future__ import annotations
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from strategies.engine import (
    StrategyConfig, StrategyResult,
    synthesize_tqqq, synthesize_qld,
    strategy_buyhold_qqq,
    strategy_timing_qqq,
    strategy_timing_qld,
    strategy_timing_tqqq,
    strategy_combo,
)


# ─────────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────────

def _make_prices(n=400, base=350.0, seed=42) -> pd.Series:
    rng    = np.random.default_rng(seed)
    daily  = rng.normal(0.0005, 0.012, size=n)
    prices = base * np.exp(np.cumsum(daily))
    return pd.Series(prices, index=pd.bdate_range("2015-01-01", periods=n))


@pytest.fixture
def cfg():
    return StrategyConfig(
        buy_threshold=1.04, sell_threshold=0.97, ma_period=20,
        dip_threshold=-0.01, max_tranches=5, initial_capital=100_000.0,
    )


@pytest.fixture
def qqq():  return _make_prices(seed=1)
@pytest.fixture
def qld():  return _make_prices(base=50.0, seed=2)
@pytest.fixture
def tqqq(): return _make_prices(base=30.0, seed=3)


# ─────────────────────────────────────────────
#  Synthesis tests
# ─────────────────────────────────────────────

class TestSynthesis:
    def test_tqqq_starts_at_100(self, qqq):
        s = synthesize_tqqq(qqq)
        assert s.iloc[0] == pytest.approx(100.0, rel=0.01)

    def test_qld_starts_at_100(self, qqq):
        s = synthesize_qld(qqq)
        assert s.iloc[0] == pytest.approx(100.0, rel=0.01)

    def test_tqqq_more_volatile_than_qld(self, qqq):
        tqqq = synthesize_tqqq(qqq)
        qld  = synthesize_qld(qqq)
        assert tqqq.pct_change().std() > qld.pct_change().std()

    def test_no_nan_in_synthesis(self, qqq):
        assert not synthesize_tqqq(qqq).isna().any()
        assert not synthesize_qld(qqq).isna().any()


# ─────────────────────────────────────────────
#  Strategy 1: BuyHold QQQ
# ─────────────────────────────────────────────

class TestBuyHoldQQQ:
    def test_initial_value(self, qqq, cfg):
        r = strategy_buyhold_qqq(qqq, cfg)
        assert r.nav.iloc[0] == pytest.approx(cfg.initial_capital, rel=0.01)

    def test_always_invested(self, qqq, cfg):
        r = strategy_buyhold_qqq(qqq, cfg)
        assert r.signals.sum() == len(r.signals)

    def test_no_trades(self, qqq, cfg):
        r = strategy_buyhold_qqq(qqq, cfg)
        assert len(r.trades) == 0

    def test_nav_tracks_qqq(self, qqq, cfg):
        r     = strategy_buyhold_qqq(qqq, cfg)
        ratio = r.nav.iloc[-1] / r.nav.iloc[0]
        qqq_ratio = qqq.iloc[-1] / qqq.iloc[0]
        assert ratio == pytest.approx(qqq_ratio, rel=0.01)


# ─────────────────────────────────────────────
#  Strategy 2-4: Timing DCA
# ─────────────────────────────────────────────

class TestTimingStrategies:
    def test_no_negative_nav(self, qqq, qld, tqqq, cfg):
        for r in [
            strategy_timing_qqq(qqq, cfg),
            strategy_timing_qld(qqq, qld, cfg),
            strategy_timing_tqqq(qqq, tqqq, cfg),
        ]:
            assert (r.nav >= 0).all(), f"{r.name} went negative"

    def test_initial_value(self, qqq, qld, tqqq, cfg):
        for r in [
            strategy_timing_qqq(qqq, cfg),
            strategy_timing_qld(qqq, qld, cfg),
            strategy_timing_tqqq(qqq, tqqq, cfg),
        ]:
            assert r.nav.iloc[0] == pytest.approx(cfg.initial_capital, rel=0.01)

    def test_buy_only_on_dip(self, qqq, qld, tqqq, cfg):
        qqq_ret = qqq.pct_change()
        for r in [
            strategy_timing_qqq(qqq, cfg),
            strategy_timing_qld(qqq, qld, cfg),
            strategy_timing_tqqq(qqq, tqqq, cfg),
        ]:
            for t in r.trades:
                if t.action == "BUY":
                    ret = qqq_ret.loc[t.date]
                    assert ret <= cfg.dip_threshold + 1e-9

    def test_max_tranches_respected(self, qqq, qld, tqqq, cfg):
        for r in [
            strategy_timing_qqq(qqq, cfg),
            strategy_timing_qld(qqq, qld, cfg),
            strategy_timing_tqqq(qqq, tqqq, cfg),
        ]:
            count = 0
            for t in r.trades:
                if t.action == "SELL":
                    count = 0
                elif t.action == "BUY":
                    count += 1
                    assert count <= cfg.max_tranches


# ─────────────────────────────────────────────
#  Strategy 5: Combo
# ─────────────────────────────────────────────

class TestCombo:
    def test_initial_value(self, qqq, qld, tqqq, cfg):
        r = strategy_combo(qqq, qld, tqqq, cfg)
        assert r.nav.iloc[0] == pytest.approx(cfg.initial_capital, rel=0.02)

    def test_no_negative_nav(self, qqq, qld, tqqq, cfg):
        r = strategy_combo(qqq, qld, tqqq, cfg)
        assert (r.nav >= 0).all()

    def test_allocation_sum(self, qqq, qld, tqqq, cfg):
        assert abs(cfg.combo_bh_pct + cfg.combo_qld_pct + cfg.combo_tqqq_pct - 1.0) < 1e-9


# ─────────────────────────────────────────────
#  Metrics
# ─────────────────────────────────────────────

class TestMetrics:
    def test_summary_keys(self, qqq, cfg):
        r   = strategy_buyhold_qqq(qqq, cfg)
        s   = r.summary()
        expected = {"name","final_value","total_ret_pct","cagr_pct",
                    "max_dd_pct","sharpe","total_trades","time_in_market_pct"}
        assert expected.issubset(s.keys())

    def test_max_drawdown_non_positive(self, qqq, cfg):
        r = strategy_buyhold_qqq(qqq, cfg)
        assert r.summary()["max_dd_pct"] <= 0

    def test_time_in_market_bounded(self, qqq, qld, tqqq, cfg):
        for r in [
            strategy_buyhold_qqq(qqq, cfg),
            strategy_timing_tqqq(qqq, tqqq, cfg),
            strategy_combo(qqq, qld, tqqq, cfg),
        ]:
            pct = r.summary()["time_in_market_pct"]
            assert 0 <= pct <= 100
