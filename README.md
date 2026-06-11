```text
 __        __         _ _   _      ____ ____ _____
 \ \      / /__  __ _| | |_| |__  / ___|  _ \_   _|
  \ \ /\ / / _ \/ _` | | __| '_ \| |  _| |_) || |
   \ V  V /  __/ (_| | | |_| | | | |_| |  __/ | |
    \_/\_/ \___|\__,_|_|\__|_| |_|\____|_|    |_|

              AI-assisted allocation research
                    Invest with caution
```

# WealthGPT

WealthGPT is an AI-assisted global equity allocation research project. It
combines live Yahoo Finance data, Modern Portfolio Theory, Black-Litterman
expected returns, structured OpenAI research views, and a local
Bloomberg-inspired dashboard.
<img width="1688" height="901" alt="image" src="https://github.com/user-attachments/assets/6fb97413-704d-4f79-b013-198e9519e293" />
<img width="1690" height="907" alt="image" src="https://github.com/user-attachments/assets/8181daa1-25ec-4307-ac8e-a8c1a699c880" />
<img width="1689" height="906" alt="image" src="https://github.com/user-attachments/assets/90291786-214c-40b4-bc16-0ad3024ec568" />

It constructs and compares:

- a maximum Sharpe ratio portfolio; and
- a global minimum-volatility portfolio.

> **Research software only.** WealthGPT is not financial advice or an automated
> trading system. Review all data, assumptions, generated research, and
> allocations independently.

## Features

- Global U.S., Canadian, U.K., and European equity universe
- Adjusted price and company metadata from `yfinance`
- Long-only SLSQP portfolio optimization with a configurable position cap
- Optional GPT-assisted Black-Litterman expected returns
- Validated and reusable research, sector, and listing caches
- Optional out-of-sample testing against broad market benchmarks
- Jobson-Korkie Sharpe-ratio comparisons
- Eight-page PDF portfolio report and CSV allocation export
- Local web dashboard with run controls, live terminal relay, report viewer,
  performance chart, market flags, and listing metadata
- Bundled example portfolios and AI sentiments visible before the first run

## Repository

```text
.
|-- wealthgpt.py                 # Main research and optimization pipeline
|-- wealthgpt_report.py          # PDF reporting and sector classification
|-- dashboard/
|   |-- server.py                # Constrained local HTTP runner
|   |-- runner.py                # Model configuration and result adapter
|   |-- index.html               # Dashboard interface
|   |-- app.js
|   |-- styles.css
|   `-- terminal-theme.css
|-- scripts/
|   `-- start-dashboard.ps1
|-- tests/
|   `-- test_release.py
|-- examples/                    # Sanitized transcripts and sample PDF
|-- start-dashboard.bat
|-- requirements.txt
|-- .env.example
`-- .github/workflows/ci.yml
```

Generated research, caches, allocations, charts, and reports are intentionally
excluded from Git. Sanitized default examples under `examples/` are included.

## Installation

Requirements:

- Python 3.11 or newer
- An OpenAI API key only when generating new GPT research views

```bash
# From your cloned or downloaded repository:
cd wealthgpt
python -m venv .venv
```

Activate the environment and install dependencies:

```bash
python -m pip install -r requirements.txt
```

Set the API key in the process environment when GPT views are enabled:

```powershell
$env:OPENAI_API_KEY="your_api_key"
```

Never commit a real API key or `.env` file.

## Run The Model

The standard command-line run uses the defaults defined in `wealthgpt.py`:

```bash
python wealthgpt.py
```

Runtime settings can be supplied without editing source:

```powershell
$env:WEALTHGPT_TRAINING_YEARS="2"
$env:WEALTHGPT_OOS_YEARS="0.5"
$env:WEALTHGPT_MAX_POSITION_WEIGHT="0.15"
$env:WEALTHGPT_GPT_VIEWS="true"
$env:WEALTHGPT_RESEARCH_TICKERS='["AAPL","MSFT","RY.TO"]'
python wealthgpt.py
```

See [.env.example](.env.example) for every supported override.

## Run The Dashboard

On Windows, double-click `start-dashboard.bat`, or run:

```powershell
.\scripts\start-dashboard.ps1
```

If an older dashboard process is still using port `8765`, run:

```powershell
.\restart-dashboard.bat
```

The legacy `start-wealthgpt-dashboard.bat` and
`restart-wealthgpt-dashboard.bat` names remain as compatibility aliases.

On any platform:

```bash
python dashboard/server.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The dashboard validates
settings, launches the model in a background process, relays terminal output,
and refreshes the overview and report tabs after completion.

For access beyond localhost, set `WEALTHGPT_REMOTE_TOKEN`, bind explicitly, and
place the service behind HTTPS and a firewall:

```bash
python dashboard/server.py --host 0.0.0.0
```

The server does not expose a general-purpose shell endpoint. Browser requests
are restricted to the dashboard origin, with local `file://` use supported.

## Outputs

A completed run may create:

```text
black_litterman_stock_analysis.json
gpt_views.csv
latest_run.json
listing_metadata_cache.json
portfolio_allocations.csv
portfolio_vs_markets_oos.png
sector_cache.json
wealthgpt_portfolio_report.pdf
```

The PDF includes portfolio metrics, top holdings, sector exposure,
concentration, effective holdings, rationales for the eight largest positions,
and a detailed allocation appendix.

## Validation

Run the release checks locally:

```bash
python -m unittest discover -s tests -v
python -m py_compile wealthgpt.py wealthgpt_report.py dashboard/server.py dashboard/runner.py
node --check dashboard/app.js
```

GitHub Actions runs the same checks on pushes and pull requests.

## Methodology

1. Download and align adjusted equity prices.
2. Estimate annualized historical returns and covariance.
3. Collect company context and optional structured GPT views.
4. Blend views with equilibrium returns using Black-Litterman.
5. Solve maximum-Sharpe and minimum-volatility portfolios with SLSQP.
6. Optionally evaluate both portfolios out of sample.
7. Export dashboard data, allocations, charts, and the PDF report.

## Limitations

- Expected returns are estimates, not guaranteed forecasts.
- Generated equity research may be stale, incomplete, or incorrect.
- Yahoo Finance data may contain delays, omissions, and classification errors.
- The universe is current rather than point-in-time and may introduce
  survivorship bias.
- Covariance estimates are sensitive to the training window.
- The equilibrium proxy is not a true capitalization-weighted market portfolio.
- Transaction costs, taxes, liquidity, turnover, and market impact are omitted.
- Statistical tests rely on assumptions that may not hold in realized markets.

Public-safe transcripts and a sample report are available in
[`examples/`](examples/).

## Full Universe

| Ticker | Country | Listed Index / Exchange | Sector                          |
| ------ | ------- | ----------------------- | ------------------------------- |
| AAPL   | USA     | Nasdaq-100 / NASDAQ     | Technology                      |
| ABBV   | USA     | S&P 500 / NYSE          | Healthcare                      |
| ABT    | USA     | S&P 500 / NYSE          | Healthcare                      |
| ACN    | USA     | S&P 500 / NYSE          | Information Technology Services |
| ADBE   | USA     | Nasdaq-100 / NASDAQ     | Software                        |
| AIG    | USA     | S&P 500 / NYSE          | Insurance                       |
| AMD    | USA     | Nasdaq-100 / NASDAQ     | Semiconductors                  |
| AMGN   | USA     | Nasdaq-100 / NASDAQ     | Biotechnology                   |
| AMT    | USA     | S&P 500 / NYSE          | REIT (Telecom Infrastructure)   |
| AMZN   | USA     | Nasdaq-100 / NASDAQ     | Consumer Discretionary          |
| AVGO   | USA     | Nasdaq-100 / NASDAQ     | Semiconductors                  |
| AXP    | USA     | S&P 500 / NYSE          | Financial Services              |
| BA     | USA     | Dow Jones / NYSE        | Aerospace & Defense             |
| BAC    | USA     | S&P 500 / NYSE          | Banking                         |
| BK     | USA     | S&P 500 / NYSE          | Custody Banking                 |
| BKNG   | USA     | Nasdaq-100 / NASDAQ     | Travel Services                 |
| BLK    | USA     | S&P 500 / NYSE          | Asset Management                |
| BMY    | USA     | S&P 500 / NYSE          | Pharmaceuticals                 |
| BRK-B  | USA     | S&P 500 / NYSE          | Diversified Financials          |
| C      | USA     | S&P 500 / NYSE          | Banking                         |
| CAT    | USA     | Dow Jones / NYSE        | Industrial Machinery            |
| CL     | USA     | S&P 500 / NYSE          | Consumer Staples                |
| CMCSA  | USA     | Nasdaq-100 / NASDAQ     | Telecommunications & Media      |
| COF    | USA     | S&P 500 / NYSE          | Consumer Finance                |
| COP    | USA     | S&P 500 / NYSE          | Energy                          |
| COST   | USA     | S&P 500 / NASDAQ        | Consumer Staples                |
| CRM    | USA     | S&P 500 / NYSE          | Software                        |
| CSCO   | USA     | Dow Jones / NASDAQ      | Networking Equipment            |
| CVS    | USA     | S&P 500 / NYSE          | Healthcare Services             |
| CVX    | USA     | Dow Jones / NYSE        | Energy                          |
| DHR    | USA     | S&P 500 / NYSE          | Life Sciences Tools             |
| DIS    | USA     | Dow Jones / NYSE        | Entertainment                   |
| DOW    | USA     | S&P 500 / NYSE          | Chemicals                       |
| GE     | USA     | S&P 500 / NYSE          | Aerospace                       |
| GILD   | USA     | Nasdaq-100 / NASDAQ     | Biotechnology                   |
| GM     | USA     | S&P 500 / NYSE          | Automobiles                     |
| GOOG   | USA     | Nasdaq-100 / NASDAQ     | Internet Services               |
| GOOGL  | USA     | Nasdaq-100 / NASDAQ     | Internet Services               |
| GS     | USA     | Dow Jones / NYSE        | Investment Banking              |
| HD     | USA     | Dow Jones / NYSE        | Home Improvement Retail         |
| HON    | USA     | S&P 500 / NASDAQ        | Industrials                     |
| IBM    | USA     | Dow Jones / NYSE        | Technology                      |
| INTC   | USA     | Nasdaq-100 / NASDAQ     | Semiconductors                  |
| JNJ    | USA     | Dow Jones / NYSE        | Healthcare                      |
| JPM    | USA     | Dow Jones / NYSE        | Banking                         |
| KHC    | USA     | Nasdaq-100 / NASDAQ     | Consumer Staples                |
| KO     | USA     | Dow Jones / NYSE        | Beverages                       |
| LIN    | USA     | S&P 500 / NASDAQ        | Industrial Gases                |
| LLY    | USA     | S&P 500 / NYSE          | Pharmaceuticals                 |
| LOW    | USA     | S&P 500 / NYSE          | Home Improvement Retail         |
| MA     | USA     | S&P 500 / NYSE          | Payment Networks                |
| MCD    | USA     | Dow Jones / NYSE        | Restaurants                     |
| META   | USA     | Nasdaq-100 / NASDAQ     | Internet Platforms              |
| MET    | USA     | S&P 500 / NYSE          | Insurance                       |
| MMM    | USA     | Dow Jones / NYSE        | Industrials                     |
| MRK    | USA     | Dow Jones / NYSE        | Pharmaceuticals                 |
| MS     | USA     | S&P 500 / NYSE          | Investment Banking              |
| MSFT   | USA     | Nasdaq-100 / NASDAQ     | Software                        |
| NEE    | USA     | S&P 500 / NYSE          | Utilities                       |
| NFLX   | USA     | Nasdaq-100 / NASDAQ     | Streaming Media                 |
| NKE    | USA     | Dow Jones / NYSE        | Consumer Discretionary          |
| NVDA   | USA     | Nasdaq-100 / NASDAQ     | Semiconductors                  |
| ORCL   | USA     | S&P 500 / NYSE          | Software                        |
| PEP    | USA     | Nasdaq-100 / NASDAQ     | Beverages                       |
| PFE    | USA     | S&P 500 / NYSE          | Pharmaceuticals                 |
| PG     | USA     | Dow Jones / NYSE        | Consumer Staples                |
| PM     | USA     | S&P 500 / NYSE          | Tobacco                         |
| QCOM   | USA     | Nasdaq-100 / NASDAQ     | Semiconductors                  |
| RTX    | USA     | S&P 500 / NYSE          | Aerospace & Defense             |
| SBUX   | USA     | Nasdaq-100 / NASDAQ     | Restaurants                     |
| SCHW   | USA     | S&P 500 / NYSE          | Brokerage                       |
| SO     | USA     | S&P 500 / NYSE          | Utilities                       |
| SPG    | USA     | S&P 500 / NYSE          | REIT (Retail)                   |
| T      | USA     | S&P 500 / NYSE          | Telecommunications              |
| TGT    | USA     | S&P 500 / NYSE          | Retail                          |
| TMO    | USA     | S&P 500 / NYSE          | Life Sciences Tools             |
| TMUS   | USA     | Nasdaq-100 / NASDAQ     | Telecommunications              |
| TSLA   | USA     | Nasdaq-100 / NASDAQ     | Automobiles                     |
| TXN    | USA     | Nasdaq-100 / NASDAQ     | Semiconductors                  |
| UNH    | USA     | Dow Jones / NYSE        | Healthcare Insurance            |
| UNP    | USA     | S&P 500 / NYSE          | Railroads                       |
| UPS    | USA     | S&P 500 / NYSE          | Logistics                       |
| USB    | USA     | S&P 500 / NYSE          | Banking                         |
| V      | USA     | Dow Jones / NYSE        | Payment Networks                |
| VZ     | USA     | Dow Jones / NYSE        | Telecommunications              |
| WFC    | USA     | S&P 500 / NYSE          | Banking                         |
| WMT    | USA     | Dow Jones / NYSE        | Consumer Staples                |
| XOM    | USA     | Dow Jones / NYSE        | Energy                          |


## Author

Jeffrey Xia
