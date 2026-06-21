<p align="center">
  <img src="resources/allolabs-logo.png" alt="AlloLabs logo" width="150">
</p>

# AlloLabs

AlloLabs is an AI-assisted global asset-allocation research platform. It
combines live Yahoo Finance data, Modern Portfolio Theory, Black-Litterman
expected returns, structured OpenAI, Anthropic Claude, or Google Gemini research views, and a local
Bloomberg-inspired dashboard.

AlloLabs can run either as the existing local browser dashboard or as a
packaged Windows desktop application. The desktop build opens in its own native
window, uses an automatically selected localhost port, and runs analysis in a
hidden bundled worker process.

It constructs and compares:

- a maximum Sharpe ratio portfolio; and
- a global minimum-volatility portfolio.

The portfolio breakdown displays every holding with more than 0.01% absolute
portfolio weight. Selecting a ticker opens an on-demand Yahoo Finance snapshot
with the company name, the same fundamental ratios supplied to AI research, and
up to five recent headlines. Company logos are bundled under
`resources/company-logos/`, so ordinary dashboard use does not expose a key or
make external image requests. The bundled release is complete without a
Logo.dev key; one is needed only when intentionally rebuilding the logo cache.
The Run Console also supports optional analyst and auditor seed prompts, so a
user can provide thesis, risk-preference, and scenario context before AI
research or final audit runs.
The Run Console includes a milestone-driven estimated progress bar. Its pacing
adapts to the selected research universe, cache refresh, AI research and audit
stages, training window, and optional out-of-sample analysis.

> **Research software only.** AlloLabs is not financial advice or an automated
> trading system. Review all data, assumptions, generated research, and
> allocations independently.

## Features

- Large-cap U.S., Canadian, U.K., European, and international ADR universe
- Adjusted price and company metadata from `yfinance`
- Selectable long-only or bounded long/short SLSQP optimization with absolute position and sector maximums; 100% leaves a limit unrestricted
- Optional L2 or differentiable smooth-L1 portfolio regularization
- Optional multi-provider AI-assisted Black-Litterman expected returns
- Independently selectable AI provider and model for research and global audit stages
- Validated and reusable research, sector, and listing caches
- Optional out-of-sample testing against broad market benchmarks
- Jobson-Korkie Sharpe-ratio comparisons
- Multi-page PDF portfolio report and CSV allocation export
- Local web dashboard with run controls, live terminal relay, report viewer,
  performance chart, market flags, and listing metadata
- Bundled example portfolios and AI sentiments visible before the first run

## Repository

```text
.
|-- allolabs.py                 # Main research and optimization pipeline
|-- allolabs_company.py         # Company context and market-data helpers
|-- allolabs_report.py          # PDF reporting and sector classification
|-- dashboard/
|   |-- server.py                # Constrained local HTTP runner
|   |-- runner.py                # Model configuration and result adapter
|   |-- index.html               # Dashboard interface
|   |-- app.js
|   |-- styles.css
|   `-- terminal-theme.css
|-- desktop/
|   |-- app.py                   # Native window and application lifecycle
|   `-- worker.py                # Hidden analysis and company-data worker
|-- packaging/
|   |-- allolabs.spec            # PyInstaller desktop bundle
|   `-- allolabs.iss             # Inno Setup installer
|-- scripts/
|   |-- cache-company-logos.py   # Rebuild the local ticker logo library
|   |-- build-desktop.ps1        # Build the Windows app and installer
|   `-- start-dashboard.ps1
|-- resources/
|   |-- company-logos/           # Locally cached universe logos and manifest
|   `-- allolabs-logo.png
|-- tests/
|   `-- test_release.py
|-- examples/                    # Sanitized transcripts and sample PDF
|-- start-dashboard.bat
|-- start-allolabs-dashboard.bat
|-- start-allolabs-desktop.bat
|-- requirements.txt
|-- requirements-desktop.txt
|-- requirements-desktop-macos.txt
|-- requirements-desktop-linux.txt
|-- .env.example
`-- .github/workflows/ci.yml
```

Generated research, caches, allocations, charts, and reports are intentionally
excluded from Git. Sanitized default examples under `examples/` are included.

## Installation

Requirements:

- Python 3.11 or newer
- An API key for the provider selected when generating new AI research views

```bash
# From your cloned or downloaded repository:
cd allolabs
python -m venv .venv
```

Activate the environment and install dependencies:

```bash
python -m pip install -r requirements.txt
```

Set one or more provider API keys in the process environment when AI views are enabled:

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:ANTHROPIC_API_KEY="your_api_key"
$env:GEMINI_API_KEY="your_api_key"
```

