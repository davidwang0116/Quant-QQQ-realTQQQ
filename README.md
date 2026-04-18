# Quant-QQQ-QLD-TQQQ-SMA200Timing-MixedPosition-Backtest

A production-grade quantitative backtest comparing five investment strategies using QQQ's 200-day simple moving average (SMA200) as the market regime signal, with dip-based DCA entry and a blended combo portfolio.

基于 QQQ 200 日简单移动均线（SMA200）判断牛熊市，对比五种投资策略的量化回测框架，支持分批回调建仓与混合组合配置。

---

## Strategies / 策略说明

| # | Name / 名称 | Description / 说明 |
|---|---|---|
| 1 | **BuyHold QQQ** | 100% QQQ, no timing / 买入持有，不择时 |
| 2 | **Timing QQQ** | QQQ + SMA200 timing + dip DCA / QQQ择时+回调分批建仓 |
| 3 | **Timing QLD** | QLD (2×) + SMA200 timing + dip DCA / 2倍杠杆择时 |
| 4 | **Timing TQQQ** | TQQQ (3×) + SMA200 timing + dip DCA / 3倍杠杆择时 |
| 5 | **Combo 60/30/10** | 60% QQQ buy-hold + 30% QLD timing + 10% TQQQ timing |

Strategies 2–5 share the same SMA200 signal and DCA parameters.  
策略 2–5 共用相同的 SMA200 信号和分批建仓参数。

---

## Signal Logic / 信号逻辑

| Signal / 信号 | Condition / 条件 | Action / 操作 |
|---|---|---|
| Bull confirmed / 牛市确认 | `QQQ > SMA200 × 1.03` | DCA entry / 分批买入 |
| Bear confirmed / 熊市确认 | `QQQ < SMA200 × 0.83` | Full exit / 一次性清仓 |
| Dip trigger / 回调触发 | QQQ daily return ≤ −1% | One tranche / 买入一批 |

Each tranche = `1/max_tranches` of current total equity. Final tranche = all remaining cash.  
每批买入当前总权益的 `1/max_tranches`，最后一批用完全部剩余现金。

---

## Data / 数据处理

| Ticker | Real Data From / 真实数据起点 | Pre-inception / 上市前处理 |
|--------|---|---|
| QQQ  | 1999-03-10 | — |
| QLD  | 2006-06-21 | Synthetic 2× QQQ / 合成2倍QQQ |
| TQQQ | 2010-02-09 | Synthetic 3× QQQ / 合成3倍QQQ |

Synthetic leverage formula / 合成公式:  
`leveraged_return = qqq_daily_return × N − daily_cost`  
`daily_cost = (1 + annual_cost)^(1/252) − 1`  
(QLD: 4% annual cost, TQQQ: 6% annual cost)

---

## Backtest Results / 回测结果

> Initial capital $100,000 | Buy ×1.04 | Sell ×0.97 | SMA200 | Tranches 5 | Dip −1%  
> 初始资金 $100,000 | 买入阈值 ×1.04 | 卖出阈值 ×0.97 | SMA200 | 分5批 | 回调幅度 −1%

### Full History ~26 Years (2000–2025) / 全历史约26年

| Strategy | Total Return | Final Value | CAGR | Max DD | Sharpe | In Market |
|---|---:|---:|---:|---:|---:|---:|
| BuyHold QQQ    |   +674.01% | $774,014   |  +8.19% | -82.96% | 0.28 | 100.0% |
| Timing QQQ     |   +755.47% | $855,466   |  +8.61% | -26.16% | 0.39 |  60.6% |
| Timing QLD     |  +2931.77% | $3,031,775 | +14.03% | -48.55% | 0.48 |  60.6% |
| Timing TQQQ    |  +7947.55% | $8,047,555 | +18.39% | -64.21% | 0.53 |  60.6% |
| **Combo 60/30/10** | **+2078.70%** | **$2,178,696** | **+12.59%** | **-54.00%** | **0.43** | **60.6%** |

### Last 15 Years (2011–2025) / 近15年

| Strategy | Total Return | Final Value | CAGR | Max DD | Sharpe | In Market |
|---|---:|---:|---:|---:|---:|---:|
| BuyHold QQQ    |  +1176.81% | $1,276,808 | +18.52% | -35.12% | 0.73 | 100.0% |
| Timing QQQ     |   +446.14% | $546,138   | +11.99% | -26.16% | 0.59 |  70.2% |
| Timing QLD     |  +1588.99% | $1,688,991 | +20.75% | -47.40% | 0.67 |  70.2% |
| Timing TQQQ    |  +4039.92% | $4,139,921 | +28.20% | -63.52% | 0.71 |  70.2% |
| **Combo 60/30/10** | **+1586.77%** | **$1,686,774** | **+20.74%** | **-39.50%** | **0.74** | **70.2%** |

