# Multi-Strategy MA200 Backtest
# 多策略 MA200 牛熊择时回测框架

A production-grade quantitative backtest comparing five investment strategies
using QQQ's 200-day moving average as the market regime signal.

基于 QQQ 200 日均线判断牛熊市，对比五种投资策略的量化回测框架。

---

## Strategies / 策略说明

| # | Name / 名称 | Description / 说明 |
|---|---|---|
| 1 | **BuyHold QQQ** | 100% QQQ, no timing / 买入持有，不择时 |
| 2 | **Timing QQQ** | QQQ + MA200 timing + dip DCA / QQQ择时+回调分批建仓 |
| 3 | **Timing QLD** | QLD (2×) + MA200 timing + dip DCA / 2倍杠杆择时 |
| 4 | **Timing TQQQ** | TQQQ (3×) + MA200 timing + dip DCA / 3倍杠杆择时 |
| 5 | **Combo 60/30/10** | 60% QQQ buy-hold + 30% QLD timing + 10% TQQQ timing |

Strategies 2–5 share the same MA200 signal and DCA parameters.
策略 2–5 共用相同的 MA200 信号和分批建仓参数。

---

## Signal Logic / 信号逻辑

| Signal / 信号 | Condition / 条件 | Action / 操作 |
|---|---|---|
| Bull confirmed / 牛市确认 | `QQQ > MA200 × 1.04` | DCA entry / 分批买入 |
| Bear confirmed / 熊市确认 | `QQQ < MA200 × 0.97` | Full exit / 一次性清仓 |
| Dip trigger / 回调触发 | QQQ daily return ≤ −1% | One tranche / 买入一批 |

Each tranche = `1/max_tranches` of current total equity.
Final tranche = all remaining cash.
每批买入当前总权益的 `1/max_tranches`，最后一批用完全部剩余现金。

---

## Data / 数据处理

| Ticker | Real Data From / 真实数据起点 | Pre-inception / 上市前处理 |
|--------|------|------|
| QQQ  | 1999-03-10 | — |
| QLD  | 2006-06-21 | Synthetic 2× QQQ / 合成2倍QQQ |
| TQQQ | 2010-02-09 | Synthetic 3× QQQ / 合成3倍QQQ |

Synthetic leverage formula / 合成公式:
`leveraged_return = qqq_daily_return × N − daily_cost`
`daily_cost = (1 + annual_cost)^(1/252) − 1`
(QLD: 4% annual cost / 年磨损, TQQQ: 6%)

---

## Project Structure / 项目结构

```
quant_backtest/
├── strategies/
│   └── engine.py           # All 5 strategies + synthesis + metrics
│                           # 五种策略核心逻辑、合成数据、指标计算
├── data/
│   ├── downloader.py       # yfinance + Parquet cache / 下载器与缓存
│   └── cache/              # Auto-generated, git-ignored / 自动生成
├── backtest/
│   └── run.py              # CLI + multi-period tables + 5 charts
│                           # CLI入口、多时间段表格、五张图表
├── reports/                # Generated charts / 生成的图表
│   ├── 1_nav_comparison.png
│   ├── 2_drawdowns.png
│   ├── 3_annual_returns.png
│   ├── 4_cagr_by_period.png
│   └── 5_sharpe_by_period.png
├── tests/
│   └── test_strategies.py  # Unit tests / 单元测试
├── .github/workflows/ci.yml
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

---

## Quick Start / 快速开始

```bash
# Create environment / 创建环境
conda create -n quant python=3.11 -y
conda activate quant
pip install -r requirements.txt

# Run backtest / 运行回测
python backtest/run.py

# Custom parameters / 自定义参数
python backtest/run.py --tranches 3 --buy 1.05 --sell 0.96 --dip -0.015

# Force refresh data / 强制重新下载数据
python backtest/run.py --refresh

# Run tests / 运行测试
pytest tests/ -v
```

---

## CLI Options / 命令行参数

| Flag | Default | Description / 说明 |
|------|---------|---|
| `--buy` | `1.04` | Bull zone threshold / 牛市阈值 |
| `--sell` | `0.97` | Bear zone threshold / 熊市阈值 |
| `--ma` | `200` | MA period (days) / 均线周期 |
| `--tranches` | `5` | DCA tranches (1=all-in) / 分批数量 |
| `--dip` | `-0.01` | Min QQQ daily return to trigger entry / 入场回调幅度 |
| `--capital` | `100000` | Initial capital / 初始资金 |
| `--refresh` | `False` | Force re-download / 强制重新下载 |

---

## Credits / 致谢

Strategy concept inspired by:
策略思路部分参考自：

> [别再定投 QQQ，这个混合配方才是普通人投资的终极答案！26 年回測結果太驚人](https://www.youtube.com/watch?v=ey7B8NthhpM)

Independent implementation for educational purposes only.
独立实现，仅供学习研究，不构成任何投资建议。

---

## Risk Warning / 风险提示

QLD and TQQQ are leveraged ETFs subject to volatility decay and large drawdowns.
**Past backtest results do not guarantee future performance. Not investment advice.**

QLD 和 TQQQ 为杠杆 ETF，存在波动率损耗，最大回撤可超过 80%。
**历史回测不代表未来表现，本项目不构成任何投资建议。**
