"""Execute AlloLabs with validated configuration supplied by the local runner."""

from __future__ import annotations

import csv
import json
import os
import re
import runpy
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

try:
    from dashboard.universe import CANADA_RESEARCH_TICKERS, CURATED_RESEARCH_TICKERS
except ModuleNotFoundError:  # Direct execution: python dashboard/runner.py
    from universe import CANADA_RESEARCH_TICKERS, CURATED_RESEARCH_TICKERS

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
    "MCE": ("Bolsa de Madrid", "Spain", "🇪🇸"),
    "CPH": ("Nasdaq Copenhagen", "Denmark", "🇩🇰"),
    "BRU": ("Euronext Brussels", "Belgium", "🇧🇪"),
    "EBS": ("SIX Swiss Exchange", "Switzerland", "🇨🇭"),
    "SWX": ("SIX Swiss Exchange", "Switzerland", "🇨🇭"),
}


def fallback_listing(ticker: str) -> dict:
    suffixes = (
        (".TO", "TOR"), (".L", "LSE"), (".PA", "PAR"), (".DE", "GER"),
        (".AS", "AMS"), (".MI", "MIL"), (".MC", "MCE"), (".CO", "CPH"),
        (".BR", "BRU"), (".SW", "EBS"),
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
    max_sector = int(config["maxSectorPercent"]) / 100
    gpt_views = bool(config["gptViews"])
    audit_views = bool(config["auditViews"])
    refresh_cache = bool(config["refreshCache"])

    selected_tickers = config.get("selectedTickers")
    if selected_tickers is None:
        legacy_universe = config.get("universe")
        if legacy_universe == "curated":
            selected_tickers = CURATED_RESEARCH_TICKERS
        elif legacy_universe == "canada":
            selected_tickers = CANADA_RESEARCH_TICKERS
        elif legacy_universe == "full":
            selected_tickers = None
        else:
            raise ValueError("Unsupported research universe.")
    selected_tickers = list(selected_tickers) if selected_tickers is not None else None

    return {
        "ALLOLABS_TRAINING_YEARS": str(training_years),
        "ALLOLABS_OOS_YEARS": str(oos_years),
        "ALLOLABS_MAX_POSITION_WEIGHT": str(max_position),
        "ALLOLABS_LONG_ONLY": "1" if config["longOnly"] else "0",
        "ALLOLABS_MAX_SECTOR_WEIGHT": str(max_sector),
        "ALLOLABS_REGULARIZATION": str(config["regularization"]),
        "ALLOLABS_REGULARIZATION_STRENGTH": str(config["regularizationStrength"]),
        "ALLOLABS_GPT_VIEWS": "1" if gpt_views else "0",
        "ALLOLABS_RESEARCH_PROVIDER": str(config["researchProvider"]),
        "ALLOLABS_RESEARCH_MODEL": str(config["researchModel"]),
        "ALLOLABS_GPT_AUDIT": "1" if audit_views else "0",
        "ALLOLABS_AUDIT_PROVIDER": str(config["auditProvider"]),
        "ALLOLABS_GPT_AUDIT_MODEL": str(config["auditModel"]),
        "ALLOLABS_REFRESH_CACHE": "1" if refresh_cache else "0",
        "ALLOLABS_ASSET_UNIVERSE_TICKERS": json.dumps(selected_tickers),
        "ALLOLABS_RESEARCH_TICKERS": json.dumps(selected_tickers),
        "ALLOLABS_ANALYST_SEED_PROMPT": str(config.get("analystSeedPrompt", "")),
        "ALLOLABS_AUDITOR_SEED_PROMPT": str(config.get("auditorSeedPrompt", "")),
        "ALLOLABS_MAX_NEWS_ARTICLES": str(int(config.get("maxNewsArticles", 5))),
        "ALLOLABS_RESEARCH_BATCH_SIZE": str(int(config.get("researchBatchSize", 12))),
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
        sector_totals[sector] = sector_totals.get(sector, 0.0) + abs(weight)
        if abs(weight) > 1e-7:
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
    holdings.sort(key=lambda item: abs(item["weight"]), reverse=True)
    gross_exposure = sum(sector_totals.values())
    sectors_payload = [
        {"sector": sector, "weight": weight / gross_exposure}
        for sector, weight in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
        if weight > 1e-7 and gross_exposure > 0
    ]
    return {"holdings": holdings, "sectors": sectors_payload}


def safe_archive_name(value: object, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned[:40] or fallback


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            })


def archive_completed_run(
    result: dict,
    namespace: dict,
    data_dir: Path,
    tickers: list[str],
    max_weights,
    min_weights,
    sectors: dict,
    analysis: dict,
    listing_metadata: dict,
) -> dict:
    generated_at = datetime.fromisoformat(result["generatedAt"])
    date_name = generated_at.strftime("%Y-%m-%d")
    time_name = generated_at.strftime("%Y-%m-%d_%H%M%S")
    config = result["config"]
    universe = safe_archive_name(config.get("universe"), "universe")
    model = safe_archive_name(config.get("researchModel"), "no-ai") if config.get("gptViews") else "no-ai"
    date_dir = data_dir / "run-history" / date_name
    date_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{time_name}_{universe}_{model}"
    run_name = base_name
    suffix = 2
    while (date_dir / run_name).exists():
        run_name = f"{base_name}-{suffix:02d}"
        suffix += 1
    archive_dir = date_dir / run_name
    archive_dir.mkdir()
    history_id = f"{date_name}/{run_name}"

    allocation_rows = []
    for ticker, max_weight, min_weight in zip(tickers, max_weights, min_weights):
        item = analysis.get(ticker, {}) if isinstance(analysis.get(ticker), dict) else {}
        listing = listing_metadata.get(ticker, fallback_listing(ticker))
        allocation_rows.append({
            "ticker": ticker,
            "sector": sectors.get(ticker, "Unclassified"),
            "industry": item.get("industry") or "Not classified",
            "max_sharpe_weight": float(max_weight),
            "min_volatility_weight": float(min_weight),
            "posterior_return": item.get("posterior_return"),
            "confidence": item.get("confidence"),
            "ai_view": item.get("view") or "",
            "exchange": listing.get("exchange"),
            "exchange_code": listing.get("exchangeCode"),
            "country": listing.get("country"),
            "currency": listing.get("currency"),
        })
    write_csv(
        archive_dir / "all-tickers.csv",
        [
            "ticker", "sector", "industry", "max_sharpe_weight", "min_volatility_weight",
            "posterior_return", "confidence", "ai_view", "exchange", "exchange_code",
            "country", "currency",
        ],
        allocation_rows,
    )

    opinion_rows = [row for row in allocation_rows if row["ai_view"]]
    write_csv(
        archive_dir / "ai-opinions.csv",
        [
            "ticker", "sector", "industry", "posterior_return", "confidence", "ai_view",
            "exchange", "country", "currency",
        ],
        opinion_rows,
    )
    config_rows = [{"setting": key, "value": value} for key, value in sorted(config.items())]
    write_csv(archive_dir / "run-config.csv", ["setting", "value"], config_rows)
    (archive_dir / "run-config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    archived_artifacts = {
        "results": "run-results.json",
        "configJson": "run-config.json",
        "configCsv": "run-config.csv",
        "allTickersCsv": "all-tickers.csv",
        "aiOpinionsCsv": "ai-opinions.csv",
        "aiOpinionsJson": "ai-opinions.json",
    }
    (archive_dir / "ai-opinions.json").write_text(
        json.dumps(analysis, indent=2, default=json_value, ensure_ascii=False), encoding="utf-8"
    )
    copy_candidates = {
        "pdf": (Path(namespace["PORTFOLIO_REPORT_PATH"]), "portfolio-report.pdf"),
    }
    if result.get("performance"):
        copy_candidates["chart"] = (
            data_dir / "portfolio_vs_markets_oos.png",
            "performance-chart.png",
        )
    for key, (source, filename) in copy_candidates.items():
        if source.is_file():
            shutil.copy2(source, archive_dir / filename)
            archived_artifacts[key] = filename

    result["archive"] = {
        "id": history_id,
        "folder": str(archive_dir),
        "artifacts": archived_artifacts,
    }
    (archive_dir / "run-results.json").write_text(
        json.dumps(result, indent=2, default=json_value, ensure_ascii=False), encoding="utf-8"
    )
    manifest = {
        "id": history_id,
        "generatedAt": result["generatedAt"],
        "dataThrough": result.get("dataThrough"),
        "universe": config.get("universe"),
        "researchProvider": config.get("researchProvider"),
        "researchModel": config.get("researchModel"),
        "auditEnabled": bool(config.get("auditViews")),
        "auditProvider": config.get("auditProvider"),
        "auditModel": config.get("auditModel"),
        "tickerCount": len(tickers),
        "opinionCount": len(opinion_rows),
        "metrics": result["metrics"],
        "periods": result["periods"],
        "artifacts": archived_artifacts,
    }
    (archive_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=json_value, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[runner] Run archive saved -> {archive_dir}", flush=True)
    return result["archive"]


def write_latest_run(namespace: dict, config: dict, script_path: Path) -> Path:
    data_dir = Path(namespace.get("DATA_DIR", script_path.parent)).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = Path(namespace["BL_CACHE_PATH"])
    try:
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        analysis = {}

    report_module = sys.modules.get("allolabs_report")
    sectors = dict(getattr(report_module, "LAST_SECTORS", {}))
    tickers = list(namespace["tickers"])
    ticker_set = set(tickers)
    analysis = {
        ticker: item
        for ticker, item in analysis.items()
        if ticker in ticker_set
    }
    max_weights = namespace["w_sharpe"]
    min_weights = namespace["w_vol"]
    listing_cache_path = data_dir / "listing_metadata_cache.json"
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
        "metricsMode": (
            "oos" if namespace.get("oos_ret_sharpe") is not None
            else "ai" if config.get("gptViews")
            else "historical"
        ),
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
        "oosMetrics": {
            "max": {
                "return": float(namespace["oos_ret_sharpe"]),
                "risk": float(namespace["oos_vol_sharpe"]),
                "sharpe": float(namespace.get("oos_sr_sharpe", 0.0)),
            },
            "min": {
                "return": float(namespace["oos_ret_vol"]),
                "risk": float(namespace["oos_vol_vol"]),
                "sharpe": float(namespace.get("oos_sr_vol", 0.0)),
            },
        } if namespace.get("oos_ret_sharpe") is not None else None,
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
        "researchAudit": namespace.get("gpt_audit_status", {}),
        "performance": performance,
        "artifacts": {
            "pdf": str(namespace["PORTFOLIO_REPORT_PATH"]),
            "allocations": str(data_dir / "portfolio_allocations.csv"),
            "sectorCache": str(data_dir / "sector_cache.json"),
            "listingCache": str(listing_cache_path),
            "auditedViews": str(namespace.get("GPT_AUDITED_VIEWS_PATH", "")),
        },
    }
    archive_completed_run(
        result,
        namespace,
        data_dir,
        tickers,
        max_weights,
        min_weights,
        sectors,
        analysis,
        listing_metadata,
    )
    output_path = data_dir / "latest_run.json"
    temporary = output_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, default=json_value), encoding="utf-8")
    temporary.replace(output_path)
    print(f"[runner] Live dashboard results saved -> {output_path}", flush=True)
    return output_path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: runner.py PATH_TO_ALLOLABS CONFIG_JSON")

    script_path = Path(sys.argv[1]).resolve()
    config = json.loads(sys.argv[2])
    if not script_path.is_file():
        raise FileNotFoundError(f"AlloLabs script not found: {script_path}")
    os.environ.update(configuration_environment(config))

    sys.path.insert(0, str(script_path.parent))
    print("[runner] Configuration validated. Starting AlloLabs.", flush=True)
    namespace = runpy.run_path(str(script_path), run_name="__main__")
    write_latest_run(namespace, config, script_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
