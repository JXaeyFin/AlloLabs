# WealthGPT v1.2

WealthGPT v1.2 introduces a Bloomberg-terminal-inspired web interface for
configuring, running, and reviewing the portfolio research pipeline.

## Highlights

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
