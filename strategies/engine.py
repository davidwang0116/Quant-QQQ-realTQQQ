"""
Strategy Engine
===============
Five strategies, all sharing the same MA200 signal logic and DCA parameters.

Strategy 1 — BuyHoldQQQ       : 100% QQQ, buy and hold, no timing
Strategy 2 — TimingQQQ        : QQQ, MA200 timing + dip DCA entry
Strategy 3 — TimingQLD        : QLD (2x), MA200 timing + dip DCA entry
Strategy 4 — TimingTQQQ       : TQQQ (3x), MA200 timing + dip DCA entry
Strategy 5 — Combo            : 60% QQQ buy-hold + 30% QLD timing + 10% TQQQ timing
                                 (allocations rebalance dynamically within each period)

Signal source for strategies 2-5: QQQ MA200
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────

@dataclass
class StrategyConfig:
    buy_threshold:  float = 1.04   # QQQ > MA200 × this  → bull zone
    sell_threshold: float = 0.97   # QQQ < MA200 × this  → bear zone
    ma_period:      int   = 200
    dip_threshold:  float = -0.01  # QQQ daily return ≤ this triggers DCA entry
    max_tranches:   int   = 5      # shared across strategies 2-5
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001  # 0.1% per trade
    # Combo strategy allocations
    combo_bh_pct:     float = 0.60  # buy-hold QQQ portion
    combo_qld_pct:    float = 0.30  # timing QLD portion
    combo_tqqq_pct:   float = 0.10  # timing TQQQ portion


# ─────────────────────────────────────────────────────────────────
#  Data helpers
# ─────────────────────────────────────────────────────────────────

def synthesize_leveraged(
    qqq: pd.Series,
    leverage: float,
    annual_cost: float = 0.06,
) -> pd.Series:
    """
    Synthesize a leveraged price series from QQQ daily returns.

    daily_cost = (1 + annual_cost)^(1/252) - 1
    leveraged_ret = qqq_ret * leverage - daily_cost
    price = cumprod(1 + leveraged_ret) * 100   (base = 100)

    annual_cost default 6% covers ~0.95% expense ratio + ~5% vol decay.
    """
    daily_cost = (1 + annual_cost) ** (1 / 252) - 1
    ret        = qqq.pct_change().fillna(0)
    lev_ret    = ret * leverage - daily_cost
    return (1 + lev_ret).cumprod() * 100


def synthesize_tqqq(qqq: pd.Series, annual_cost: float = 0.06) -> pd.Series:
    return synthesize_leveraged(qqq, leverage=3.0, annual_cost=annual_cost)


def synthesize_qld(qqq: pd.Series, annual_cost: float = 0.04) -> pd.Series:
    """QLD = 2x QQQ. Lower cost than TQQQ (~0.95% ER + ~3% vol decay)."""
    return synthesize_leveraged(qqq, leverage=2.0, annual_cost=annual_cost)


def build_price_series(
    qqq_full:  pd.Series,
    real_qld:  Optional[pd.Series],
    real_tqqq: Optional[pd.Series],
    start: str,
    end:   str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Return (qqq, qld, tqqq) price series for [start, end].
    Fills pre-inception periods with synthetic data spliced to real data.
    """
    qqq = qqq_full.loc[start:end]

    # ── QLD: real from 2006-06-21, synthetic before ───────────────
    qld_synth = synthesize_qld(qqq_full).loc[start:end]
    if real_qld is not None:
        real_slice = real_qld.loc[start:end]
        if not real_slice.empty:
            first_real = real_slice.index[0]
            # Scale synthetic tail so it ends at the same value as real starts
            if first_real > qld_synth.index[0]:
                scale = real_slice.iloc[0] / qld_synth.loc[first_real]
                pre   = qld_synth.loc[:first_real].iloc[:-1] * scale
                qld   = pd.concat([pre, real_slice])
            else:
                qld = real_slice
        else:
            qld = qld_synth
    else:
        qld = qld_synth

    # ── TQQQ: real from 2010-02-09, synthetic before ─────────────
    tqqq_synth = synthesize_tqqq(qqq_full).loc[start:end]
    if real_tqqq is not None:
        real_slice = real_tqqq.loc[start:end]
        if not real_slice.empty:
            first_real = real_slice.index[0]
            if first_real > tqqq_synth.index[0]:
                scale = real_slice.iloc[0] / tqqq_synth.loc[first_real]
                pre   = tqqq_synth.loc[:first_real].iloc[:-1] * scale
                tqqq  = pd.concat([pre, real_slice])
            else:
                tqqq = real_slice
        else:
            tqqq = tqqq_synth
    else:
        tqqq = tqqq_synth

    return qqq, qld.reindex(qqq.index).ffill(), tqqq.reindex(qqq.index).ffill()


