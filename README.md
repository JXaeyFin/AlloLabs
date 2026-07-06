<p align="center">
  <img src="resources/allolabs-logo.png" alt="AlloLabs logo" width="150">
</p>

# AlloLabs

AlloLabs is an AI-assisted global asset-allocation research platform. It
combines live Yahoo Finance data, Modern Portfolio Theory, Black-Litterman
expected returns, structured AI research views from OpenAI, Anthropic Claude,
Google Gemini, or DeepSeek, and an interactive desktop dashboard with an
integrated AI guide.

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
| `AlloLabs-Setup-1.4.0.exe` | One-click installer with Start Menu and Desktop shortcuts |
| `AlloLabs-v1.4.0-Windows-x64.zip` | Portable build — extract anywhere and run `AlloLabs.exe` |

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
$env:DEEPSEEK_API_KEY="your_key"
```

```bash
# Bash / Zsh
export OPENAI_API_KEY="your_key"
export ANTHROPIC_API_KEY="your_key"
export GEMINI_API_KEY="your_key"
export DEEPSEEK_API_KEY="your_key"
```

Only the key for the provider selected at each stage is used. Never commit a
real API key or `.env` file. See [.env.example](.env.example) for every
supported override.

---

## Features

- Large-cap U.S., Canadian, U.K., European, and international ADR universe
- Dedicated universe customization with presets, market-level selection, and individual ticker checkboxes
- Allo Guide for portfolio education, mandate drafting, run configuration, and portfolio explanation
- Catalog-grounded ticker suggestions across 947 supported securities in six market groups
- Adjusted price and company metadata from `yfinance`
- Long-only or bounded long/short SLSQP optimization with position and sector caps
- Optional L2 or smooth-L1 portfolio regularization
- Multi-provider AI-assisted Black-Litterman expected returns with a **market-cap-weighted equilibrium prior** (caps fetched live from yfinance; mean-fills any missing values)
- Independent AI provider and model selection for research and audit stages
- Optional global AI consistency audit with cross-sectional bias detection
- Analyst and auditor seed prompts for thesis, risk, and scenario context
- Configurable per-ticker news depth (1–20 articles, default 5) with full article summaries included in the AI prompt
- Validated and reusable research, sector, and listing caches
- Out-of-sample testing against broad market benchmarks with Jobson-Korkie tests
- Institutional-style PDF allocation memorandum with industry profiles, hedge analysis, macro/micro sensitivity maps, security briefs, and complete allocation schedules
- Interactive dashboard with hover tooltips, animated SVG startup, and live terminal relay
- **Dynamic overview metric cards** that automatically switch between three display modes:
  - *Historical* — in-sample optimizer estimates (Max Sharpe / Min Vol return, risk, Sharpe)
  - *AI views* — Black-Litterman posterior expected returns with historical volatility estimates
  - *OOS* — realized out-of-sample return, volatility, and Sharpe for the test window
- Tiered ticker search across research views and the universe picker (exact → prefix → contains → fuzzy/subsequence)
- Local run history for browsing and reloading dated configurations, portfolios, AI opinions, charts, and PDFs
- Bundled example portfolios and AI research visible before the first run

---

## Run the Desktop App

On Windows, double-click `start-allolabs-desktop.bat`, or run:

```bash
pythonw -m desktop.app
# falls back to python -m desktop.app if pythonw is unavailable
```

The desktop app opens a native window embedding the full AlloLabs interface.
It validates settings, launches the model in a background process, relays
terminal output, and refreshes results after completion.

The startup splash connects to the embedded runner, checks API keys, and
preloads portfolio data while the logo animation plays.

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
$env:ALLOLABS_MAX_NEWS_ARTICLES="10"   # news articles per ticker in AI prompt (1–20, default 5)
python allolabs.py
```

---

## Supported AI Models

Both dashboard stages expose the complete structured-output catalog:

- **OpenAI:** GPT-5.5, GPT-5.4, GPT-5.4 mini, GPT-5.4 nano
- **Anthropic:** Claude Fable 5, Opus 4.8, Sonnet 4.6, Haiku 4.5
- **Google:** Gemini 3.5 Flash, 3.1 Pro Preview, 3.1 Flash-Lite, 3 Flash Preview, 2.5 Pro, 2.5 Flash, 2.5 Flash-Lite
- **DeepSeek:** DeepSeek Chat, DeepSeek Reasoner

The optional global audit sends the complete research set in one request and
can be significantly more expensive than the batched research stage. It is
fail-closed: the optimizer will not continue with unaudited views when the
audit is enabled but incomplete.

---

## Build from Source

### Windows Desktop Application

