"""Fetch one validated company snapshot using the analysis environment."""

from __future__ import annotations

import json
import sys
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Path Setup
# Ensures the repository root is on sys.path when this script is launched as a
# subprocess (e.g. by dashboard/server.py or the bundled AlloLabsWorker).
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from allolabs_company import fetch_ticker_context


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: company_details.py TICKER")
    ticker = sys.argv[1].strip()
    if not ticker:
        print("A ticker symbol is required.", file=sys.stderr, flush=True)
        return 2
    # fetch_ticker_context already degrades gracefully on missing fields, but a
    # hard network failure can still raise.  Convert any such error into a
    # single readable stderr line (which the dashboard surfaces to the user)
    # and a non-zero exit code, rather than letting a raw traceback escape.
    try:
        payload = fetch_ticker_context(ticker, max_news=5)
    except Exception as exc:  # noqa: BLE001 - boundary: report cleanly, never crash
        print(
            f"Yahoo Finance lookup failed for {ticker.upper()}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    # ensure_ascii keeps stdout safe regardless of the console code page.
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
