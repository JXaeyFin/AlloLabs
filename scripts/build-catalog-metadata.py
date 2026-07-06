"""Build dashboard/catalog_metadata.json from the ticker catalog via yfinance.

For every ticker in dashboard/market_tickers.py, fetches company name, sector,
industry, country, and market cap, and writes a compact metadata map used by
the Allo guide's catalog search tool. Failures degrade to empty fields rather
than aborting; rerun any time the catalog changes.

Usage:  python scripts/build-catalog-metadata.py
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yfinance as yf

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "dashboard"))

from market_tickers import (  # noqa: E402
    CANADA_TSX_ALL,
    EUROPE_STOXX_ALL,
    GLOBAL_ADRS,
    UK_FTSE_ALL,
    US_NASDAQ_EXT,
    US_SP500,
)

OUTPUT_PATH = REPO / "dashboard" / "catalog_metadata.json"
MAX_WORKERS = 8


def cap_bucket(market_cap: float | None) -> str:
    if not market_cap or market_cap <= 0:
        return ""
    if market_cap >= 200e9:
        return "mega"
    if market_cap >= 10e9:
        return "large"
    if market_cap >= 2e9:
        return "mid"
    return "small"


def fetch_one(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).get_info() or {}
    except Exception:
        return {}
    cap = info.get("marketCap")
    return {
        "name": (info.get("longName") or info.get("shortName") or "").strip(),
        "sector": (info.get("sector") or "").strip(),
        "industry": (info.get("industry") or "").strip(),
        "country": (info.get("country") or "").strip(),
        "cap": cap_bucket(float(cap) if cap else None),
    }


def main() -> int:
    tickers = list(dict.fromkeys(
        US_SP500 + US_NASDAQ_EXT + CANADA_TSX_ALL
        + UK_FTSE_ALL + EUROPE_STOXX_ALL + GLOBAL_ADRS
    ))
    print(f"Fetching metadata for {len(tickers)} tickers...")

    metadata: dict[str, dict] = {}
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_one, t): t for t in tickers}
        for count, future in enumerate(as_completed(futures), 1):
            ticker = futures[future]
            record = future.result()
            if record.get("name"):
                metadata[ticker] = record
            else:
                failed.append(ticker)
            if count % 100 == 0:
                print(f"  {count}/{len(tickers)} done ({len(failed)} missing)")

    if failed:
        print(f"Retrying {len(failed)} missing tickers after backoff...")
        time.sleep(20)
        still_failed = []
        for ticker in failed:
            record = fetch_one(ticker)
            if record.get("name"):
                metadata[ticker] = record
            else:
                still_failed.append(ticker)
            time.sleep(0.4)
        failed = still_failed

    for ticker in failed:
        metadata[ticker] = {"name": "", "sector": "", "industry": "",
                            "country": "", "cap": ""}

    payload = {ticker: metadata[ticker] for ticker in tickers}
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    named = sum(1 for r in payload.values() if r["name"])
    print(f"Wrote {OUTPUT_PATH} — {named}/{len(payload)} with full metadata; "
          f"{len(failed)} unresolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
