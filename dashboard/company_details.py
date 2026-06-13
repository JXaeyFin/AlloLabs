"""Fetch one validated company snapshot using the analysis environment."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wealthgpt_company import fetch_ticker_context


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: company_details.py TICKER")
    print(json.dumps(fetch_ticker_context(sys.argv[1], max_news=5)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