### Last 10 Years (2016–2025) / 近10年

| Strategy | Total Return | Final Value | CAGR | Max DD | Sharpe | In Market |
|---|---:|---:|---:|---:|---:|---:|
| BuyHold QQQ    |  +508.21% | $608,205   | +19.81% | -35.12% | 0.74 | 100.0% |
| Timing QQQ     |  +282.35% | $382,347   | +14.37% | -26.16% | 0.69 |  72.8% |
| Timing QLD     |  +808.72% | $908,715   | +24.73% | -47.40% | 0.75 |  72.8% |
| Timing TQQQ    | +1685.22% | $1,785,215 | +33.45% | -63.52% | 0.78 |  72.8% |
| **Combo 60/30/10** | **+716.06%** | **$816,059** | **+23.39%** | **-39.36%** | **0.78** | **72.8%** |

### Last 5 Years (2021–2025) / 近5年

| Strategy | Total Return | Final Value | CAGR | Max DD | Sharpe | In Market |
|---|---:|---:|---:|---:|---:|---:|
| BuyHold QQQ    | +106.36% | $206,364 | +15.64% | -35.12% | 0.58 | 100.0% |
| Timing QQQ     |  +59.11% | $159,109 |  +9.76% | -15.72% | 0.48 |  58.0% |
| Timing QLD     | +100.15% | $200,146 | +14.93% | -29.60% | 0.52 |  58.0% |
| Timing TQQQ    | +134.92% | $234,917 | +18.69% | -41.18% | 0.54 |  58.0% |
| **Combo 60/30/10** | **+107.35%** | **$207,354** | **+15.75%** | **-32.33%** | **0.58** | **58.0%** |

---

## Annual Returns / 逐年收益

| Year | BuyHold QQQ | Timing QQQ | Timing QLD | Timing TQQQ | Combo 60/30/10 |
|---:|---:|---:|---:|---:|---:|
| 2000 | -38.4% |   0.0% |   0.0% |   0.0% | -23.0% |
| 2001 | -33.3% |   0.0% |   0.0% |   0.0% | -16.0% |
| 2002 | -37.4% |   0.0% |   0.0% |   0.0% | -14.2% |
| 2003 | +49.7% | +37.5% | +77.3% | +123.8% | +78.0% |
| 2004 | +10.5% |  -3.9% | -11.1% |  -18.2% |  -7.6% |
| 2005 |  +1.6% | -11.8% | -23.5% |  -33.7% | -18.5% |
| 2006 |  +7.1% |  -3.7% |  -9.7% |  -14.6% |  -4.6% |
| 2007 | +19.0% | +19.0% | +29.0% |  +44.1% | +27.3% |
| 2008 | -41.7% |  -8.5% | -16.3% |  -24.0% | -26.9% |
| 2009 | +54.7% | +27.0% | +58.7% |  +91.6% | +63.2% |
| 2010 | +20.1% |  +1.2% |  -1.0% |   -4.6% |  +4.1% |
| 2011 |  +3.5% |  -0.3% |  -2.7% |   -6.3% |  -1.4% |
| 2012 | +18.1% |  -4.0% |  -9.7% |  -16.2% |  -1.5% |
| 2013 | +36.6% | +22.4% | +47.9% |  +78.0% | +47.9% |
| 2014 | +19.2% | +19.2% | +37.6% |  +57.1% | +34.3% |
| 2015 |  +9.4% |  -0.9% |  -3.7% |   -7.2% |  -0.1% |
| 2016 |  +7.1% |  -0.8% |  -1.8% |   -2.9% |  +1.2% |
| 2017 | +32.7% | +32.7% | +70.3% | +118.1% | +64.9% |
| 2018 |  -0.1% |  +6.6% |  +7.5% |   +5.7% |  +4.7% |
| 2019 | +39.0% | +14.5% | +27.2% |  +40.2% | +33.9% |
| 2020 | +48.4% | +22.7% | +37.6% |  +44.9% | +42.8% |
| 2021 | +27.4% | +27.4% | +54.7% |  +83.0% | +53.6% |
| 2022 | -32.6% | -11.7% | -22.3% |  -31.9% | -28.1% |
| 2023 | +54.9% | +34.5% | +68.1% | +105.6% | +76.1% |
| 2024 | +25.6% | +25.6% | +42.8% |  +58.3% | +44.5% |
| 2025 | +21.8% |  +5.1% |  +5.0% |   +3.2% |  +7.5% |

