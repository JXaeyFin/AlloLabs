# AlloLabs v1.3.1

AlloLabs v1.3.1 extends the v1.3 desktop release with user-supplied AI context,
larger terminal-readable dashboard text, and a refreshed installer-ready build.

AlloLabs v1.3.0 completed the platform's rebrand, introduced a
Bloomberg-terminal-inspired web interface for
configuring, running, and reviewing the portfolio research pipeline, and
reworks the PDF report as an educational portfolio research monitor. It also
introduces a native Windows application shell and reproducible installer build.

## Highlights

- New analyst and auditor seed prompts let users inject their own thesis,
  hypotheses, risk preferences, and scenario assumptions into the AI research
  and audit stages while preserving evidence and calibration guardrails.
- Dashboard typography and control sizing were enlarged and balanced for a more
  readable terminal-style desktop experience.
- Complete product, module, launcher, environment-variable, report, and
  artifact rebrand to AlloLabs while retaining the established logo artwork.
- Unified Run Console with dynamic optimizer, training, out-of-sample, AI
  provider, model, regularization, position-cap, and sector-cap controls.
- Live terminal relay with configuration-aware progress estimation.
- Maximum-Sharpe and minimum-volatility portfolio dashboards with sector
  exposure, performance metrics, and clickable holding details.
- Company detail panels with fundamental ratios, linked news headlines, and
  285 locally bundled company logos.
- OpenAI, Anthropic Claude, and Google Gemini research support with an optional
  configurable global AI audit stage.
- Model guide with provider-key detection, model strengths, limitations, and
  published context-window information.
- Integrated PDF report viewer, performance chart, example results, and
  preloaded AI research views.
- Improved optimizer stability, long-only and bounded long/short handling,
  soft regularization, hard limits, metadata resolution, and report generation.
- Paginated allocation appendix with readable fixed row spacing and coverage
  down to 0.005% absolute portfolio weight.
- Refined holding-rationale pages with locally bundled rounded-square company
  marks and graceful fallback when a logo is unavailable.
- Native desktop window backed by the existing dashboard and local relay.
- Self-contained hidden analysis workers, random localhost ports, per-launch
  authentication, single-instance protection, and graceful shutdown.
- Writable reports, results, and caches under `%LOCALAPPDATA%\AlloLabs` in
  installed builds, keeping application assets read-only.
- PyInstaller one-directory packaging and an Inno Setup installer definition.
- Native macOS and Linux portable build pipelines with platform-specific
  webview dependencies, data directories, self-tests, and release archives.
- Rebuilt the PDF as a Bloomberg-terminal-style research monitor that leads
  with risk and construction, separates historical returns from equilibrium
  priors, AI views, and Black-Litterman inputs, flags unstable estimates, and
  explains model and implementation limitations without presenting optimized
  returns as promised outcomes.

## Distribution Notes

- No API credentials are included.
- Company logos are served locally; Logo.dev is not contacted during dashboard
  use.
- Generated live portfolios, research caches, reports, and local archives are
  excluded from the release.
- Sanitized examples remain bundled so the dashboard is populated before the
  first run.

## Requirements

- Python 3.11 or newer
- Dependencies listed in `requirements.txt`
- At least one supported AI-provider API key only when generating new AI views

This project is research software, not financial advice or an automated trading
system.
