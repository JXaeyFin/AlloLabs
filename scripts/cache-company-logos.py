"""Download the WealthGPT asset-universe logos into the repository."""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = REPOSITORY_ROOT / "wealthgpt.py"
OUTPUT_DIR = REPOSITORY_ROOT / "resources" / "company-logos"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache one Logo.dev PNG for every WealthGPT asset-universe ticker."
    )
    parser.add_argument("--refresh", action="store_true", help="Replace existing logo files.")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent requests (default: 6).")
    return parser.parse_args()


def load_asset_universe() -> list[str]:
    tree = ast.parse(UNIVERSE_PATH.read_text(encoding="utf-8"), filename=str(UNIVERSE_PATH))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if isinstance(target, ast.Name) and target.id == "ASSET_UNIVERSE":
            value = ast.literal_eval(node.value)
            if not isinstance(value, list) or not all(isinstance(ticker, str) for ticker in value):
                break
            normalized = [ticker.strip().upper() for ticker in value]
            if len(normalized) != len(set(normalized)):
                raise ValueError("ASSET_UNIVERSE contains duplicate tickers.")
            return normalized
    raise ValueError(f"Could not read ASSET_UNIVERSE from {UNIVERSE_PATH}.")


def logo_request_url(ticker: str, token: str, fallback: str) -> str:
    query = urlencode(
        {
            "token": token,
            "size": "128",
            "format": "png",
            "theme": "dark",
            "retina": "true",
            "fallback": fallback,
        }
    )
    return f"https://img.logo.dev/ticker/{quote(ticker, safe='')}?{query}"


def request_png(ticker: str, token: str, fallback: str) -> bytes:
    request = Request(
        logo_request_url(ticker, token, fallback),
        headers={"User-Agent": "WealthGPT-logo-cache/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        content_type = response.headers.get_content_type()
    if content_type != "image/png" or not body.startswith(PNG_SIGNATURE):
        raise ValueError(f"Unexpected Logo.dev response for {ticker}: {content_type}")
    return body


def fetch_logo(ticker: str, token: str, refresh: bool) -> dict[str, object]:
    destination = OUTPUT_DIR / f"{ticker}.png"
    if destination.is_file() and not refresh:
        return {
            "ticker": ticker,
            "file": destination.name,
            "status": "existing",
            "bytes": destination.stat().st_size,
        }

    errors: list[str] = []
    for fallback, status in (("404", "company"), ("monogram", "monogram")):
        for attempt in range(3):
            try:
                body = request_png(ticker, token, fallback)
                temporary = destination.with_suffix(".png.tmp")
                temporary.write_bytes(body)
                temporary.replace(destination)
                return {
                    "ticker": ticker,
                    "file": destination.name,
                    "status": status,
                    "bytes": len(body),
                }
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                errors.append(f"{fallback} attempt {attempt + 1}: {exc}")
                if isinstance(exc, HTTPError) and exc.code == 404:
                    break
                time.sleep(0.4 * (attempt + 1))
    return {
        "ticker": ticker,
        "file": destination.name,
        "status": "failed",
        "error": errors[-1] if errors else "Unknown error",
    }


def main() -> int:
    arguments = parse_arguments()
    token = os.environ.get("LOGO_DEV_PUBLISHABLE_KEY", "").strip()
    if not token:
        print("LOGO_DEV_PUBLISHABLE_KEY is required.", file=sys.stderr)
        return 2
    if arguments.workers < 1 or arguments.workers > 16:
        print("--workers must be between 1 and 16.", file=sys.stderr)
        return 2

    tickers = load_asset_universe()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Caching {len(tickers)} WealthGPT company logos in {OUTPUT_DIR}...")

    records: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=arguments.workers) as executor:
        futures = {
            executor.submit(fetch_logo, ticker, token, arguments.refresh): ticker
            for ticker in tickers
        }
        for completed, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            record = future.result()
            records.append(record)
            print(
                f"[{completed:03d}/{len(tickers):03d}] "
                f"{record['ticker']}: {record['status']}"
            )

    records.sort(key=lambda record: str(record["ticker"]))
    counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        counts[status] = counts.get(status, 0) + 1
    manifest = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "Logo.dev ticker endpoint",
        "universeFile": UNIVERSE_PATH.name,
        "tickerCount": len(tickers),
        "counts": counts,
        "logos": records,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    failed = [record["ticker"] for record in records if record["status"] == "failed"]
    print(f"Manifest saved to {MANIFEST_PATH}")
    print("Coverage: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    if failed:
        print("Failed tickers: " + ", ".join(str(ticker) for ticker in failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
