"""
Backtest runner — ties data, strategy, and reporting together.

Run from project root:
    python backtest/run.py
    python backtest/run.py --refresh          # force re-download data
    python backtest/run.py --buy 1.05 --sell 0.96   # custom thresholds
"""

from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")           # headless — works on servers / CI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Make sure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.downloader import fetch_prices
from strategies.tqqq_ma200 import TQQQMA200Strategy, MA200Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

TQQQ_INCEPTION = "2010-02-09"


# ─────────────────────────────────────────────
#  Core runner
# ─────────────────────────────────────────────

def run_backtest(cfg: MA200Config, force_refresh: bool = False):
    logger.info("=== TQQQ MA200 Strategy Backtest ===")
    logger.info(f"Buy threshold:  MA200 × {cfg.buy_threshold}")
    logger.info(f"Sell threshold: MA200 × {cfg.sell_threshold}")
    logger.info(f"MA period:      {cfg.ma_period} days")
    logger.info(f"Initial capital: ${cfg.initial_capital:,.0f}")

    # ── 1. Download data ──────────────────────────────────────────
    logger.info("Fetching price data...")
    qqq_full  = fetch_prices("QQQ",  start="1999-03-10", force_refresh=force_refresh)
    tqqq      = fetch_prices("TQQQ", start="1999-03-10", force_refresh=force_refresh)

    # Restrict QQQ to TQQQ era for the backtest (but MA200 needs prior history)
    qqq_signal = qqq_full   # full history for MA200 warm-up

    # ── 2. Run strategy ───────────────────────────────────────────
    strategy = TQQQMA200Strategy(cfg)
    result   = strategy.run(qqq_signal, tqqq)

    # ── 3. Print summary ──────────────────────────────────────────
    summary = result.summary()
    print("\n" + "─" * 54)
    print("  BACKTEST RESULTS")
    print("─" * 54)
    _row("Strategy Final Value",   f"${summary['strategy_final_value']:>12,.0f}")
    _row("Buy & Hold Final Value", f"${summary['buyhold_final_value']:>12,.0f}")
    print("─" * 54)
    _row("Strategy CAGR",          f"{summary['strategy_cagr_pct']:>11.1f}%")
    _row("Buy & Hold CAGR",        f"{summary['buyhold_cagr_pct']:>11.1f}%")
    _row("Strategy Max Drawdown",  f"{summary['strategy_max_drawdown_pct']:>11.1f}%")
    _row("Buy & Hold Max Drawdown",f"{summary['buyhold_max_drawdown_pct']:>11.1f}%")
    _row("Strategy Sharpe Ratio",  f"{summary['strategy_sharpe']:>12.2f}")
    _row("Buy & Hold Sharpe",      f"{summary['buyhold_sharpe']:>12.2f}")
    print("─" * 54)
    _row("Total Trades",           f"{summary['total_trades']:>12}")
    _row("Win Rate",               f"{summary['win_rate_pct']:>11.1f}%")
    _row("Time in Market",         f"{summary['time_in_market_pct']:>11.1f}%")
    print("─" * 54 + "\n")

    # ── 4. Trade log ──────────────────────────────────────────────
    if result.trades:
        print("TRADES (most recent 20):")
        header = f"{'Date':<12} {'Action':<6} {'Price':>8} {'Value':>14}  Reason"
        print(header)
        print("─" * len(header))
        for t in result.trades[-20:]:
            print(
                f"{t.date.date()!s:<12} "
                f"{'🟢 BUY' if t.action=='BUY' else '🔴 SELL':<8} "
                f"${t.price:>7.2f} "
                f"${t.portfolio_value:>13,.0f}  "
                f"{t.reason}"
            )
        print()

    # ── 5. Annual returns table ───────────────────────────────────
    _print_annual_returns(result)

    # ── 6. Generate charts ────────────────────────────────────────
    chart_path = _plot_results(result, summary)
    logger.info(f"Chart saved → {chart_path}")

    return result, summary


# ─────────────────────────────────────────────
#  Chart
# ─────────────────────────────────────────────