# ─────────────────────────────────────────────────────────────────
#  Trade record
# ─────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    date:            pd.Timestamp
    action:          str    # "BUY" | "SELL"
    ticker:          str
    price:           float
    shares:          float
    value:           float
    cash_after:      float
    portfolio_value: float
    reason:          str
    tranche:         int = 0


# ─────────────────────────────────────────────────────────────────
#  Result container
# ─────────────────────────────────────────────────────────────────

@dataclass
class StrategyResult:
    name:    str
    nav:     pd.Series        # portfolio value over time
    signals: pd.Series        # 1 = in market, 0 = cash
    trades:  list[Trade]
    config:  StrategyConfig

    def cagr(self) -> float:
        s = self.nav
        n = (s.index[-1] - s.index[0]).days / 365.25
        if n <= 0:
            return 0.0
        return float((s.iloc[-1] / s.iloc[0]) ** (1 / n) - 1)

    def max_drawdown(self) -> float:
        s  = self.nav
        dd = (s / s.cummax()) - 1
        return float(dd.min())

    def sharpe(self, risk_free: float = 0.04) -> float:
        ret    = self.nav.pct_change().dropna()
        excess = ret - risk_free / 252
        std    = excess.std()
        return float(excess.mean() / std * np.sqrt(252)) if std > 0 else 0.0

    def total_return(self) -> float:
        return float(self.nav.iloc[-1] / self.nav.iloc[0] - 1)

    def summary(self) -> dict:
        initial = self.config.initial_capital
        return {
            "name":          self.name,
            "final_value":   round(self.nav.iloc[-1], 2),
            "total_ret_pct": round(self.total_return() * 100, 2),
            "cagr_pct":      round(self.cagr() * 100, 2),
            "max_dd_pct":    round(self.max_drawdown() * 100, 2),
            "sharpe":        round(self.sharpe(), 2),
            "total_trades":  len(self.trades),
            "time_in_market_pct": round(float(self.signals.mean()) * 100, 2),
        }


# ─────────────────────────────────────────────────────────────────
#  MA200 signal generator (shared)
# ─────────────────────────────────────────────────────────────────

