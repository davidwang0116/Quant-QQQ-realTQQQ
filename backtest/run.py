"""
Backtest runner — five strategies, four time periods, full reporting.

Run from project root:
    python backtest/run.py
    python backtest/run.py --refresh
    python backtest/run.py --tranches 1 --buy 1.05 --sell 0.96
"""

from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.downloader import fetch_prices
from strategies.engine import (
    StrategyConfig, StrategyResult,
    build_price_series,
    strategy_buyhold_qqq,
    strategy_timing_qqq,
    strategy_timing_qld,
    strategy_timing_tqqq,
    strategy_combo,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

END_DATE = "2025-12-31"

PERIODS = [
    ("Full History (~26Y)", "2000-01-01", END_DATE),
    ("Last 15 Years",       "2011-01-01", END_DATE),
    ("Last 10 Years",       "2016-01-01", END_DATE),
    ("Last  5 Years",       "2021-01-01", END_DATE),
]

STRATEGY_COLORS = {
    "BuyHold QQQ":    "#8b949e",
    "Timing QQQ":     "#79c0ff",
    "Timing QLD":     "#56d364",
    "Timing TQQQ":    "#f78166",
    "Combo 60/30/10": "#e3b341",
}

# ── wcwidth for CJK-safe column alignment ─────────────────────────
try:
    from wcwidth import wcswidth as _wcswidth
    def _pad(text: str, width: int) -> str:
        vis = _wcswidth(text)
        return text + " " * max(width - vis, 0)
except ImportError:
    def _pad(text: str, width: int) -> str:
        return f"{text:<{width}}"


# ─────────────────────────────────────────────
#  Data loading
# ─────────────────────────────────────────────

def load_data(force_refresh: bool = False) -> dict[str, pd.Series]:
    logger.info("Downloading price data...")
    qqq  = fetch_prices("QQQ",  start="1999-01-01", end=END_DATE, force_refresh=force_refresh)
    # QLD inception 2006-06-21, TQQQ inception 2010-02-09
    qld  = fetch_prices("QLD",  start="2006-06-21", end=END_DATE, force_refresh=force_refresh)
    tqqq = fetch_prices("TQQQ", start="2010-02-09", end=END_DATE, force_refresh=force_refresh)
    return {"QQQ": qqq, "QLD": qld, "TQQQ": tqqq}


# ─────────────────────────────────────────────
#  Run one period → five results
# ─────────────────────────────────────────────

def run_period(
    prices: dict[str, pd.Series],
    cfg:    StrategyConfig,
    start:  str,
    end:    str,
) -> list[StrategyResult]:
    qqq, qld, tqqq = build_price_series(
        qqq_full  = prices["QQQ"],
        real_qld  = prices["QLD"],
        real_tqqq = prices["TQQQ"],
        start=start, end=end,
    )

    results = [
        strategy_buyhold_qqq(qqq, cfg),
        strategy_timing_qqq(qqq, cfg),
        strategy_timing_qld(qqq, qld, cfg),
        strategy_timing_tqqq(qqq, tqqq, cfg),
        strategy_combo(qqq, qld, tqqq, cfg),
    ]
    return results


# ─────────────────────────────────────────────
#  Main entry
# ─────────────────────────────────────────────

def run_all(cfg: StrategyConfig, force_refresh: bool = False) -> None:
    logger.info("=== Multi-Strategy MA200 Backtest ===")
    logger.info(f"Tranches={cfg.max_tranches}  Buy={cfg.buy_threshold}  "
                f"Sell={cfg.sell_threshold}  Capital=${cfg.initial_capital:,.0f}")

    prices = load_data(force_refresh)

    all_period_results: list[tuple[str, list[StrategyResult]]] = []
    for label, start, end in PERIODS:
        logger.info(f"Period: {label}  ({start} → {end})")
        results = run_period(prices, cfg, start, end)
        all_period_results.append((label, results))

    # ── Print comparison tables ───────────────────────────────────
    for label, results in all_period_results:
        _print_period_table(label, results)

    # ── Print annual returns for full-history period ──────────────
    _print_annual_table(all_period_results[0][1])

    # ── Charts ────────────────────────────────────────────────────
    full_results = all_period_results[0][1]
    _plot_nav_comparison(full_results)
    _plot_annual_returns(full_results)
    _plot_drawdowns(full_results)
    _plot_period_cagr(all_period_results)
    _plot_period_sharpe(all_period_results)

    logger.info(f"Charts saved to {REPORTS_DIR}/")
    _generate_markdown_report(all_period_results, cfg)

# ─────────────────────────────────────────────
#  Print helpers
# ─────────────────────────────────────────────

def _print_period_table(label: str, results: list[StrategyResult]) -> None:
    cw = {"name": 18, "ret": 12, "bal": 14, "cagr": 10, "dd": 10, "sharpe": 7, "tim": 9}
    header = (
        f"{_pad('Strategy', cw['name'])} "
        f"| {_pad('Total Ret', cw['ret'])} "
        f"| {_pad('Final Value', cw['bal'])} "
        f"| {_pad('CAGR', cw['cagr'])} "
        f"| {_pad('Max DD', cw['dd'])} "
        f"| {_pad('Sharpe', cw['sharpe'])} "
        f"| {_pad('In Mkt', cw['tim'])}"
    )
    sep = "=" * len(header)
    print(f"\n{sep}")
    print(f"  {label}")
    print(sep)
    print(header)
    print("-" * len(header))
    for r in results:
        s = r.summary()
        print(
            f"{_pad(r.name, cw['name'])} "
            f"| {s['total_ret_pct']:>{cw['ret']}.2f}% "
            f"| ${s['final_value']:>{cw['bal']-1},.0f} "
            f"| {s['cagr_pct']:>{cw['cagr']}.2f}% "
            f"| {s['max_dd_pct']:>{cw['dd']}.2f}% "
            f"| {s['sharpe']:>{cw['sharpe']}.2f} "
            f"| {s['time_in_market_pct']:>{cw['tim']}.1f}%"
        )
    print(sep)


def _print_annual_table(results: list[StrategyResult]) -> None:
    annual: dict[str, dict[int, float]] = {}
    for r in results:
        annual[r.name] = _annual_returns(r.nav)

    years = sorted({y for d in annual.values() for y in d})
    names = [r.name for r in results]

    col_w = 10
    header = f"{'Year':<6}" + "".join(f"  {n[:col_w]:>{col_w}}" for n in names)
    print(f"\n{'Annual Returns':=^{len(header)}}")
    print(header)
    print("-" * len(header))
    for y in years:
        row = f"{y:<6}"
        for n in names:
            v = annual[n].get(y, float("nan"))
            if pd.isna(v):
                row += f"  {'--':>{col_w}}"
            else:
                sign = "+" if v > 0 else ""
                row += f"  {sign}{v:>{col_w-1}.1f}%"
        print(row)
    print()


def _annual_returns(series: pd.Series) -> dict[int, float]:
    yearly       = series.resample("YE").last()
    prev         = series.resample("YE").last().shift(1)
    prev.iloc[0] = series.iloc[0]
    ret          = ((yearly / prev) - 1) * 100
    return {d.year: round(float(v), 1) for d, v in ret.items()}


# ─────────────────────────────────────────────
#  Charts
# ─────────────────────────────────────────────

_DARK = "#0d1117"
_AX   = "#161b22"
_GRID = "#21262d"
_TEXT = "#c9d1d9"
_MUT  = "#8b949e"


def _style_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(_AX)
    ax.tick_params(colors=_MUT, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(_GRID)
    ax.yaxis.label.set_color(_MUT)
    ax.xaxis.label.set_color(_MUT)
    ax.title.set_color(_TEXT)
    ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.6)


def _legend(ax: plt.Axes) -> None:
    ax.legend(
        facecolor=_AX, edgecolor=_GRID,
        labelcolor=_TEXT, fontsize=8,
        framealpha=0.9,
    )


def _plot_nav_comparison(results: list[StrategyResult]) -> None:
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=_DARK)
    _style_ax(ax)
    ax.set_title("Portfolio NAV — Log Scale (Full History)", fontsize=12)

    for r in results:
        color = STRATEGY_COLORS.get(r.name, "#ffffff")
        lw    = 2.0 if r.name != "BuyHold QQQ" else 1.2
        ls    = "--" if r.name == "BuyHold QQQ" else "-"
        ax.semilogy(r.nav.index, r.nav.values, color=color, lw=lw, ls=ls, label=r.name)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    _legend(ax)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "1_nav_comparison.png", dpi=150,
                bbox_inches="tight", facecolor=_DARK)
    plt.close()
    logger.info("Saved 1_nav_comparison.png")


