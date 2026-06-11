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

| Region             |   Count |
| ------------------ | ------: |
| US Core            |      90 |
| US Extension       |      66 |
| Canada             |      47 |
| UK                 |      20 |
| Europe             |      28 |
| **Total Holdings** | **251** |

_Note. Two duplicates are present (249)_

| Sector Group                                            | Count |   % |
| ------------------------------------------------------- | ----: | --: |
| Technology / Software                                   |    28 | 11% |
| Semiconductors & Equipment                              |    20 |  8% |
| Financials (Banks, Insurance, Asset Managers, Payments) |    34 | 14% |
| Healthcare / Pharma / Biotech                           |    29 | 12% |
| Consumer (Staples, Retail, Restaurants, Luxury)         |    34 | 14% |
| Industrials / Infrastructure / Engineering              |    31 | 12% |
| Energy                                                  |    18 |  7% |
| Materials / Mining                                      |    15 |  6% |
| Utilities                                               |    11 |  4% |
| Telecom / Media                                         |    15 |  6% |
| REITs                                                   |     2 |  1% |
| Transportation / Logistics                              |     8 |  3% |
| Data / Information Services                             |     6 |  2% |
| Other Specialized                                       |   0–2 | <1% |

US Main
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

US Extension
| Ticker | Country         | Listed Index / Exchange | Sector                            |
| ------ | --------------- | ----------------------- | --------------------------------- |
| ABNB   | USA             | Nasdaq-100 / NASDAQ     | Travel Platform                   |
| ADI    | USA             | Nasdaq-100 / NASDAQ     | Semiconductors                    |
| ADP    | USA             | S&P 500 / NASDAQ        | Human Capital Management Software |
| AEP    | USA             | NASDAQ                  | Electric Utilities                |
| AKAM   | USA             | NASDAQ                  | Cloud & CDN Services              |
| ALNY   | USA             | NASDAQ                  | RNA Therapeutics                  |
| ANSS   | USA             | NASDAQ                  | Engineering Simulation Software   |
| APP    | USA             | NASDAQ                  | Mobile Advertising Technology     |
| ARM    | UK / USA        | NASDAQ                  | Semiconductors                    |
| BKR    | USA             | NASDAQ                  | Oilfield Services                 |
| BIIB   | USA             | NASDAQ                  | Biotechnology                     |
| CDW    | USA             | S&P 500 / NASDAQ        | IT Solutions & Distribution       |
| CHTR   | USA             | NASDAQ                  | Cable & Broadband                 |
| CPRT   | USA             | NASDAQ                  | Vehicle Auctions                  |
| CRWD   | USA             | NASDAQ                  | Cybersecurity                     |
| CSX    | USA             | NASDAQ                  | Railways                          |
| CTAS   | USA             | Nasdaq-100 / NASDAQ     | Business Services                 |
| CTSH   | USA             | NASDAQ                  | IT Consulting                     |
| DASH   | USA             | NASDAQ                  | Food Delivery Platform            |
| DDOG   | USA             | NASDAQ                  | Cloud Monitoring Software         |
| DXCM   | USA             | NASDAQ                  | Medical Devices                   |
| EA     | USA             | NASDAQ                  | Video Games                       |
| EBAY   | USA             | NASDAQ                  | E-commerce                        |
| EXC    | USA             | NASDAQ                  | Electric Utilities                |
| FANG   | USA             | NASDAQ                  | Oil & Gas Exploration             |
| FAST   | USA             | NASDAQ                  | Industrial Distribution           |
| FTNT   | USA             | Nasdaq-100 / NASDAQ     | Cybersecurity                     |
| GFS    | USA             | NASDAQ                  | Semiconductor Foundry             |
| IDXX   | USA             | NASDAQ                  | Veterinary Diagnostics            |
| INSM   | USA             | NASDAQ                  | Biotechnology                     |
| ISRG   | USA             | Nasdaq-100 / NASDAQ     | Surgical Robotics                 |
| KDP    | USA             | NASDAQ                  | Beverages                         |
| KLAC   | USA             | Nasdaq-100 / NASDAQ     | Semiconductor Equipment           |
| LRCX   | USA             | Nasdaq-100 / NASDAQ     | Semiconductor Equipment           |
| MAR    | USA             | S&P 500 / NASDAQ        | Hotels & Hospitality              |
| MDB    | USA             | NASDAQ                  | Database Software                 |
| MDLZ   | USA             | Nasdaq-100 / NASDAQ     | Consumer Staples                  |
| MELI   | Uruguay         | NASDAQ                  | E-commerce & Fintech              |
| MCHP   | USA             | Nasdaq-100 / NASDAQ     | Semiconductors                    |
| MNST   | USA             | Nasdaq-100 / NASDAQ     | Energy Drinks                     |
| MPWR   | USA             | Nasdaq-100 / NASDAQ     | Analog Semiconductors             |
| MRVL   | USA             | Nasdaq-100 / NASDAQ     | Semiconductors                    |
| MU     | USA             | Nasdaq-100 / NASDAQ     | Memory Semiconductors             |
| NXPI   | Netherlands     | NASDAQ                  | Semiconductors                    |
| ODFL   | USA             | NASDAQ                  | Logistics                         |
| ON     | USA             | NASDAQ                  | Semiconductors                    |
| ORLY   | USA             | NASDAQ                  | Auto Parts Retail                 |
| PANW   | USA             | Nasdaq-100 / NASDAQ     | Cybersecurity                     |
| PAYX   | USA             | NASDAQ                  | Payroll Services                  |
| PCAR   | USA             | Nasdaq-100 / NASDAQ     | Heavy Trucks                      |
| PDD    | China           | NASDAQ                  | E-commerce                        |
| PLTR   | USA             | NASDAQ                  | AI & Data Analytics               |
| REGN   | USA             | NASDAQ                  | Biotechnology                     |
| ROP    | USA             | S&P 500 / NASDAQ        | Industrial Software               |
| ROST   | USA             | NASDAQ                  | Discount Retail                   |
| SHOP   | Canada          | NASDAQ                  | E-commerce Software               |
| SNPS   | USA             | Nasdaq-100 / NASDAQ     | Electronic Design Automation      |
| STX    | Ireland         | NASDAQ                  | Data Storage                      |
| TEAM   | Australia / USA | NASDAQ                  | Collaboration Software            |
| TTWO   | USA             | NASDAQ                  | Video Games                       |
| VRSK   | USA             | NASDAQ                  | Data Analytics                    |
| VRTX   | USA             | NASDAQ                  | Biotechnology                     |
| WBD    | USA             | NASDAQ                  | Media & Entertainment             |
| WDAY   | USA             | NASDAQ                  | Enterprise Software               |
| XEL    | USA             | NASDAQ                  | Electric Utilities                |
| ZS     | USA             | NASDAQ                  | Cybersecurity                     |

