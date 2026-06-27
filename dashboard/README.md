# AlloLabs Dashboard

The dashboard is a dependency-free HTML/CSS/JavaScript interface served by the
standard-library Python relay in `server.py`.

From the repository root:

```bash
python dashboard/server.py
```

Then open `http://127.0.0.1:8765`.

## Capabilities

- Dedicated Universe tab with quick presets, whole-market selection, and individual ticker checkboxes
- Tiered ticker search across the universe picker and the research view: exact match → prefix → contains → fuzzy/subsequence, sorted by relevance tier
- One validated ticker selection shared by market-data ingestion, AI research, and portfolio optimization
- One consolidated Run Console for all analysis and execution controls
- Configurable per-ticker news depth (1–20 articles) surfaced alongside fundamentals in every AI research prompt
- Selectable long-only or bounded long/short weights, validated absolute position/sector maximums, and optional L2/smooth-L1 regularization
- Separate OpenAI, Anthropic Claude, or Google Gemini provider/model selection for research generation and global audit
- Compact Model Guide with published context/output limits and practical strengths/trade-offs
- Background model execution with live terminal output
- Automatic overview refresh after a successful run with **dynamic metric cards** that display:
  - *Historical mode* — in-sample Max Sharpe and Min Vol optimizer estimates
  - *AI views mode* — Black-Litterman posterior expected returns with historical volatility estimates
  - *OOS mode* — realized out-of-sample return, volatility, and annualized Sharpe for the test window
- Portfolio holdings and sector exposure
- AI research views with Yahoo listing venue, country, currency, and flags
- Optional high-capacity global audit of the complete generated research set
- Embedded PDF report and OOS chart
- Bundled example portfolios and AI research before the first local run
- Optional bearer-token authentication for non-localhost binding

The relay can launch only the repository's AlloLabs runner. It does not expose
arbitrary command execution.

## Configuration

Use another model path or Python interpreter when needed:

```bash
python dashboard/server.py --script /path/to/allolabs.py \
  --analysis-python /path/to/python
```

For remote access:

```powershell
$env:ALLOLABS_REMOTE_TOKEN="replace-with-a-long-random-value"
python dashboard/server.py --host 0.0.0.0
```

Use a trusted HTTPS reverse proxy and firewall for any non-local deployment.

Listing metadata is cached for 30 days in `listing_metadata_cache.json`.
Sector classifications are resolved from known mappings, research metadata,
the local cache, and Yahoo Finance.

When `latest_run.json` does not exist, the dashboard serves
`examples/default-run.json` and its bundled report/chart. A completed local run
automatically takes precedence without modifying the example files.