def _plot_drawdowns(results: list[StrategyResult]) -> None:
    fig, ax = plt.subplots(figsize=(14, 5), facecolor=_DARK)
    _style_ax(ax)
    ax.set_title("Drawdown Comparison (Full History)", fontsize=12)

    for r in results:
        dd    = (r.nav / r.nav.cummax() - 1) * 100
        color = STRATEGY_COLORS.get(r.name, "#ffffff")
        lw    = 1.5 if r.name != "BuyHold QQQ" else 1.0
        ax.plot(dd.index, dd.values, color=color, lw=lw, label=r.name)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    _legend(ax)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "2_drawdowns.png", dpi=150,
                bbox_inches="tight", facecolor=_DARK)
    plt.close()
    logger.info("Saved 2_drawdowns.png")


def _plot_annual_returns(results: list[StrategyResult]) -> None:
    annual = {r.name: _annual_returns(r.nav) for r in results}
    years  = sorted({y for d in annual.values() for y in d})
    n_strat = len(results)
    w       = 0.15
    x       = np.arange(len(years))

    fig, ax = plt.subplots(figsize=(16, 6), facecolor=_DARK)
    _style_ax(ax)
    ax.set_title("Annual Returns by Strategy (Full History)", fontsize=12)

    for i, r in enumerate(results):
        vals   = [annual[r.name].get(y, 0) for y in years]
        color  = STRATEGY_COLORS.get(r.name, "#ffffff")
        offset = (i - n_strat / 2 + 0.5) * w
        ax.bar(x + offset, vals, width=w, color=color, alpha=0.85, label=r.name)

    ax.axhline(0, color=_GRID, lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years], rotation=45, fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _legend(ax)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "3_annual_returns.png", dpi=150,
                bbox_inches="tight", facecolor=_DARK)
    plt.close()
    logger.info("Saved 3_annual_returns.png")


