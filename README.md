<p align="center">
  <img width="560" height="560" alt="Untitled design (3)" src="https://github.com/user-attachments/assets/a3b22038-3cbb-4c31-9825-594a137d7168" />
</p>
                                                                                                         

```text
 __    __           _ _   _       ___       _            _   ___                           
/ / /\ \ \___  __ _| | |_| |__   / _ \_ __ | |_  /\   /\/ | / _ \                          
\ \/  \/ / _ \/ _` | | __| '_ \ / /_\/ '_ \| __| \ \ / /| || | | |                         
 \  /\  /  __/ (_| | | |_| | | / /_\\| |_) | |_   \ V / | || |_| |                         
  \/  \/ \___|\__,_|_|\__|_| |_\____/| .__/ \__|   \_/  |_(_)___/                          
                                     |_|                                                   
   ___                _            _ _   _                   _   _        __  
  / (_)_ ___ _____ __| |_  __ __ _(_) |_| |_    __ __ _ _  _| |_(_)___ _ _\ \ 
 | || | ' \ V / -_|_-<  _| \ V  V / |  _| ' \  / _/ _` | || |  _| / _ \ ' \| |
 | ||_|_||_\_/\___/__/\__|  \_/\_/|_|\__|_||_| \__\__,_|\_,_|\__|_\___/_||_| |
  \_\                                                                     /_/
                                                                   
                                                                   
```

# WealthGPT

An AI-assisted portfolio allocation research model for the S&P/TSX 60.

I set out to beat the all-cap weighted TSX 60 ETF (XIU.TO):

WealthGPT combines Modern Portfolio Theory, Black-Litterman expected returns,
live market data, and structured equity research generated through the OpenAI
Responses API. It constructs and compares:

- a maximum Sharpe ratio portfolio; and
- a global minimum-volatility portfolio.

The model also produces a polished PDF report covering allocations, sector
exposure, portfolio metrics, and research rationales for the eight largest
holdings in each portfolio.

> **Research software only.** This project is not financial advice and should
> not be used as an automated trading system without independent validation.

## Highlights

- Live adjusted price data and company context from `yfinance`
- Long-only SLSQP portfolio optimization
- Black-Litterman posterior expected returns
- Strict JSON-schema equity views through the OpenAI Responses API
- Validated, reusable research cache
- Maximum Sharpe and minimum-volatility portfolios
- Optional out-of-sample benchmark testing
- Jobson-Korkie Sharpe-ratio significance testing
- Automatic PDF portfolio report generation

## Project Structure

```text
.
|-- wealthgpt.py          # Main data, research, optimization, and evaluation pipeline
|-- wealthgpt_report.py   # PDF reporting and sector-exposure visualizations
|-- requirements.txt      # Runtime Python dependencies
|-- .env.example          # Environment-variable template
|-- .gitignore
`-- README.md
```

Generated JSON, CSV, PDF, and chart files are intentionally excluded from Git.

## Methodology

1. Download adjusted TSX 60 prices from Yahoo Finance.
2. Calculate annualized historical returns and the covariance matrix.
3. Collect fundamentals and recent company news.
4. Generate structured 12-month equity views using GPT.
5. Blend those views with equilibrium returns using Black-Litterman.
6. Optimize long-only maximum-Sharpe and minimum-volatility portfolios.
7. Optionally evaluate both portfolios against TSX benchmarks out of sample.
8. Export research data, allocations, charts, and an eight-page PDF report.

## Requirements

- Python 3.11 or newer
- An OpenAI API key when generating missing or refreshed equity views

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Set the OpenAI API key as an environment variable.

PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key"
```

macOS or Linux:

```bash
export OPENAI_API_KEY="your_api_key"
```

Never place a real key in the source code or commit a `.env` file.

The main settings are near the top of `wealthgpt.py`:

```python
training_years = 1
oos_years = 0

risk_free_rate = 0.0268
gpt_model = "gpt-5.4"
gpt_black_litterman = True
black_litterman_ticker_subset = None
```

Set `oos_years` above zero to enable out-of-sample analysis. To limit API use
during development, set `black_litterman_ticker_subset` to a list of tickers.

## Usage

Run the complete model:

```bash
python wealthgpt.py
```

The first complete run may make multiple OpenAI API requests and incur usage
charges. Valid equity views are cached, so later runs reuse them unless the
cache is deleted or cache refreshing is enabled.

## Generated Outputs

The script can create:

```text
black_litterman_stock_analysis.json
gpt_views.csv
portfolio_allocations.csv
wealthgpt_portfolio_report.pdf
portfolio_vs_markets_oos.png
```

The PDF report includes:

- headline return, volatility, and Sharpe estimates;
- largest portfolio positions;
- sector exposure comparisons;
- concentration and effective-holdings measures;
- rationale for the eight largest holdings in each portfolio; and
- a detailed allocation appendix.

## Important Limitations

- Expected returns are estimates, not forecasts with guaranteed accuracy.
- Model-generated equity views can be incomplete, stale, or incorrect.
- Yahoo Finance data may contain delays, omissions, or classification errors.
- Covariance estimates are sensitive to the selected training window.
- The equal-weight proxy used for equilibrium returns is not a true
  capitalization-weighted market portfolio.
- Long-only optimization can produce concentrated allocations.
- In-sample Sharpe ratios should not be interpreted as expected realized
  performance.
- The Jobson-Korkie test relies on assumptions that may not hold for all return
  series.

## Responsible Use

Review all generated research and allocations before relying on them. Production
use would require stronger data provenance, point-in-time constituent history,
transaction costs, liquidity constraints, turnover controls, robust covariance
estimation, and independent model validation.

## Author

Jeffrey Xia
