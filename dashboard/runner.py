"""Execute WealthGPT with validated configuration supplied by the local runner."""

from __future__ import annotations

import json
import os
import runpy
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path


CURATED_RESEARCH_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "LLY",
    "JPM", "XOM", "COST", "ISRG", "RY.TO", "TD.TO", "ENB.TO", "CNQ.TO",
    "BAM.TO", "MFC.TO", "FTS.TO", "CNR.TO", "CP.TO", "SHOP.TO", "CSU.TO",
    "AEM.TO", "NTR.TO", "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L", "LSEG.L",
    "ASML.AS", "SAP.DE", "SIE.DE", "MC.PA", "BNP.PA", "NESN.SW",
    "NOVN.SW", "ROG.SW", "UBSG.SW",
]

CANADA_RESEARCH_TICKERS = [
    "RY.TO", "TD.TO", "BMO.TO", "BNS.TO", "NA.TO", "CM.TO", "ENB.TO",
    "TRP.TO", "SU.TO", "CNQ.TO", "BAM.TO", "MFC.TO", "FTS.TO", "CNR.TO",
    "CP.TO", "SHOP.TO", "CSU.TO", "WCN.TO", "AEM.TO", "NTR.TO",
]

LISTING_CACHE_MAX_AGE_DAYS = 30
EXCHANGE_DETAILS = {
    "TOR": ("Toronto Stock Exchange (TSX)", "Canada", "🇨🇦"),
    "VAN": ("TSX Venture Exchange", "Canada", "🇨🇦"),
    "NMS": ("Nasdaq Global Select Market", "United States", "🇺🇸"),
    "NGM": ("Nasdaq Global Market", "United States", "🇺🇸"),
    "NCM": ("Nasdaq Capital Market", "United States", "🇺🇸"),
    "NYQ": ("New York Stock Exchange (NYSE)", "United States", "🇺🇸"),
    "ASE": ("NYSE American", "United States", "🇺🇸"),
    "LSE": ("London Stock Exchange (LSE)", "United Kingdom", "🇬🇧"),
    "PAR": ("Euronext Paris", "France", "🇫🇷"),
    "GER": ("Xetra / Frankfurt", "Germany", "🇩🇪"),
    "FRA": ("Frankfurt Stock Exchange", "Germany", "🇩🇪"),
    "AMS": ("Euronext Amsterdam", "Netherlands", "🇳🇱"),
    "MIL": ("Borsa Italiana", "Italy", "🇮🇹"),
    "BRU": ("Euronext Brussels", "Belgium", "🇧🇪"),
    "EBS": ("SIX Swiss Exchange", "Switzerland", "🇨🇭"),
    "SWX": ("SIX Swiss Exchange", "Switzerland", "🇨🇭"),
}


def fallback_listing(ticker: str) -> dict:
    suffixes = (
        (".TO", "TOR"), (".L", "LSE"), (".PA", "PAR"), (".DE", "GER"),
        (".AS", "AMS"), (".MI", "MIL"), (".BR", "BRU"), (".SW", "EBS"),
    )
    exchange_code = next((code for suffix, code in suffixes if ticker.upper().endswith(suffix)), "NMS")
    exchange_name, country, flag = EXCHANGE_DETAILS[exchange_code]
    return {
        "exchangeCode": exchange_code,
        "exchange": exchange_name,
        "country": country,
        "flag": flag,
        "currency": None,
        "quoteType": "EQUITY",
        "shortName": ticker,
        "source": "Ticker suffix fallback",
        "fetchedAt": None,
    }


