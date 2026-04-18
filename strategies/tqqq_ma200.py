"""
TQQQ MA200 Bull/Bear Timing Strategy  (DCA Entry Edition)
==========================================================
Signal Logic:
  EXIT  — QQQ < MA200 × 0.97  → clear full position → Cash
  ENTRY — ALL three conditions must be met on the same day:
            1. QQQ > MA200 × 1.04        (confirmed bull zone)
            2. QQQ daily return < -1%    (dip entry — buy the pullback)
            3. tranches_held < max_tranches  (position not yet full)
          → invest 20% of original capital (1 tranche) into TQQQ

  A "tranche" = initial_capital / max_tranches.
  Once all 5 tranches are deployed the entry signal is ignored until
  a SELL clears the position and resets the tranche counter.

Author: Your Name
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class MA200Config:
    """Strategy parameters — tweak and re-run backtest to optimise."""
    buy_threshold: float  = 1.04   # QQQ must be above MA200 × this
    sell_threshold: float = 0.97   # QQQ must be below MA200 × this
    ma_period: int        = 200
    signal_ticker: str    = "QQQ"  # ticker used for MA signal
    trade_ticker: str     = "TQQQ" # ticker we actually trade
    initial_capital: float = 100_000.0
    commission_pct: float  = 0.001  # 0.1% per trade
    # ── DCA entry parameters ──────────────────────────────────────
    dip_threshold: float  = -0.01  # QQQ daily return must be ≤ this to trigger entry
    max_tranches: int     = 5      # maximum number of buy tranches
    tranche_pct: float    = 0.20   # fraction of initial_capital per tranche


@dataclass
class Trade:
    date: pd.Timestamp
    action: str           # "BUY" | "SELL"
    price: float
    shares: float
    value: float
    cash_after: float
    portfolio_value: float
    reason: str
    tranche: int = 0      # which tranche this BUY is (1-5); 0 for SELL


class TQQQMA200Strategy:
    """
    Vectorised signal generator + event-driven trade executor.

    Usage
    -----
    >>> strat = TQQQMA200Strategy(config)
    >>> results = strat.run(qqq_df, tqqq_df)
    >>> print(results.summary())
    """

    def __init__(self, config: Optional[MA200Config] = None):
        self.cfg = config or MA200Config()
        self.trades: list[Trade] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_signals(self, qqq: pd.Series) -> pd.Series:
        """
        Returns a bear-zone flag Series: 1 = in sell zone, 0 = not.
        Actual entry decisions are made in run() using the dip condition.
        """
        ma        = qqq.rolling(self.cfg.ma_period, min_periods=self.cfg.ma_period).mean()
        sell_zone = qqq < ma * self.cfg.sell_threshold
        return sell_zone.astype(int)

    def run(self, qqq_prices: pd.Series, tqqq_prices: pd.Series) -> "BacktestResult":
        """
        Execute the DCA tranche strategy and return a BacktestResult.

        Entry rules (ALL must be true on the same day):
          1. QQQ > MA200 × buy_threshold       — confirmed bull zone
          2. QQQ daily return ≤ dip_threshold  — pullback entry (-1% default)
          3. tranches_held < max_tranches       — position not yet full

        Exit rule:
          QQQ < MA200 × sell_threshold  → sell ALL shares, reset tranches

        Parameters
        ----------
        qqq_prices  : pd.Series  — QQQ daily adjusted close, DatetimeIndex
        tqqq_prices : pd.Series  — TQQQ daily adjusted close, DatetimeIndex
        """
        common = qqq_prices.index.intersection(tqqq_prices.index)
        qqq    = qqq_prices.loc[common]
        tqqq   = tqqq_prices.loc[common]

        ma200      = qqq.rolling(self.cfg.ma_period).mean()
        qqq_ret    = qqq.pct_change()          # daily return of QQQ
        sell_flags = self.generate_signals(qqq) # 1 = bear zone triggered

        # ── portfolio state ───────────────────────────────────────
        cash            = self.cfg.initial_capital
        shares          = 0.0
        tranches_held   = 0                    # how many tranches are deployed
    
        self.trades.clear()
        portfolio      = []
        signal_tracker = []   # 0 = flat/partial, 1 = any position

        for date in common:
            tqqq_price = tqqq.loc[date]
            qqq_price  = qqq.loc[date]
            ma         = ma200.loc[date]
            ret        = qqq_ret.loc[date]
            pv         = cash + shares * tqqq_price

            # ── EXIT: QQQ breaks below sell threshold ─────────────
            if sell_flags.loc[date] == 1 and shares > 0:
                proceeds   = shares * tqqq_price
                commission = proceeds * self.cfg.commission_pct
                cash       = cash + proceeds - commission
                pv         = cash
                self.trades.append(Trade(
                    date=date, action="SELL",
                    price=tqqq_price, shares=shares, value=proceeds,
                    cash_after=cash, portfolio_value=pv,
                    reason=(
                        f"BEAR EXIT: QQQ {qqq_price:.2f} < "
                        f"MA200 {ma:.2f} × {self.cfg.sell_threshold} | "
                        f"cleared {tranches_held} tranches"
                    ),
                    tranche=0,
                ))
                shares        = 0.0
                tranches_held = 0

            # ── ENTRY: bull zone + dip + tranches available ────────
            elif (
                pd.notna(ma)                                  # MA warmed up
                and qqq_price > ma * self.cfg.buy_threshold   # bull zone
                and pd.notna(ret)
                and ret <= self.cfg.dip_threshold             # dip entry
                and tranches_held < self.cfg.max_tranches     # not fully loaded
                and cash > 0                                  # has cash
            ):
                tranche_cash = (cash + shares * tqqq_price) * self.cfg.tranche_pct  # 当前权益的20%
                tranche_cash = min(tranche_cash, cash)    # 不能超过剩余现金
                tranches_held += 1
                invest     = tranche_cash - tranche_cash * self.cfg.commission_pct
                new_shares = invest / tqqq_price
                shares    += new_shares
                cash      -= tranche_cash
                pv         = cash + shares * tqqq_price
                self.trades.append(Trade(
                    date=date, action="BUY",
                    price=tqqq_price, shares=new_shares, value=invest,
                    cash_after=cash, portfolio_value=pv,
                    reason=(
                        f"DIP BUY tranche {tranches_held}/{self.cfg.max_tranches}: "
                        f"QQQ {qqq_price:.2f} > MA200 {ma:.2f} × {self.cfg.buy_threshold} | "
                        f"QQQ ret {ret*100:.2f}% ≤ {self.cfg.dip_threshold*100:.0f}%"
                    ),
                    tranche=tranches_held,
                ))

            portfolio.append({"date": date, "portfolio_value": cash + shares * tqqq_price})
            signal_tracker.append(1 if shares > 0 else 0)

        nav_df  = pd.DataFrame(portfolio).set_index("date")
        sig_ser = pd.Series(signal_tracker, index=common, name="signal")

        # Buy-and-hold benchmark
        bh_shares = self.cfg.initial_capital / qqq.iloc[0]
        bh_values = bh_shares * qqq
        bh_df     = bh_values.rename("buyhold_value").to_frame()

        return BacktestResult(
            strategy_nav  = nav_df["portfolio_value"],
            buyhold_nav   = bh_df["buyhold_value"],
            signals       = sig_ser,
            ma200         = ma200,
            trades        = self.trades,
            config        = self.cfg,
        )


# ------------------------------------------------------------------
# Result container
# ------------------------------------------------------------------

@dataclass
class BacktestResult:
    strategy_nav : pd.Series
    buyhold_nav  : pd.Series
    signals      : pd.Series
    ma200        : pd.Series
    trades       : list[Trade]
    config       : MA200Config

    # ---- Metrics ------------------------------------------------

    def cagr(self, series: pd.Series) -> float:
        n_years = (series.index[-1] - series.index[0]).days / 365.25
        return (series.iloc[-1] / series.iloc[0]) ** (1 / n_years) - 1

    def max_drawdown(self, series: pd.Series) -> float:
        peak = series.cummax()
        dd   = (series - peak) / peak
        return float(dd.min())

    def sharpe(self, series: pd.Series, risk_free: float = 0.04) -> float:
        daily_ret = series.pct_change().dropna()
        excess    = daily_ret - risk_free / 252
        return float(excess.mean() / excess.std() * np.sqrt(252))

    def time_in_market(self) -> float:
        return float(self.signals.mean())

    def summary(self) -> dict:
        s = self.strategy_nav
        b = self.buyhold_nav
        buys  = [t for t in self.trades if t.action == "BUY"]
        sells = [t for t in self.trades if t.action == "SELL"]
        wins  = sum(
            1 for buy, sell in zip(buys, sells)
            if sell.portfolio_value > buy.portfolio_value
        )
        win_rate = wins / len(sells) if sells else 0.0

        return {
            "strategy_final_value"   : round(s.iloc[-1], 2),
            "buyhold_final_value"    : round(b.iloc[-1], 2),
            "strategy_cagr_pct"      : round(self.cagr(s) * 100, 2),
            "buyhold_cagr_pct"       : round(self.cagr(b) * 100, 2),
            "strategy_max_drawdown_pct": round(self.max_drawdown(s) * 100, 2),
            "buyhold_max_drawdown_pct" : round(self.max_drawdown(b) * 100, 2),
            "strategy_sharpe"        : round(self.sharpe(s), 2),
            "buyhold_sharpe"         : round(self.sharpe(b), 2),
            "total_trades"           : len(self.trades),
            "win_rate_pct"           : round(win_rate * 100, 2),
            "time_in_market_pct"     : round(self.time_in_market() * 100, 2),
        }
