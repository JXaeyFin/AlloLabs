# AlloLabs v1.4.1 (unreleased)

## Modular portfolio optimizer

- Rebuilt portfolio construction as a modular optimizer layer
  (`allolabs_optimizer.py`) with five selectable targets: Max Sharpe Ratio,
  Min Volatility, Max Return, Risk Parity, and Max Diversification. A run
  computes exactly the targets the user selects; the classic
  Max Sharpe + Min Volatility pair remains the default.
- Added solver backends: CVXPY (OSQP, ECOS, SCS) for convex formulations and
  SciPy (SLSQP, trust-constr) for nonlinear ones, with an `auto` mode that
  picks per target, convexity, and universe size. Unregularized Max Sharpe and
  Max Diversification now use an exact convex fractional-programming
  reformulation.
- Fixed the known large-universe failure where SLSQP aborted with
  `Positive directional derivative for linesearch` on ~947-asset Max Sharpe
  runs. Auto mode routes large Max Sharpe to the convex reformulation (or
  trust-constr when regularization keeps it nonlinear); SLSQP remains the
  default only below 250 assets and can still be requested explicitly.
- Added Console controls for optimization target and solver mode, with full
  server allowlist validation, runner environment mapping
  (`ALLOLABS_OPTIMIZATION_TARGETS`, `ALLOLABS_SOLVER_MODE`), and archived
  run-config round-tripping. Existing configurations without the new fields
  behave exactly as before.
- Injected the selected optimization target, solver mode, and implied risk
  posture into analyst research prompts, global audit prompts, and the Allo
  guide's app-state snapshot, so AI reviews are calibrated to the portfolio
  construction objective.
- Generalized the console report, out-of-sample analysis, Jobson-Korkie
  significance testing, performance chart, run archive, and dashboard results
  to any computed target set. The PDF memorandum still requires the classic
  pair (documented limitation); other target sets skip it with a console note.
- CVXPY ships in `requirements.txt` but remains optional at runtime: without
  it, every target still solves through SciPy with unchanged mathematical
  meaning, and explicit `cvxpy-*` solver requests fail with a clear message.

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
- Added Guide mode infrastructure: a persistent mode toggle, bottom-right mode
  indicator updates, draggable follow-me Allo dock, and UI highlight hooks for
  guided tours across tabs.
- Added Guide mode tab steering so Allo can switch to a relevant tab before
  highlighting controls, such as Console regularization settings.
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
- Added a `Known Issues` note for large-universe Max Sharpe SLSQP line-search
  failures.
- Expanded the release suite to 70 tests, including authenticated Guide endpoint
  tests, catalog coverage, DeepSeek request construction, provider masking, and
  modular optimizer routing, solver fallback, and configuration wiring.

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

- `python -m unittest discover -s tests -v`: 70 tests run; all passed in the
  reviewed source checkout.
- Python compilation checks pass for the pipeline, guide, relay, runner, and
  test suite.
- `node --check dashboard/app.js` passes.

No API credentials or generated private research data are included. AlloLabs
remains research software, not financial advice or an automated trading system.