def normalize_listing(ticker: str, info: dict) -> dict:
    fallback = fallback_listing(ticker)
    exchange_code = str(info.get("exchange") or fallback["exchangeCode"]).upper()
    known_exchange = EXCHANGE_DETAILS.get(exchange_code)
    exchange_name = (
        info.get("fullExchangeName")
        or info.get("exchangeName")
        or (known_exchange[0] if known_exchange else None)
        or fallback["exchange"]
    )
    country = info.get("country") or (known_exchange[1] if known_exchange else None) or fallback["country"]
    flag = known_exchange[2] if known_exchange else fallback["flag"]
    return {
        "exchangeCode": exchange_code,
        "exchange": str(exchange_name),
        "country": str(country),
        "flag": flag,
        "currency": info.get("currency"),
        "quoteType": info.get("quoteType") or "EQUITY",
        "shortName": info.get("shortName") or info.get("longName") or ticker,
        "market": info.get("market"),
        "timeZone": info.get("timeZoneFullName") or info.get("exchangeTimezoneName"),
        "source": "Yahoo Finance",
        "fetchedAt": datetime.now().astimezone().isoformat(),
    }


def load_listing_cache(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def cache_entry_fresh(entry: dict) -> bool:
    try:
        fetched = datetime.fromisoformat(entry["fetchedAt"])
        age = datetime.now().astimezone() - fetched.astimezone()
        return age.days < LISTING_CACHE_MAX_AGE_DAYS
    except (KeyError, TypeError, ValueError):
        return False


def fetch_listing(ticker: str) -> tuple[str, dict]:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).get_info() or {}
        return ticker, normalize_listing(ticker, info)
    except Exception as exc:
        listing = fallback_listing(ticker)
        listing["error"] = str(exc)
        listing["fetchedAt"] = datetime.now().astimezone().isoformat()
        return ticker, listing


def resolve_listing_metadata(tickers, cache_path: Path) -> dict[str, dict]:
    cache = load_listing_cache(cache_path)
    resolved: dict[str, dict] = {}
    missing: list[str] = []
    for ticker in sorted(set(tickers)):
        cached = cache.get(ticker)
        if isinstance(cached, dict) and cache_entry_fresh(cached):
            resolved[ticker] = cached
        else:
            missing.append(ticker)

    if missing:
        print(f"[runner] Fetching Yahoo listing metadata for {len(missing)} research tickers...", flush=True)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(fetch_listing, ticker) for ticker in missing]
            for future in as_completed(futures):
                ticker, listing = future.result()
                resolved[ticker] = listing

    cache_path.write_text(
        json.dumps({ticker: resolved[ticker] for ticker in sorted(resolved)}, indent=2),
        encoding="utf-8",
    )
    return resolved


def configuration_environment(config: dict) -> dict[str, str]:
    training_years = float(config["trainingYears"])
    oos_years = int(config["oosMonths"]) / 12
    max_position = int(config["maxPositionPercent"]) / 100
    gpt_views = bool(config["gptViews"])
    refresh_cache = bool(config["refreshCache"])

    universe = config["universe"]
    if universe == "curated":
        subset = CURATED_RESEARCH_TICKERS
    elif universe == "canada":
        subset = CANADA_RESEARCH_TICKERS
    elif universe == "full":
        subset = None
    else:
        raise ValueError("Unsupported research universe.")

    return {
        "WEALTHGPT_TRAINING_YEARS": str(training_years),
        "WEALTHGPT_OOS_YEARS": str(oos_years),
        "WEALTHGPT_MAX_POSITION_WEIGHT": str(max_position),
        "WEALTHGPT_GPT_VIEWS": "1" if gpt_views else "0",
        "WEALTHGPT_REFRESH_CACHE": "1" if refresh_cache else "0",
        "WEALTHGPT_RESEARCH_TICKERS": json.dumps(subset),
    }


def json_value(value):
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def portfolio_payload(tickers, weights, sectors, analysis):
    holdings = []
    sector_totals: dict[str, float] = {}
    for ticker, raw_weight in zip(tickers, weights):
        weight = float(raw_weight)
        sector = sectors.get(ticker, "Unclassified")
        sector_totals[sector] = sector_totals.get(sector, 0.0) + weight
        if weight > 1e-7:
            item = analysis.get(ticker, {})
            holdings.append(
                {
                    "ticker": ticker,
                    "weight": weight,
                    "sector": sector,
                    "industry": item.get("industry") or "Not classified",
                    "posteriorReturn": item.get("posterior_return"),
                    "confidence": item.get("confidence"),
                    "view": item.get("view"),
                }
            )
    holdings.sort(key=lambda item: item["weight"], reverse=True)
    sectors_payload = [
        {"sector": sector, "weight": weight}
        for sector, weight in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
        if weight > 1e-7
    ]
    return {"holdings": holdings, "sectors": sectors_payload}