def _plot_results(result, summary: dict) -> Path:
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), facecolor="#0d1117")
    fig.suptitle(
        f"TQQQ MA200 Strategy  |  CAGR {summary['strategy_cagr_pct']:.1f}%  |  "
        f"MaxDD {summary['strategy_max_drawdown_pct']:.1f}%  |  "
        f"Sharpe {summary['strategy_sharpe']:.2f}",
        color="white", fontsize=13, y=0.98
    )

    for ax in axes:
        ax.set_facecolor("#0d1117")
        ax.tick_params(colors="#8b949e")
        ax.spines[:].set_color("#30363d")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    strat = result.strategy_nav
    bh    = result.buyhold_nav

    # ── Panel 1: NAV (log scale) ──────────────────────────────────
    ax1 = axes[0]
    ax1.semilogy(strat.index, strat.values, color="#58a6ff", lw=1.5, label="Strategy")
    ax1.semilogy(bh.index,    bh.values,    color="#8b949e", lw=1,   label="QQQ Buy & Hold", ls="--")

    # Shade invested periods
    in_pos = False
    start_date = None
    for date, sig in result.signals.items():
        if sig == 1 and not in_pos:
            start_date = date
            in_pos = True
        elif sig == 0 and in_pos:
            ax1.axvspan(start_date, date, alpha=0.08, color="#3fb950")
            in_pos = False
    if in_pos:
        ax1.axvspan(start_date, strat.index[-1], alpha=0.08, color="#3fb950")

    ax1.set_ylabel("Portfolio Value ($)", color="#8b949e")
    ax1.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=9)
    ax1.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )

    # ── Panel 2: Drawdown ─────────────────────────────────────────
    ax2 = axes[1]
    def drawdown(s):
        return (s / s.cummax() - 1) * 100

    dd_s = drawdown(strat)
    dd_b = drawdown(bh)
    ax2.fill_between(dd_s.index, dd_s.values, 0, alpha=0.6, color="#f85149", label="Strategy DD")
    ax2.plot(dd_b.index, dd_b.values, color="#8b949e", lw=0.8, label="B&H DD", ls="--")
    ax2.set_ylabel("Drawdown (%)", color="#8b949e")
    ax2.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=9)

    # ── Panel 3: Annual returns ───────────────────────────────────
    ax3 = axes[2]
    strat_annual = _annual_returns(strat)
    bh_annual    = _annual_returns(bh)
    years = sorted(set(strat_annual.keys()) | set(bh_annual.keys()))
    x     = range(len(years))
    w     = 0.38

    bars_s = ax3.bar([i - w/2 for i in x],
                     [strat_annual.get(y, 0) for y in years],
                     width=w, color="#58a6ff", alpha=0.85, label="Strategy")
    bars_b = ax3.bar([i + w/2 for i in x],
                     [bh_annual.get(y, 0)    for y in years],
                     width=w, color="#8b949e", alpha=0.6,  label="Buy & Hold")

    ax3.axhline(0, color="#30363d", lw=0.8)
    ax3.set_xticks(list(x))
    ax3.set_xticklabels([str(y) for y in years], rotation=45, fontsize=8)
    ax3.set_ylabel("Annual Return (%)", color="#8b949e")
    ax3.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=9)

    plt.tight_layout()
    out = REPORTS_DIR / "backtest_result.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return out


def _annual_returns(series: pd.Series) -> dict[int, float]:
    yearly = series.resample("YE").last()
    prev   = series.resample("YE").last().shift(1)
    prev.iloc[0] = series.iloc[0]
    ret = ((yearly / prev) - 1) * 100
    return {d.year: round(float(v), 1) for d, v in ret.items()}


def _print_annual_returns(result) -> None:
    strat_yr = _annual_returns(result.strategy_nav)
    bh_yr    = _annual_returns(result.buyhold_nav)
    years = sorted(set(strat_yr) | set(bh_yr))
    print(f"{'Year':<6}  {'Strategy':>10}  {'QQQ B&H':>10}  {'Alpha':>8}")
    print("─" * 42)
    for y in years:
        s = strat_yr.get(y, float("nan"))
        b = bh_yr.get(y, float("nan"))
        a = s - b if not (pd.isna(s) or pd.isna(b)) else float("nan")
        sign = lambda v: "+" if v > 0 else ""
        print(
            f"{y:<6}  "
            f"{sign(s)}{s:>8.1f}%  "
            f"{sign(b)}{b:>8.1f}%  "
            f"{sign(a)}{a:>6.1f}%"
        )
    print()


def _row(label: str, value: str) -> None:
    print(f"  {label:<28} {value}")


# ─────────────────────────────────────────────
#  CLI entry-point
# ─────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="TQQQ MA200 strategy backtest")
    p.add_argument("--buy",     type=float, default=1.04,      help="Buy  threshold multiplier (default 1.04)")
    p.add_argument("--sell",    type=float, default=0.97,      help="Sell threshold multiplier (default 0.97)")
    p.add_argument("--ma",      type=int,   default=200,       help="MA period in days (default 200)")
    p.add_argument("--capital", type=float, default=100_000.0, help="Initial capital in USD (default 100000)")
    p.add_argument("--refresh", action="store_true",           help="Force re-download price data")
    p.add_argument("--tranches", type=int, default=5,
               help="建仓批次：1=全仓买入，5=每批20%%（默认5）")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg  = MA200Config(
        buy_threshold   = args.buy,
        sell_threshold  = args.sell,
        ma_period       = args.ma,
        initial_capital = args.capital,
        max_tranches=args.tranches,
    )
    run_backtest(cfg, force_refresh=args.refresh)
