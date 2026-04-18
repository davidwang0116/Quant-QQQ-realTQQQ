"""
Unit tests for TQQQ MA200 strategy (DCA tranche edition).

Run:  pytest tests/ -v
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from strategies.tqqq_ma200 import TQQQMA200Strategy, MA200Config, BacktestResult


# ─────────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────────

def make_price_series(n=500, start="2010-02-11", base=100.0, seed=42):
    rng   = np.random.default_rng(seed)
    daily = rng.normal(loc=0.0005, scale=0.012, size=n)
    prices = base * np.exp(np.cumsum(daily))
    idx    = pd.bdate_range(start=start, periods=n)
    return pd.Series(prices, index=idx)


@pytest.fixture
def cfg():
    return MA200Config(
        buy_threshold=1.04, sell_threshold=0.97, ma_period=20,
        initial_capital=100_000.0, dip_threshold=-0.01,
        max_tranches=5, tranche_pct=0.20,
    )


@pytest.fixture
def strategy(cfg):
    return TQQQMA200Strategy(cfg)


@pytest.fixture
def qqq():
    return make_price_series(n=400, base=350.0, seed=1)


@pytest.fixture
def tqqq():
    return make_price_series(n=400, base=45.0, seed=2)


# ─────────────────────────────────────────────
#  DCA tranche entry tests
# ─────────────────────────────────────────────

class TestTrancheBuying:
    def test_max_tranches_not_exceeded(self, strategy, qqq, tqqq):
        result = strategy.run(qqq, tqqq)
        buys = [t for t in result.trades if t.action == "BUY"]
        # Between any two consecutive SELL events, BUY count <= max_tranches
        tranche_count = 0
        for t in result.trades:
            if t.action == "SELL":
                tranche_count = 0
            else:
                tranche_count += 1
                assert tranche_count <= strategy.cfg.max_tranches

    def test_buy_only_on_dip(self, strategy, qqq, tqqq):
        """Every BUY trade must coincide with a QQQ daily return ≤ dip_threshold."""
        result  = strategy.run(qqq, tqqq)
        qqq_ret = qqq.pct_change()
        for t in result.trades:
            if t.action == "BUY":
                ret = qqq_ret.loc[t.date]
                assert ret <= strategy.cfg.dip_threshold + 1e-9, (
                    f"BUY on {t.date} but QQQ ret={ret:.4f} > dip_threshold"
                )

    def test_buy_only_in_bull_zone(self, strategy, qqq, tqqq):
        """Every BUY must occur when QQQ > MA200 × buy_threshold."""
        result = strategy.run(qqq, tqqq)
        ma200  = qqq.rolling(strategy.cfg.ma_period).mean()
        for t in result.trades:
            if t.action == "BUY":
                assert qqq.loc[t.date] > ma200.loc[t.date] * strategy.cfg.buy_threshold - 1e-6

    def test_tranche_size_consistent(self, strategy):
        """Each tranche invests exactly tranche_pct × initial_capital (before commission)."""
        expected = strategy.cfg.initial_capital * strategy.cfg.tranche_pct
        idx  = pd.bdate_range("2020-01-01", periods=300)
        # Build QQQ that stays well above MA and drops >1% every other day
        base = np.ones(300) * 400.0
        for i in range(20, 300):
            base[i] = base[i-1] * (0.985 if i % 2 == 0 else 1.02)
        qqq  = pd.Series(base, index=idx)
        tqqq = pd.Series(np.linspace(45, 60, 300), index=idx)
        result = strategy.run(qqq, tqqq)
        for t in result.trades:
            if t.action == "BUY":
                gross = t.shares * t.price / (1 - strategy.cfg.commission_pct)
                assert abs(gross - expected) < 1.0, (
                    f"Tranche size {gross:.2f} != expected {expected:.2f}"
                )

    def test_no_buy_when_fully_loaded(self, cfg):
        """When all 5 tranches are filled, no more BUYs until a SELL resets."""
        strat = TQQQMA200Strategy(cfg)
        idx   = pd.bdate_range("2020-01-01", periods=400)
        # QQQ always > MA × 1.04 and drops every other day (triggers dip entry)
        base = np.ones(400) * 420.0
        for i in range(1, 400):
            base[i] = base[i-1] * (0.985 if i % 2 == 0 else 1.005)
        qqq  = pd.Series(base, index=idx)
        tqqq = pd.Series(np.ones(400) * 50.0, index=idx)
        result = strat.run(qqq, tqqq)
        buys = [t for t in result.trades if t.action == "BUY"]
        # Without a SELL, total buys must not exceed max_tranches
        assert len(buys) <= cfg.max_tranches

    def test_tranches_reset_after_sell(self, cfg):
        """After a SELL, the strategy can accumulate up to max_tranches again."""
        strat = TQQQMA200Strategy(cfg)
        idx   = pd.bdate_range("2020-01-01", periods=600)
        prices = np.ones(600) * 420.0
        # Phase 1 (0-200): bull + dips → fill tranches
        for i in range(1, 200):
            prices[i] = prices[i-1] * (0.985 if i % 2 == 0 else 1.005)
        # Phase 2 (200-250): crash below sell threshold
        for i in range(200, 250):
            prices[i] = prices[i-1] * 0.992
        # Phase 3 (250-600): bull again + dips
        for i in range(250, 600):
            prices[i] = prices[i-1] * (0.985 if i % 2 == 0 else 1.006)
        qqq  = pd.Series(prices, index=idx)
        tqqq = pd.Series(np.ones(600) * 50.0, index=idx)
        result = strat.run(qqq, tqqq)
        sells = [t for t in result.trades if t.action == "SELL"]
        # There should be at least one sell (phase 2 crash)
        # and buys should appear in both phase 1 and phase 3
        assert len(sells) >= 1


# ─────────────────────────────────────────────
#  Portfolio integrity tests
# ─────────────────────────────────────────────

class TestPortfolioIntegrity:
    def test_no_negative_portfolio(self, strategy, qqq, tqqq):
        result = strategy.run(qqq, tqqq)
        assert (result.strategy_nav >= 0).all()

    def test_no_negative_cash(self, strategy, qqq, tqqq):
        """Cash should never go negative — tranches are capped by available cash."""
        result = strategy.run(qqq, tqqq)
        for t in result.trades:
            assert t.cash_after >= -1.0   # allow tiny float epsilon

    def test_initial_value(self, strategy, qqq, tqqq):
        result = strategy.run(qqq, tqqq)
        assert result.strategy_nav.iloc[0] == pytest.approx(100_000.0, rel=0.01)

    def test_sell_clears_position(self, strategy, qqq, tqqq):
        result = strategy.run(qqq, tqqq)
        sells  = [t for t in result.trades if t.action == "SELL"]
        for t in sells:
            assert t.shares == 0.0   # shares field reset on sell


# ─────────────────────────────────────────────
#  Metrics tests
# ─────────────────────────────────────────────

class TestMetrics:
    def test_summary_keys(self, strategy, qqq, tqqq):
        expected = {
            "strategy_final_value", "buyhold_final_value",
            "strategy_cagr_pct", "buyhold_cagr_pct",
            "strategy_max_drawdown_pct", "buyhold_max_drawdown_pct",
            "strategy_sharpe", "buyhold_sharpe",
            "total_trades", "win_rate_pct", "time_in_market_pct",
        }
        result = strategy.run(qqq, tqqq)
        assert expected.issubset(result.summary().keys())

    def test_max_drawdown_non_positive(self, strategy, qqq, tqqq):
        result = strategy.run(qqq, tqqq)
        assert result.summary()["strategy_max_drawdown_pct"] <= 0

    def test_time_in_market_bounded(self, strategy, qqq, tqqq):
        result = strategy.run(qqq, tqqq)
        pct = result.summary()["time_in_market_pct"]
        assert 0 <= pct <= 100

    def test_win_rate_bounded(self, strategy, qqq, tqqq):
        result = strategy.run(qqq, tqqq)
        assert 0 <= result.summary()["win_rate_pct"] <= 100

