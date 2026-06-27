"""Shared universe catalog and preset helpers for the dashboard runner."""

from __future__ import annotations

import ast
from pathlib import Path


CURATED_RESEARCH_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "LLY",
    "JPM", "XOM", "COST", "ISRG", "RY.TO", "TD.TO", "ENB.TO", "CNQ.TO",
    "BAM.TO", "MFC.TO", "FTS.TO", "CNR.TO", "CP.TO", "SHOP.TO", "CSU.TO",
    "AEM.TO", "NTR.TO", "AZN.L", "SHEL.L", "HSBA.L", "ULVR.L", "LSEG.L",
    "ASML.AS", "SAP.DE", "SIE.DE", "MC.PA", "BNP.PA", "NESN.SW",
    "NOVN.SW", "RHHBY", "UBSG.SW",
]

CANADA_RESEARCH_TICKERS = [
    "RY.TO", "TD.TO", "BMO.TO", "BNS.TO", "NA.TO", "CM.TO",
    "ENB.TO", "TRP.TO", "SU.TO", "CNQ.TO", "CVE.TO", "TOU.TO",
    "POW.TO", "SLF.TO", "MFC.TO", "FFH.TO", "BAM.TO", "BN.TO",
    "BIP-UN.TO", "FTS.TO", "EMA.TO", "PPL.TO", "TRI.TO", "OTEX.TO",
    "CSU.TO", "WCN.TO", "WSP.TO", "CNR.TO", "CP.TO", "ATD.TO",
    "DOL.TO", "QSR.TO", "MRU.TO", "SHOP.TO", "GIB-A.TO", "WN.TO",
    "WPM.TO", "FNV.TO", "AEM.TO", "ABX.TO", "TECK-B.TO", "NTR.TO",
    "FM.TO", "CCO.TO", "BCE.TO", "T.TO", "RCI-B.TO", "CLS.TO",
    "GWO.TO", "IFC.TO", "IMO.TO",
]


def load_asset_universe(script_path: Path) -> list[str]:
    """Read the pipeline's literal asset list without importing and executing it."""
    tree = ast.parse(script_path.read_text(encoding="utf-8-sig"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "ASSET_UNIVERSE"
            for target in node.targets
        )
    )
    tickers = ast.literal_eval(assignment.value)
    if not isinstance(tickers, list) or not all(isinstance(item, str) for item in tickers):
        raise ValueError("ASSET_UNIVERSE must be a literal list of ticker symbols.")
    return tickers


def _slice(tickers: list[str], first: str, following: str | None) -> list[str]:
    start = tickers.index(first)
    end = tickers.index(following) if following else len(tickers)
    return tickers[start:end]


def universe_catalog(script_path: Path) -> dict:
    """Return every supported ticker grouped by its market coverage."""
    tickers = load_asset_universe(script_path)
    groups = [
        {
            "id": "us-large-cap",
            "label": "S&P 100 & U.S. large cap",
            "shortLabel": "S&P 100 / U.S.",
            "description": "U.S. core and mega-cap coverage, anchored in S&P 100 names.",
            "tickers": _slice(tickers, "AAPL", "ABNB"),
        },
        {
            "id": "us-growth",
            "label": "Nasdaq & U.S. growth",
            "shortLabel": "Nasdaq / Growth",
            "description": "Growth, technology, healthcare, consumer, industrial and utility extensions.",
            "tickers": _slice(tickers, "ABNB", "RY.TO"),
        },
        {
            "id": "canada",
            "label": "Canada large cap",
            "shortLabel": "Canada",
            "description": "Canadian financials, energy, industrial, defensive and growth leaders.",
            "tickers": _slice(tickers, "RY.TO", "AZN.L"),
        },
        {
            "id": "london",
            "label": "FTSE 100 / London",
            "shortLabel": "FTSE / London",
            "description": "London-listed global companies represented in the research catalog.",
            "tickers": _slice(tickers, "AZN.L", "ALV.DE"),
        },
        {
            "id": "europe",
            "label": "Euro STOXX & Europe",
            "shortLabel": "Europe",
            "description": "Large-cap listings across the Eurozone and Switzerland.",
            "tickers": _slice(tickers, "ALV.DE", "BHP"),
        },
        {
            "id": "global-adrs",
            "label": "Global ADR leaders",
            "shortLabel": "Global ADRs",
            "description": "International leaders represented through U.S.-traded securities.",
            "tickers": _slice(tickers, "BHP", None),
        },
    ]
    flattened = [ticker for group in groups for ticker in group["tickers"]]
    if flattened != tickers:
        raise ValueError("Universe market grouping must preserve every asset exactly once.")
    return {
        "groups": groups,
        "presets": [
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
                "tickers": tickers,
            },
        ],
        "tickerCount": len(tickers),
    }


def preset_id_for_selection(selected: list[str], catalog: dict) -> str:
    selected_set = set(selected)
    for preset in catalog["presets"]:
        if selected_set == set(preset["tickers"]):
            return str(preset["id"])
    return "custom"