---

## Charts / 图表

Full detailed charts are in the [`reports/`](reports/) folder and auto-updated weekly by CI.  
完整图表在 [`reports/`](reports/) 目录，由 CI 每周自动更新。

### NAV Comparison / 净值曲线对比
![NAV Comparison](reports/1_nav_comparison.png)

### Drawdown Comparison / 回撤对比
![Drawdowns](reports/2_drawdowns.png)

### Annual Returns / 逐年收益柱状图
![Annual Returns](reports/3_annual_returns.png)

### CAGR by Period / 各时间段年化收益
![CAGR by Period](reports/4_cagr_by_period.png)

### Sharpe by Period / 各时间段夏普比率
![Sharpe by Period](reports/5_sharpe_by_period.png)

---

## Project Structure / 项目结构

```
## 📂 项目结构 (Project Structure)

```text
Quant-QQQ-QLD-TQQQ/
├── strategies/             
│   └── engine.py           # 5 strategies + synthesis + metrics / 5种策略逻辑与指标
├── data/                  
│   ├── downloader.py       # yfinance + Parquet cache / 下载器与缓存
│   └── cache/              # Auto-generated (Git ignored) / 自动生成的本地数据
├── backtest/               
│   ├── run.py              # Main entry + CLI / 主运行入口
│   └── optimize.py         # Parameter optimization / 参数优化
├── reports/                # 回测结果展示 (Default: 5 Tranches / 默认5批版)
│   ├── results.md          
│   ├── *.png               # NAV, DD, Returns charts / 净值、回撤、收益图表
│   ├── tranches_1/         # All-in version / 全仓版结果
│   │   ├── results.md
│   │   └── *.png
│   ├── tranches_3/         # 3 Tranches version / 3批版结果
│   │   ├── results.md
│   │   └── *.png
│   └── tranches_5/         # 5 Tranches version / 5批版结果
│       ├── results.md
│       └── *.png
├── tests/                  # Unit tests / 单元测试
│   └── test_strategies.py  # Logic verification / 逻辑验证
├── utils/                  # Utility functions / 工具类函数
├── .github/workflows/      # CI/CD
│   └── ci.yml              # Auto backtest workflow / 自动化回测流水线
├── requirements.txt        # Dependencies / 依赖包列表
├── pyproject.toml          # Project metadata / 项目配置文件
└── README.md               # Project documentation / 项目说明文档
```

---

## Quick Start / 快速开始

```bash
conda create -n quant python=3.11 -y
conda activate quant
pip install -r requirements.txt

python backtest/run.py                                      # default / 默认参数
python backtest/run.py --tranches 3 --buy 1.05 --sell 0.96  # custom / 自定义
python backtest/run.py --refresh                            # force reload / 强制重载数据
pytest tests/ -v                                            # run tests / 运行测试
```

## CLI Options / 命令行参数

| Flag | Default | Description / 说明 |
|------|---------|---|
| `--buy`      | `1.04`    | Bull zone threshold / 牛市阈值 |
| `--sell`     | `0.97`    | Bear zone threshold / 熊市阈值 |
| `--ma`       | `200`     | SMA period (days) / 均线周期 |
| `--tranches` | `5`       | DCA tranches: 1=all-in, N=1/N equity / 分批数量 |
| `--dip`      | `-0.01`   | Min QQQ daily return for entry / 入场回调幅度 |
| `--capital`  | `100000`  | Initial capital / 初始资金 |
| `--refresh`  | `False`   | Force re-download data / 强制重新下载 |

---


## Credits / 致谢

Strategy concept inspired by:  
策略思路部分参考自：

> [别再定投 QQQ，这个混合配方才是普通人投资的终极答案！26 年回測結果太驚人](https://www.youtube.com/watch?v=ey7B8NthhpM)

Independent implementation for educational purposes only.  
独立实现，仅供学习研究，不构成任何投资建议。

---

## Risk Warning / 风险提示

QLD and TQQQ are leveraged ETFs subject to volatility decay and large drawdowns (TQQQ max DD exceeded **-80%** historically). **Past backtest results do not guarantee future performance. Not investment advice.**

QLD 和 TQQQ 为杠杆 ETF，存在波动率损耗，历史最大回撤超过 **-80%**。  
**历史回测不代表未来表现，本项目不构成任何投资建议。**