def _plot_period_cagr(all_period_results: list[tuple[str, list[StrategyResult]]]) -> None:
    period_labels = [p[0] for p in all_period_results]
    n_periods = len(period_labels)
    n_strat   = len(all_period_results[0][1])
    w         = 0.15
    x         = np.arange(n_periods)

    fig, ax = plt.subplots(figsize=(12, 5), facecolor=_DARK)
    _style_ax(ax)
    ax.set_title("CAGR by Period & Strategy", fontsize=12)

    strat_names = [r.name for r in all_period_results[0][1]]
    for i, name in enumerate(strat_names):
        vals   = [results[i].summary()["cagr_pct"] for _, results in all_period_results]
        color  = STRATEGY_COLORS.get(name, "#ffffff")
        offset = (i - n_strat / 2 + 0.5) * w
        bars   = ax.bar(x + offset, vals, width=w, color=color, alpha=0.85, label=name)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f"{val:.1f}%", ha="center", va="bottom",
                    fontsize=7, color=_TEXT)

    ax.axhline(0, color=_GRID, lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(period_labels, fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _legend(ax)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "4_cagr_by_period.png", dpi=150,
                bbox_inches="tight", facecolor=_DARK)
    plt.close()
    logger.info("Saved 4_cagr_by_period.png")


def _plot_period_sharpe(all_period_results: list[tuple[str, list[StrategyResult]]]) -> None:
    period_labels = [p[0] for p in all_period_results]
    n_periods = len(period_labels)
    n_strat   = len(all_period_results[0][1])
    w         = 0.15
    x         = np.arange(n_periods)

    fig, ax = plt.subplots(figsize=(12, 5), facecolor=_DARK)
    _style_ax(ax)
    ax.set_title("Sharpe Ratio by Period & Strategy", fontsize=12)

    strat_names = [r.name for r in all_period_results[0][1]]
    for i, name in enumerate(strat_names):
        vals   = [results[i].summary()["sharpe"] for _, results in all_period_results]
        color  = STRATEGY_COLORS.get(name, "#ffffff")
        offset = (i - n_strat / 2 + 0.5) * w
        bars   = ax.bar(x + offset, vals, width=w, color=color, alpha=0.85, label=name)
        for bar, val in zip(bars, vals):
            ypos = bar.get_height() + 0.02 if val >= 0 else bar.get_height() - 0.08
            ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                    f"{val:.2f}", ha="center", va="bottom",
                    fontsize=7, color=_TEXT)

    ax.axhline(0, color=_GRID, lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(period_labels, fontsize=9)
    _legend(ax)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "5_sharpe_by_period.png", dpi=150,
                bbox_inches="tight", facecolor=_DARK)
    plt.close()
    logger.info("Saved 5_sharpe_by_period.png")

