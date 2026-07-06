# AlloLabs v1.4.0

Released July 5, 2026.

AlloLabs v1.4 is the largest update since the public v1.3.2 source baseline. It
adds an integrated AI guide, expands the selectable global equity catalog,
introduces DeepSeek throughout the research stack, strengthens
thesis-alignment behavior, and makes the desktop workflow more resilient.

## Highlights

### Allo Guide

- Added a dedicated Guide tab (F7) for portfolio theory questions, investment
  mandate drafting, ticker-universe design, run diagnostics, configuration, and
  portfolio explanations.
- Added server-side guide calls for Anthropic, OpenAI, Google Gemini, DeepSeek,
  and Nvidia NIM. API credentials remain outside the browser.
- Injects the current universe, Console settings, latest portfolio results, and
  run status into each guide turn.
- Grounds ticker suggestions in the complete supported catalog and rejects
  out-of-catalog invention through explicit prompt and server context.
- Supports inline run-configuration cards, one-click loading into Console,
  automatic conversation compaction, retained session summaries, retries, and
  human-readable provider errors.

### Research providers and thesis alignment

- Added DeepSeek Chat and DeepSeek Reasoner to research and audit selection,
  server allowlists, key detection, documentation, and the model reference.
- Added DeepSeek JSON-mode request handling with provider-specific output-token
  limits and response validation.
- Split global audits into bounded batches with shared portfolio-wide
  calibration statistics, exact schema item counts, semantic retry, and final
  merged-universe validation.
- Reframed analyst and auditor seed prompts as investment mandates, strengthened
  mandate-alignment instructions, and included mandate hashes in cache
  invalidation.
- Added configurable research batch size and per-ticker news depth.
- Updated the selectable OpenAI, Anthropic, and Gemini model catalogs.

### Universe and market data

- Expanded the working catalog to 947 unique securities across U.S. large-cap,
  U.S. growth, Canada, London, Europe, and global ADR groups.
- Added market-level selection, catalog presets, tiered company/ticker search,
  and persistent custom universes.
- Added a generated catalog metadata file and repeatable yfinance metadata
  sweep script.
- Parallelized market-cap lookups, quieted noisy yfinance retry logging, added
  retry backoff, and allowed runs to continue when isolated symbols lack usable
  price history.

### Dashboard and reports

- Added dynamic Historical, AI Views, and OOS overview metrics.
- Added market and currency allocation donuts, interactive chart tooltips,
  stronger run-progress feedback, and local run-history browsing.
- Added clickable company/research details with fundamentals, news, and locally
  bundled company logos.
- Added automatic persistence for Console and Guide settings.
- Refreshed navigation, responsive Guide layouts, startup/logo animation, and
  terminal styling.
- Expanded the PDF and memo reporting paths with allocation exhibits,
  sensitivity analysis, and safer handling of missing research metadata.

### Desktop, packaging, and reliability

- Consolidated supported use around the native desktop application and removed
  deprecated dashboard launcher scripts.
- Renamed the Windows desktop dependency file to
  `requirements-desktop-win.txt` and updated build automation accordingly.
- Improved subprocess startup failure handling, hidden Windows process launch,
  worker error reporting, shutdown/reaping, and top-level HTTP error responses.
- Updated Windows, macOS, and Linux package metadata and artifact names to
  v1.4.0.
- Expanded the release suite to 45 tests, including authenticated Guide endpoint
  tests, catalog coverage, DeepSeek request construction, provider masking, and
  configuration wiring.

## Upgrade notes

- Existing data under the AlloLabs user-data directory remains compatible.
- DeepSeek requires `DEEPSEEK_API_KEY`. Nvidia NIM guide use requires
  `NVIDIA_NIM_API_KEY`.
- Source-build users on Windows should install
  `requirements-desktop-win.txt`; the former `requirements-desktop.txt` name is
  retired.
- The removed `start-dashboard*` and `restart-dashboard*` scripts are no longer
  supported. Launch `start-allolabs-desktop.bat` or run `pythonw -m desktop.app`.

## Validation

- `python -m unittest discover -s tests -v`: 45 passed, 6 dependency-based
  report tests skipped when scientific reporting packages are unavailable.
- Python compilation checks pass for the pipeline, guide, relay, runner, and
  test suite.
- `node --check dashboard/app.js` passes.

No API credentials or generated private research data are included. AlloLabs
remains research software, not financial advice or an automated trading system.
