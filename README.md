<p align="center">
  <img src="resources/allolabs-logo.png" alt="AlloLabs logo" width="150">
</p>

# AlloLabs

AlloLabs is an AI-assisted global asset-allocation research platform. It
combines live Yahoo Finance data, Modern Portfolio Theory, Black-Litterman
expected returns, structured AI research views from OpenAI, Anthropic Claude,
or Google Gemini, and an interactive dashboard built with a liquid glass
design language.

It constructs and compares:

- a maximum Sharpe ratio portfolio; and
- a global minimum-volatility portfolio.

> **Research software only.** AlloLabs is not financial advice or an automated
> trading system. Review all data, assumptions, generated research, and
> allocations independently.

---

## Install

### Windows Installer (recommended)

Download the latest release from
[GitHub Releases](https://github.com/JXaeyFin/AlloLabs/releases):

| File | Description |
|------|-------------|
| `AlloLabs-Setup-1.3.2.exe` | One-click installer with Start Menu and Desktop shortcuts |
| `AlloLabs-v1.3.2-Windows-x64.zip` | Portable build — extract anywhere and run `AlloLabs.exe` |

The installer places the application in `%LOCALAPPDATA%\Programs\AlloLabs`,
creates Start Menu and Desktop shortcuts, and launches the app. No admin
privileges are required. To uninstall, run the included
`Uninstall-AlloLabs.ps1` script or delete the install directory.

### macOS and Linux

Download the platform-specific portable archive from GitHub Releases:

```text
AlloLabs-macOS-arm64.zip     # Apple Silicon
AlloLabs-macOS-x64.zip       # Intel Mac
AlloLabs-Linux-x64.tar.gz    # Linux x86_64
AlloLabs-Linux-arm64.tar.gz  # Linux ARM
```

On macOS, Control-click and select **Open** on first launch if Gatekeeper
warns about an unsigned publisher. On Linux, run `chmod +x AlloLabs
AlloLabsWorker` if needed.

### From Source

Requires Python 3.11 or newer.

```bash
git clone https://github.com/JXaeyFin/AlloLabs.git
cd AlloLabs
python -m venv .venv
```

Activate the environment and install dependencies:

```bash
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Set one or more provider API keys when AI views are enabled:

```powershell
# PowerShell
$env:OPENAI_API_KEY="your_key"
$env:ANTHROPIC_API_KEY="your_key"
$env:GEMINI_API_KEY="your_key"
```

```bash
# Bash / Zsh
export OPENAI_API_KEY="your_key"
export ANTHROPIC_API_KEY="your_key"
export GEMINI_API_KEY="your_key"
```

Only the key for the provider selected at each stage is used. Never commit a
real API key or `.env` file. See [.env.example](.env.example) for every
supported override.

---

## Features

- Large-cap U.S., Canadian, U.K., European, and international ADR universe
- Adjusted price and company metadata from `yfinance`
- Long-only or bounded long/short SLSQP optimization with position and sector caps
- Optional L2 or smooth-L1 portfolio regularization
- Multi-provider AI-assisted Black-Litterman expected returns
- Independent AI provider and model selection for research and audit stages
- Optional global AI consistency audit with cross-sectional bias detection
- Analyst and auditor seed prompts for thesis, risk, and scenario context
- Validated and reusable research, sector, and listing caches
- Out-of-sample testing against broad market benchmarks with Jobson-Korkie tests
- Multi-page PDF portfolio report and CSV allocation export
- Interactive dashboard with hover tooltips, animated SVG startup, and live terminal relay
- Bundled example portfolios and AI research visible before the first run

---

## Run the Dashboard

On Windows, double-click `start-dashboard.bat`, or run:

```bash
python dashboard/server.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The dashboard validates
settings, launches the model in a background process, relays terminal output,
and refreshes results after completion.

The startup splash connects to the runner, checks API keys, and preloads
portfolio data while the logo animation plays.

---

## Run the Model (CLI)

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
python allolabs.py
```

---

## Supported AI Models

Both dashboard stages expose the complete structured-output catalog:

- **OpenAI:** GPT-5.5, GPT-5.4, GPT-5.4 mini, GPT-5.4 nano
- **Anthropic:** Claude Fable 5, Opus 4.8, Sonnet 4.6, Haiku 4.5
- **Google:** Gemini 3.5 Flash, 3.1 Pro Preview, 3.1 Flash-Lite, 3 Flash Preview, 2.5 Pro, 2.5 Flash, 2.5 Flash-Lite

The optional global audit sends the complete research set in one request and
can be significantly more expensive than the batched research stage. It is
fail-closed: the optimizer will not continue with unaudited views when the
audit is enabled but incomplete.

---

## Build from Source

### Windows Desktop Application

```powershell
pip install -r requirements-desktop.txt
powershell -ExecutionPolicy Bypass -File scripts/build-desktop.ps1
```

If Inno Setup 6 is installed, the installer is written under `release/`.
Pass `-SkipInstaller` to produce only the portable directory.

### macOS and Linux

```bash
pip install -r requirements-desktop-linux.txt  # or requirements-desktop-macos.txt
chmod +x scripts/build-portable.sh
scripts/build-portable.sh
```

### Rebuild Company Logos

```powershell
$env:LOGO_DEV_PUBLISHABLE_KEY="your_publishable_key"
python scripts/cache-company-logos.py
Remove-Item Env:LOGO_DEV_PUBLISHABLE_KEY
```

---

## Repository Structure

```text
allolabs.py                  Main research and optimization pipeline
allolabs_company.py          Company context and market-data helpers
allolabs_report.py           PDF reporting and sector classification
dashboard/
  server.py                  Constrained local HTTP runner
  runner.py                  Model configuration and result adapter
  index.html                 Dashboard interface (liquid glass UI)
  app.js                     Client-side logic and interactions
  styles.css                 Structural layout skeleton
  terminal-theme.css         Visual theme and animations
desktop/
  app.py                     Native window and application lifecycle
  worker.py                  Hidden analysis and company-data worker
packaging/
  allolabs.spec              PyInstaller desktop bundle
  allolabs.iss               Inno Setup installer
installer-builder/
  allolabs_setup.py          Universal self-extracting installer
resources/
  company-logos/             Locally cached universe logos and manifest
  allolabs-logo.png          Application logo
examples/                    Sanitized transcripts and sample reports
.github/workflows/           CI and release automation
```

---

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

Desktop builds write these to `%LOCALAPPDATA%\AlloLabs` (Windows),
`~/Library/Application Support/AlloLabs` (macOS), or
`~/.local/share/AlloLabs` (Linux).

---

## Validation

```bash
python -m unittest discover -s tests -v
python -m py_compile allolabs.py allolabs_report.py dashboard/server.py dashboard/runner.py
node --check dashboard/app.js
```

GitHub Actions runs the same checks on pushes and pull requests.

---

## Limitations

- Expected returns are estimates, not guaranteed forecasts.
- Generated equity research may be stale, incomplete, or incorrect.
- Yahoo Finance data may contain delays, omissions, and classification errors.
- The universe is current rather than point-in-time and may introduce survivorship bias.
- Covariance estimates are sensitive to the training window.
- Transaction costs, taxes, liquidity, turnover, and market impact are omitted.
- Statistical tests rely on assumptions that may not hold in realized markets.

---

## Author

Jeffrey Xia