def _generate_markdown_report(
    all_period_results: list[tuple[str, list[StrategyResult]]],
    cfg: StrategyConfig,
) -> None:
    from datetime import date
    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────
    lines += [
        "# Multi-Strategy MA200 Backtest Report",
        "",
        f"**Generated:** {date.today().isoformat()}  ",
        f"**Parameters:** Buy `×{cfg.buy_threshold}` | Sell `×{cfg.sell_threshold}` "
        f"| MA `{cfg.ma_period}` | Tranches `{cfg.max_tranches}` "
        f"| Dip `{cfg.dip_threshold*100:.1f}%` "
        f"| Capital `${cfg.initial_capital:,.0f}`  ",
        f"**Combo allocation:** QQQ {cfg.combo_bh_pct*100:.0f}% "
        f"/ QLD {cfg.combo_qld_pct*100:.0f}% "
        f"/ TQQQ {cfg.combo_tqqq_pct*100:.0f}%",
        "",
        "---",
        "",
    ]

    # ── Period comparison tables ──────────────────────────────────
    lines += ["## Performance Summary / 分周期回测结果", ""]

    for label, results in all_period_results:
        lines += [f"### {label}", ""]
        lines += ["| Strategy | Total Return | Final Value | CAGR | Max DD | Sharpe | In Market |"]
        lines += ["|---|---:|---:|---:|---:|---:|---:|"]
        for r in results:
            s = r.summary()
            lines.append(
                f"| **{r.name}** "
                f"| {s['total_ret_pct']:+.2f}% "
                f"| ${s['final_value']:,.0f} "
                f"| {s['cagr_pct']:+.2f}% "
                f"| {s['max_dd_pct']:.2f}% "
                f"| {s['sharpe']:.2f} "
                f"| {s['time_in_market_pct']:.1f}% |"
            )
        lines.append("")

    # ── Annual returns table ──────────────────────────────────────
    lines += ["---", "", "## Annual Returns (Full History) / 逐年收益", ""]
    full_results = all_period_results[0][1]
    annual = {r.name: _annual_returns(r.nav) for r in full_results}
    years  = sorted({y for d in annual.values() for y in d})
    names  = [r.name for r in full_results]

    lines.append("| Year | " + " | ".join(names) + " |")
    lines.append("|---" + "|---:" * len(names) + "|")
    for y in years:
        row = f"| {y} |"
        for n in names:
            v = annual[n].get(y)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                row += " — |"
            else:
                sign = "+" if v > 0 else ""
                row += f" {sign}{v:.1f}% |"
        lines.append(row)
    lines.append("")

    # ── Charts ────────────────────────────────────────────────────
    lines += ["---", "", "## Charts / 图表", ""]

    charts = [
        ("1_nav_comparison.png",  "NAV Comparison (Log Scale) / 净值曲线对比（对数坐标）"),
        ("2_drawdowns.png",       "Drawdown Comparison / 回撤对比"),
        ("3_annual_returns.png",  "Annual Returns by Strategy / 逐年收益柱状图"),
        ("4_cagr_by_period.png",  "CAGR by Period / 各时间段年化收益"),
        ("5_sharpe_by_period.png","Sharpe by Period / 各时间段夏普比率"),
    ]
    for filename, caption in charts:
        lines += [
            f"### {caption}",
            "",
            f"![{caption}]({filename})",
            "",
        ]

    # ── Write file ────────────────────────────────────────────────
    out = REPORTS_DIR / "results.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Report saved → {out}")
# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Multi-strategy MA200 backtest")
    p.add_argument("--buy",      type=float, default=1.04)
    p.add_argument("--sell",     type=float, default=0.97)
    p.add_argument("--ma",       type=int,   default=200)
    p.add_argument("--tranches", type=int,   default=5,
                   help="Entry tranches: 1=all-in, N=1/N equity per tranche")
    p.add_argument("--capital",  type=float, default=100_000.0)
    p.add_argument("--dip",      type=float, default=-0.01,
                   help="QQQ daily return threshold for DCA entry (default -0.01)")
    p.add_argument("--refresh",  action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg  = StrategyConfig(
        buy_threshold   = args.buy,
        sell_threshold  = args.sell,
        ma_period       = args.ma,
        max_tranches    = args.tranches,
        initial_capital = args.capital,
        dip_threshold   = args.dip,
    )
    run_all(cfg, force_refresh=args.refresh)
