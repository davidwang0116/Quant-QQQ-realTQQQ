# TQQQ MA200 Strategy Backtest

A clean, production-grade quantitative backtest framework for the QQQ 200-day moving average bull/bear timing strategy applied to TQQQ.

## Strategy Logic

| Signal | Condition | Action |
|--------|-----------|--------|
| Bull confirmed | `QQQ > MA200 × 1.04` | Full position → TQQQ |
| Bear confirmed | `QQQ < MA200 × 0.97` | Full exit → Cash |
| In-between | Neither threshold crossed | Hold current position |

## Project Structure

```
quant_backtest/
├── strategies/
│   └── tqqq_ma200.py      # Strategy logic, signal generator, metrics
├── data/
│   ├── downloader.py       # yfinance wrapper with Parquet cache
│   └── cache/              # Auto-generated, git-ignored
├── backtest/
│   └── run.py              # CLI runner + chart generator
├── reports/
│   └── backtest_result.png # Latest chart (committed by CI)
├── tests/
│   └── test_strategy.py    # 15+ unit tests (pytest)
├── .github/
│   └── workflows/
│       └── ci.yml          # Lint → Test → Weekly backtest
├── requirements.txt
├── pyproject.toml          # ruff + mypy + pytest config
└── .gitignore
```

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/davidwang0116/quant-backtest.git
cd quant-backtest
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run backtest (downloads data automatically)
python backtest/run.py

# 4. Custom parameters
python backtest/run.py --buy 1.05 --sell 0.96 --capital 50000

# 5. Force re-download fresh data
python backtest/run.py --refresh

# 6. Run tests
pytest tests/ -v

# 7. Lint and format
ruff check .
ruff format .
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--buy` | `1.04` | QQQ must exceed MA200 × this to buy |
| `--sell` | `0.97` | QQQ must drop below MA200 × this to sell |
| `--ma` | `200` | Moving average period (days) |
| `--capital` | `100000` | Initial capital in USD |
| `--refresh` | `False` | Force re-download price data |

## GitHub Setup

```bash
git init
git remote add origin https://github.com/YOUR_USERNAME/quant-backtest.git
git add .
git commit -m "feat: initial TQQQ MA200 backtest framework"
git push -u origin main
```

The CI pipeline runs automatically on every push and weekly on Monday.
Add `CODECOV_TOKEN` to your repository secrets for coverage reporting.

## Risk Warning

TQQQ is a 3× leveraged ETF. Past backtest performance does not guarantee future results. This project is for educational and research purposes only — not investment advice.