def write_latest_run(namespace: dict, config: dict, script_path: Path) -> Path:
    analysis_path = Path(namespace["BL_CACHE_PATH"])
    try:
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        analysis = {}

    report_module = sys.modules.get("wealthgpt_report")
    sectors = dict(getattr(report_module, "LAST_SECTORS", {}))
    tickers = list(namespace["tickers"])
    max_weights = namespace["w_sharpe"]
    min_weights = namespace["w_vol"]
    listing_cache_path = script_path.parent / "listing_metadata_cache.json"
    listing_metadata = resolve_listing_metadata(analysis.keys(), listing_cache_path)

    cum_ret = namespace.get("cum_ret")
    performance = None
    if cum_ret is not None and not cum_ret.empty:
        performance = {
            "dates": [index.isoformat() for index in cum_ret.index],
            "series": {
                column: [float(value) for value in cum_ret[column].values]
                for column in cum_ret.columns
            },
        }

    result = {
        "generatedAt": datetime.now().astimezone().isoformat(),
        "dataThrough": json_value(namespace.get("oos_end") or namespace["training_end"]),
        "config": config,
        "periods": {
            "trainingStart": json_value(namespace["training_start"]),
            "trainingEnd": json_value(namespace["training_end"]),
            "oosStart": json_value(namespace.get("oos_start")),
            "oosEnd": json_value(namespace.get("oos_end")),
        },
        "metrics": {
            "max": {
                "return": float(namespace["opt_ret_S"]),
                "risk": float(namespace["opt_risk_S"]),
                "sharpe": float(namespace["opt_sr_S"]),
            },
            "min": {
                "return": float(namespace["opt_ret_V"]),
                "risk": float(namespace["opt_risk_V"]),
                "sharpe": float(namespace["opt_sr_V"]),
            },
        },
        "portfolios": {
            "max": portfolio_payload(tickers, max_weights, sectors, analysis),
            "min": portfolio_payload(tickers, min_weights, sectors, analysis),
        },
        "research": [
            {
                "ticker": ticker,
                "industry": item.get("industry") or "Not classified",
                "sector": sectors.get(ticker, "Unclassified"),
                "posteriorReturn": item.get("posterior_return"),
                "confidence": item.get("confidence"),
                "view": item.get("view"),
                "listing": listing_metadata.get(ticker, fallback_listing(ticker)),
            }
            for ticker, item in sorted(analysis.items())
            if isinstance(item, dict)
        ],
        "performance": performance,
        "artifacts": {
            "pdf": str(namespace["PORTFOLIO_REPORT_PATH"]),
            "allocations": str(script_path.parent / "portfolio_allocations.csv"),
            "sectorCache": str(script_path.parent / "sector_cache.json"),
            "listingCache": str(listing_cache_path),
        },
    }
    output_path = script_path.parent / "latest_run.json"
    temporary = output_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, default=json_value), encoding="utf-8")
    temporary.replace(output_path)
    print(f"[runner] Live dashboard results saved -> {output_path}", flush=True)
    return output_path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: runner.py PATH_TO_WEALTHGPT CONFIG_JSON")

    script_path = Path(sys.argv[1]).resolve()
    config = json.loads(sys.argv[2])
    if not script_path.is_file():
        raise FileNotFoundError(f"WealthGPT script not found: {script_path}")
    os.environ.update(configuration_environment(config))

    sys.path.insert(0, str(script_path.parent))
    print("[runner] Configuration validated. Starting WealthGPT.", flush=True)
    namespace = runpy.run_path(str(script_path), run_name="__main__")
    write_latest_run(namespace, config, script_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