UK
| Ticker |      Country | Listed Index / Exchange          | Sector                     |
| ------ | -----------: | -------------------------------- | -------------------------- |
| AZN.L  |           UK | London Stock Exchange / FTSE 100 | Pharmaceuticals            |
| ULVR.L |           UK | London Stock Exchange / FTSE 100 | Consumer Staples           |
| SHEL.L |           UK | London Stock Exchange / FTSE 100 | Energy                     |
| BP.L   |           UK | London Stock Exchange / FTSE 100 | Energy                     |
| HSBA.L |           UK | London Stock Exchange / FTSE 100 | Banking                    |
| GSK.L  |           UK | London Stock Exchange / FTSE 100 | Pharmaceuticals            |
| RIO.L  |           UK | London Stock Exchange / FTSE 100 | Mining                     |
| BATS.L |           UK | London Stock Exchange / FTSE 100 | Tobacco                    |
| DGE.L  |           UK | London Stock Exchange / FTSE 100 | Beverages                  |
| GLEN.L |           UK | London Stock Exchange / FTSE 100 | Mining / Commodities       |
| AAL.L  |           UK | London Stock Exchange / FTSE 100 | Mining                     |
| LSEG.L |           UK | London Stock Exchange / FTSE 100 | Financial Data / Exchanges |
| NG.L   |           UK | London Stock Exchange / FTSE 100 | Utilities                  |
| VOD.L  |           UK | London Stock Exchange / FTSE 100 | Telecommunications         |
| REL.L  |           UK | London Stock Exchange / FTSE 100 | Information Services       |
| CPG.L  |           UK | London Stock Exchange / FTSE 100 | Business Services          |
| SMIN.L |           UK | London Stock Exchange / FTSE 100 | Industrial Technology      |
| IMB.L  |           UK | London Stock Exchange / FTSE 100 | Tobacco                    |
| CRH.L  | UK / Ireland | London Stock Exchange / FTSE 100 | Building Materials         |
| SN.L   |           UK | London Stock Exchange / FTSE 100 | Medical Devices            |

