"""Shared universe catalog and preset helpers for the dashboard runner."""

from __future__ import annotations

from pathlib import Path

try:
    from dashboard.market_tickers import (
        CANADA_RESEARCH_TICKERS,
        CANADA_TSX_ALL,
        CURATED_RESEARCH_TICKERS,
        EUROPE_STOXX_ALL,
        EUROSTOXX50,
        FTSE100,
        GLOBAL_ADRS,
        INDEX_LEADERS_TICKERS,
        SP500_TOP100,
        TSX60,
        UK_FTSE_ALL,
        US_NASDAQ_EXT,
        US_SP500,
    )
except ModuleNotFoundError:  # Direct execution or relative import
    from market_tickers import (  # type: ignore[no-redef]
        CANADA_RESEARCH_TICKERS,
        CANADA_TSX_ALL,
        CURATED_RESEARCH_TICKERS,
        EUROPE_STOXX_ALL,
        EUROSTOXX50,
        FTSE100,
        GLOBAL_ADRS,
        INDEX_LEADERS_TICKERS,
        SP500_TOP100,
        TSX60,
        UK_FTSE_ALL,
        US_NASDAQ_EXT,
        US_SP500,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Full Market Groups
# Six mutually-exclusive market segments that together form the browseable
# universe.  Each ticker appears in exactly one group.
# ═══════════════════════════════════════════════════════════════════════════════

_GROUPS: list[dict] = [
    {
        "id": "us-large-cap",
        "label": "S&P 500 & U.S. large cap",
        "shortLabel": "S&P 500 / NYSE",
        "description": "Full S&P 500 plus notable S&P 400 mid-caps and NYSE-listed large caps.",
        "tickers": US_SP500,
    },
    {
        "id": "us-growth",
        "label": "NASDAQ Extended",
        "shortLabel": "NASDAQ / Growth",
        "description": "High-growth NASDAQ-listed companies beyond the S&P 500 — cloud, fintech, EV, and biotech.",
        "tickers": US_NASDAQ_EXT,
    },
    {
        "id": "canada",
        "label": "Canada — TSX",
        "shortLabel": "Canada (TSX)",
        "description": "TSX 60 blue chips plus TSX Composite leaders across energy, mining, financials, and tech.",
        "tickers": CANADA_TSX_ALL,
    },
    {
        "id": "london",
        "label": "United Kingdom — FTSE",
        "shortLabel": "UK (LSE)",
        "description": "FTSE 100 constituents and selected FTSE 250 names.",
        "tickers": UK_FTSE_ALL,
    },
    {
        "id": "europe",
        "label": "Europe — STOXX 600",
        "shortLabel": "Europe",
        "description": "EuroStoxx 50 plus STOXX 600 coverage: Germany, France, Netherlands, Switzerland, Italy, Spain, and Nordics.",
        "tickers": EUROPE_STOXX_ALL,
    },
    {
        "id": "global-adrs",
        "label": "Global ADRs",
        "shortLabel": "Global ADRs",
        "description": "International market leaders trading as U.S.-listed ADRs — Japan, Korea, Taiwan, China, India, Brazil, and Australia.",
        "tickers": GLOBAL_ADRS,
    },
]

# Flattened ticker list (used to build SUPPORTED_TICKERS in server.py)
ALL_UNIVERSE_TICKERS: list[str] = [t for group in _GROUPS for t in group["tickers"]]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Legacy AST Loader (kept for backward compatibility with any external
# tooling that calls load_asset_universe directly)
# ═══════════════════════════════════════════════════════════════════════════════

def load_asset_universe(script_path: Path) -> list[str]:
    """Return the full browseable ticker list (no longer parses allolabs.py)."""
    return list(ALL_UNIVERSE_TICKERS)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Catalog Builder
# ═══════════════════════════════════════════════════════════════════════════════

def universe_catalog(script_path: Path | None = None) -> dict:
    """Return every supported ticker grouped by market, plus preset selections."""
    all_tickers = ALL_UNIVERSE_TICKERS
    return {
        "groups": _GROUPS,
        "presets": [
            {
                "id": "index-leaders",
                "label": "Index leaders",
                "description": "S&P 500 top 100, TSX 60, FTSE 100, EuroStoxx 50 — the benchmark core.",
                "tickers": INDEX_LEADERS_TICKERS,
            },
            {
                "id": "curated",
                "label": "Curated essentials",
                "description": "Token-efficient cross-market starter set.",
                "tickers": CURATED_RESEARCH_TICKERS,
            },
            {
                "id": "canada",
                "label": "Canada core",
                "description": "Complete supported Canadian large-cap set.",
                "tickers": CANADA_RESEARCH_TICKERS,
            },
            {
                "id": "full",
                "label": "Full catalog",
                "description": "Every supported security across all markets.",
                "tickers": all_tickers,
            },
        ],
        "tickerCount": len(all_tickers),
    }


def preset_id_for_selection(selected: list[str], catalog: dict) -> str:
    selected_set = set(selected)
    for preset in catalog["presets"]:
        if selected_set == set(preset["tickers"]):
            return str(preset["id"])
    return "custom"
