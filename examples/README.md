# WealthGPT Example Walkthrough

This folder contains a public-safe example of a complete WealthGPT workflow.
Machine-specific paths, credentials, request identifiers, and exact API timing
have been removed or replaced with clearly marked placeholders.

## Included Files

```text
examples/
|-- README.md
|-- default-run.json
|-- default-portfolio-report.pdf
|-- default-performance.png
|-- terminal-first-run.txt
|-- terminal-cached-run.txt
`-- wealthgpt-sample-report.pdf
```

- `default-run.json` powers the dashboard before the first local run.
- `default-portfolio-report.pdf` and `default-performance.png` accompany that
  bundled snapshot.
- `terminal-first-run.txt` demonstrates initial research generation.
- `terminal-cached-run.txt` demonstrates reuse of validated cached views.
- `wealthgpt-sample-report.pdf` shows the resulting portfolio report.

## 1. Install

From the repository root:

```bash
python -m pip install -r requirements.txt
```

Set the OpenAI API key in the process environment.

PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key"
```

macOS or Linux:

```bash
export OPENAI_API_KEY="your_api_key"
```

The key is used only when the requested universe is not already covered by a
valid local research cache.

## 2. Configure

Use the dashboard controls or environment variables:

```powershell
$env:WEALTHGPT_TRAINING_YEARS="1"
$env:WEALTHGPT_OOS_YEARS="0"
$env:WEALTHGPT_MAX_POSITION_WEIGHT="0.20"
$env:WEALTHGPT_GPT_VIEWS="true"
$env:WEALTHGPT_RESEARCH_TICKERS='["AAPL","MSFT","RY.TO"]'
```

## 3. Run

```bash
python wealthgpt.py
```

The startup banner is followed by the selected date windows and market-data
download status.

## 4. Market Data

WealthGPT downloads adjusted global equity prices and builds:

- annualized historical returns;
- an annualized covariance matrix; and
- a cleaned, aligned investable universe.

Insufficient or non-finite training data causes an explicit failure rather than
silent continuation.

## 5. Equity Research

On a first run, WealthGPT collects available fundamentals and recent headlines
through `yfinance`. It requests structured 12-month equity views from the OpenAI
Responses API.

Each view contains:

- ticker and industry;
- probability-weighted expected return;
- confidence score; and
- concise upside and risk rationale.

The response is constrained by a strict JSON schema. Missing, duplicated,
unexpected, or out-of-range views are rejected.

Validated research is saved locally. Later runs can reuse the cache, reducing
latency and avoiding unnecessary API use.

## 6. Black-Litterman

The model combines structured views with equilibrium returns through a
Black-Litterman posterior update. Confidence determines the uncertainty assigned
to each view.

The exported analysis distinguishes historical return, equilibrium prior,
model view, posterior expected return, and the change from prior to posterior.

## 7. Portfolio Optimization

Two long-only portfolios are solved using SLSQP:

1. **Maximum Sharpe:** maximizes estimated excess return per unit of volatility.
2. **Minimum Volatility:** minimizes estimated annualized portfolio risk.

Weights are validated and normalized to sum to 100%.

## 8. Optional Out-of-Sample Test

When OOS testing is enabled, WealthGPT compares the portfolios with available
broad-market trackers including `XIU.TO`, `SPY`, `QQQ`, `ISF.L`, and
`^STOXX50E`.

It reports realized return and annualized volatility, plots cumulative returns,
and performs Jobson-Korkie Sharpe-ratio comparisons.

The included snapshot has out-of-sample testing disabled.

## 9. PDF Report

The report includes:

- return, volatility, and Sharpe estimates;
- top holdings and full allocations;
- sector-exposure comparisons;
- concentration and effective-holdings measures;
- rationale for the eight largest holdings in each portfolio; and
- a detailed allocation appendix.

See [`wealthgpt-sample-report.pdf`](wealthgpt-sample-report.pdf).

## Reading the Results

The example is a point-in-time research snapshot, not a current recommendation.
Portfolio weights reflect both expected returns and covariance. A company can
receive a meaningful allocation with a modest standalone view, or receive no
allocation despite a positive view.

## Public-Safety Redactions

The transcripts use placeholders such as:

```text
<PROJECT_DIR>
<REDACTED_API_TIMING>
<ADDITIONAL SMALL POSITIONS OMITTED>
```

No API keys, authorization headers, usernames, absolute machine paths, request
IDs, or private environment values are included.

## Disclaimer

WealthGPT is research software, not financial advice. The sample may contain
model errors, stale market information, or inaccurate generated analysis.