EU
| Ticker  |             Country | Listed Index / Exchange   | Sector                        |
| ------- | ------------------: | ------------------------- | ----------------------------- |
| ASML.AS |         Netherlands | Euronext Amsterdam        | Semiconductors                |
| SAP.DE  |             Germany | Xetra / DAX               | Software                      |
| SIE.DE  |             Germany | Xetra / DAX               | Industrials                   |
| AIR.PA  |              France | Euronext Paris / CAC 40   | Aerospace & Defense           |
| OR.PA   |              France | Euronext Paris / CAC 40   | Consumer Staples              |
| MC.PA   |              France | Euronext Paris / CAC 40   | Luxury Goods                  |
| SAN.PA  |              France | Euronext Paris / CAC 40   | Pharmaceuticals               |
| BNP.PA  |              France | Euronext Paris / CAC 40   | Banking                       |
| ENGI.PA |              France | Euronext Paris / CAC 40   | Utilities                     |
| AI.PA   |              France | Euronext Paris / CAC 40   | Industrial Gases              |
| RMS.PA  |              France | Euronext Paris / CAC 40   | Luxury Goods                  |
| KER.PA  |              France | Euronext Paris / CAC 40   | Luxury Goods                  |
| DG.PA   |              France | Euronext Paris / CAC 40   | Construction / Infrastructure |
| ENEL.MI |               Italy | Borsa Italiana / FTSE MIB | Utilities                     |
| ISP.MI  |               Italy | Borsa Italiana / FTSE MIB | Banking                       |
| ENI.MI  |               Italy | Borsa Italiana / FTSE MIB | Energy                        |
| STLA.MI | Netherlands / Italy | Borsa Italiana / FTSE MIB | Automobiles                   |
| ABI.BR  |             Belgium | Euronext Brussels         | Beverages                     |
| DSY.PA  |              France | Euronext Paris / CAC 40   | Software                      |
| HO.PA   |              France | Euronext Paris / CAC 40   | Aerospace & Defense           |
| PHIA.AS |         Netherlands | Euronext Amsterdam        | Healthcare Technology         |
| AD.AS   |         Netherlands | Euronext Amsterdam        | Consumer Staples Retail       |
| ZURN.SW |         Switzerland | SIX Swiss Exchange        | Insurance                     |
| NESN.SW |         Switzerland | SIX Swiss Exchange        | Consumer Staples              |
| NOVN.SW |         Switzerland | SIX Swiss Exchange        | Pharmaceuticals               |
| ROG.SW  |         Switzerland | SIX Swiss Exchange        | Pharmaceuticals               |
| UBSG.SW |         Switzerland | SIX Swiss Exchange        | Banking                       |
| CS.PA   |              France | Euronext Paris / CAC 40   | Insurance                     |

