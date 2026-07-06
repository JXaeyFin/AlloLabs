# AlloLabs Dashboard (Embedded UI Layer)

The `dashboard/` directory is the **embedded interface layer** that runs inside
the desktop application's WebView window. It is not a standalone web app; the
`desktop/app.py` wrapper starts the local HTTP relay on a random port, injects
a one-time access token, and opens it in a native window.

## How It Fits Together

```
desktop/app.py          Opens the native window (PyWebView / Edge WebView2)
  └─ dashboard/server.py   Starts the local HTTP relay (127.0.0.1, random port)
       └─ dashboard/runner.py   Launches allolabs.py as a subprocess
  └─ dashboard/index.html  Served to the WebView as the application UI
       ├─ app.js            Client-side logic and API calls
       ├─ styles.css        Structural layout skeleton
       └─ terminal-theme.css  Visual theme and animations
```

## Contents

| File | Role |
|------|------|
| `server.py` | Authenticated local HTTP relay; handles API requests, static files, run history, and `/api/guide` proxy |
| `runner.py` | Translates dashboard config to environment variables, launches the pipeline |
| `universe.py` | Shared ticker catalog: presets, market groups, and universe loading |
| `company_details.py` | Subprocess helper — fetches one ticker's context and prints JSON |
| `index.html` | Application UI — 7 tabs including Guide Mode |
| `app.js` | All client-side logic, API polling, chart rendering |
| `styles.css` | Structural layout (flex, grid, panel geometry) |
| `terminal-theme.css` | Color theme, animations, splash screen |

## Capabilities

- **Guide Mode (F7)** — Allo AI assistant for finance Q&A, run configuration, thesis drafting, and portfolio explanation. Backend proxy keeps all API keys server-side; the browser never sees them.
- Dedicated Universe tab with quick presets, whole-market selection, and individual ticker checkboxes
- Tiered ticker search: exact → prefix → contains → fuzzy/subsequence
- Separate OpenAI, Anthropic Claude, Google Gemini, or DeepSeek selection for research and audit stages
- Compact Model Guide with context limits, output limits, and practical trade-off notes
- Background model execution with live terminal relay
- Dynamic overview metric cards (Historical / AI views / OOS mode)
- Portfolio holdings with sector exposure, rationale, and AI confidence
- Optional global AI audit of the complete research set
- Embedded PDF report viewer and OOS performance chart
- Local run history browser
- Bundled example run shown before the first real execution

## Advanced: Developer / Remote Access

The relay can also be started standalone for development or diagnostics:

```bash
python dashboard/server.py
```

This opens the same interface in a browser at `http://127.0.0.1:8765`. For
production use, always run through `desktop/app.py` (or `start-allolabs-desktop.bat`).

For remote access with authentication:

```powershell
$env:ALLOLABS_REMOTE_TOKEN="replace-with-a-long-random-value"
python dashboard/server.py --host 0.0.0.0
```

Use a trusted HTTPS reverse proxy and firewall for any non-local deployment.

## Notes

- Listing metadata is cached for 30 days in `listing_metadata_cache.json` (written to the data directory).
- Sector classifications use known mappings, research metadata, a local cache, and Yahoo Finance.
- When `latest_run.json` does not exist, the app serves `examples/default-run.json` and its bundled report/chart.