```powershell
pip install -r requirements-desktop-win.txt
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
╔══════════════════════════════════════════════════════════════╗
║  SOURCE — core Python modules (run from source or bundled)   ║
╚══════════════════════════════════════════════════════════════╝
allolabs.py                  Main research and optimization pipeline
allolabs_company.py          Yahoo Finance company context and market-data helpers
allolabs_guide.py            Allo AI assistant — system prompt, context, and LLM proxy
allolabs_paths.py            Cross-platform application and data paths
allolabs_report.py           PDF reporting and sector classification
allolabs_report_memo.py      Editorial memo layout, exhibits, and sensitivity analysis

╔══════════════════════════════════════════════════════════════╗
║  DESKTOP — native window wrapper (PyWebView)                 ║
╚══════════════════════════════════════════════════════════════╝
desktop/
  app.py                     Native window lifecycle, single-instance lock
  worker.py                  Bundled analysis and company-data worker entry point

╔══════════════════════════════════════════════════════════════╗
║  DASHBOARD (UI) — embedded WebView interface layer           ║
╚══════════════════════════════════════════════════════════════╝
dashboard/
  server.py                  Authenticated local HTTP relay
  runner.py                  Model configuration, result adapter, and run history
  universe.py                Shared market groups, presets, and ticker catalog
  company_details.py         Per-ticker company context helper (subprocess worker)
  index.html                 Application UI (liquid glass design)
  app.js                     Client-side logic and interactions
  styles.css                 Structural layout skeleton
  terminal-theme.css         Visual theme and animations

╔══════════════════════════════════════════════════════════════╗
║  BUILD & PACKAGING — producing installable releases          ║
╚══════════════════════════════════════════════════════════════╝
packaging/
  allolabs.spec              PyInstaller bundle definition (app + worker)
  allolabs.iss               Inno Setup Windows installer script
  PORTABLE_README.md         README copied into portable/zip releases
installer-builder/
  allolabs_setup.py          Universal self-extracting installer (Windows)
installer-payload/
  install.cmd / install.ps1  Scripts executed during installation
  PORTABLE_README.md         End-user portable release README

╔══════════════════════════════════════════════════════════════╗
║  SCRIPTS — build, verify, and maintenance helpers            ║
╚══════════════════════════════════════════════════════════════╝
scripts/
  build-desktop.ps1          Windows: venv + PyInstaller + Inno Setup
  build-portable.sh          macOS / Linux: venv + PyInstaller + archive
  verify-portable.ps1/.py    Sanity-check a portable build directory
  cache-company-logos.py     Download and cache universe company logos

╔══════════════════════════════════════════════════════════════╗
║  REQUIREMENTS — dependency lists by target environment       ║
╚══════════════════════════════════════════════════════════════╝
requirements.txt             Runtime deps for running from source
requirements-desktop-win.txt Windows desktop build (adds pywebview + pyinstaller)
requirements-desktop-macos.txt  macOS desktop build
requirements-desktop-linux.txt  Linux desktop build

╔══════════════════════════════════════════════════════════════╗
║  RELEASE — built installers and portable archives            ║
╚══════════════════════════════════════════════════════════════╝
release/
  AlloLabs-Setup-1.4.0.exe      Windows one-click installer
  AlloLabs-v1.4.0-Windows-x64.zip  Windows portable (extract and run)
  SHA256SUMS.txt                 Checksums for all release artifacts
  README-v1.4.0.txt              Release notes in plain text

╔══════════════════════════════════════════════════════════════╗
║  RESOURCES & EXAMPLES                                        ║
╚══════════════════════════════════════════════════════════════╝
resources/
  allolabs-logo.png          Application logo (PNG and ICO)
  company-logos/             Locally cached per-ticker logos and manifest.json
examples/
  default-run.json           Bundled example run (shown before first real run)
  default-portfolio-report.pdf  Example PDF report
  default-performance.png    Example OOS performance chart
  terminal-*.txt             Annotated example terminal transcripts

╔══════════════════════════════════════════════════════════════╗
║  CI/CD                                                       ║
╚══════════════════════════════════════════════════════════════╝
.github/workflows/
  ci.yml                     Syntax, import, and unit-test checks
  desktop-release.yml        Windows PyInstaller + Inno Setup release
  portable-unix-release.yml  macOS and Linux portable build and archive
tests/
  test_release.py            Comprehensive integration and contract tests
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
run-history/
  YYYY-MM-DD/
    YYYY-MM-DD_HHMMSS_universe_model/
      manifest.json
      run-results.json
      run-config.json
      run-config.csv
      all-tickers.csv
      ai-opinions.csv
      ai-opinions.json
      portfolio-report.pdf
      performance-chart.png
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

Leveraging support from:
OpenAI Codex
Anthropic Claude Code