TSX
| Ticker    | Country | Listed Index / Exchange | Sector                         |
| --------- | ------- | ----------------------- | ------------------------------ |
| RY.TO     | Canada  | TSX 60 / TSX            | Banking                        |
| TD.TO     | Canada  | TSX 60 / TSX            | Banking                        |
| BMO.TO    | Canada  | TSX 60 / TSX            | Banking                        |
| BNS.TO    | Canada  | TSX 60 / TSX            | Banking                        |
| NA.TO     | Canada  | TSX Composite / TSX     | Banking                        |
| CM.TO     | Canada  | TSX 60 / TSX            | Banking                        |
| ENB.TO    | Canada  | TSX 60 / TSX            | Energy Infrastructure          |
| TRP.TO    | Canada  | TSX 60 / TSX            | Energy Infrastructure          |
| SU.TO     | Canada  | TSX 60 / TSX            | Integrated Energy              |
| CNQ.TO    | Canada  | TSX 60 / TSX            | Oil & Gas E&P                  |
| CVE.TO    | Canada  | TSX 60 / TSX            | Oil & Gas E&P                  |
| TOU.TO    | Canada  | TSX Composite / TSX     | Natural Gas                    |
| POW.TO    | Canada  | TSX 60 / TSX            | Financial Conglomerate         |
| SLF.TO    | Canada  | TSX 60 / TSX            | Insurance                      |
| MFC.TO    | Canada  | TSX 60 / TSX            | Insurance                      |
| FFH.TO    | Canada  | TSX 60 / TSX            | Insurance / Investment Holding |
| BAM.TO    | Canada  | TSX 60 / TSX            | Alternative Asset Management   |
| BN.TO     | Canada  | TSX 60 / TSX            | Diversified Holdings           |
| BIP-UN.TO | Canada  | TSX Composite / TSX     | Infrastructure                 |
| FTS.TO    | Canada  | TSX 60 / TSX            | Utilities                      |
| EMA.TO    | Canada  | TSX 60 / TSX            | Utilities                      |
| PPL.TO    | Canada  | TSX 60 / TSX            | Utilities                      |
| TRI.TO    | Canada  | TSX 60 / TSX            | Information Services           |
| OTEX.TO   | Canada  | TSX 60 / TSX            | Software                       |
| CSU.TO    | Canada  | TSX 60 / TSX            | Software                       |
| WCN.TO    | Canada  | TSX 60 / TSX            | Environmental Services         |
| WSP.TO    | Canada  | TSX 60 / TSX            | Engineering & Consulting       |
| CNR.TO    | Canada  | TSX 60 / TSX            | Railways                       |
| CP.TO     | Canada  | TSX 60 / TSX            | Railways                       |
| ATD.TO    | Canada  | TSX 60 / TSX            | Convenience Retail             |
| DOL.TO    | Canada  | TSX 60 / TSX            | Discount Retail                |
| QSR.TO    | Canada  | TSX 60 / TSX            | Restaurants                    |
| MRU.TO    | Canada  | TSX 60 / TSX            | Grocery Retail                 |
| SHOP.TO   | Canada  | TSX 60 / TSX            | E-Commerce Software            |
| GIB-A.TO  | Canada  | TSX 60 / TSX            | IT Services & Consulting       |
| WN.TO     | Canada  | TSX 60 / TSX            | Grocery Retail                 |
| WPM.TO    | Canada  | TSX 60 / TSX            | Precious Metals Royalty        |
| FNV.TO    | Canada  | TSX 60 / TSX            | Precious Metals Royalty        |
| AEM.TO    | Canada  | TSX 60 / TSX            | Gold Mining                    |
| ABX.TO    | Canada  | TSX 60 / TSX            | Gold Mining                    |
| TECK-B.TO | Canada  | TSX 60 / TSX            | Diversified Mining             |
| NTR.TO    | Canada  | TSX 60 / TSX            | Fertilizers & Agriculture      |
| FM.TO     | Canada  | TSX 60 / TSX            | Base Metals Mining             |
| CCO.TO    | Canada  | TSX Composite / TSX     | Uranium Mining                 |
| BCE.TO    | Canada  | TSX 60 / TSX            | Telecommunications             |
| T.TO      | Canada  | TSX 60 / TSX            | Telecommunications             |
| RCI-B.TO  | Canada  | TSX 60 / TSX            | Telecommunications             |




## Author

Jeffrey Xia