def _ma200_signals(qqq: pd.Series, cfg: StrategyConfig) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Returns (ma200, sell_flag, qqq_ret).
    sell_flag = 1 when QQQ < MA200 * sell_threshold.
    """
    ma200     = qqq.rolling(cfg.ma_period, min_periods=cfg.ma_period).mean()
    sell_flag = (qqq < ma200 * cfg.sell_threshold).astype(int)
    qqq_ret   = qqq.pct_change()
    return ma200, sell_flag, qqq_ret


# ─────────────────────────────────────────────────────────────────
#  Core DCA timing engine (reusable for any asset)
# ─────────────────────────────────────────────────────────────────

def _run_timing_dca(
    name:      str,
    ticker:    str,
    qqq:       pd.Series,
    asset:     pd.Series,
    cfg:       StrategyConfig,
    capital:   float,
) -> StrategyResult:
    """
    MA200 timing + dip DCA entry for any asset.
    Returns StrategyResult with portfolio NAV starting at `capital`.
    """
    common    = qqq.index.intersection(asset.index)
    qqq       = qqq.loc[common]
    asset     = asset.loc[common]
    ma200, sell_flag, qqq_ret = _ma200_signals(qqq, cfg)

    cash          = capital
    shares        = 0.0
    tranches_held = 0
    trades: list[Trade] = []
    portfolio     = []
    signal_track  = []

    for date in common:
        price = asset.loc[date]
        qp    = qqq.loc[date]
        ma    = ma200.loc[date]
        ret   = qqq_ret.loc[date]
        pv    = cash + shares * price

        # EXIT
        if sell_flag.loc[date] == 1 and shares > 0:
            proceeds   = shares * price
            commission = proceeds * cfg.commission_pct
            cash       = cash + proceeds - commission
            pv         = cash
            trades.append(Trade(
                date=date, action="SELL", ticker=ticker,
                price=price, shares=shares, value=proceeds,
                cash_after=cash, portfolio_value=pv,
                reason=f"BEAR: QQQ {qp:.2f} < MA200 {ma:.2f}×{cfg.sell_threshold}",
                tranche=0,
            ))
            shares        = 0.0
            tranches_held = 0

        # ENTRY
        elif (
            pd.notna(ma)
            and qp > ma * cfg.buy_threshold
            and pd.notna(ret)
            and ret <= cfg.dip_threshold
            and tranches_held < cfg.max_tranches
            and cash > 0
        ):
            tranches_held += 1
            pv_now        = cash + shares * price
            tranche_cash  = pv_now / cfg.max_tranches
            if tranches_held == cfg.max_tranches:
                tranche_cash = cash
            else:
                tranche_cash = min(tranche_cash, cash)
            invest     = tranche_cash * (1 - cfg.commission_pct)
            new_shares = invest / price
            shares    += new_shares
            cash      -= tranche_cash
            pv         = cash + shares * price
            trades.append(Trade(
                date=date, action="BUY", ticker=ticker,
                price=price, shares=new_shares, value=invest,
                cash_after=cash, portfolio_value=pv,
                reason=(
                    f"DIP BUY {tranches_held}/{cfg.max_tranches}: "
                    f"QQQ {qp:.2f}>MA200 {ma:.2f}×{cfg.buy_threshold} "
                    f"ret {ret*100:.2f}%"
                ),
                tranche=tranches_held,
            ))

        portfolio.append(cash + shares * price)
        signal_track.append(1 if shares > 0 else 0)

    nav = pd.Series(portfolio, index=common, name=name)
    sig = pd.Series(signal_track, index=common, name="signal")
    return StrategyResult(name=name, nav=nav, signals=sig, trades=trades, config=cfg)


# ─────────────────────────────────────────────────────────────────
#  Five public strategy runners
# ─────────────────────────────────────────────────────────────────

def strategy_buyhold_qqq(
    qqq: pd.Series,
    cfg: StrategyConfig,
) -> StrategyResult:
    """Strategy 1: 100% QQQ buy and hold."""
    capital = cfg.initial_capital
    shares  = capital / qqq.iloc[0]
    nav     = (shares * qqq).rename("BuyHold QQQ")
    sig     = pd.Series(1, index=qqq.index, name="signal")
    return StrategyResult(
        name="BuyHold QQQ", nav=nav, signals=sig, trades=[], config=cfg
    )


def strategy_timing_qqq(
    qqq: pd.Series,
    cfg: StrategyConfig,
) -> StrategyResult:
    """Strategy 2: QQQ with MA200 timing + dip DCA."""
    return _run_timing_dca(
        name="Timing QQQ", ticker="QQQ",
        qqq=qqq, asset=qqq, cfg=cfg, capital=cfg.initial_capital,
    )


def strategy_timing_qld(
    qqq: pd.Series,
    qld: pd.Series,
    cfg: StrategyConfig,
) -> StrategyResult:
    """Strategy 3: QLD (2x) with MA200 timing + dip DCA."""
    return _run_timing_dca(
        name="Timing QLD", ticker="QLD",
        qqq=qqq, asset=qld, cfg=cfg, capital=cfg.initial_capital,
    )


def strategy_timing_tqqq(
    qqq:  pd.Series,
    tqqq: pd.Series,
    cfg:  StrategyConfig,
) -> StrategyResult:
    """Strategy 4: TQQQ (3x) with MA200 timing + dip DCA."""
    return _run_timing_dca(
        name="Timing TQQQ", ticker="TQQQ",
        qqq=qqq, asset=tqqq, cfg=cfg, capital=cfg.initial_capital,
    )


def strategy_combo(
    qqq:  pd.Series,
    qld:  pd.Series,
    tqqq: pd.Series,
    cfg:  StrategyConfig,
) -> StrategyResult:
    """
    Strategy 5: Combo portfolio.
      60% QQQ buy-hold  (cfg.combo_bh_pct)
      30% QLD timing    (cfg.combo_qld_pct)
      10% TQQQ timing   (cfg.combo_tqqq_pct)

    Each sub-portfolio starts with its allocated capital.
    Final NAV = sum of the three sub-portfolio NAVs.
    """
    capital     = cfg.initial_capital
    cap_bh      = capital * cfg.combo_bh_pct
    cap_qld     = capital * cfg.combo_qld_pct
    cap_tqqq    = capital * cfg.combo_tqqq_pct

    bh_cfg      = StrategyConfig(**{**cfg.__dict__, "initial_capital": cap_bh})
    qld_cfg     = StrategyConfig(**{**cfg.__dict__, "initial_capital": cap_qld})
    tqqq_cfg    = StrategyConfig(**{**cfg.__dict__, "initial_capital": cap_tqqq})

    bh_res      = strategy_buyhold_qqq(qqq, bh_cfg)
    qld_res     = _run_timing_dca("QLD-leg", "QLD",  qqq, qld,  qld_cfg,  cap_qld)
    tqqq_res    = _run_timing_dca("TQQQ-leg","TQQQ", qqq, tqqq, tqqq_cfg, cap_tqqq)

    common      = bh_res.nav.index \
                    .intersection(qld_res.nav.index) \
                    .intersection(tqqq_res.nav.index)

    combo_nav   = (
        bh_res.nav.loc[common]
        + qld_res.nav.loc[common]
        + tqqq_res.nav.loc[common]
    ).rename("Combo 60/30/10")

    # Signal = 1 if any sub-portfolio is invested
    combo_sig   = (
        (qld_res.signals.loc[common] + tqqq_res.signals.loc[common]) > 0
    ).astype(int)

    all_trades  = sorted(
        qld_res.trades + tqqq_res.trades,
        key=lambda t: t.date
    )

    return StrategyResult(
        name="Combo 60/30/10",
        nav=combo_nav,
        signals=combo_sig,
        trades=all_trades,
        config=cfg,
    )