Only the key for the provider selected at each stage is used. Never commit a
real API key or `.env` file.

## Windows Desktop Application

For a source checkout, `start-allolabs-desktop.bat` opens the dashboard in a
dedicated application window. It uses pywebview when installed and can fall
back to Microsoft Edge application mode during development.

Build the self-contained Windows application:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-desktop.ps1
```

The build uses PyInstaller's one-directory mode for faster, more dependable
scientific-library startup. If Inno Setup 6 is installed, the final installer
is written under `release/`. Pass `-SkipInstaller` to produce only
`dist/AlloLabs-Windows-x64/AlloLabs.exe`.

The build automatically runs `scripts/verify-portable.ps1`. A valid portable
folder contains both `AlloLabs.exe` and the hidden-process
`AlloLabsWorker.exe`; the verifier imports every required analytical dependency
without making network requests.

Installed builds keep bundled application files read-only and write generated
reports, results, caches, and settings under `%LOCALAPPDATA%\AlloLabs`.

The `Windows Desktop Build` GitHub Actions workflow performs the same packaging
on `windows-latest`. Run it manually or push a version tag to receive
`AlloLabs-v1.3.1-Windows-x64.zip` and `AlloLabs-Setup-1.3.1.exe`.

## macOS And Linux Portable Applications

PyInstaller creates native binaries and cannot cross-compile them from Windows.
On a Mac or Linux machine, run:

```bash
chmod +x scripts/build-portable.sh
scripts/build-portable.sh
```

The detected platform and processor determine the output:

```text
dist/AlloLabs-macOS-arm64/
dist/AlloLabs-macOS-x64/
dist/AlloLabs-Linux-arm64/
dist/AlloLabs-Linux-x64/
```

macOS receives an ad-hoc-signed `AlloLabs.app` bundle and ZIP archive. Linux
receives native `AlloLabs` and `AlloLabsWorker` executables plus a `.tar.gz`
archive. Every build runs the offline worker self-test before it is packaged.

The `macOS and Linux Portable Builds` GitHub Actions workflow creates the
available native artifacts automatically. The artifact architecture is derived
from the hosted runner rather than being mislabeled.

To rebuild the bundled company logos after changing `ASSET_UNIVERSE`, set the
Logo.dev publishable key only for the command and run:

```powershell
$env:LOGO_DEV_PUBLISHABLE_KEY="your_publishable_key"
python scripts/cache-company-logos.py
Remove-Item Env:LOGO_DEV_PUBLISHABLE_KEY
```

The script skips existing PNGs by default and writes coverage details to
`resources/company-logos/manifest.json`. Use `--refresh` to replace every file.

## Run The Model

The standard command-line run uses the defaults defined in `allolabs.py`:

```bash
python allolabs.py
```

Runtime settings can be supplied without editing source:

```powershell
$env:ALLOLABS_TRAINING_YEARS="2"
$env:ALLOLABS_OOS_YEARS="0.5"
$env:ALLOLABS_MAX_POSITION_WEIGHT="0.15"
$env:ALLOLABS_MAX_SECTOR_WEIGHT="0.35"
$env:ALLOLABS_REGULARIZATION="l2"
$env:ALLOLABS_REGULARIZATION_STRENGTH="0.25"
$env:ALLOLABS_GPT_VIEWS="true"
$env:ALLOLABS_RESEARCH_PROVIDER="anthropic"
$env:ALLOLABS_RESEARCH_MODEL="claude-sonnet-4-6"
$env:ALLOLABS_GPT_AUDIT="true"
$env:ALLOLABS_AUDIT_PROVIDER="gemini"
$env:ALLOLABS_GPT_AUDIT_MODEL="gemini-3.1-pro-preview"
$env:ALLOLABS_RESEARCH_TICKERS='["AAPL","MSFT","RY.TO"]'
python allolabs.py
```

See [.env.example](.env.example) for every supported override.

Both dashboard stages expose the complete supported structured-output catalog.
Recommended research and audit choices are labeled in each dropdown:

- OpenAI: GPT-5.5 and the GPT-5.4, mini, and nano family.
- Anthropic: Claude Fable 5, Opus 4.8, Sonnet 4.6, and Haiku 4.5.
- Google: Gemini 3.5 Flash; 3.1 Pro Preview and Flash-Lite; 3 Flash Preview;
  and the Gemini 2.5 Pro, Flash, and Flash-Lite family.

Availability depends on the provider account. The optional global audit sends
the complete selected research set in one additional request and can be
materially more expensive than the batched research stage. It is fail-closed:
the optimizer will not silently continue with unaudited views when the audit is
enabled but incomplete or unsuccessful.
The audit defaults to `gpt-5.5`; the research stage defaults to `gpt-5.4`.
Its final pass evaluates record-level return/confidence consistency and
cross-sectional sector, region, familiarity, scale, and optimism biases. It
rewrites each audited rationale as a report-ready, security-specific explanation
of roughly 45-75 words while preserving the complete ticker set.

L2 regularization penalizes squared deviations from equal weight. Smooth L1
penalizes a differentiable approximation of absolute deviations from equal
weight, acting as a turnover or transaction-cost proxy when no existing
portfolio is supplied. Hard sector limits are enforced as SLSQP inequalities.

## Run The Dashboard

On Windows, double-click `start-dashboard.bat`, or run:

```powershell
.\scripts\start-dashboard.ps1
```

If an older dashboard process is still using port `8765`, run:

```powershell
.\restart-dashboard.bat
```

The branded `start-allolabs-dashboard.bat` and
`restart-allolabs-dashboard.bat` launchers are also included.

On any platform:

```bash
python dashboard/server.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The dashboard validates
settings, launches the model in a background process, relays terminal output,
and refreshes the overview and report tabs after completion.

For access beyond localhost, set `ALLOLABS_REMOTE_TOKEN`, bind explicitly, and
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
gpt_audited_views.json
gpt_views.csv
latest_run.json
listing_metadata_cache.json
portfolio_allocations.csv
portfolio_vs_markets_oos.png
sector_cache.json
allolabs_portfolio_report.pdf
```

The Bloomberg-terminal-inspired PDF leads with risk, construction, and
concentration rather than presenting model returns as promises. It includes a
return-input bridge separating historical observations, equilibrium priors, AI
views, and Black-Litterman posterior inputs; educational model-risk notes;
security rationales; sector exposure; and a paginated allocation appendix down
to 0.005% absolute weight. Holding-rationale cards use locally bundled
rounded-square company marks where available.

## Validation

Run the release checks locally:

```bash
python -m unittest discover -s tests -v
python -m py_compile allolabs.py allolabs_report.py dashboard/server.py dashboard/runner.py
node --check dashboard/app.js
```

GitHub Actions runs the same checks on pushes and pull requests.

## Methodology

1. Download and align adjusted equity prices, retrying symbols omitted by bulk requests.
2. Estimate annualized historical returns and covariance.
3. Collect company context and optional structured multi-provider AI views.
4. Optionally audit the complete generated view set with the global audit model.
5. Blend views with equilibrium returns using Black-Litterman.
6. Solve maximum-Sharpe and minimum-volatility portfolios with SLSQP.
7. Optionally evaluate both portfolios out of sample.
8. Export dashboard data, allocations, charts, and the PDF report.

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

## Author

Jeffrey Xia
